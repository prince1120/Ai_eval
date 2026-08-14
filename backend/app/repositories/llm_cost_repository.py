import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.llm_cost_log import LLMCostLog

logger = logging.getLogger(__name__)


# Official API Rate Matrix (USD per 1 Million Tokens)
# Format: model_name -> (Input USD / 1M, Output USD / 1M)
MODEL_PRICING = {
    # --- Mistral AI Models ---
    # Verified against https://mistral.ai/pricing/api on 2026-08-13.
    # ministral-8b was previously recorded here as 0.10/0.10; it is 0.15/0.15,
    # so every 8B row logged before this date under-reports by a third.
    "ministral-3b-2512": (0.10, 0.10),
    "ministral-3b": (0.10, 0.10),
    "ministral-8b-2410": (0.15, 0.15),
    "ministral-8b": (0.15, 0.15),
    "ministral-14b": (0.20, 0.20),
    "mistral-small-latest": (0.15, 0.60),
    "mistral-small": (0.15, 0.60),
    "mistral-medium-latest": (1.50, 7.50),
    "mistral-medium": (1.50, 7.50),
    "mistral-large-latest": (0.50, 1.50),
    "mistral-large": (0.50, 1.50),
    "codestral-latest": (0.20, 0.60),
    "open-mistral-7b": (0.25, 0.25),
    "mistral-tiny": (0.25, 0.25),

    # --- OpenAI Models ---
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-2024-08-06": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    "o1": (15.00, 60.00),
    "o3-mini": (1.10, 4.40),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-3.5-turbo": (0.50, 1.50),

    # --- Anthropic Claude Models ---
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-opus-20240229": (15.00, 75.00),

    # --- Groq & STT Models ---
    # STT is billed per audio-second, not per token; these entries exist only
    # so the model name resolves. Actual STT cost is passed in via
    # override_total_cost_usd from whisper_cost_usd().
    "whisper-large-v3": (0.0, 0.0),
    "whisper-large-v3-turbo": (0.0, 0.0),
    "distil-whisper-large-v3-en": (0.0, 0.0),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "openai/gpt-oss-20b": (0.075, 0.30),
    "gpt-oss-20b": (0.075, 0.30),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "gpt-oss-120b": (0.15, 0.60),
    "qwen3-32b": (0.29, 0.59),

    # --- Google Gemini Models ---
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
}

DEFAULT_PRICING = (0.10, 0.30)

# Base URL fragment -> provider label, so cost rows are attributed to whoever
# actually served the request rather than a hardcoded guess.
PROVIDER_BY_HOST = {
    "groq.com": "groq",
    "mistral.ai": "mistral",
    "openai.com": "openai",
    "anthropic.com": "anthropic",
    "googleapis.com": "google",
}


def _provider_from_base_url(base_url: Optional[str]) -> str:
    host = (base_url or "").lower()
    for fragment, provider in PROVIDER_BY_HOST.items():
        if fragment in host:
            return provider
    return "unknown"


def calculate_llm_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> Dict[str, float]:
    """Calculate exact input, output, and total USD cost based on official per-1M token rates."""
    cleaned_name = (model_name or "").lower().strip()
    rate = MODEL_PRICING.get(cleaned_name)

    if not rate:
        for k, v in MODEL_PRICING.items():
            if k in cleaned_name or cleaned_name in k:
                rate = v
                break

    if not rate:
        # Falling back silently would report confident-looking but wrong spend,
        # which is worse than no number at all. Make it visible in the logs.
        logger.warning(
            f"No pricing entry for model '{model_name}'; falling back to "
            f"{DEFAULT_PRICING} USD/1M tokens. Add it to MODEL_PRICING."
        )
        rate = DEFAULT_PRICING

    input_rate, output_rate = rate
    input_cost = (prompt_tokens / 1_000_000.0) * input_rate
    output_cost = (completion_tokens / 1_000_000.0) * output_rate
    total_cost = input_cost + output_cost

    return {
        "input_cost_usd": round(input_cost, 6),
        "output_cost_usd": round(output_cost, 6),
        "total_cost_usd": round(total_cost, 6),
    }


def _apply_date_filter(query, date_preset: Optional[str]):
    if not date_preset or date_preset == "all":
        return query

    now_utc = datetime.now(timezone.utc)
    today_start = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)

    if date_preset == "today":
        return query.where(LLMCostLog.created_at >= today_start)
    elif date_preset == "yesterday":
        yesterday_start = today_start - timedelta(days=1)
        return query.where(LLMCostLog.created_at >= yesterday_start, LLMCostLog.created_at < today_start)
    elif date_preset == "7days":
        return query.where(LLMCostLog.created_at >= (now_utc - timedelta(days=7)))
    elif date_preset == "30days":
        return query.where(LLMCostLog.created_at >= (now_utc - timedelta(days=30)))

    return query


class LLMCostRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_request(
        self,
        organization_id: uuid.UUID,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        user_id: Optional[uuid.UUID] = None,
        analysis_run_id: Optional[uuid.UUID] = None,
        transcript_id: Optional[uuid.UUID] = None,
        action: str = "scorecard_evaluation",
        provider: str = "mistral",
        status: str = "success",
        error_message: Optional[str] = None,
        override_total_cost_usd: Optional[float] = None,
    ) -> LLMCostLog:
        # STT (Whisper) isn't billed per token - it's billed per second of audio.
        # Callers that already computed a real duration-based cost pass it here
        # directly instead of routing through the token-rate table below.
        if override_total_cost_usd is not None:
            costs = {
                "input_cost_usd": 0.0,
                "output_cost_usd": 0.0,
                "total_cost_usd": round(override_total_cost_usd, 6),
            }
        else:
            costs = calculate_llm_cost(model_name, prompt_tokens, completion_tokens)
        total_tokens = prompt_tokens + completion_tokens

        log_entry = LLMCostLog(
            organization_id=organization_id,
            user_id=user_id,
            analysis_run_id=analysis_run_id,
            transcript_id=transcript_id,
            action=action,
            provider=provider,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            input_cost_usd=costs["input_cost_usd"],
            output_cost_usd=costs["output_cost_usd"],
            total_cost_usd=costs["total_cost_usd"],
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
        )
        self.session.add(log_entry)
        await self.session.flush()
        return log_entry

    async def get_summary_stats(
        self,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        date_preset: Optional[str] = None,
    ) -> Dict[str, Any]:
        query = select(
            func.coalesce(func.sum(LLMCostLog.total_cost_usd), 0).label("total_spend"),
            func.coalesce(func.sum(LLMCostLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(LLMCostLog.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(LLMCostLog.completion_tokens), 0).label("completion_tokens"),
            func.count(LLMCostLog.id).label("total_requests"),
            func.coalesce(func.avg(LLMCostLog.latency_ms), 0).label("avg_latency_ms"),
        ).where(LLMCostLog.organization_id == organization_id)

        if user_id:
            query = query.where(LLMCostLog.user_id == user_id)
        query = _apply_date_filter(query, date_preset)

        result = await self.session.execute(query)
        row = result.one()
        return {
            "total_spend_usd": float(row.total_spend),
            "total_tokens": int(row.total_tokens),
            "prompt_tokens": int(row.prompt_tokens),
            "completion_tokens": int(row.completion_tokens),
            "total_requests": int(row.total_requests),
            "avg_latency_ms": round(float(row.avg_latency_ms), 1),
        }

    async def get_model_breakdown(
        self,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        date_preset: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = (
            select(
                LLMCostLog.model_name,
                LLMCostLog.provider,
                func.count(LLMCostLog.id).label("request_count"),
                func.coalesce(func.sum(LLMCostLog.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(LLMCostLog.total_cost_usd), 0).label("total_cost_usd"),
            )
            .where(LLMCostLog.organization_id == organization_id)
        )

        if user_id:
            query = query.where(LLMCostLog.user_id == user_id)
        query = _apply_date_filter(query, date_preset)

        query = query.group_by(LLMCostLog.model_name, LLMCostLog.provider).order_by(desc("total_cost_usd"))
        result = await self.session.execute(query)
        return [
            {
                "model_name": row.model_name,
                "provider": row.provider,
                "request_count": int(row.request_count),
                "total_tokens": int(row.total_tokens),
                "total_cost_usd": float(row.total_cost_usd),
            }
            for row in result.all()
        ]

    async def list_logs(
        self,
        organization_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        model_name: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        date_preset: Optional[str] = None,
    ) -> List[LLMCostLog]:
        query = (
            select(LLMCostLog)
            .options(
                selectinload(LLMCostLog.user),
                selectinload(LLMCostLog.analysis_run),
                selectinload(LLMCostLog.transcript),
            )
            .where(LLMCostLog.organization_id == organization_id)
        )

        if model_name:
            query = query.where(LLMCostLog.model_name == model_name)
        if user_id:
            query = query.where(LLMCostLog.user_id == user_id)
        query = _apply_date_filter(query, date_preset)

        query = query.order_by(LLMCostLog.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())
