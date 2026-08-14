"""Tests for provider quota tracking.

Uses the in-memory backend and an injected clock, so results are deterministic
and nothing sleeps.
"""
import asyncio
import unittest

from app.core.quota import (
    LLM_FREE_TIER_LIMITS,
    WHISPER_FREE_TIER_LIMITS,
    InMemoryQuotaBackend,
    QuotaGuard,
    QuotaLimit,
)


def run(coro):
    return asyncio.run(coro)


class TestQuotaLimit(unittest.TestCase):

    def test_window_index_advances_with_time(self):
        limit = QuotaLimit("rpm", 20, 60)
        self.assertEqual(limit.window_index(0.0), 0)
        self.assertEqual(limit.window_index(59.9), 0)
        self.assertEqual(limit.window_index(60.0), 1)

    def test_keys_differ_across_windows_and_scopes(self):
        limit = QuotaLimit("rpm", 20, 60)
        self.assertNotEqual(limit.key("groq", 0.0), limit.key("groq", 60.0))
        self.assertNotEqual(limit.key("groq", 0.0), limit.key("mistral", 0.0))

    def test_seconds_until_reset(self):
        limit = QuotaLimit("rpm", 20, 60)
        self.assertAlmostEqual(limit.seconds_until_reset(10.0), 50.0)
        self.assertAlmostEqual(limit.seconds_until_reset(59.0), 1.0)


class TestQuotaGuard(unittest.TestCase):

    def guard(self, limits=None):
        return QuotaGuard(
            "test",
            limits or [QuotaLimit("requests", 3, 60)],
            backend=InMemoryQuotaBackend(),
        )

    def test_allows_within_limit(self):
        guard = self.guard()
        for _ in range(3):
            decision = run(guard.consume({"requests": 1}, now=0.0))
            self.assertTrue(decision.allowed)

    def test_refuses_past_limit_with_retry_after(self):
        guard = self.guard()
        for _ in range(3):
            run(guard.consume({"requests": 1}, now=10.0))
        decision = run(guard.consume({"requests": 1}, now=10.0))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.blocking_limit, "requests")
        self.assertAlmostEqual(decision.retry_after_seconds, 50.0)

    def test_window_rollover_restores_capacity(self):
        guard = self.guard()
        for _ in range(3):
            run(guard.consume({"requests": 1}, now=10.0))
        self.assertFalse(run(guard.consume({"requests": 1}, now=10.0)).allowed)
        # Next minute is a fresh window.
        self.assertTrue(run(guard.consume({"requests": 1}, now=70.0)).allowed)

    def test_rejects_oversized_single_request(self):
        guard = self.guard([QuotaLimit("audio_seconds", 100, 3600)])
        decision = run(guard.consume({"audio_seconds": 250}, now=0.0))
        self.assertFalse(decision.allowed)

    def test_rollback_leaves_no_partial_consumption(self):
        # Two limits: the first has room, the second does not. The first must
        # not stay incremented, or repeated refusals would slowly drain it.
        guard = QuotaGuard(
            "test",
            [QuotaLimit("requests", 100, 60), QuotaLimit("seconds", 10, 60)],
            backend=InMemoryQuotaBackend(),
        )
        decision = run(guard.consume({"requests": 1, "seconds": 50}, now=0.0))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.blocking_limit, "seconds")

        snapshot = run(guard.snapshot(now=0.0))
        self.assertEqual(snapshot["requests"]["used"], 0)
        self.assertEqual(snapshot["seconds"]["used"], 0)

    def test_check_does_not_consume(self):
        guard = self.guard()
        for _ in range(5):
            self.assertTrue(run(guard.check({"requests": 1}, now=0.0)).allowed)
        self.assertEqual(run(guard.snapshot(now=0.0))["requests"]["used"], 0)

    def test_check_reports_blocking_limit(self):
        guard = self.guard()
        for _ in range(3):
            run(guard.consume({"requests": 1}, now=0.0))
        decision = run(guard.check({"requests": 1}, now=0.0))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.blocking_limit, "requests")

    def test_release_returns_capacity(self):
        guard = self.guard()
        for _ in range(3):
            run(guard.consume({"requests": 1}, now=0.0))
        self.assertFalse(run(guard.consume({"requests": 1}, now=0.0)).allowed)

        run(guard.release({"requests": 1}, now=0.0))
        self.assertTrue(run(guard.consume({"requests": 1}, now=0.0)).allowed)

    def test_snapshot_reports_remaining_and_reset(self):
        guard = self.guard()
        run(guard.consume({"requests": 2}, now=15.0))
        snapshot = run(guard.snapshot(now=15.0))
        self.assertEqual(snapshot["requests"]["used"], 2)
        self.assertEqual(snapshot["requests"]["remaining"], 1)
        self.assertAlmostEqual(snapshot["requests"]["resets_in_seconds"], 45.0)

    def test_unlisted_amounts_are_ignored(self):
        guard = self.guard()
        decision = run(guard.consume({"something_else": 999}, now=0.0))
        self.assertTrue(decision.allowed)

    def test_independent_scopes_do_not_interfere(self):
        backend = InMemoryQuotaBackend()
        limits = [QuotaLimit("requests", 1, 60)]
        a = QuotaGuard("org-a", limits, backend=backend)
        b = QuotaGuard("org-b", limits, backend=backend)
        self.assertTrue(run(a.consume({"requests": 1}, now=0.0)).allowed)
        self.assertFalse(run(a.consume({"requests": 1}, now=0.0)).allowed)
        # Different scope has its own counters.
        self.assertTrue(run(b.consume({"requests": 1}, now=0.0)).allowed)


class TestFreeTierProfiles(unittest.TestCase):
    """The documented limits are what make the zero-budget plan work, so the
    profiles are pinned here."""

    def test_whisper_daily_audio_budget_is_the_binding_limit(self):
        guard = QuotaGuard("groq", WHISPER_FREE_TIER_LIMITS, backend=InMemoryQuotaBackend())
        # 5-minute calls, one per simulated minute so RPM never binds.
        accepted = 0
        for i in range(200):
            decision = run(guard.consume(
                {
                    "whisper_requests_per_minute": 1,
                    "whisper_audio_seconds_per_hour": 300,
                    "whisper_audio_seconds_per_day": 300,
                },
                now=i * 60.0,
            ))
            if decision.allowed:
                accepted += 1

        # 28,800/day with a 10% safety margin -> ~25,920s -> ~86 five-min calls,
        # but the hourly ceiling (7,200 * 0.9 = 6,480s = 21/hour) binds first.
        self.assertGreater(accepted, 50)
        self.assertLess(accepted, 90)

    def test_hourly_audio_ceiling_binds_before_daily(self):
        guard = QuotaGuard("groq", WHISPER_FREE_TIER_LIMITS, backend=InMemoryQuotaBackend())
        accepted = 0
        # All within a single hour and spread so RPM never binds.
        for i in range(60):
            decision = run(guard.consume(
                {
                    "whisper_requests_per_minute": 1,
                    "whisper_audio_seconds_per_hour": 300,
                    "whisper_audio_seconds_per_day": 300,
                },
                now=i * 60.0,
            ))
            if decision.allowed:
                accepted += 1
        # 6,480 hourly seconds / 300 = 21 calls.
        self.assertEqual(accepted, 21)

    def test_llm_tokens_per_minute_is_tight(self):
        guard = QuotaGuard("groq-llm", LLM_FREE_TIER_LIMITS, backend=InMemoryQuotaBackend())
        # A single scorecard call is ~5,700 tokens against 6,000/min * 0.9.
        first = run(guard.consume(
            {"llm_requests_per_minute": 1, "llm_tokens_per_minute": 5_400,
             "llm_tokens_per_day": 5_400},
            now=0.0,
        ))
        self.assertTrue(first.allowed)
        second = run(guard.consume(
            {"llm_requests_per_minute": 1, "llm_tokens_per_minute": 5_400,
             "llm_tokens_per_day": 5_400},
            now=0.0,
        ))
        self.assertFalse(second.allowed)
        self.assertEqual(second.blocking_limit, "llm_tokens_per_minute")
        # Under a minute to wait, so the queue parks rather than fails.
        self.assertLessEqual(second.retry_after_seconds, 60.0)

    def test_safety_margin_keeps_us_under_published_limits(self):
        rpm = next(l for l in WHISPER_FREE_TIER_LIMITS
                   if l.name == "whisper_requests_per_minute")
        self.assertLess(rpm.limit, 20)
        daily = next(l for l in WHISPER_FREE_TIER_LIMITS
                     if l.name == "whisper_audio_seconds_per_day")
        self.assertLess(daily.limit, 28_800)


class TestInMemoryBackend(unittest.TestCase):

    def test_expired_keys_are_purged(self):
        backend = InMemoryQuotaBackend()
        run(backend.incr("k", 5, ttl_seconds=0))
        # TTL of 0 means the entry is already stale on the next access.
        self.assertEqual(run(backend.get("k")), 0)

    def test_decr_floors_at_zero(self):
        backend = InMemoryQuotaBackend()
        run(backend.incr("k", 2, 60))
        run(backend.decr("k", 10))
        self.assertEqual(run(backend.get("k")), 0)

    def test_concurrent_increments_are_serialised(self):
        backend = InMemoryQuotaBackend()

        async def hammer():
            await asyncio.gather(*(backend.incr("k", 1, 60) for _ in range(100)))
            return await backend.get("k")

        self.assertEqual(run(hammer()), 100)


if __name__ == "__main__":
    unittest.main()
