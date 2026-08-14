"""Tests for speaker attribution.

The verbatim check is the important part: it is what makes it safe to let a
model re-split the transcript instead of labelling fixed segments.
"""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from app.services.diarization import (
    MIN_WORD_RETENTION,
    assign_speakers_to_segments,
    diarize_transcript,
    parse_labelled_dialogue,
    render_turns,
    verify_verbatim,
)
from app.services.stt_service import TranscriptSegment


def seg(index, start, end, text):
    return TranscriptSegment(index=index, start=start, end=end, text=text)


def fake_client(content, usage_tokens=100):
    client = MagicMock()
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    usage = MagicMock()
    usage.prompt_tokens = usage_tokens
    usage.completion_tokens = usage_tokens
    usage.total_tokens = usage_tokens * 2
    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


class TestParseLabelledDialogue(unittest.TestCase):

    def test_parses_basic_turns(self):
        turns = parse_labelled_dialogue("Agent: hello there\nCustomer: my order is late")
        self.assertEqual(turns, [("agent", "hello there"), ("customer", "my order is late")])

    def test_accepts_label_synonyms_and_markdown(self):
        turns = parse_labelled_dialogue(
            "**Agent:** hi\nCaller: problem here\nUser: more\nSupport: fixed"
        )
        self.assertEqual([s for s, _ in turns], ["agent", "customer", "customer", "agent"])

    def test_continuation_lines_attach_to_previous_speaker(self):
        turns = parse_labelled_dialogue("Agent: first part\nsecond part\nCustomer: mine")
        self.assertEqual(turns[0], ("agent", "first part second part"))

    def test_preserves_devanagari_verbatim(self):
        original = "आपका order अभी तक deliver नहीं हुआ"
        turns = parse_labelled_dialogue(f"Customer: {original}")
        self.assertEqual(turns[0][1], original)

    def test_empty_input(self):
        self.assertEqual(parse_labelled_dialogue(""), [])
        self.assertEqual(parse_labelled_dialogue("no labels at all"), [])


class TestVerifyVerbatim(unittest.TestCase):
    """This guard is why re-splitting is acceptable at all."""

    def test_pure_relabelling_passes(self):
        original = "hello sir my mixer is broken please help"
        rewritten = "Agent: hello sir Customer: my mixer is broken please help"
        self.assertTrue(verify_verbatim(original, rewritten)["ok"])

    def test_translation_is_rejected(self):
        original = "मेरा mixer खराब है"
        rewritten = "my mixer is broken"
        result = verify_verbatim(original, rewritten)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "words_lost")

    def test_summarisation_is_rejected(self):
        original = " ".join(f"word{i}" for i in range(100))
        rewritten = "word1 word2 word3"
        self.assertFalse(verify_verbatim(original, rewritten)["ok"])

    def test_invented_content_is_rejected(self):
        original = "short call"
        rewritten = "short call " + " ".join(f"invented{i}" for i in range(50))
        result = verify_verbatim(original, rewritten)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "words_invented")

    def test_minor_word_loss_is_tolerated(self):
        # Dropping the odd filler should not throw away a good split.
        words = [f"word{i}" for i in range(100)]
        rewritten = " ".join(words[:95])
        result = verify_verbatim(" ".join(words), rewritten)
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["retention"], MIN_WORD_RETENTION)

    def test_punctuation_and_case_ignored(self):
        self.assertTrue(verify_verbatim("Hello, sir!", "Agent: hello sir")["ok"])

    def test_empty_inputs(self):
        self.assertFalse(verify_verbatim("", "anything")["ok"])
        self.assertFalse(verify_verbatim("something", "")["ok"])


class TestAssignSpeakersToSegments(unittest.TestCase):
    """Turns are re-split, but timestamps live on the original segments."""

    def test_maps_speakers_onto_segments(self):
        segments = [
            seg(0, 0.0, 2.0, "hello sir how can i help"),
            seg(1, 2.0, 5.0, "my mixer is broken"),
        ]
        turns = [("agent", "hello sir how can i help"), ("customer", "my mixer is broken")]
        assign_speakers_to_segments(segments, turns)
        self.assertEqual(segments[0].speaker, "agent")
        self.assertEqual(segments[1].speaker, "customer")

    def test_segment_spanning_a_turn_takes_the_majority_speaker(self):
        # The case per-segment labelling could never get right.
        segments = [seg(0, 0.0, 4.0, "thank you for calling my mixer is broken please")]
        turns = [
            ("agent", "thank you for calling"),
            ("customer", "my mixer is broken please"),
        ]
        assign_speakers_to_segments(segments, turns)
        self.assertEqual(segments[0].speaker, "customer")

    def test_unmatched_segment_inherits_previous_speaker(self):
        segments = [
            seg(0, 0.0, 2.0, "hello sir"),
            seg(1, 2.0, 3.0, "zzz qqq"),
        ]
        assign_speakers_to_segments(segments, [("agent", "hello sir")])
        self.assertEqual(segments[1].speaker, "agent")

    def test_no_turns_leaves_segments_untouched(self):
        segments = [seg(0, 0.0, 1.0, "hi")]
        self.assertEqual(assign_speakers_to_segments(segments, []), 0)


class TestRenderTurns(unittest.TestCase):

    def test_merges_consecutive_same_speaker(self):
        out = render_turns([("agent", "one"), ("agent", "two"), ("customer", "three")])
        self.assertEqual(out, "Agent: one two\nCustomer: three")


class TestDiarizeTranscript(unittest.TestCase):

    def setUp(self):
        self.segments = [
            seg(0, 0.0, 2.0, "hello sir how can i help you"),
            seg(1, 2.0, 5.0, "my mixer is broken and smoking"),
        ]
        self.raw = "hello sir how can i help you my mixer is broken and smoking"

    def test_happy_path(self):
        client = fake_client(
            "Agent: hello sir how can i help you\n"
            "Customer: my mixer is broken and smoking"
        )
        out = asyncio.run(diarize_transcript(client, "m", self.segments, self.raw))
        self.assertEqual(out["method"], "llm_turns")
        self.assertIsNone(out["warning"])
        self.assertIn("Agent:", out["dialogue"])
        self.assertIn("Customer:", out["dialogue"])
        self.assertEqual(self.segments[0].speaker, "agent")

    def test_single_speaker_output_is_rejected(self):
        # The exact failure seen in production: everything under one speaker.
        client = fake_client(f"Agent: {self.raw}")
        out = asyncio.run(diarize_transcript(client, "m", self.segments, self.raw))
        self.assertEqual(out["method"], "unlabelled")
        self.assertEqual(out["warning"], "single_speaker")
        self.assertEqual(out["dialogue"], self.raw)

    def test_translated_output_is_rejected(self):
        client = fake_client("Agent: नमस्ते सर\nCustomer: मेरा मिक्सर खराब है")
        out = asyncio.run(diarize_transcript(client, "m", self.segments, self.raw))
        self.assertEqual(out["method"], "unlabelled")
        self.assertEqual(out["warning"], "words_lost")

    def test_summarised_output_is_rejected(self):
        client = fake_client("Agent: hello\nCustomer: broken")
        out = asyncio.run(diarize_transcript(client, "m", self.segments, self.raw))
        self.assertEqual(out["method"], "unlabelled")

    def test_provider_error_falls_back_to_plain_transcript(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
        out = asyncio.run(diarize_transcript(client, "m", self.segments, self.raw))
        self.assertEqual(out["method"], "unlabelled")
        self.assertEqual(out["warning"], "llm_error")
        self.assertEqual(out["dialogue"], self.raw)

    def test_rejection_reports_usage_for_cost_logging(self):
        client = fake_client(f"Agent: {self.raw}", usage_tokens=250)
        out = asyncio.run(diarize_transcript(client, "m", self.segments, self.raw))
        self.assertEqual(out["token_usage"]["prompt_tokens"], 250)

    def test_empty_transcript(self):
        out = asyncio.run(diarize_transcript(fake_client(""), "m", [], ""))
        self.assertEqual(out["warning"], "empty")


if __name__ == "__main__":
    unittest.main()


class TestSelfConsistencyMerge(unittest.TestCase):
    """Median-of-N is what makes a re-run reproduce the previous score.
    Without it, re-scoring one unchanged transcript moved the overall result
    by up to 15.7 points."""

    def _make_outcome(self, scores, overall=0.0):
        from app.services.prompt_builder_service import EvaluationOutcome
        return EvaluationOutcome(
            overall_score=overall,
            parameter_results=[
                {"parameter_id": None, "name_snapshot": name, "ai_instructions_snapshot": "x",
                 "score": float(v), "max_score": 10, "reason": f"reason for {v}",
                 "evidence": f"evidence {v}", "suggestion": "", "confidence": 1.0}
                for name, v in scores.items()
            ],
            section_results=[{"section_id": None, "name_snapshot": "S", "extracted_content": "c"}],
            raw_llm_response={}, model_used="m",
            token_usage={"prompt_tokens": 100, "completion_tokens": 50, "latency_ms": 10},
        )

    def _template(self, names):
        import uuid as _uuid
        from unittest.mock import MagicMock
        params = []
        for n in names:
            p = MagicMock()
            p.id = _uuid.uuid4(); p.name = n; p.weight = 1.0
            p.min_score = 0; p.max_score = 10
            params.append(p)
        tpl = MagicMock(); tpl.parameters = params
        return tpl

    def _merge(self, list_of_scores):
        from app.services.prompt_builder_service import PromptBuilderService
        from unittest.mock import MagicMock
        svc = PromptBuilderService(MagicMock())
        names = list(list_of_scores[0])
        return svc._merge_by_median(
            self._template(names), [self._make_outcome(s) for s in list_of_scores]
        )

    def test_median_discards_a_single_outlier(self):
        # The real failure: a 0 next to passing scores dragged the whole run.
        out = self._merge([{"P": 0}, {"P": 7}, {"P": 8}])
        self.assertEqual(out.parameter_results[0]["score"], 7.0)

    def test_unanimous_scores_are_kept(self):
        out = self._merge([{"P": 8}, {"P": 8}, {"P": 8}])
        self.assertEqual(out.parameter_results[0]["score"], 8.0)
        self.assertEqual(out.parameter_results[0]["confidence"], 1.0)

    def test_disagreement_lowers_confidence(self):
        out = self._merge([{"P": 2}, {"P": 7}, {"P": 9}])
        self.assertLess(out.parameter_results[0]["confidence"], 0.5)

    def test_narrative_matches_the_median_score(self):
        # The reason shown must come from the pass that produced the number.
        out = self._merge([{"P": 3}, {"P": 6}, {"P": 9}])
        result = out.parameter_results[0]
        self.assertEqual(result["score"], 6.0)
        self.assertIn("6", result["reason"])

    def test_tokens_are_summed_across_passes(self):
        out = self._merge([{"P": 5}, {"P": 5}, {"P": 5}])
        self.assertEqual(out.token_usage["prompt_tokens"], 300)
        self.assertEqual(out.token_usage["self_consistency_samples"], 3)

    def test_multiple_parameters_merge_independently(self):
        out = self._merge([{"A": 2, "B": 9}, {"A": 8, "B": 9}, {"A": 7, "B": 9}])
        by_name = {r["name_snapshot"]: r["score"] for r in out.parameter_results}
        self.assertEqual(by_name["A"], 7.0)
        self.assertEqual(by_name["B"], 9.0)
