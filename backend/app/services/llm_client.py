import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Protocol, runtime_checkable
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError, APITimeoutError

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResult:
    content: Dict[str, Any]
    raw_text: str
    model_used: str
    token_usage: Dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0


@runtime_checkable
class LLMClient(Protocol):

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        organization_id: Optional[str] = None,
    ) -> LLMResult:
        ...


class OpenAICompatibleClient:

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        self.api_key = api_key or settings.LLM_API_KEY
        self.base_url = base_url or settings.LLM_BASE_URL
        self.model_name = model_name or settings.LLM_MODEL_NAME
        self.temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        self.max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        self.timeout = timeout or settings.LLM_TIMEOUT
        self.max_retries = max_retries or settings.LLM_MAX_RETRIES

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )

    def _extract_json(self, raw_text: str) -> Dict[str, Any]:
        """Defensively parse JSON from LLM output, extracting codeblocks if needed."""
        cleaned = raw_text.strip()
        # 1. Direct JSON parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 2. Extract ```json ... ``` codeblock
        json_match = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", cleaned, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 3. Fallback: find first '{' and last '}'
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            try:
                return json.loads(cleaned[start_idx : end_idx + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Failed to parse valid JSON from LLM response: {raw_text[:200]}")

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        organization_id: Optional[str] = None,
    ) -> LLMResult:
        attempt = 0
        backoff = 1.0

        start_time = time.perf_counter()
        while attempt <= self.max_retries:
            attempt += 1
            try:
                logger.info(
                    f"LLM call attempt {attempt}/{self.max_retries + 1} "
                    f"model={self.model_name} org_id={organization_id or 'N/A'}"
                )

                try:
                    # Enforce strict JSON mode
                    response = await self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        response_format={"type": "json_object"},
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                    )
                except APIError as api_err:
                    # Fallback for LLM providers that do not support response_format
                    if "response_format" in str(api_err).lower() or "400" in str(api_err):
                        logger.warning("Provider rejected response_format, retrying without response_format flag...")
                        response = await self.client.chat.completions.create(
                            model=self.model_name,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                            temperature=self.temperature,
                            max_tokens=self.max_tokens,
                        )
                    else:
                        raise api_err

                raw_content = response.choices[0].message.content or ""
                parsed_json = self._extract_json(raw_content)
                end_time = time.perf_counter()
                latency_ms = int((end_time - start_time) * 1000)

                # Extract token usage if returned
                usage_dict = {}
                if hasattr(response, "usage") and response.usage:
                    usage_dict = {
                        "prompt_tokens": response.usage.prompt_tokens or 0,
                        "completion_tokens": response.usage.completion_tokens or 0,
                        "total_tokens": response.usage.total_tokens or 0,
                    }
                    logger.info(
                        f"LLM call success: total_tokens={usage_dict['total_tokens']} "
                        f"latency_ms={latency_ms} org_id={organization_id or 'N/A'}"
                    )

                return LLMResult(
                    content=parsed_json,
                    raw_text=raw_content,
                    model_used=response.model or self.model_name,
                    token_usage=usage_dict,
                    latency_ms=latency_ms,
                )

            except (APIError, APIConnectionError, RateLimitError, APITimeoutError, ValueError) as exc:
                logger.warning(f"LLM call attempt {attempt} failed: {exc}")
                if attempt > self.max_retries:
                    logger.error(f"LLM call exhausted all {self.max_retries + 1} retries.")
                    raise RuntimeError(f"LLM Client execution failed after {self.max_retries} retries: {exc}") from exc

                await asyncio.sleep(backoff)
                backoff *= 2.0
