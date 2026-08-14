"""Speaker attribution for call transcripts.

Why this works the way it does
------------------------------
Whisper's segments are cut on silence and length, not on speaker change, so a
single segment routinely contains the tail of one speaker's sentence and the
start of the other's. Labelling each segment with one speaker therefore has a
hard accuracy ceiling: for any segment that straddles a turn boundary, every
possible answer is partly wrong. Measured on a real 48-segment support call,
per-segment labelling put the agent's closing line and the customer's opening
complaint under the same speaker no matter which model was used.

So the model is allowed to re-split the text where the turns actually change.
The risk with that - the reason it was avoided at first - is that a model
rewriting a transcript can silently drop, translate or invent words. That risk
is handled by *verifying* rather than by avoiding: the words that come back are
compared against the words that went in, and anything that fails the check is
discarded in favour of the unmodified transcript.

Speakers are then mapped back onto the original timestamped segments by walking
both word sequences together, so evidence links and talk-time analytics keep
working.
"""
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

AGENT = "agent"
CUSTOMER = "customer"

_LABEL_RE = re.compile(
    r"^\s*(?:\*\*)?\s*(agent|customer|caller|user|support|rep)\s*(?:\*\*)?\s*:\s*",
    re.IGNORECASE,
)
_AGENT_WORDS = {"agent", "support", "rep"}

# Fraction of the original words that must survive the rewrite. Whisper output
# is messy and a model may reasonably drop a stray filler or fix spacing, but
# losing much more than this means it summarised or translated instead of
# splitting, and the result cannot be trusted as a transcript.
MIN_WORD_RETENTION = 0.85
# Guard against the opposite failure: a model that pads the transcript with
# invented dialogue.
MAX_WORD_INFLATION = 1.15


def normalize_words(text: str) -> List[str]:
    return re.findall(r"\w+", (text or "").lower())


def strip_speaker_labels(text: str) -> str:
    """Remove 'Agent:' / 'Customer:' prefixes so only spoken words remain.

    The verbatim check must compare speech to speech; counting the labels the
    model was asked to insert would make every correct split look like invented
    content.
    """
    return "\n".join(
        _LABEL_RE.sub("", line) for line in (text or "").splitlines()
    )


def parse_labelled_dialogue(text: str) -> List[Tuple[str, str]]:
    """Turn 'Agent: ...' / 'Customer: ...' lines into (speaker, text) pairs.

    Unlabelled continuation lines attach to the preceding speaker, which is how
    models tend to wrap long turns.
    """
    turns: List[Tuple[str, str]] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = _LABEL_RE.match(line)
        if match:
            speaker = AGENT if match.group(1).lower() in _AGENT_WORDS else CUSTOMER
            body = line[match.end():].strip()
            if body:
                turns.append((speaker, body))
            else:
                # A bare "Agent:" line labels whatever follows it.
                turns.append((speaker, ""))
        elif turns:
            speaker, body = turns[-1]
            turns[-1] = (speaker, f"{body} {line}".strip())

    return [(s, t) for s, t in turns if t]


def verify_verbatim(original: str, rewritten: str) -> Dict[str, Any]:
    """Check that the model split the transcript instead of rewriting it.

    Compares word multisets rather than exact sequences, so reordering within a
    turn or changed punctuation is tolerated while dropped, translated or
    invented content is not.
    """
    original_words = normalize_words(strip_speaker_labels(original))
    new_words = normalize_words(strip_speaker_labels(rewritten))

    if not original_words:
        return {"ok": False, "reason": "empty_source", "retention": 0.0}
    if not new_words:
        return {"ok": False, "reason": "empty_result", "retention": 0.0}

    original_counts: Dict[str, int] = {}
    for word in original_words:
        original_counts[word] = original_counts.get(word, 0) + 1

    kept = 0
    for word in new_words:
        if original_counts.get(word, 0) > 0:
            original_counts[word] -= 1
            kept += 1

    retention = kept / len(original_words)
    inflation = len(new_words) / len(original_words)

    if retention < MIN_WORD_RETENTION:
        return {"ok": False, "reason": "words_lost", "retention": retention}
    if inflation > MAX_WORD_INFLATION:
        return {"ok": False, "reason": "words_invented", "retention": retention}

    return {"ok": True, "reason": None, "retention": retention}


def assign_speakers_to_segments(segments: List[Any], turns: List[Tuple[str, str]]) -> int:
    """Map turn speakers back onto the timestamped segments.

    Walks the turn word stream alongside each segment's words and gives the
    segment whichever speaker contributed most of it, so timestamps, evidence
    links and talk-time stats stay usable even though the turns were re-split.
    """
    if not segments or not turns:
        return 0

    # Flat list of (word, speaker) across the whole labelled dialogue.
    stream: List[Tuple[str, str]] = []
    for speaker, body in turns:
        for word in normalize_words(body):
            stream.append((word, speaker))

    if not stream:
        return 0

    cursor = 0
    assigned = 0
    last_speaker = turns[0][0]

    for segment in segments:
        words = normalize_words(segment.text)
        if not words:
            segment.speaker = last_speaker
            continue

        votes: Dict[str, int] = {}
        matched = 0
        search_limit = min(len(stream), cursor + len(words) * 3 + 10)

        for word in words:
            probe = cursor
            while probe < search_limit and stream[probe][0] != word:
                probe += 1
            if probe < search_limit:
                speaker = stream[probe][1]
                votes[speaker] = votes.get(speaker, 0) + 1
                matched += 1
                cursor = probe + 1

        if votes:
            segment.speaker = max(votes, key=votes.get)
            last_speaker = segment.speaker
            assigned += 1
        else:
            segment.speaker = last_speaker

    return assigned


def render_turns(turns: List[Tuple[str, str]]) -> str:
    """Render turns as the 'Agent: ...' / 'Customer: ...' block the report shows."""
    lines: List[str] = []
    for speaker, body in turns:
        if lines and lines[-1].startswith(f"{speaker.capitalize()}:"):
            lines[-1] = f"{lines[-1]} {body}".strip()
        else:
            lines.append(f"{speaker.capitalize()}: {body}")
    return "\n".join(lines)


SYSTEM_PROMPT = (
    "You split a call-centre transcript into speaker turns.\n\n"
    "The transcript is one unbroken block of speech-to-text output from a call "
    "between a support AGENT and a CUSTOMER. Punctuation is unreliable and "
    "there are no speaker markers. Your job is to insert them.\n\n"
    "WHO IS WHO (applies to any industry):\n"
    "- Agent: greets and names the company, asks for the customer's details "
    "(name, address, pincode, model, purchase date), explains policy, raises "
    "complaints/tickets, books technician visits, promises callbacks, closes "
    "the call. Uses 'sir'/'madam'. Says things like 'मैं आपकी complaint raise "
    "कर रही हूँ', 'आपका address बताइए'.\n"
    "- Customer: describes the problem, gives their own details when asked, "
    "answers questions, asks when it will be fixed and whether there is a "
    "charge.\n\n"
    "RULES - these matter more than anything else:\n"
    "1. Reproduce the words EXACTLY as given. Do not translate, correct, "
    "summarise, reorder or add anything. Devanagari stays Devanagari, English "
    "stays English.\n"
    "2. You may only insert 'Agent:' / 'Customer:' labels and line breaks.\n"
    "3. Every word of the input must appear exactly once in the output.\n"
    "4. Speakers alternate as a real conversation does - a question from one "
    "side is usually answered by the other.\n"
    "5. Start each line with 'Agent:' or 'Customer:' and nothing else. No "
    "markdown, no commentary, no numbering.\n\n"
    "Output the labelled transcript only."
)


async def diarize_transcript(
    client: Any,
    model: str,
    segments: List[Any],
    raw_text: str,
    max_tokens: int = 8000,
) -> Dict[str, Any]:
    """Split a transcript into speaker turns and map them back onto segments."""
    start = time.perf_counter()
    source = raw_text or " ".join(s.text for s in segments)

    if not source.strip():
        return {
            "turns": [], "dialogue": "", "method": "none", "warning": "empty",
            "token_usage": {}, "latency_ms": 0,
        }

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Transcript:\n{source}"},
            ],
            temperature=0.0,
            max_tokens=max_tokens,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        usage = {}
        if getattr(response, "usage", None):
            usage = {
                "prompt_tokens": response.usage.prompt_tokens or 0,
                "completion_tokens": response.usage.completion_tokens or 0,
                "total_tokens": response.usage.total_tokens or 0,
            }

        content = response.choices[0].message.content or ""
        turns = parse_labelled_dialogue(content)
        speakers = {s for s, _ in turns}

        if not turns:
            return _rejected(source, "unparseable", usage, latency_ms)
        if len(speakers) < 2:
            # A support call has two parties; one speaker means the model
            # failed at the one thing it was asked to do.
            return _rejected(source, "single_speaker", usage, latency_ms)

        check = verify_verbatim(source, " ".join(t for _, t in turns))
        if not check["ok"]:
            logger.warning(
                f"Diarization rejected: {check['reason']} "
                f"(retention {check['retention']:.2f})"
            )
            return _rejected(source, check["reason"], usage, latency_ms)

        assign_speakers_to_segments(segments, turns)
        logger.info(
            f"Diarized into {len(turns)} turns, "
            f"word retention {check['retention']:.2%}"
        )
        return {
            "turns": turns,
            "dialogue": render_turns(turns),
            "method": "llm_turns",
            "warning": None,
            "retention": round(check["retention"], 4),
            "token_usage": usage,
            "latency_ms": latency_ms,
        }

    except Exception as err:
        logger.warning(f"Diarization call failed: {err}")
        return _rejected(source, "llm_error", {}, int((time.perf_counter() - start) * 1000))


def _rejected(source: str, warning: str, usage: Dict, latency_ms: int) -> Dict[str, Any]:
    """Fall back to the unlabelled transcript.

    Showing the raw text with a warning is honest; showing confidently wrong
    speaker labels is not, and the scorecard would then be scoring the wrong
    person for everything said on the call.
    """
    return {
        "turns": [],
        "dialogue": source,
        "method": "unlabelled",
        "warning": warning,
        "token_usage": usage,
        "latency_ms": latency_ms,
    }
