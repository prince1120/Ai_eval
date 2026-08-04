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


def detect_all_transcript_languages(text: str, whisper_lang: Optional[str] = None) -> List[str]:
    """Detect all languages and scripts present in the transcript text."""
    langs = []

    # 1. Devanagari Script (Hindi, Marathi)
    if re.search(r'[\u0900-\u097F]', text):
        langs.append("Hindi (Devanagari)")

    # 2. Tamil Script
    if re.search(r'[\u0B80-\u0BFF]', text):
        langs.append("Tamil")

    # 3. Telugu Script
    if re.search(r'[\u0C00-\u0C7F]', text):
        langs.append("Telugu")

    # 4. Bengali Script
    if re.search(r'[\u0980-\u09FF]', text):
        langs.append("Bengali")

    # 5. Gujarati Script
    if re.search(r'[\u0A80-\u0AFF]', text):
        langs.append("Gujarati")

    # 6. Arabic / Urdu Script
    if re.search(r'[\u0600-\u06FF]', text):
        langs.append("Arabic / Urdu")

    # 7. Romanized Hindi / Hinglish words (common speech terms in Latin script)
    hinglish_keywords = [
        r'\baap\b', r'\bhai\b', r'\bhain\b', r'\bka\b', r'\bki\b', r'\bke\b', r'\bko\b',
        r'\bkya\b', r'\bnahi\b', r'\bnahin\b', r'\bkar\b', r'\bkaro\b', r'\bkarna\b',
        r'\bbolo\b', r'\bbaat\b', r'\bhaan\b', r'\bacha\b', r'\bdekh\b', r'\bji\b'
    ]
    hinglish_matches = sum(1 for kw in hinglish_keywords if re.search(kw, text, re.IGNORECASE))
    if hinglish_matches >= 2:
        langs.append("Hinglish")

    # 8. English (Latin script with English words)
    english_keywords = [
        r'\bthe\b', r'\bis\b', r'\byou\b', r'\bhave\b', r'\bthis\b', r'\bcall\b',
        r'\bwith\b', r'\bproduct\b', r'\bservice\b', r'\bplease\b', r'\bokay\b', r'\byes\b'
    ]
    english_matches = sum(1 for kw in english_keywords if re.search(kw, text, re.IGNORECASE))
    if english_matches >= 2 or (whisper_lang and whisper_lang.lower() in ["en", "english"]):
        if "English" not in langs:
            langs.append("English")

    if whisper_lang and whisper_lang.capitalize() not in langs and whisper_lang.lower() not in ["en", "english", "hi", "hindi"]:
        langs.append(whisper_lang.capitalize())

    if not langs:
        langs = ["English"]

    return langs


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

        # Multilingual prompt to guide Groq Whisper for Indian accent, Hindi, Hinglish & English calls
        stt_prompt = (
            "This is a customer support call audio recording in Hindi, Hinglish (Hindi + English), or English. "
            "Transcribe exact spoken words accurately in original script and language (Devanagari for Hindi, Latin for English)."
        )

        response = await self.client.audio.transcriptions.create(
            model=self.stt_model_name,
            file=audio_file,
            response_format="verbose_json",
            prompt=stt_prompt,
        )
        end_time = time.perf_counter()
        stt_latency_ms = int((end_time - start_time) * 1000)

        raw_transcription = getattr(response, "text", None) or str(response)
        whisper_lang = getattr(response, "language", None)
        duration_seconds = getattr(response, "duration", None)

        # Detect all spoken languages and scripts used in the transcript
        all_langs = detect_all_transcript_languages(raw_transcription, whisper_lang=whisper_lang)
        detected_language = ", ".join(all_langs)

        if not duration_seconds:
            duration_seconds = estimate_audio_duration_seconds(file_bytes, filename)

        logger.info(
            f"Groq Whisper raw transcription complete: {len(raw_transcription)} chars, "
            f"language='{detected_language}', duration={duration_seconds}s"
        )

        stt_usage = {
            "duration_seconds": round(float(duration_seconds), 2),
            "estimated_cost_usd": round(float(duration_seconds) * GROQ_WHISPER_USD_PER_SECOND, 6),
            "is_estimated": True,
        }

        # Automatically format with Agent & Customer speaker labels preserving exact original language & script
        diarize_res = await self.diarize_transcript(raw_transcription)

        return {
            "raw_text": raw_transcription.strip(),
            "diarized_text": diarize_res["diarized_text"],
            "detected_language": detected_language,
            "audio_duration_seconds": round(float(duration_seconds), 2),
            "stt_usage": stt_usage,
            "stt_latency_ms": stt_latency_ms,
            "diarize_usage": diarize_res["token_usage"],
            "diarize_latency_ms": diarize_res["latency_ms"],
        }
