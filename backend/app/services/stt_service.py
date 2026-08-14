import asyncio
import hashlib
import io
import json
import logging
import math
import os
import re
import tempfile
import time
import wave
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError, APITimeoutError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Groq bills Whisper per second of audio, not per token, with a 10-second
# minimum per request. https://groq.com/pricing
GROQ_WHISPER_USD_PER_SECOND = {
    "whisper-large-v3": 0.111 / 3600,
    "whisper-large-v3-turbo": 0.040 / 3600,
    "distil-whisper-large-v3-en": 0.020 / 3600,
}
DEFAULT_WHISPER_USD_PER_SECOND = 0.111 / 3600
GROQ_MIN_BILLED_SECONDS = 10.0

# Whisper's decoder emits a compression_ratio per segment; values above this
# mean the text is highly repetitive, which in practice is the signature of a
# hallucination loop (usually triggered by silence or music).
HALLUCINATION_COMPRESSION_RATIO = 2.4
# Segments above this no_speech_prob are treated as non-speech and excluded
# from the confidence average so hold music does not drag the score down.
NON_SPEECH_PROB_THRESHOLD = 0.6
# Fraction of the transcript that must be verbatim prompt text before it is
# treated as an echo rather than a real call that happens to share a phrase.
PROMPT_ECHO_COVERAGE_THRESHOLD = 0.5


def sha256_digest(file_bytes: bytes) -> str:
    """Content hash used to deduplicate re-uploads of the same recording.

    Re-transcribing an identical file burns STT quota for nothing, and on the
    free tier quota is the scarcest resource in the pipeline.
    """
    return hashlib.sha256(file_bytes).hexdigest()


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


def whisper_cost_usd(model_name: str, duration_seconds: float) -> float:
    """Billable STT cost, honouring Groq's 10-second per-request minimum."""
    rate = GROQ_WHISPER_USD_PER_SECOND.get(
        (model_name or "").lower().strip(), DEFAULT_WHISPER_USD_PER_SECOND
    )
    billed = max(float(duration_seconds), GROQ_MIN_BILLED_SECONDS)
    return billed * rate


@dataclass
class TranscriptSegment:
    """One Whisper segment plus the quality signals Whisper reports for it.

    These signals (avg_logprob, no_speech_prob, compression_ratio) come back in
    the verbose_json response and are what make it possible to tell the user
    "this transcript is unreliable" instead of silently analysing noise.
    """

    index: int
    start: float
    end: float
    text: str
    avg_logprob: Optional[float] = None
    no_speech_prob: Optional[float] = None
    compression_ratio: Optional[float] = None
    speaker: Optional[str] = None

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def is_speech(self) -> bool:
        return (self.no_speech_prob or 0.0) < NON_SPEECH_PROB_THRESHOLD

    @property
    def token_probability(self) -> float:
        """Geometric mean token probability, derived from Whisper's avg_logprob.

        avg_logprob is a mean log-probability, so exp() maps it back to a 0-1
        confidence: -0.3 -> 0.74, -0.6 -> 0.55, -1.0 -> 0.37.
        """
        if self.avg_logprob is None:
            return 1.0
        return math.exp(max(-10.0, float(self.avg_logprob)))


def parse_whisper_segments(response: Any) -> List[TranscriptSegment]:
    """Extract segments from a Whisper verbose_json response.

    The OpenAI SDK returns either objects or plain dicts depending on provider,
    so both shapes are handled.
    """
    raw_segments = getattr(response, "segments", None)
    if raw_segments is None and isinstance(response, dict):
        raw_segments = response.get("segments")
    if not raw_segments:
        return []

    def _get(item: Any, key: str) -> Any:
        if isinstance(item, dict):
            return item.get(key)
        return getattr(item, key, None)

    segments: List[TranscriptSegment] = []
    for idx, item in enumerate(raw_segments):
        text = (_get(item, "text") or "").strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                index=len(segments),
                start=float(_get(item, "start") or 0.0),
                end=float(_get(item, "end") or 0.0),
                text=text,
                avg_logprob=_get(item, "avg_logprob"),
                no_speech_prob=_get(item, "no_speech_prob"),
                compression_ratio=_get(item, "compression_ratio"),
            )
        )
    return segments


def _normalize_words(text: str) -> List[str]:
    return re.findall(r"\w+", (text or "").lower())


def detect_prompt_echo(text: str, prompt: str, min_run: int = 6) -> bool:
    """Detect Whisper regurgitating its own conditioning prompt as transcript.

    Whisper is conditioned on a prompt to bias vocabulary, and on audio with
    little or no speech it frequently just emits that prompt back. The result
    looks like a confident, well-formed transcript: compression_ratio stays
    low, no_speech_prob stays low, and avg_logprob looks unremarkable - so none
    of the usual quality signals catch it. Observed in end-to-end testing,
    where a tone-only recording transcribed as the prompt text verbatim.

    Detected by looking for a long contiguous run of prompt words inside the
    transcript. Real call audio never reproduces the instruction phrasing, so
    a run this long is unambiguous.
    """
    prompt_words = _normalize_words(prompt)
    text_words = _normalize_words(text)
    if len(prompt_words) < min_run or len(text_words) < min_run:
        return False

    prompt_runs = {
        tuple(prompt_words[i : i + min_run])
        for i in range(len(prompt_words) - min_run + 1)
    }

    # Measure how much of the transcript is prompt, not merely whether any of
    # it is. The prompt is now a *style sample* of real agent/customer dialogue,
    # so a genuine call legitimately reproduces short phrases from it -
    # "आपकी क्या help कर सकता हूँ" is exactly what an agent says. Flagging on a
    # single match marked good transcripts unreliable. A real echo, by
    # contrast, is almost entirely prompt text.
    covered = [False] * len(text_words)
    for i in range(len(text_words) - min_run + 1):
        if tuple(text_words[i : i + min_run]) in prompt_runs:
            for j in range(i, i + min_run):
                covered[j] = True

    return (sum(covered) / len(text_words)) >= PROMPT_ECHO_COVERAGE_THRESHOLD


def score_transcript_quality(
    segments: List[TranscriptSegment],
    min_confidence: Optional[float] = None,
    prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Duration-weighted confidence score plus specific quality flags.

    Weighting by duration stops a flurry of short "haan"/"ok" segments from
    dominating the score of a call whose substantive turns transcribed poorly.
    """
    threshold = (
        min_confidence if min_confidence is not None else settings.STT_MIN_CONFIDENCE
    )
    flags: List[str] = []

    if not segments:
        return {
            "confidence": 0.0,
            "flags": ["no_segments"],
            "speech_ratio": 0.0,
            "segment_count": 0,
            "is_reliable": False,
        }

    speech = [s for s in segments if s.is_speech]
    total_duration = sum(s.duration for s in segments) or 1.0
    speech_duration = sum(s.duration for s in speech)

    scored = speech or segments
    weight_total = sum(s.duration for s in scored)
    if weight_total > 0:
        confidence = sum(s.token_probability * s.duration for s in scored) / weight_total
    else:
        confidence = sum(s.token_probability for s in scored) / len(scored)

    repetitive = [
        s
        for s in segments
        if (s.compression_ratio or 0.0) > HALLUCINATION_COMPRESSION_RATIO
    ]
    if repetitive:
        flags.append("possible_hallucination")

    speech_ratio = speech_duration / total_duration
    if speech_ratio < 0.5:
        flags.append("high_silence")

    if confidence < threshold:
        flags.append("low_confidence")

    if prompt and detect_prompt_echo(" ".join(s.text for s in segments), prompt):
        flags.append("prompt_echo")

    unreliable_flags = {"possible_hallucination", "prompt_echo"}
    return {
        "confidence": round(confidence, 4),
        "flags": flags,
        "speech_ratio": round(speech_ratio, 4),
        "segment_count": len(segments),
        "repetitive_segment_count": len(repetitive),
        "is_reliable": confidence >= threshold and not unreliable_flags.intersection(flags),
    }


def detect_all_transcript_languages(text: str, whisper_lang: Optional[str] = None) -> List[str]:
    """Detect all languages and scripts present in the transcript text.

    Script-range detection is reliable. The romanized-Hinglish keyword pass is
    a weak signal only - it needs several distinct matches before it fires,
    because individual tokens like "ka" and "ji" appear inside ordinary English
    text and proper nouns.
    """
    langs = []

    # 1. Devanagari Script (Hindi, Marathi)
    if re.search(r'[ऀ-ॿ]', text):
        langs.append("Hindi (Devanagari)")

    # 2. Tamil Script
    if re.search(r'[஀-௿]', text):
        langs.append("Tamil")

    # 3. Telugu Script
    if re.search(r'[ఀ-౿]', text):
        langs.append("Telugu")

    # 4. Bengali Script
    if re.search(r'[ঀ-৿]', text):
        langs.append("Bengali")

    # 5. Gujarati Script
    if re.search(r'[઀-૿]', text):
        langs.append("Gujarati")

    # 6. Kannada Script
    if re.search(r'[ಀ-೿]', text):
        langs.append("Kannada")

    # 7. Malayalam Script
    if re.search(r'[ഀ-ൿ]', text):
        langs.append("Malayalam")

    # 8. Gurmukhi Script (Punjabi)
    if re.search(r'[਀-੿]', text):
        langs.append("Punjabi (Gurmukhi)")

    # 9. Odia Script
    if re.search(r'[଀-୿]', text):
        langs.append("Odia")

    # 10. Arabic / Urdu Script
    if re.search(r'[؀-ۿ]', text):
        langs.append("Arabic / Urdu")

    # 11. Romanized Hindi / Hinglish. Requires 4+ *distinct* markers so that
    # stray matches in English prose do not mislabel an English-only call.
    hinglish_keywords = [
        r'\baap\b', r'\bhai\b', r'\bhain\b', r'\bnahi\b', r'\bnahin\b',
        r'\bkya\b', r'\bkaro\b', r'\bkarna\b', r'\bkiya\b', r'\bbolo\b',
        r'\bbaat\b', r'\bhaan\b', r'\bacha\b', r'\bachha\b', r'\bdekh\b',
        r'\bmujhe\b', r'\bhamare\b', r'\bapka\b', r'\bkyun\b', r'\bthoda\b',
    ]
    hinglish_matches = sum(1 for kw in hinglish_keywords if re.search(kw, text, re.IGNORECASE))
    if hinglish_matches >= 4:
        langs.append("Hinglish")

    # 12. English
    english_keywords = [
        r'\bthe\b', r'\bis\b', r'\byou\b', r'\bhave\b', r'\bthis\b', r'\bcall\b',
        r'\bwith\b', r'\bproduct\b', r'\bservice\b', r'\bplease\b', r'\bokay\b', r'\byes\b'
    ]
    english_matches = sum(1 for kw in english_keywords if re.search(kw, text, re.IGNORECASE))
    if english_matches >= 2 or (whisper_lang and whisper_lang.lower() in ["en", "english"]):
        if "English" not in langs:
            langs.append("English")

    # Whisper's own language detection is the strongest single signal we have,
    # so fold it in unless a script check already covered that language.
    # (Previously "hindi" and "english" were unconditionally discarded here,
    # which meant a romanized-Hindi transcript with no Devanagari lost the
    # detection entirely and fell through to the "English" default below.)
    if whisper_lang:
        normalized = whisper_lang.strip().lower()
        label = WHISPER_LANGUAGE_LABELS.get(normalized, whisper_lang.capitalize())
        already_covered = any(
            label.split(" (")[0].lower() in existing.lower() for existing in langs
        )
        if not already_covered:
            langs.append(label)

    if not langs:
        langs = ["English"]

    return langs


# Whisper reports languages as names or ISO codes depending on the model; map
# the ones that matter for this market onto the labels used in reports.
WHISPER_LANGUAGE_LABELS = {
    "hi": "Hindi", "hindi": "Hindi",
    "en": "English", "english": "English",
    "ta": "Tamil", "tamil": "Tamil",
    "te": "Telugu", "telugu": "Telugu",
    "bn": "Bengali", "bengali": "Bengali",
    "gu": "Gujarati", "gujarati": "Gujarati",
    "kn": "Kannada", "kannada": "Kannada",
    "ml": "Malayalam", "malayalam": "Malayalam",
    "mr": "Marathi", "marathi": "Marathi",
    "pa": "Punjabi", "punjabi": "Punjabi",
    "or": "Odia", "odia": "Odia",
    "ur": "Urdu", "urdu": "Urdu",
}

# Whisper's `prompt` is NOT an instruction field. It is conditioning context -
# the model treats it as the text immediately preceding the audio and continues
# in that style. Giving it instructions ("Transcribe the exact spoken words...")
# makes it continue writing instructions instead of transcribing: on a real
# 400-second Hindi call that produced 1,400 characters of mangled prompt text
# and no transcript at all.
#
# What works is a short sample of the *expected output*: a snippet of realistic
# agent/customer dialogue in the exact script mix we want back. Measured on the
# same 120 seconds of audio:
#   instructional prompt -> 323 chars, pure echo, unusable
#   no prompt            -> 1,055 chars, correct content, but Urdu (Nastaliq) script
#   this sample          ->   850 chars, correct content, Devanagari + Latin
# The sample is what steers Hindi to Devanagari while leaving English words in
# Latin, which is what Hinglish call transcripts need.
# Words, not sentences. A sample made of full utterances still leaked: the
# line "जी मेरा order अभी तक deliver नहीं हुआ है।" turned up verbatim - twice -
# in a call about a smoking mixer, because Whisper continues whatever prose it
# is given. A bare vocabulary list cannot be continued as dialogue, but still
# establishes the script mix we want (Devanagari for Hindi, Latin for English).
STT_STYLE_SAMPLE = (
    "नमस्ते हाँ जी सर मैडम शिकायत complaint service request order "
    "delivery technician warranty bill invoice replacement refund "
    "address pincode landmark mobile number model product "
    "ठीक है धन्यवाद कृपया समस्या जानकारी"
)


def build_stt_prompt(vocabulary: Optional[str] = None) -> str:
    """Conditioning text sent to Whisper as `prompt`.

    Capped at 224 tokens by the API. Client-specific vocabulary (brand names,
    product SKUs, agent names) measurably improves proper-noun accuracy, which
    is where call-QA transcripts fail most visibly - and unlike instructions,
    a bare term list cannot be continued as prose.
    """
    if vocabulary:
        return f"{STT_STYLE_SAMPLE} {vocabulary}"
    return STT_STYLE_SAMPLE


VALID_SPEAKERS = {"agent", "customer", "other"}


def apply_speaker_turns(
    segments: List[TranscriptSegment], turns: List[Dict[str, Any]]
) -> int:
    """Assign a speaker to every segment from a list of turn-start markers.

    `turns` is the LLM's output: the segment index at which each new speaker
    turn begins. Segments between markers inherit the preceding speaker. This
    is why the diarization call is cheap - it emits one marker per turn (~25
    for a 5-minute call) instead of re-emitting the whole transcript.

    Returns the number of turn markers actually applied.
    """
    if not segments:
        return 0

    cleaned: List[tuple[int, str]] = []
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        raw_index = turn.get("start_segment", turn.get("segment", turn.get("index")))
        speaker = str(turn.get("speaker", "")).strip().lower()
        if speaker in ("agent:", "customer:"):
            speaker = speaker.rstrip(":")
        if speaker not in VALID_SPEAKERS:
            continue
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        if not 0 <= index < len(segments):
            continue
        # Keep markers strictly ascending; a model that emits them out of order
        # would otherwise silently overwrite earlier turns.
        if cleaned and index <= cleaned[-1][0]:
            continue
        cleaned.append((index, speaker))

    if not cleaned:
        return 0

    # A first marker after segment 0 leaves a gap; attribute the opening
    # segments to the opposite speaker, since calls open with one party talking.
    if cleaned[0][0] != 0:
        opener = "agent" if cleaned[0][1] == "customer" else "customer"
        cleaned.insert(0, (0, opener))

    for position, (index, speaker) in enumerate(cleaned):
        end = cleaned[position + 1][0] if position + 1 < len(cleaned) else len(segments)
        for seg in segments[index:end]:
            seg.speaker = speaker

    return len(cleaned)


SPEAKER_CODES = {"A": "agent", "C": "customer", "O": "other"}


def apply_speaker_labels(
    segments: List[TranscriptSegment], labels: Any
) -> Dict[str, Any]:
    """Assign one speaker per segment from a positional label list.

    Per-segment labelling replaced turn-boundary detection because a small
    model cannot reliably find boundaries: asked for turns, ministral-3b
    returned a single turn for a 46-segment two-party call and every line came
    out as the agent. Classifying each segment independently is a far easier
    task, and at one letter per segment it is still only ~60 output tokens.
    """
    if not segments:
        return {"applied": 0, "warning": "no_segments"}

    if isinstance(labels, dict):
        labels = labels.get("speakers") or labels.get("labels") or []
    if isinstance(labels, str):
        labels = re.findall(r"[ACO]", labels.upper())
    if not isinstance(labels, list):
        return {"applied": 0, "warning": "unparseable"}

    resolved: List[Optional[str]] = []
    for item in labels:
        token = str(item).strip().upper()
        if token in SPEAKER_CODES:
            resolved.append(SPEAKER_CODES[token])
        elif token.lower() in VALID_SPEAKERS:
            resolved.append(token.lower())
        else:
            resolved.append(None)

    applied = 0
    last = "agent"
    for idx, seg in enumerate(segments):
        speaker = resolved[idx] if idx < len(resolved) else None
        if speaker is None:
            # A missing or junk label inherits the previous speaker rather than
            # silently becoming "other", which would fragment the dialogue.
            speaker = last
        else:
            applied += 1
        seg.speaker = speaker
        last = speaker

    distinct = {s.speaker for s in segments}
    warning = None
    if applied == 0:
        warning = "unparseable"
    elif applied < len(segments) * 0.5:
        warning = "partial_labels"
    elif len(distinct) < 2:
        # A support call has two parties. One speaker across the whole call
        # means the model failed, not that the customer never spoke.
        warning = "single_speaker"

    return {"applied": applied, "warning": warning, "distinct_speakers": len(distinct)}


def fallback_alternating_speakers(segments: List[TranscriptSegment]) -> None:
    """Last-resort diarization used when the LLM labelling fails outright.

    Whisper emits contiguous segments (one ends exactly where the next begins),
    so an earlier pause-gap heuristic never fired and labelled entire calls as
    a single speaker. Alternating on every segment is crude but at least
    produces a two-party dialogue that a reviewer can correct, and the result
    is always flagged so nobody mistakes it for real diarization.
    """
    for idx, seg in enumerate(segments):
        seg.speaker = "agent" if idx % 2 == 0 else "customer"


def render_dialogue(segments: List[TranscriptSegment]) -> str:
    """Render labelled segments as 'Agent: ...' / 'Customer: ...' lines.

    Consecutive segments from one speaker are merged into a single turn. The
    text is copied verbatim from Whisper - nothing is regenerated by an LLM, so
    the original wording, script and code-switching survive exactly.
    """
    if not segments:
        return ""

    lines: List[str] = []
    current_speaker: Optional[str] = None
    buffer: List[str] = []
    last_named: str = "agent"

    for seg in segments:
        speaker = seg.speaker or "other"
        # "other" covers IVR and hold announcements, but the model also reaches
        # for it when unsure about a normal line. The report only renders Agent
        # and Customer turns, so an "Other:" line was silently absorbed into
        # whichever speaker came before it - attributing the customer's words
        # to the agent. Folding it into the running speaker keeps the dialogue
        # honest about who is talking.
        if speaker == "other":
            speaker = current_speaker or last_named
        else:
            last_named = speaker
        if speaker != current_speaker:
            if buffer:
                lines.append(f"{current_speaker.capitalize()}: {' '.join(buffer)}")
            current_speaker = speaker
            buffer = []
        buffer.append(seg.text)

    if buffer:
        lines.append(f"{current_speaker.capitalize()}: {' '.join(buffer)}")

    return "\n".join(lines)


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

        # Separate client for speaker attribution - it does not have to run on
        # the same provider as the scorecard LLM, and on the free tier Groq's
        # 8B model does this job markedly better than a 3B one.
        self.diarization_model = (
            settings.DIARIZATION_MODEL_NAME or settings.LLM_MODEL_NAME
        )
        self.diarization_base_url = settings.DIARIZATION_BASE_URL or settings.LLM_BASE_URL
        self.llm_client = AsyncOpenAI(
            api_key=settings.DIARIZATION_API_KEY or settings.LLM_API_KEY,
            base_url=self.diarization_base_url,
            timeout=settings.LLM_TIMEOUT,
        )

    async def diarize_segments(self, segments: List[TranscriptSegment]) -> Dict[str, Any]:
        """Attribute speakers, letting the model re-split where turns change.

        Delegates to app/services/diarization.py, which explains why the text
        is re-split rather than labelled segment-by-segment, and how the result
        is verified word-for-word before being trusted.
        """
        from app.services.diarization import diarize_transcript

        if not segments:
            return {
                "dialogue": "",
                "labelled": 0,
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "latency_ms": 0,
                "model_name": self.diarization_model,
                "method": "none",
                "warning": "no_segments",
            }

        logger.info(f"Diarizing {len(segments)} segments...")
        raw_text = " ".join(seg.text for seg in segments)

        result = await diarize_transcript(
            client=self.llm_client,
            model=self.diarization_model,
            segments=segments,
            raw_text=raw_text,
        )

        if result["method"] != "llm_turns":
            # Leave every segment unattributed rather than guessing; the report
            # renders the plain transcript and says why.
            for seg in segments:
                seg.speaker = None

        return {
            "dialogue": result["dialogue"],
            "labelled": len(result["turns"]),
            "token_usage": result.get("token_usage") or {},
            "latency_ms": result.get("latency_ms", 0),
            "model_name": self.diarization_model,
            "method": result["method"],
            "warning": result.get("warning"),
            "retention": result.get("retention"),
        }

    async def _transcribe_with_retry(
        self, file_bytes: bytes, filename: str, vocabulary: Optional[str] = None
    ) -> Any:
        """Call Groq Whisper, retrying transient failures with exponential backoff.

        Rate-limit responses are expected rather than exceptional on the free
        tier (20 RPM, 7,200 audio-seconds/hour), so losing an upload to a single
        429 is not acceptable.
        """
        stt_prompt = build_stt_prompt(vocabulary)

        attempt = 0
        backoff = 2.0
        last_error: Optional[Exception] = None

        while attempt <= settings.STT_MAX_RETRIES:
            attempt += 1
            try:
                return await self.client.audio.transcriptions.create(
                    model=self.stt_model_name,
                    file=(filename, io.BytesIO(file_bytes)),
                    response_format="verbose_json",
                    prompt=stt_prompt,
                    # temperature is deliberately NOT pinned. Whisper's default
                    # is a fallback ladder (0 -> 0.2 -> ... -> 1.0): when a
                    # segment's compression_ratio or avg_logprob crosses a bad
                    # threshold it retries hotter, which is its built-in escape
                    # from repetition and echo loops. Pinning 0.0 disables that
                    # recovery and makes a loop, once entered, unrecoverable.
                )
            except (RateLimitError, APITimeoutError, APIConnectionError, APIError) as exc:
                last_error = exc
                logger.warning(
                    f"STT attempt {attempt}/{settings.STT_MAX_RETRIES + 1} failed: {exc}"
                )
                if attempt > settings.STT_MAX_RETRIES:
                    break
                await asyncio.sleep(backoff)
                backoff *= 2.0

        raise RuntimeError(
            f"Whisper transcription failed after {settings.STT_MAX_RETRIES + 1} attempts: {last_error}"
        ) from last_error

    async def _transcribe_chunks(
        self,
        source_path: str,
        chunks: List[Any],
        vocabulary: Optional[str] = None,
        source_bytes: Optional[bytes] = None,
        source_name: str = "audio",
    ) -> tuple[List[TranscriptSegment], str, Optional[str]]:
        """Transcribe planned chunks in parallel and stitch them back together.

        Concurrency is capped because the free tier allows only 20 requests per
        minute; firing every chunk at once would just collect 429s.
        """
        from app.services.audio_service import extract_chunk, stitch_chunk_segments

        semaphore = asyncio.Semaphore(settings.STT_MAX_CONCURRENT_CHUNKS)
        languages: List[str] = []

        single_whole_file = (
            len(chunks) == 1 and chunks[0].start <= 0.01 and not chunks[0].is_hard_split
        )

        async def run(chunk):
            async with semaphore:
                # Re-cutting a file that is already exactly the chunk wastes a
                # transcode and risks corrupting a perfectly good input.
                if single_whole_file:
                    data = source_bytes
                else:
                    data = await extract_chunk(source_path, chunk)
                name = source_name if single_whole_file else f"chunk{chunk.index}.opus"
                response = await self._transcribe_with_retry(data, name, vocabulary)
                lang = getattr(response, "language", None)
                if lang:
                    languages.append(lang)
                return chunk, parse_whisper_segments(response), (
                    getattr(response, "text", None) or ""
                )

        results = await asyncio.gather(*(run(c) for c in chunks))

        stitched = stitch_chunk_segments([(c, segs) for c, segs, _ in results])
        # Rebuild the flat transcript from the stitched segments rather than
        # concatenating per-chunk text, so it always matches the timeline.
        raw_text = " ".join(s.text for s in stitched).strip()
        dominant_language = max(set(languages), key=languages.count) if languages else None
        return stitched, raw_text, dominant_language

    async def transcribe_audio(
        self,
        file_bytes: bytes,
        filename: str,
        vocabulary: Optional[str] = None,
        preprocess: bool = True,
    ) -> Dict[str, Any]:
        """Transcribe audio and return raw text, labelled segments, quality signals and metrics.

        When ffmpeg is available the audio is first normalised to 16 kHz mono
        Opus and split on silence, which shrinks the upload, skips hold music
        and dead air, and keeps every request under the provider's size limit.
        Without ffmpeg it falls back to sending the original file as-is.
        """
        logger.info(
            f"Transcribing audio '{filename}' ({len(file_bytes)} bytes) "
            f"via Groq Whisper [{self.stt_model_name}]"
        )

        start_time = time.perf_counter()
        prepared = await self._prepare(file_bytes, filename) if preprocess else None

        if prepared is not None:
            normalised, info, chunks, temp_path = prepared
            try:
                segments, raw_transcription, whisper_lang = await self._transcribe_chunks(
                    temp_path, chunks, vocabulary,
                    source_bytes=normalised, source_name=filename,
                )
            finally:
                _cleanup_path(temp_path)
            duration_seconds = info.duration_seconds
            billable_seconds = _billable_seconds(chunks)
            processed_bytes = len(normalised)
            chunk_count = len(chunks)
        else:
            response = await self._transcribe_with_retry(file_bytes, filename, vocabulary)
            raw_transcription = getattr(response, "text", None) or str(response)
            whisper_lang = getattr(response, "language", None)
            duration_seconds = getattr(response, "duration", None)
            segments = parse_whisper_segments(response)
            billable_seconds = None
            processed_bytes = len(file_bytes)
            chunk_count = 1

        stt_latency_ms = int((time.perf_counter() - start_time) * 1000)
        quality = score_transcript_quality(segments, prompt=build_stt_prompt(vocabulary))

        all_langs = detect_all_transcript_languages(raw_transcription, whisper_lang=whisper_lang)
        detected_language = ", ".join(all_langs)

        if not duration_seconds:
            duration_seconds = (
                segments[-1].end if segments
                else estimate_audio_duration_seconds(file_bytes, filename)
            )
        duration_seconds = float(duration_seconds)

        logger.info(
            f"Whisper transcription complete: {len(raw_transcription)} chars, "
            f"{len(segments)} segments, language='{detected_language}', "
            f"duration={duration_seconds:.1f}s, confidence={quality['confidence']}, "
            f"flags={quality['flags']}"
        )

        # Bill against the audio actually sent, not the wall-clock length of
        # the recording - silence skipped at chunk boundaries is never charged.
        charged_seconds = (
            billable_seconds if billable_seconds is not None
            else max(duration_seconds, GROQ_MIN_BILLED_SECONDS)
        )
        stt_usage = {
            "duration_seconds": round(duration_seconds, 2),
            "billable_seconds": round(charged_seconds, 2),
            "seconds_saved": round(max(0.0, duration_seconds - charged_seconds), 2),
            "chunk_count": chunk_count,
            "processed_bytes": processed_bytes,
            "estimated_cost_usd": round(
                whisper_cost_usd(self.stt_model_name, charged_seconds), 6
            ),
            "is_estimated": True,
        }

        diarize_res = await self.diarize_segments(segments)
        dialogue = diarize_res.get("dialogue") or render_dialogue(segments)

        return {
            "raw_text": raw_transcription.strip(),
            "diarized_text": dialogue,
            "segments": [asdict(s) for s in segments],
            "quality": quality,
            "detected_language": detected_language,
            "audio_duration_seconds": round(duration_seconds, 2),
            "stt_model": self.stt_model_name,
            "audio_sha256": sha256_digest(file_bytes),
            "stt_usage": stt_usage,
            "stt_latency_ms": stt_latency_ms,
            "diarize_usage": diarize_res["token_usage"],
            "diarize_latency_ms": diarize_res["latency_ms"],
            "diarize_method": diarize_res["method"],
            "diarize_warning": diarize_res.get("warning"),
        }

    async def _prepare(self, file_bytes: bytes, filename: str):
        """Normalise and plan the audio, returning None if ffmpeg is unavailable.

        Preprocessing is an optimisation, never a hard requirement - a missing
        or failing ffmpeg degrades to sending the original file rather than
        failing the upload.
        """
        from app.services import audio_service

        if not audio_service.ffmpeg_available():
            logger.warning(
                "ffmpeg not found on PATH - skipping transcode and silence "
                "trimming, sending the original file to the STT provider"
            )
            return None

        suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ".audio"
        try:
            normalised, info, chunks = await audio_service.prepare_audio(file_bytes, suffix)
        except audio_service.AudioProcessingError as err:
            logger.warning(f"Audio preprocessing failed ({err}); using original file")
            return None

        if not chunks:
            logger.warning("Audio preprocessing produced no chunks; using original file")
            return None

        handle, temp_path = tempfile.mkstemp(suffix=".opus")
        with os.fdopen(handle, "wb") as fh:
            fh.write(normalised)
        return normalised, info, chunks, temp_path


def _cleanup_path(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _billable_seconds(chunks) -> float:
    from app.services.audio_service import estimate_billable_seconds

    return estimate_billable_seconds(chunks, GROQ_MIN_BILLED_SECONDS)
