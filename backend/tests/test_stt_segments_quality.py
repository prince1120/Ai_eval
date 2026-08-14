"""Unit tests for the STT segment, quality-scoring and diarization helpers.

These are all pure functions, so unlike the rest of the suite they need no
database and no network.
"""
import math
import unittest

from app.services.stt_service import (
    GROQ_MIN_BILLED_SECONDS,
    TranscriptSegment,
    apply_speaker_turns,
    detect_all_transcript_languages,
    fallback_alternating_speakers,
    parse_whisper_segments,
    render_dialogue,
    score_transcript_quality,
    sha256_digest,
    whisper_cost_usd,
)


def make_segment(index, start, end, text, avg_logprob=-0.2, no_speech_prob=0.0,
                 compression_ratio=1.5):
    return TranscriptSegment(
        index=index,
        start=start,
        end=end,
        text=text,
        avg_logprob=avg_logprob,
        no_speech_prob=no_speech_prob,
        compression_ratio=compression_ratio,
    )


class TestParseWhisperSegments(unittest.TestCase):

    def test_parses_dict_response(self):
        response = {
            "segments": [
                {"start": 0.0, "end": 2.5, "text": " Hello there ", "avg_logprob": -0.3,
                 "no_speech_prob": 0.01, "compression_ratio": 1.2},
                {"start": 2.5, "end": 5.0, "text": "Namaste", "avg_logprob": -0.4,
                 "no_speech_prob": 0.02, "compression_ratio": 1.1},
            ]
        }
        segments = parse_whisper_segments(response)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].text, "Hello there")
        self.assertEqual(segments[0].index, 0)
        self.assertEqual(segments[1].index, 1)
        self.assertAlmostEqual(segments[1].avg_logprob, -0.4)

    def test_parses_object_response(self):
        class Seg:
            def __init__(self, **kw):
                self.__dict__.update(kw)

        class Resp:
            segments = [Seg(start=0.0, end=1.0, text="Hi", avg_logprob=-0.1,
                            no_speech_prob=0.0, compression_ratio=1.0)]

        segments = parse_whisper_segments(Resp())
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].text, "Hi")

    def test_blank_segments_are_dropped_and_indices_stay_contiguous(self):
        response = {"segments": [
            {"start": 0.0, "end": 1.0, "text": "one"},
            {"start": 1.0, "end": 2.0, "text": "   "},
            {"start": 2.0, "end": 3.0, "text": "two"},
        ]}
        segments = parse_whisper_segments(response)
        self.assertEqual([s.text for s in segments], ["one", "two"])
        self.assertEqual([s.index for s in segments], [0, 1])

    def test_missing_segments_returns_empty(self):
        self.assertEqual(parse_whisper_segments({}), [])
        self.assertEqual(parse_whisper_segments({"segments": []}), [])


class TestQualityScoring(unittest.TestCase):

    def test_confidence_is_exp_of_avg_logprob(self):
        segments = [make_segment(0, 0.0, 10.0, "clear speech", avg_logprob=-0.3)]
        result = score_transcript_quality(segments)
        self.assertAlmostEqual(result["confidence"], round(math.exp(-0.3), 4), places=3)
        self.assertTrue(result["is_reliable"])
        self.assertEqual(result["flags"], [])

    def test_confidence_is_duration_weighted(self):
        # One long poor segment plus many short good ones: the long one should
        # dominate, which is the whole point of weighting by duration.
        segments = [make_segment(0, 0.0, 30.0, "long poor", avg_logprob=-1.2)]
        segments += [
            make_segment(i, 30.0 + i, 31.0 + i, "ok", avg_logprob=-0.1)
            for i in range(1, 6)
        ]
        result = score_transcript_quality(segments)
        self.assertLess(result["confidence"], 0.55)
        self.assertIn("low_confidence", result["flags"])

    def test_low_confidence_flag_and_unreliable(self):
        segments = [make_segment(0, 0.0, 5.0, "mumbled", avg_logprob=-1.5)]
        result = score_transcript_quality(segments)
        self.assertIn("low_confidence", result["flags"])
        self.assertFalse(result["is_reliable"])

    def test_hallucination_flag_on_high_compression_ratio(self):
        segments = [
            make_segment(0, 0.0, 5.0, "thanks thanks thanks", compression_ratio=3.1),
        ]
        result = score_transcript_quality(segments)
        self.assertIn("possible_hallucination", result["flags"])
        self.assertFalse(result["is_reliable"])
        self.assertEqual(result["repetitive_segment_count"], 1)

    def test_high_silence_flag(self):
        segments = [
            make_segment(0, 0.0, 20.0, "hold music", no_speech_prob=0.95),
            make_segment(1, 20.0, 25.0, "hello", no_speech_prob=0.01),
        ]
        result = score_transcript_quality(segments)
        self.assertIn("high_silence", result["flags"])
        self.assertLess(result["speech_ratio"], 0.5)

    def test_non_speech_segments_excluded_from_confidence(self):
        # Hold music with a terrible logprob must not drag down the score of
        # the actual conversation.
        segments = [
            make_segment(0, 0.0, 10.0, "music", avg_logprob=-3.0, no_speech_prob=0.95),
            make_segment(1, 10.0, 20.0, "clear speech", avg_logprob=-0.2, no_speech_prob=0.0),
        ]
        result = score_transcript_quality(segments)
        self.assertAlmostEqual(result["confidence"], round(math.exp(-0.2), 4), places=3)

    def test_empty_segments(self):
        result = score_transcript_quality([])
        self.assertEqual(result["confidence"], 0.0)
        self.assertIn("no_segments", result["flags"])
        self.assertFalse(result["is_reliable"])

    def test_missing_avg_logprob_defaults_to_confident(self):
        segments = [TranscriptSegment(index=0, start=0.0, end=5.0, text="hi")]
        result = score_transcript_quality(segments)
        self.assertEqual(result["confidence"], 1.0)


class TestApplySpeakerTurns(unittest.TestCase):

    def setUp(self):
        self.segments = [make_segment(i, i * 2.0, i * 2.0 + 2.0, f"seg{i}") for i in range(6)]

    def test_applies_turns_and_fills_gaps(self):
        turns = [
            {"start_segment": 0, "speaker": "agent"},
            {"start_segment": 2, "speaker": "customer"},
            {"start_segment": 5, "speaker": "agent"},
        ]
        applied = apply_speaker_turns(self.segments, turns)
        self.assertEqual(applied, 3)
        self.assertEqual(
            [s.speaker for s in self.segments],
            ["agent", "agent", "customer", "customer", "customer", "agent"],
        )

    def test_first_turn_after_zero_gets_opposite_opener(self):
        turns = [{"start_segment": 2, "speaker": "customer"}]
        apply_speaker_turns(self.segments, turns)
        self.assertEqual(self.segments[0].speaker, "agent")
        self.assertEqual(self.segments[1].speaker, "agent")
        self.assertEqual(self.segments[2].speaker, "customer")

    def test_out_of_order_indices_are_dropped(self):
        turns = [
            {"start_segment": 0, "speaker": "agent"},
            {"start_segment": 3, "speaker": "customer"},
            {"start_segment": 1, "speaker": "agent"},  # regression - must be ignored
        ]
        applied = apply_speaker_turns(self.segments, turns)
        self.assertEqual(applied, 2)
        self.assertEqual(self.segments[1].speaker, "agent")
        self.assertEqual(self.segments[3].speaker, "customer")

    def test_out_of_range_indices_are_dropped(self):
        turns = [
            {"start_segment": 0, "speaker": "agent"},
            {"start_segment": 99, "speaker": "customer"},
            {"start_segment": -1, "speaker": "customer"},
        ]
        applied = apply_speaker_turns(self.segments, turns)
        self.assertEqual(applied, 1)
        self.assertTrue(all(s.speaker == "agent" for s in self.segments))

    def test_invalid_speaker_labels_are_dropped(self):
        turns = [
            {"start_segment": 0, "speaker": "agent"},
            {"start_segment": 2, "speaker": "supervisor"},
            {"start_segment": 4, "speaker": "Customer:"},
        ]
        applied = apply_speaker_turns(self.segments, turns)
        self.assertEqual(applied, 2)
        self.assertEqual(self.segments[2].speaker, "agent")
        self.assertEqual(self.segments[4].speaker, "customer")

    def test_alternate_key_names_accepted(self):
        turns = [{"segment": 0, "speaker": "agent"}, {"index": 3, "speaker": "customer"}]
        self.assertEqual(apply_speaker_turns(self.segments, turns), 2)

    def test_returns_zero_on_unusable_input(self):
        self.assertEqual(apply_speaker_turns(self.segments, []), 0)
        self.assertEqual(apply_speaker_turns(self.segments, ["nonsense"]), 0)
        self.assertEqual(apply_speaker_turns([], [{"start_segment": 0, "speaker": "agent"}]), 0)

    def test_other_speaker_is_valid(self):
        turns = [{"start_segment": 0, "speaker": "other"}]
        self.assertEqual(apply_speaker_turns(self.segments, turns), 1)
        self.assertEqual(self.segments[0].speaker, "other")


class TestFallbackAndRendering(unittest.TestCase):

    def test_fallback_alternates_every_segment(self):
        # The previous pause-gap heuristic could never fire: Whisper emits
        # contiguous segments (one ends exactly where the next starts), so a
        # whole 46-segment call came back labelled as a single speaker.
        segments = [
            make_segment(0, 0.0, 2.0, "hello"),
            make_segment(1, 2.0, 4.0, "still me"),
            make_segment(2, 4.0, 6.0, "my turn"),
        ]
        fallback_alternating_speakers(segments)
        self.assertEqual(
            [s.speaker for s in segments], ["agent", "customer", "agent"]
        )

    def test_fallback_always_yields_two_parties(self):
        segments = [make_segment(i, i * 2.0, i * 2.0 + 2.0, f"s{i}") for i in range(8)]
        fallback_alternating_speakers(segments)
        self.assertEqual(len({s.speaker for s in segments}), 2)

    def test_render_merges_consecutive_same_speaker(self):
        segments = [make_segment(i, i, i + 1, f"s{i}") for i in range(4)]
        for s in segments[:2]:
            s.speaker = "agent"
        for s in segments[2:]:
            s.speaker = "customer"
        self.assertEqual(render_dialogue(segments), "Agent: s0 s1\nCustomer: s2 s3")

    def test_render_preserves_text_verbatim(self):
        # The whole reason diarization moved to index-labelling: the transcript
        # text must survive byte for byte, including Devanagari and Hinglish.
        original = "आपका ऑर्डर ready hai, sir"
        segments = [make_segment(0, 0.0, 3.0, original)]
        segments[0].speaker = "agent"
        self.assertIn(original, render_dialogue(segments))

    def test_unlabelled_segments_fall_back_to_a_named_speaker(self):
        # The report only renders Agent and Customer turns, so an "Other:" line
        # was silently absorbed into the preceding speaker - putting the
        # customer's words in the agent's mouth. "other" now folds into the
        # running speaker explicitly instead.
        segments = [make_segment(0, 0.0, 1.0, "hi")]
        self.assertEqual(render_dialogue(segments), "Agent: hi")

    def test_other_continues_the_current_speaker(self):
        segments = [make_segment(i, i, i + 1, f"s{i}") for i in range(3)]
        segments[0].speaker = "customer"
        segments[1].speaker = "other"
        segments[2].speaker = "customer"
        self.assertEqual(render_dialogue(segments), "Customer: s0 s1 s2")

    def test_render_empty(self):
        self.assertEqual(render_dialogue([]), "")


class TestCostAndHashing(unittest.TestCase):

    def test_large_v3_costs_more_than_turbo(self):
        turbo = whisper_cost_usd("whisper-large-v3-turbo", 3600)
        large = whisper_cost_usd("whisper-large-v3", 3600)
        self.assertAlmostEqual(turbo, 0.040, places=4)
        self.assertAlmostEqual(large, 0.111, places=4)

    def test_ten_second_minimum_billing(self):
        # Groq bills a 10s minimum, so a 2s clip and a 10s clip cost the same.
        self.assertEqual(
            whisper_cost_usd("whisper-large-v3", 2.0),
            whisper_cost_usd("whisper-large-v3", GROQ_MIN_BILLED_SECONDS),
        )

    def test_unknown_model_falls_back_to_large_v3_rate(self):
        self.assertAlmostEqual(whisper_cost_usd("some-future-model", 3600), 0.111, places=4)

    def test_sha256_is_stable_and_content_sensitive(self):
        self.assertEqual(sha256_digest(b"audio"), sha256_digest(b"audio"))
        self.assertNotEqual(sha256_digest(b"audio"), sha256_digest(b"audio2"))
        self.assertEqual(len(sha256_digest(b"x")), 64)


class TestLanguageDetection(unittest.TestCase):

    def test_devanagari_detected(self):
        langs = detect_all_transcript_languages("आपका ऑर्डर तैयार है")
        self.assertIn("Hindi (Devanagari)", langs)

    def test_english_only_not_flagged_as_hinglish(self):
        # The old keyword list fired on stray tokens; plain English must not
        # be mislabelled.
        text = ("Thank you for calling, is this the right number to call you back on? "
                "Please have the product details with you and yes we can help.")
        langs = detect_all_transcript_languages(text, whisper_lang="english")
        self.assertIn("English", langs)
        self.assertNotIn("Hinglish", langs)

    def test_genuine_hinglish_detected(self):
        text = "Aap ka order ready hai sir, mujhe thoda time do, kya main aapko callback karu? Haan theek hai"
        langs = detect_all_transcript_languages(text)
        self.assertIn("Hinglish", langs)

    def test_additional_indic_scripts(self):
        self.assertIn("Kannada", detect_all_transcript_languages("ನಮಸ್ಕಾರ"))
        self.assertIn("Malayalam", detect_all_transcript_languages("നമസ്കാരം"))
        self.assertIn("Punjabi (Gurmukhi)", detect_all_transcript_languages("ਸਤ ਸ੍ਰੀ ਅਕਾਲ"))
        self.assertIn("Odia", detect_all_transcript_languages("ନମସ୍କାର"))

    def test_defaults_to_english_when_nothing_matches(self):
        self.assertEqual(detect_all_transcript_languages("..."), ["English"])

    def test_whisper_hindi_is_kept_when_script_check_misses(self):
        # Regression: "hindi" and "english" used to be discarded outright, so a
        # romanized-Hindi transcript with no Devanagari lost the detection and
        # silently fell through to the English default.
        langs = detect_all_transcript_languages("theek hai", whisper_lang="hindi")
        self.assertIn("Hindi", langs)
        self.assertNotEqual(langs, ["English"])

    def test_whisper_iso_code_is_mapped_to_a_label(self):
        self.assertIn("Tamil", detect_all_transcript_languages("vanakkam", whisper_lang="ta"))

    def test_whisper_language_not_duplicated_when_script_already_matched(self):
        langs = detect_all_transcript_languages("आपका ऑर्डर", whisper_lang="hindi")
        hindi_entries = [lang for lang in langs if "hindi" in lang.lower()]
        self.assertEqual(len(hindi_entries), 1)

    def test_whisper_english_not_duplicated(self):
        text = "Thank you for calling, is this the right number please, yes okay"
        langs = detect_all_transcript_languages(text, whisper_lang="english")
        self.assertEqual(langs.count("English"), 1)


if __name__ == "__main__":
    unittest.main()


class TestPromptEchoDetection(unittest.TestCase):
    """Whisper regurgitating its conditioning prompt looks like a clean,
    confident transcript, so none of the numeric signals catch it. Found in
    end-to-end testing against a tone-only recording."""

    def setUp(self):
        from app.services.stt_service import build_stt_prompt
        self.prompt = build_stt_prompt()

    def test_detects_verbatim_prompt_echo(self):
        from app.services.stt_service import detect_prompt_echo
        # Whisper returns prompt text when fed silence / non-speech tone
        echoed = self.prompt + " " + self.prompt
        self.assertTrue(detect_prompt_echo(echoed, self.prompt))

    def test_real_conversation_is_not_flagged(self):
        from app.services.stt_service import detect_prompt_echo
        real = ("Agent: Thank you for calling, how may I help you today? "
                "Customer: Mera order abhi tak nahi aaya hai, please check karo.")
        self.assertFalse(detect_prompt_echo(real, self.prompt))

    def test_incidental_short_overlap_is_not_flagged(self):
        from app.services.stt_service import detect_prompt_echo
        # Shares a few prompt words but no long run.
        text = "The customer support call was about a Hindi language issue."
        self.assertFalse(detect_prompt_echo(text, self.prompt))

    def test_short_inputs_are_safe(self):
        from app.services.stt_service import detect_prompt_echo
        self.assertFalse(detect_prompt_echo("", self.prompt))
        self.assertFalse(detect_prompt_echo("hello there", self.prompt))
        self.assertFalse(detect_prompt_echo("some text", ""))

    def test_echo_marks_transcript_unreliable(self):
        from app.services.stt_service import score_transcript_quality
        echoed = self.prompt + " " + self.prompt
        segments = [make_segment(0, 0.0, 14.0, echoed, avg_logprob=-0.45,
                                 compression_ratio=1.85)]
        result = score_transcript_quality(segments, prompt=self.prompt)
        self.assertIn("prompt_echo", result["flags"])
        self.assertFalse(result["is_reliable"])

    def test_no_prompt_supplied_skips_the_check(self):
        from app.services.stt_service import score_transcript_quality
        segments = [make_segment(0, 0.0, 10.0, "ordinary speech here")]
        result = score_transcript_quality(segments)
        self.assertNotIn("prompt_echo", result["flags"])

    def test_vocabulary_is_appended_to_the_prompt(self):
        from app.services.stt_service import build_stt_prompt
        prompt = build_stt_prompt("Jio, Airtel, VI")
        self.assertIn("Jio, Airtel, VI", prompt)


class TestPerSegmentSpeakerLabels(unittest.TestCase):
    """Per-segment labelling replaced turn-boundary detection: asked for turn
    boundaries, ministral-3b returned a single turn for a 46-segment two-party
    call and the whole transcript rendered as one speaker."""

    def setUp(self):
        self.segments = [make_segment(i, i * 2.0, i * 2.0 + 2.0, f"s{i}") for i in range(6)]

    def test_applies_letter_codes(self):
        from app.services.stt_service import apply_speaker_labels
        out = apply_speaker_labels(self.segments, {"speakers": ["A", "C", "C", "A", "A", "C"]})
        self.assertEqual(out["applied"], 6)
        self.assertIsNone(out["warning"])
        self.assertEqual(
            [s.speaker for s in self.segments],
            ["agent", "customer", "customer", "agent", "agent", "customer"],
        )

    def test_accepts_full_words_too(self):
        from app.services.stt_service import apply_speaker_labels
        apply_speaker_labels(self.segments, {"speakers": ["agent", "customer"] * 3})
        self.assertEqual(self.segments[1].speaker, "customer")

    def test_single_speaker_is_flagged(self):
        from app.services.stt_service import apply_speaker_labels
        out = apply_speaker_labels(self.segments, {"speakers": ["A"] * 6})
        self.assertEqual(out["warning"], "single_speaker")

    def test_short_list_inherits_previous_speaker(self):
        from app.services.stt_service import apply_speaker_labels
        out = apply_speaker_labels(self.segments, {"speakers": ["A", "C"]})
        self.assertEqual(out["applied"], 2)
        self.assertEqual(out["warning"], "partial_labels")
        # Unlabelled tail inherits rather than becoming "other".
        self.assertTrue(all(s.speaker in ("agent", "customer") for s in self.segments))

    def test_junk_labels_are_ignored(self):
        from app.services.stt_service import apply_speaker_labels
        out = apply_speaker_labels(self.segments, {"speakers": ["A", "X", "C", "?", "A", "C"]})
        self.assertEqual(out["applied"], 4)

    def test_bare_string_of_letters_is_parsed(self):
        from app.services.stt_service import apply_speaker_labels
        out = apply_speaker_labels(self.segments, "ACCACA")
        self.assertEqual(out["applied"], 6)

    def test_unparseable_input_is_flagged(self):
        from app.services.stt_service import apply_speaker_labels
        self.assertEqual(apply_speaker_labels(self.segments, 12345)["warning"], "unparseable")
        self.assertEqual(apply_speaker_labels(self.segments, {"speakers": []})["warning"], "unparseable")

    def test_renders_both_parties(self):
        from app.services.stt_service import apply_speaker_labels
        apply_speaker_labels(self.segments, {"speakers": ["A", "C", "C", "A", "A", "C"]})
        rendered = render_dialogue(self.segments)
        self.assertIn("Agent:", rendered)
        self.assertIn("Customer:", rendered)
