import io
import json
import logging
import re
import time
import wave
from typing import Optional, Dict, Any, List
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# Groq's whisper-large-v3-turbo is billed per second of audio, not per token
# (~$0.04/hour as of writing). https://groq.com/pricing
GROQ_WHISPER_USD_PER_SECOND = 0.04 / 3600


def estimate_audio_duration_seconds(file_bytes: bytes, filename: str) -> float:
    """Exact for WAV (reads the header); a rough bitrate-based estimate for
    compressed formats (mp3/m4a/ogg) since parsing those properly needs a
    dedicated media library. Good enough for cost *estimation*, not billing."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension == "wav":
        try:
            with wave.open(io.BytesIO(file_bytes)) as wf:
                return wf.getnframes() / float(wf.getframerate())
        except Exception:
            pass
    # ~64kbps is a reasonable average for compressed speech recordings
    return (len(file_bytes) * 8) / 64_000


class STTService:

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        stt_model_name: Optional[str] = None,
    ):
        self.api_key = api_key or settings.GROQ_STT_KEY or settings.LLM_API_KEY
        self.base_url = base_url or settings.GROQ_STT_BASE_URL
        self.stt_model_name = stt_model_name or settings.STT_MODEL_NAME

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=settings.LLM_TIMEOUT,
        )

        # Separate LLM client for speaker diarization formatting
        self.llm_client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=settings.LLM_TIMEOUT,
        )

    async def diarize_transcript(self, raw_transcript: str) -> Dict[str, Any]:
        """Analyze raw call transcript context to format 100% generic Agent vs Customer turns for any domain with zero translation."""
        logger.info("Running automatic speaker diarization and turn labeling...")
        system_prompt = (
            "You are an expert audio dialogue diarizer and speaker identification AI.\n"
            "Your task is to take a raw unstructured transcript of a call between a service representative and a user/customer, and separate it into clean, accurate dialogue turns labeled as 'Agent:' or 'Customer:'.\n\n"
            "GENERIC SPEAKER ROLE IDENTIFICATION RULES (APPLIES TO ALL DOMAINS & CALL TYPES):\n"
            "1. 'Agent:' IS THE SUPPORT REPRESENTATIVE / AGENT WHO:\n"
            "   - Greets the caller, introduces themselves or the company, and offers assistance.\n"
            "   - Guides the caller, asks clarifying questions, or explains instructions, procedures, troubleshooting steps, policies, or resolution timelines.\n"
            "   - Provides politeness, assistance, and closing greetings.\n\n"
            "2. 'Customer:' IS THE CALLER / USER / CLIENT WHO:\n"
            "   - Explains their reason for calling, problem, question, order status, complaint, or request.\n"
            "   - Shares personal/account details (name, reference ID, phone number, product/service details).\n"
            "   - Responds to the agent's questions.\n\n"
            "UNIVERSAL FORMATTING RULES:\n"
            "- START DIRECTLY WITH THE FIRST SPEAKER TURN ('Agent:' or 'Customer:'). DO NOT ADD CHATTER, INTRO LINES, OR MARKDOWN LINES (e.g. DO NOT write 'Here is the transcript:' or '---').\n"
            "- DO NOT BOLD THE LABELS. Write strictly 'Agent:' or 'Customer:' at the start of each line.\n"
            "- WRITE THE SPEAKER LABEL AND SPEECH ON THE SAME LINE (e.g. 'Agent: Thank you for calling...').\n"
            "- ABSOLUTELY NO TRANSLATION. Keep 100% of original words, language, and script (Hindi Devanagari, English, Hinglish, etc.) exactly as spoken.\n"
            "- DO NOT PARAPHRASE, REWRITE, OR DELETE ANY SENTENCES."
        )

        user_prompt = f"Raw Transcript:\n{raw_transcript}"

        start_time = time.perf_counter()
        try:
            res = await self.llm_client.chat.completions.create(
                model=settings.LLM_MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=4000,
            )
            end_time = time.perf_counter()
            latency_ms = int((end_time - start_time) * 1000)

            diarized_text = res.choices[0].message.content or raw_transcript

            usage = {}
            if hasattr(res, "usage") and res.usage:
                usage = {
                    "prompt_tokens": res.usage.prompt_tokens or 0,
                    "completion_tokens": res.usage.completion_tokens or 0,
                    "total_tokens": res.usage.total_tokens or 0,
                }

            # Safe speaker tag formatting ONLY
            cleaned = diarized_text.strip()
            cleaned = re.sub(r'\*\*(Agent|Customer Care|Customer|User):\*\*', r'\1:', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'^(Agent|Customer Care|Customer|User):\s*\n+', r'\1: ', cleaned, flags=re.MULTILINE | re.IGNORECASE)

            return {
                "diarized_text": cleaned.strip(),
                "token_usage": usage,
                "latency_ms": latency_ms,
                "model_name": settings.LLM_MODEL_NAME,
            }
        except Exception as err:
            logger.warning(f"Speaker diarization formatting failed, using raw transcript: {err}")
            return {
                "diarized_text": raw_transcript,
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "latency_ms": 0,
                "model_name": settings.LLM_MODEL_NAME,
            }

    async def transcribe_audio(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Transcribe audio bytes with Groq Whisper, returning untouched raw text, diarized turns, and STT metrics."""
        logger.info(
            f"Transcribing audio '{filename}' ({len(file_bytes)} bytes) "
            f"via Groq Whisper [{self.stt_model_name}]"
        )

        audio_file = (filename, io.BytesIO(file_bytes))
        start_time = time.perf_counter()

        response = await self.client.audio.transcriptions.create(
            model=self.stt_model_name,
            file=audio_file,
        )
        end_time = time.perf_counter()
        stt_latency_ms = int((end_time - start_time) * 1000)

        raw_transcription = response.text if hasattr(response, "text") else str(response)
        logger.info(f"Groq Whisper raw transcription complete: {len(raw_transcription)} chars")

        # Whisper is billed per second of audio, not per token - see
        # estimate_audio_duration_seconds() docstring for accuracy caveats.
        duration_seconds = estimate_audio_duration_seconds(file_bytes, filename)
        stt_usage = {
            "duration_seconds": round(duration_seconds, 2),
            "estimated_cost_usd": round(duration_seconds * GROQ_WHISPER_USD_PER_SECOND, 6),
            "is_estimated": True,
        }

        # Automatically format with Agent & Customer speaker labels preserving exact original language & script
        diarize_res = await self.diarize_transcript(raw_transcription)

        return {
            "raw_text": raw_transcription.strip(),
            "diarized_text": diarize_res["diarized_text"],
            "stt_usage": stt_usage,
            "stt_latency_ms": stt_latency_ms,
            "diarize_usage": diarize_res["token_usage"],
            "diarize_latency_ms": diarize_res["latency_ms"],
        }
