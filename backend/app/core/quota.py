"""Provider quota tracking.

On the Groq free tier the binding constraints are not money but hard rate
limits, and hitting one costs a 429 plus retry budget rather than a bill:

    whisper-large-v3      20 req/min,  7,200 audio-sec/hour,  28,800 audio-sec/day
    llama-3.1-8b-instant  30 req/min,  6,000 tokens/min,      500,000 tokens/day

A worker that ignores these will fire every queued call at once, collect 429s,
and burn the daily allowance on retries. So the queue asks this module for
permission before every provider call, and parks the job when the answer is no.

The design keeps all decision logic behind a tiny storage interface so it can
be tested deterministically in memory, with Redis used only in production.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol, Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QuotaLimit:
    """One provider limit, e.g. 20 requests per 60 seconds."""

    name: str
    limit: int
    window_seconds: int

    def window_index(self, now: float) -> int:
        return int(now // self.window_seconds)

    def key(self, scope: str, now: float) -> str:
        return f"quota:{scope}:{self.name}:{self.window_index(now)}"

    def seconds_until_reset(self, now: float) -> float:
        return ((self.window_index(now) + 1) * self.window_seconds) - now


@dataclass
class QuotaDecision:
    allowed: bool
    retry_after_seconds: float = 0.0
    blocking_limit: Optional[str] = None
    # Remaining headroom per limit, for logging and the admin dashboard.
    remaining: Dict[str, int] = field(default_factory=dict)


class QuotaBackend(Protocol):
    async def incr(self, key: str, amount: int, ttl_seconds: int) -> int: ...
    async def get(self, key: str) -> int: ...
    async def decr(self, key: str, amount: int) -> None: ...


class InMemoryQuotaBackend:
    """Single-process backend. Correct for tests and a single worker; use the
    Redis backend once more than one worker shares a provider account."""

    def __init__(self) -> None:
        self._counters: Dict[str, int] = {}
        self._expiry: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    def _purge(self, now: float) -> None:
        for key in [k for k, exp in self._expiry.items() if exp <= now]:
            self._counters.pop(key, None)
            self._expiry.pop(key, None)

    async def incr(self, key: str, amount: int, ttl_seconds: int) -> int:
        async with self._lock:
            now = time.time()
            self._purge(now)
            self._counters[key] = self._counters.get(key, 0) + amount
            self._expiry.setdefault(key, now + ttl_seconds)
            return self._counters[key]

    async def get(self, key: str) -> int:
        async with self._lock:
            self._purge(time.time())
            return self._counters.get(key, 0)

    async def decr(self, key: str, amount: int) -> None:
        async with self._lock:
            if key in self._counters:
                self._counters[key] = max(0, self._counters[key] - amount)


class RedisQuotaBackend:
    """Shared backend so every worker sees the same consumption."""

    def __init__(self, client):
        self._client = client

    async def incr(self, key: str, amount: int, ttl_seconds: int) -> int:
        pipe = self._client.pipeline()
        pipe.incrby(key, amount)
        # NX so an in-flight window is never extended by a later increment.
        pipe.expire(key, ttl_seconds, nx=True)
        result = await pipe.execute()
        return int(result[0])

    async def get(self, key: str) -> int:
        value = await self._client.get(key)
        return int(value) if value else 0

    async def decr(self, key: str, amount: int) -> None:
        await self._client.decrby(key, amount)


class QuotaGuard:
    """Checks and consumes a set of limits atomically enough for our purposes.

    Consumption is optimistic: every limit is incremented, and if any of them
    overshoots, all increments are rolled back and the caller is told how long
    to wait. Under contention this can briefly under-count, which is the safe
    direction - it makes the guard slightly more conservative, never less.
    """

    def __init__(
        self,
        scope: str,
        limits: Sequence[QuotaLimit],
        backend: Optional[QuotaBackend] = None,
    ):
        self.scope = scope
        self.limits = list(limits)
        self.backend = backend or InMemoryQuotaBackend()

    async def check(self, amounts: Dict[str, int], now: Optional[float] = None) -> QuotaDecision:
        """Report whether a call would fit, without consuming anything."""
        now = now if now is not None else time.time()
        remaining: Dict[str, int] = {}
        blocking: Optional[QuotaLimit] = None

        for limit in self.limits:
            used = await self.backend.get(limit.key(self.scope, now))
            want = amounts.get(limit.name, 0)
            remaining[limit.name] = max(0, limit.limit - used)
            if blocking is None and used + want > limit.limit:
                blocking = limit

        if blocking is not None:
            return QuotaDecision(
                allowed=False,
                retry_after_seconds=blocking.seconds_until_reset(now),
                blocking_limit=blocking.name,
                remaining=remaining,
            )
        return QuotaDecision(allowed=True, remaining=remaining)

    async def consume(
        self, amounts: Dict[str, int], now: Optional[float] = None
    ) -> QuotaDecision:
        """Reserve capacity, or refuse and say when to try again."""
        now = now if now is not None else time.time()
        applied: List[tuple[QuotaLimit, int]] = []
        remaining: Dict[str, int] = {}

        for limit in self.limits:
            want = amounts.get(limit.name, 0)
            key = limit.key(self.scope, now)
            if want == 0:
                used = await self.backend.get(key)
                remaining[limit.name] = max(0, limit.limit - used)
                continue

            total = await self.backend.incr(key, want, limit.window_seconds + 60)
            applied.append((limit, want))

            if total > limit.limit:
                for done_limit, done_amount in applied:
                    await self.backend.decr(done_limit.key(self.scope, now), done_amount)
                logger.info(
                    f"Quota '{limit.name}' exhausted for scope '{self.scope}' "
                    f"({total - want}/{limit.limit} used, wanted {want}); "
                    f"retry in {limit.seconds_until_reset(now):.0f}s"
                )
                return QuotaDecision(
                    allowed=False,
                    retry_after_seconds=limit.seconds_until_reset(now),
                    blocking_limit=limit.name,
                    remaining=remaining,
                )

            remaining[limit.name] = max(0, limit.limit - total)

        return QuotaDecision(allowed=True, remaining=remaining)

    async def release(self, amounts: Dict[str, int], now: Optional[float] = None) -> None:
        """Hand capacity back when a call failed before reaching the provider.

        Only correct for failures that never consumed provider quota, such as a
        connection error. A 429 or a completed request must NOT be released.
        """
        now = now if now is not None else time.time()
        for limit in self.limits:
            amount = amounts.get(limit.name, 0)
            if amount:
                await self.backend.decr(limit.key(self.scope, now), amount)

    async def snapshot(self, now: Optional[float] = None) -> Dict[str, Dict[str, float]]:
        """Current consumption, for logging and the cost dashboard."""
        now = now if now is not None else time.time()
        out: Dict[str, Dict[str, float]] = {}
        for limit in self.limits:
            used = await self.backend.get(limit.key(self.scope, now))
            out[limit.name] = {
                "used": used,
                "limit": limit.limit,
                "remaining": max(0, limit.limit - used),
                "resets_in_seconds": round(limit.seconds_until_reset(now), 1),
            }
        return out


# --- Documented Groq free-tier limits ---------------------------------------
# https://console.groq.com/docs/rate-limits . Deliberately set a little under
# the published numbers: the published limit is where the provider starts
# returning 429s, and clock skew between our window and theirs means running
# right at the edge produces avoidable failures.
SAFETY_MARGIN = 0.9


def _margin(value: int) -> int:
    return max(1, int(value * SAFETY_MARGIN))


WHISPER_FREE_TIER_LIMITS = [
    QuotaLimit("whisper_requests_per_minute", _margin(20), 60),
    QuotaLimit("whisper_audio_seconds_per_hour", _margin(7_200), 3_600),
    QuotaLimit("whisper_audio_seconds_per_day", _margin(28_800), 86_400),
]

LLM_FREE_TIER_LIMITS = [
    QuotaLimit("llm_requests_per_minute", _margin(30), 60),
    QuotaLimit("llm_tokens_per_minute", _margin(6_000), 60),
    QuotaLimit("llm_tokens_per_day", _margin(500_000), 86_400),
]
