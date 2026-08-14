"""Audio preprocessing: transcode, silence detection, and chunk planning.

Everything here exists to serve three goals, in order of value:

1. Shrink the audio. Whisper resamples everything to 16 kHz mono internally, so
   every byte above that is uploaded, stored and paid for and then discarded.
   A 1-hour WAV goes from ~635 MB to ~11 MB as 16 kHz mono Opus.
2. Skip silence. Hold music, IVR and dead air consume STT quota, which on the
   free tier (28,800 audio-seconds/day) is the scarcest resource in the whole
   pipeline.
3. Split files that exceed the provider's per-request size limit, and let the
   pieces be transcribed in parallel.

ffmpeg is the only external dependency. The alternative for silence detection
would be Silero VAD, which pulls in torch at ~800 MB - unusable on a free-tier
box. ffmpeg's silencedetect filter gets the same split points for ~70 MB.

The planning and stitching functions are deliberately pure so they can be
tested without ffmpeg installed.
"""
import asyncio
import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from app.core.config import settings
from app.services.stt_service import TranscriptSegment

logger = logging.getLogger(__name__)

# --- Transcode target -------------------------------------------------------
# Whisper works at 16 kHz mono. Opus is exceptionally good on speech at low
# bitrates; 24 kbps is a deliberately conservative default - 16 kbps is close
# enough to the edge that it should not be adopted without measuring WER on the
# golden set first.
TARGET_SAMPLE_RATE = 16_000
TARGET_CHANNELS = 1
TARGET_BITRATE = "24k"
TARGET_BITRATE_BPS = 24_000
# Groq's per-request upload ceiling on the free tier. A file under this needs
# no chunking at all.
MAX_SINGLE_REQUEST_BYTES = 24 * 1024 * 1024
# Tried in order when a recording will not fit in one request. Speech stays
# intelligible to Whisper well below the 24 kbps default; 12 kbps mono Opus
# still carries roughly 4.5 hours inside the limit.
FALLBACK_BITRATES = ("16k", "12k", "10k")

# --- Silence detection ------------------------------------------------------
SILENCE_NOISE_DB = -30
SILENCE_MIN_DURATION = 0.5
# A silence must be at least this long to be considered a safe place to cut.
# Cutting mid-word costs the word and destabilises the decoder either side.
MIN_SILENCE_TO_SPLIT = 0.8
# A silence this long is almost always hold music or a transfer, so cut there
# even if the current chunk is still short. This is what turns a 3-minute hold
# into a chunk boundary instead of 3 minutes of billed dead air.
FORCE_SPLIT_SILENCE = 5.0

# --- Chunk sizing -----------------------------------------------------------
TARGET_CHUNK_SECONDS = 480.0   # 8 minutes
MAX_CHUNK_SECONDS = 900.0      # hard ceiling before a mid-speech split
# Groq bills a 10-second minimum per request, so very short chunks waste quota.
# This also stops a noisy recording from being shredded into hundreds of pieces.
MIN_CHUNK_SECONDS = 30.0
# Overlap applied only when a chunk must be split mid-speech, so the decoder
# has context either side of an unnatural cut.
HARD_SPLIT_OVERLAP_SECONDS = 3.0

FFMPEG_TIMEOUT_SECONDS = 300


class AudioProcessingError(RuntimeError):
    """Raised when ffmpeg is unavailable or fails on a file."""


@dataclass
class AudioInfo:
    duration_seconds: float
    sample_rate: int
    channels: int
    codec: str
    size_bytes: int


@dataclass
class SilenceInterval:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class ChunkPlan:
    index: int
    start: float
    end: float
    # True when the cut was forced mid-speech rather than landing on a silence,
    # which is the only case where stitching has to dedupe an overlap.
    is_hard_split: bool = False

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


# ---------------------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------------------

_SILENCE_START_RE = re.compile(r"silence_start:\s*(-?[\d.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*(-?[\d.]+)")


def parse_silence_log(stderr: str, duration: float) -> List[SilenceInterval]:
    """Parse the silence_start / silence_end pairs ffmpeg writes to stderr.

    A trailing silence_start with no matching silence_end means the file ends
    in silence, so it is closed off at the file duration.
    """
    intervals: List[SilenceInterval] = []
    pending_start: Optional[float] = None

    for line in stderr.splitlines():
        start_match = _SILENCE_START_RE.search(line)
        if start_match:
            pending_start = max(0.0, float(start_match.group(1)))
            continue
        end_match = _SILENCE_END_RE.search(line)
        if end_match and pending_start is not None:
            end = min(duration, float(end_match.group(1)))
            if end > pending_start:
                intervals.append(SilenceInterval(pending_start, end))
            pending_start = None

    if pending_start is not None and duration > pending_start:
        intervals.append(SilenceInterval(pending_start, duration))

    return intervals


def derive_speech_spans(
    duration: float,
    silences: Sequence[SilenceInterval],
    min_silence: float = MIN_SILENCE_TO_SPLIT,
) -> List[Tuple[float, float]]:
    """Invert the silence list into spans of speech.

    Only silences at least `min_silence` long break a span; shorter pauses are
    natural speech rhythm and are kept inside the span so the audio handed to
    Whisper stays continuous.
    """
    if duration <= 0:
        return []

    splitters = sorted(
        (s for s in silences if s.duration >= min_silence), key=lambda s: s.start
    )

    spans: List[Tuple[float, float]] = []
    cursor = 0.0
    for silence in splitters:
        start = max(0.0, min(silence.start, duration))
        if start > cursor:
            spans.append((cursor, start))
        cursor = max(cursor, min(silence.end, duration))

    if cursor < duration:
        spans.append((cursor, duration))

    return [(a, b) for a, b in spans if b > a]


def plan_chunks(
    duration: float,
    silences: Sequence[SilenceInterval] = (),
    target_seconds: float = TARGET_CHUNK_SECONDS,
    max_seconds: float = MAX_CHUNK_SECONDS,
    min_seconds: float = MIN_CHUNK_SECONDS,
    drop_silence: bool = False,
) -> List[ChunkPlan]:
    """Split audio into chunks, cutting on silence where possible.

    With `drop_silence=False` (the default) the chunks **tile the whole
    recording** - silence is only used to choose *where* to cut, never to skip
    audio. Silence is cheap; a lost sentence is not. Measured on a real call,
    trimming at chunk edges dropped 9 seconds of a 311-second recording,
    because speech quieter than the -30 dB threshold reads as silence and was
    never sent to the provider at all.

    `drop_silence=True` restores the trimming behaviour for callers who care
    more about quota than completeness.
    """
    if duration <= 0:
        return []

    if not drop_silence:
        return _tile_full_timeline(duration, silences, target_seconds, max_seconds)

    spans = derive_speech_spans(duration, silences)
    if not spans:
        # Entirely silent, or no silence data at all: fall back to the whole file.
        return _split_span(0.0, duration, max_seconds, start_index=0)

    chunks: List[ChunkPlan] = []
    current_start: Optional[float] = None
    current_end: Optional[float] = None

    def flush() -> None:
        nonlocal current_start, current_end
        if current_start is None or current_end is None:
            return
        chunks.extend(
            _split_span(current_start, current_end, max_seconds, start_index=len(chunks))
        )
        current_start = None
        current_end = None

    previous_end: Optional[float] = None

    for span_start, span_end in spans:
        if current_start is None:
            current_start, current_end = span_start, span_end
            previous_end = span_end
            continue

        gap = span_start - (previous_end if previous_end is not None else span_start)
        current_length = current_end - current_start

        # A long silence is a natural boundary (hold music, transfer), so cut
        # there and leave the silence out of both chunks entirely.
        if gap >= FORCE_SPLIT_SILENCE and current_length >= min_seconds:
            flush()
            current_start, current_end = span_start, span_end
            previous_end = span_end
            continue

        # Otherwise absorb the span and only close once the chunk has actually
        # reached the target. Closing as soon as the *next* span would overshoot
        # leaves chunks far below target, and every extra chunk costs another
        # request against a 20 RPM limit plus a 10-second billing minimum.
        current_end = span_end
        previous_end = span_end

        if (current_end - current_start) >= target_seconds:
            flush()

    flush()

    # A tiny trailing chunk costs a whole request (and Groq's 10-second minimum)
    # for very little audio, so fold it back into its predecessor.
    if len(chunks) > 1 and chunks[-1].duration < min_seconds:
        tail = chunks.pop()
        previous = chunks[-1]
        chunks[-1] = ChunkPlan(
            index=previous.index,
            start=previous.start,
            end=tail.end,
            is_hard_split=previous.is_hard_split,
        )

    return [
        ChunkPlan(index=i, start=c.start, end=c.end, is_hard_split=c.is_hard_split)
        for i, c in enumerate(chunks)
    ]


def _tile_full_timeline(
    duration: float,
    silences: Sequence[SilenceInterval],
    target_seconds: float,
    max_seconds: float,
) -> List[ChunkPlan]:
    """Cover [0, duration] with contiguous chunks, cutting inside silences.

    Every second of the recording lands in exactly one chunk. Cut points are
    nudged to the middle of a nearby silence so the split does not land
    mid-word, but no audio is ever skipped.
    """
    if duration <= max_seconds:
        return [ChunkPlan(index=0, start=0.0, end=duration)]

    # Midpoints of silences long enough to be a safe place to cut.
    candidates = sorted(
        (s.start + s.end) / 2.0
        for s in silences
        if s.duration >= MIN_SILENCE_TO_SPLIT
    )

    boundaries: List[float] = [0.0]
    while duration - boundaries[-1] > max_seconds:
        ideal = boundaries[-1] + target_seconds
        window_start = boundaries[-1] + MIN_CHUNK_SECONDS
        window_end = min(boundaries[-1] + max_seconds, duration)

        usable = [c for c in candidates if window_start <= c <= window_end]
        # Nearest safe silence to the target length, or a hard cut if the
        # speaker simply never pauses.
        cut = min(usable, key=lambda c: abs(c - ideal)) if usable else window_end
        boundaries.append(cut)

    boundaries.append(duration)

    return [
        ChunkPlan(index=i, start=boundaries[i], end=boundaries[i + 1])
        for i in range(len(boundaries) - 1)
        if boundaries[i + 1] > boundaries[i]
    ]


def _split_span(
    start: float, end: float, max_seconds: float, start_index: int
) -> List[ChunkPlan]:
    """Break a single continuous span that exceeds the per-chunk ceiling.

    There is no silence to cut on here, so successive pieces overlap slightly
    and stitching drops the duplicated segments.
    """
    length = end - start
    if length <= max_seconds:
        return [ChunkPlan(index=start_index, start=start, end=end)]

    pieces: List[ChunkPlan] = []
    cursor = start
    while cursor < end:
        piece_end = min(cursor + max_seconds, end)
        pieces.append(
            ChunkPlan(
                index=start_index + len(pieces),
                start=cursor,
                end=piece_end,
                is_hard_split=cursor > start,
            )
        )
        if piece_end >= end:
            break
        cursor = piece_end - HARD_SPLIT_OVERLAP_SECONDS

    return pieces


def estimate_billable_seconds(
    chunks: Sequence[ChunkPlan], min_billed_per_request: float = 10.0
) -> float:
    """Audio-seconds the provider will actually charge for these chunks.

    Accounts for the per-request minimum, so a plan that shreds a call into
    many small pieces shows up as more expensive rather than less.
    """
    return sum(max(c.duration, min_billed_per_request) for c in chunks)


def stitch_chunk_segments(
    results: Sequence[Tuple[ChunkPlan, Sequence[TranscriptSegment]]],
) -> List[TranscriptSegment]:
    """Merge per-chunk Whisper output back onto the original call timeline.

    Whisper reports timestamps relative to the chunk it was given, so each
    segment is shifted by its chunk's start offset. Without this every evidence
    link and audio jump in the report would point at the wrong moment.

    Segments falling inside a hard-split overlap are dropped, keeping the copy
    from the earlier chunk, which had the leading context.
    """
    stitched: List[TranscriptSegment] = []
    previous_end = 0.0

    for chunk, segments in sorted(results, key=lambda item: item[0].start):
        for segment in segments:
            start = segment.start + chunk.start
            end = segment.end + chunk.start

            # Only hard splits overlap; silence-aligned chunks never do.
            if chunk.is_hard_split and start < previous_end:
                continue

            stitched.append(
                TranscriptSegment(
                    index=len(stitched),
                    start=round(start, 3),
                    end=round(end, 3),
                    text=segment.text,
                    avg_logprob=segment.avg_logprob,
                    no_speech_prob=segment.no_speech_prob,
                    compression_ratio=segment.compression_ratio,
                    speaker=segment.speaker,
                )
            )
            previous_end = max(previous_end, end)

    return stitched


# ---------------------------------------------------------------------------
# ffmpeg-backed operations
# ---------------------------------------------------------------------------

def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


async def _run(command: Sequence[str], label: str) -> Tuple[int, bytes, bytes]:
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as err:
        raise AudioProcessingError(
            f"{label} failed: ffmpeg is not installed or not on PATH"
        ) from err

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=FFMPEG_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError as err:
        process.kill()
        await process.wait()
        raise AudioProcessingError(
            f"{label} timed out after {FFMPEG_TIMEOUT_SECONDS}s"
        ) from err

    return process.returncode or 0, stdout, stderr


class _TempAudioFile:
    """Writes bytes to a temp file, because ffmpeg needs seekable input to
    probe durations and cut accurate time ranges."""

    def __init__(self, data: bytes, suffix: str = ".audio"):
        self._data = data
        self._suffix = suffix
        self.path: str = ""

    def __enter__(self) -> str:
        handle, self.path = tempfile.mkstemp(suffix=self._suffix)
        with os.fdopen(handle, "wb") as fh:
            fh.write(self._data)
        return self.path

    def __exit__(self, *exc_info) -> None:
        try:
            os.unlink(self.path)
        except OSError:
            pass


async def probe_audio(path: str) -> AudioInfo:
    """Read duration, sample rate, channels and codec via ffprobe."""
    code, stdout, stderr = await _run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate,channels,codec_name",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=0",
            path,
        ],
        "ffprobe",
    )
    if code != 0:
        raise AudioProcessingError(f"ffprobe failed: {stderr.decode(errors='replace')[:300]}")

    fields = {}
    for line in stdout.decode(errors="replace").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            fields[key.strip()] = value.strip()

    try:
        duration = float(fields.get("duration", 0.0) or 0.0)
    except ValueError:
        duration = 0.0

    return AudioInfo(
        duration_seconds=duration,
        sample_rate=int(fields.get("sample_rate") or 0),
        channels=int(fields.get("channels") or 0),
        codec=fields.get("codec_name", "unknown"),
        size_bytes=os.path.getsize(path) if os.path.exists(path) else 0,
    )


async def transcode_to_opus(
    data: bytes, source_suffix: str = ".audio", bitrate: Optional[str] = None
) -> bytes:
    """Convert arbitrary input audio to 16 kHz mono Opus in an Ogg container."""
    with _TempAudioFile(data, source_suffix) as source:
        output = source + ".opus"
        try:
            code, _, stderr = await _run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", source,
                    "-ac", str(TARGET_CHANNELS),
                    "-ar", str(TARGET_SAMPLE_RATE),
                    "-c:a", "libopus",
                    "-b:a", bitrate or TARGET_BITRATE,
                    # Opus is tuned for music by default; voip mode is
                    # noticeably better on speech at low bitrates.
                    "-application", "voip",
                    output,
                ],
                "ffmpeg transcode",
            )
            if code != 0:
                raise AudioProcessingError(
                    f"Transcode failed: {stderr.decode(errors='replace')[:300]}"
                )
            with open(output, "rb") as fh:
                result = fh.read()
        finally:
            try:
                os.unlink(output)
            except OSError:
                pass

    logger.info(
        f"Transcoded audio {len(data)} -> {len(result)} bytes "
        f"({len(data) / max(1, len(result)):.1f}x smaller)"
    )
    return result


async def detect_silence(path: str, duration: float) -> List[SilenceInterval]:
    """Locate silent stretches using ffmpeg's silencedetect filter."""
    _, _, stderr = await _run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", path,
            "-af", f"silencedetect=noise={SILENCE_NOISE_DB}dB:d={SILENCE_MIN_DURATION}",
            "-f", "null", "-",
        ],
        "ffmpeg silencedetect",
    )
    intervals = parse_silence_log(stderr.decode(errors="replace"), duration)
    logger.info(f"Detected {len(intervals)} silent stretches in {duration:.1f}s of audio")
    return intervals


async def extract_chunk(path: str, chunk: ChunkPlan) -> bytes:
    """Cut one planned chunk out of a source file as 16 kHz mono Opus."""
    output = f"{path}.chunk{chunk.index}.opus"
    try:
        code, _, stderr = await _run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                # -ss before -i seeks quickly; -accurate_seek keeps the cut
                # aligned so stitched timestamps stay trustworthy.
                "-accurate_seek", "-ss", f"{chunk.start:.3f}",
                "-t", f"{chunk.duration:.3f}",
                "-i", path,
                "-ac", str(TARGET_CHANNELS),
                "-ar", str(TARGET_SAMPLE_RATE),
                "-c:a", "libopus", "-b:a", TARGET_BITRATE,
                "-application", "voip",
                output,
            ],
            "ffmpeg chunk extract",
        )
        if code != 0:
            raise AudioProcessingError(
                f"Chunk {chunk.index} extraction failed: "
                f"{stderr.decode(errors='replace')[:300]}"
            )
        with open(output, "rb") as fh:
            return fh.read()
    finally:
        try:
            os.unlink(output)
        except OSError:
            pass


async def prepare_audio(data: bytes, source_suffix: str = ".audio") -> Tuple[bytes, AudioInfo, List[ChunkPlan]]:
    """Get audio ready for transcription, touching it as little as possible.

    The default path does nothing at all: the original bytes go to the provider
    exactly as uploaded, as a single request. Every transformation that was
    tried here cost transcript content -

      * silence trimming dropped 9 seconds of a 311-second call, because
        `silencedetect` at -30 dB cannot tell silence from quiet speech;
      * re-encoding re-compressed already-lossy 16 kbps telephony audio, which
        can only lose detail Whisper might have used, and on real call
        recordings made the file *larger*;
      * splitting risks losing or duplicating words at every seam.

    None of that is worth it. Whisper resamples to 16 kHz mono internally
    anyway, so sending the original costs nothing but a few extra bytes of
    upload. Processing now happens only when a recording is too large for one
    request, and even then it re-encodes rather than splits.
    """
    if not ffmpeg_available():
        raise AudioProcessingError("ffmpeg/ffprobe not found on PATH")

    with _TempAudioFile(data, source_suffix) as source_path:
        info = await probe_audio(source_path)

    whole_file = [ChunkPlan(index=0, start=0.0, end=info.duration_seconds)]

    if len(data) <= MAX_SINGLE_REQUEST_BYTES:
        logger.info(
            f"Sending audio untouched: {info.duration_seconds:.1f}s, "
            f"{len(data)} bytes, {info.codec} {info.sample_rate}Hz "
            f"{info.channels}ch - no transcode, no trimming, no split"
        )
        return data, info, whole_file

    # Only now is any transformation justified: the provider will reject this
    # outright otherwise. Re-encode progressively smaller, still whole-file.
    logger.info(
        f"Audio is {len(data)} bytes, above the {MAX_SINGLE_REQUEST_BYTES} "
        "single-request limit - re-encoding to fit rather than splitting"
    )
    prepared = data
    for bitrate in (TARGET_BITRATE,) + FALLBACK_BITRATES:
        prepared = await transcode_to_opus(data, source_suffix, bitrate=bitrate)
        if len(prepared) <= MAX_SINGLE_REQUEST_BYTES:
            logger.info(f"Fits in one request at {bitrate} ({len(prepared)} bytes)")
            return prepared, info, whole_file

    if not settings.STT_ALLOW_CHUNKING:
        raise AudioProcessingError(
            f"This recording is {info.duration_seconds / 3600:.1f} hours long and "
            "will not fit in a single transcription request even at the lowest "
            "bitrate. Split it before uploading, or set STT_ALLOW_CHUNKING=True "
            "to let the system split it automatically."
        )

    # Explicitly opted in: split, tiling the whole timeline so nothing is
    # dropped, preferring silences as cut points.
    with _TempAudioFile(prepared, ".opus") as path:
        silences = await detect_silence(path, info.duration_seconds)
        chunks = plan_chunks(info.duration_seconds, silences)

    logger.info(f"Split into {len(chunks)} chunk(s) covering the full recording")
    return prepared, info, chunks
