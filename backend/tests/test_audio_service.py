"""Unit tests for audio chunk planning, silence parsing and timeline stitching.

All pure logic - no ffmpeg binary and no database required.
"""
import unittest

from app.services.audio_service import (
    FORCE_SPLIT_SILENCE,
    HARD_SPLIT_OVERLAP_SECONDS,
    MAX_CHUNK_SECONDS,
    ChunkPlan,
    SilenceInterval,
    derive_speech_spans,
    estimate_billable_seconds,
    parse_silence_log,
    plan_chunks,
    stitch_chunk_segments,
)
from app.services.stt_service import TranscriptSegment


def seg(index, start, end, text, speaker=None):
    return TranscriptSegment(
        index=index, start=start, end=end, text=text,
        avg_logprob=-0.2, no_speech_prob=0.0, compression_ratio=1.3,
        speaker=speaker,
    )


class TestParseSilenceLog(unittest.TestCase):

    def test_parses_start_end_pairs(self):
        log = (
            "[silencedetect @ 0x55] silence_start: 5.0\n"
            "[silencedetect @ 0x55] silence_end: 7.5 | silence_duration: 2.5\n"
            "[silencedetect @ 0x55] silence_start: 20.25\n"
            "[silencedetect @ 0x55] silence_end: 23.0 | silence_duration: 2.75\n"
        )
        intervals = parse_silence_log(log, duration=60.0)
        self.assertEqual(len(intervals), 2)
        self.assertAlmostEqual(intervals[0].start, 5.0)
        self.assertAlmostEqual(intervals[0].end, 7.5)
        self.assertAlmostEqual(intervals[1].duration, 2.75)

    def test_unterminated_silence_closed_at_duration(self):
        # A file that fades out ends with silence_start and no silence_end.
        log = "silence_start: 50.0\n"
        intervals = parse_silence_log(log, duration=60.0)
        self.assertEqual(len(intervals), 1)
        self.assertAlmostEqual(intervals[0].end, 60.0)

    def test_end_clamped_to_duration(self):
        log = "silence_start: 10.0\nsilence_end: 999.0\n"
        intervals = parse_silence_log(log, duration=60.0)
        self.assertAlmostEqual(intervals[0].end, 60.0)

    def test_empty_log(self):
        self.assertEqual(parse_silence_log("", duration=60.0), [])

    def test_ignores_unrelated_output(self):
        log = "Input #0, wav\n  Duration: 00:01:00.00\nsilence_start: 1.0\nsilence_end: 2.0\n"
        self.assertEqual(len(parse_silence_log(log, 60.0)), 1)


class TestDeriveSpeechSpans(unittest.TestCase):

    def test_inverts_silences(self):
        silences = [SilenceInterval(10.0, 12.0), SilenceInterval(30.0, 33.0)]
        spans = derive_speech_spans(60.0, silences)
        self.assertEqual(spans, [(0.0, 10.0), (12.0, 30.0), (33.0, 60.0)])

    def test_short_silences_do_not_break_spans(self):
        # 0.2s pauses are speech rhythm, not boundaries.
        silences = [SilenceInterval(10.0, 10.2), SilenceInterval(20.0, 20.2)]
        spans = derive_speech_spans(60.0, silences)
        self.assertEqual(spans, [(0.0, 60.0)])

    def test_leading_and_trailing_silence_excluded(self):
        silences = [SilenceInterval(0.0, 5.0), SilenceInterval(55.0, 60.0)]
        spans = derive_speech_spans(60.0, silences)
        self.assertEqual(spans, [(5.0, 55.0)])

    def test_fully_silent_file(self):
        spans = derive_speech_spans(60.0, [SilenceInterval(0.0, 60.0)])
        self.assertEqual(spans, [])

    def test_no_silence_gives_one_span(self):
        self.assertEqual(derive_speech_spans(60.0, []), [(0.0, 60.0)])

    def test_zero_duration(self):
        self.assertEqual(derive_speech_spans(0.0, []), [])


class TestPlanChunks(unittest.TestCase):

    def test_short_call_is_single_chunk(self):
        chunks = plan_chunks(300.0, [])
        self.assertEqual(len(chunks), 1)
        self.assertAlmostEqual(chunks[0].start, 0.0)
        self.assertAlmostEqual(chunks[0].end, 300.0)
        self.assertFalse(chunks[0].is_hard_split)

    def test_edge_silence_is_kept_by_default(self):
        # Trimming used to drop this, but speech quieter than the -30 dB
        # threshold reads as silence too: on a real 311s call that silently
        # lost 9 seconds. Completeness beats the quota saving.
        silences = [SilenceInterval(0.0, 20.0), SilenceInterval(285.0, 300.0)]
        chunks = plan_chunks(300.0, silences)
        self.assertEqual(len(chunks), 1)
        self.assertAlmostEqual(chunks[0].start, 0.0)
        self.assertAlmostEqual(chunks[0].end, 300.0)

    def test_trimming_still_available_when_explicitly_requested(self):
        silences = [SilenceInterval(0.0, 20.0), SilenceInterval(285.0, 300.0)]
        chunks = plan_chunks(300.0, silences, drop_silence=True)
        self.assertAlmostEqual(chunks[0].start, 20.0)
        self.assertAlmostEqual(chunks[0].end, 285.0)

    def test_long_hold_is_still_transcribed_by_default(self):
        # A 3-minute hold no longer causes the surrounding audio to be split
        # around it and the hold discarded - the whole call is sent.
        silences = [SilenceInterval(120.0, 300.0)]
        chunks = plan_chunks(420.0, silences)
        self.assertEqual(len(chunks), 1)
        self.assertAlmostEqual(sum(c.duration for c in chunks), 420.0)

    def test_long_hold_is_dropped_only_when_trimming_is_requested(self):
        silences = [SilenceInterval(120.0, 300.0)]
        chunks = plan_chunks(420.0, silences, drop_silence=True)
        self.assertEqual(len(chunks), 2)
        self.assertAlmostEqual(sum(c.duration for c in chunks), 240.0)

    def test_splits_long_call_near_target(self):
        # Speech broken by 1s pauses every 60s across a 30-minute call.
        silences = [SilenceInterval(t, t + 1.0) for t in range(60, 1800, 60)]
        chunks = plan_chunks(1800.0, silences)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(chunk.duration, MAX_CHUNK_SECONDS + 1.0)

    def test_chunks_are_ordered_and_reindexed(self):
        silences = [SilenceInterval(t, t + FORCE_SPLIT_SILENCE + 1) for t in (300, 700, 1100)]
        chunks = plan_chunks(1500.0, silences)
        self.assertEqual([c.index for c in chunks], list(range(len(chunks))))
        for earlier, later in zip(chunks, chunks[1:]):
            self.assertLessEqual(earlier.end, later.start)

    def test_long_recording_is_tiled_with_no_gaps(self):
        chunks = plan_chunks(2000.0, [])
        self.assertGreater(len(chunks), 1)
        self.assertAlmostEqual(chunks[0].start, 0.0)
        self.assertAlmostEqual(chunks[-1].end, 2000.0)
        # Every second lands in exactly one chunk: no gaps, no overlaps.
        for earlier, later in zip(chunks, chunks[1:]):
            self.assertAlmostEqual(earlier.end, later.start, places=6)
        self.assertAlmostEqual(sum(c.duration for c in chunks), 2000.0, places=6)

    def test_cuts_land_on_silence_when_one_is_available(self):
        # A pause every 60s: the split should land on one, not mid-word.
        silences = [SilenceInterval(t, t + 1.0) for t in range(60, 2000, 60)]
        chunks = plan_chunks(2000.0, silences)
        for earlier in chunks[:-1]:
            nearest = min(abs(earlier.end - (s.start + s.end) / 2) for s in silences)
            self.assertLess(nearest, 1.0)
        self.assertAlmostEqual(sum(c.duration for c in chunks), 2000.0, places=6)

    def test_tiny_trailing_chunk_folded_into_previous(self):
        # A 4-second scrap after a long silence would cost a whole request
        # (and Groq's 10s minimum) for almost no audio.
        silences = [SilenceInterval(400.0, 410.0)]
        chunks = plan_chunks(414.0, silences)
        self.assertEqual(len(chunks), 1)
        self.assertAlmostEqual(chunks[0].end, 414.0)

    def test_fully_silent_file_falls_back_to_whole_file(self):
        chunks = plan_chunks(120.0, [SilenceInterval(0.0, 120.0)])
        self.assertEqual(len(chunks), 1)
        self.assertAlmostEqual(chunks[0].start, 0.0)
        self.assertAlmostEqual(chunks[0].end, 120.0)

    def test_zero_duration_gives_no_chunks(self):
        self.assertEqual(plan_chunks(0.0, []), [])

    def test_no_silence_data_still_produces_valid_plan(self):
        chunks = plan_chunks(600.0, [])
        self.assertEqual(len(chunks), 1)
        self.assertAlmostEqual(chunks[0].duration, 600.0)


class TestBillableSeconds(unittest.TestCase):

    def test_sums_chunk_durations(self):
        chunks = [ChunkPlan(0, 0.0, 100.0), ChunkPlan(1, 200.0, 300.0)]
        self.assertAlmostEqual(estimate_billable_seconds(chunks), 200.0)

    def test_applies_ten_second_minimum_per_chunk(self):
        # Four 2-second chunks are billed as 10s each, not 2s.
        chunks = [ChunkPlan(i, i * 10.0, i * 10.0 + 2.0) for i in range(4)]
        self.assertAlmostEqual(estimate_billable_seconds(chunks), 40.0)

    def test_default_plan_bills_the_whole_recording(self):
        # The cost of choosing completeness: no saving by default.
        billed = estimate_billable_seconds(
            plan_chunks(420.0, [SilenceInterval(120.0, 300.0)])
        )
        self.assertAlmostEqual(billed, 420.0)

    def test_opt_in_trimming_reduces_billing(self):
        trimmed = estimate_billable_seconds(
            plan_chunks(420.0, [SilenceInterval(120.0, 300.0)], drop_silence=True)
        )
        self.assertAlmostEqual(trimmed, 240.0)


class TestStitchChunkSegments(unittest.TestCase):

    def test_offsets_timestamps_onto_original_timeline(self):
        results = [
            (ChunkPlan(0, 0.0, 100.0), [seg(0, 0.0, 5.0, "first")]),
            (ChunkPlan(1, 300.0, 400.0), [seg(0, 0.0, 4.0, "after hold")]),
        ]
        stitched = stitch_chunk_segments(results)
        self.assertEqual(len(stitched), 2)
        self.assertAlmostEqual(stitched[0].start, 0.0)
        # Second chunk began at 300s in the original call, so its local 0.0
        # must land at 300.0 or every evidence link points at the wrong moment.
        self.assertAlmostEqual(stitched[1].start, 300.0)
        self.assertAlmostEqual(stitched[1].end, 304.0)

    def test_reindexes_contiguously(self):
        results = [
            (ChunkPlan(0, 0.0, 50.0), [seg(0, 0.0, 5.0, "a"), seg(1, 5.0, 10.0, "b")]),
            (ChunkPlan(1, 60.0, 110.0), [seg(0, 0.0, 5.0, "c")]),
        ]
        stitched = stitch_chunk_segments(results)
        self.assertEqual([s.index for s in stitched], [0, 1, 2])
        self.assertEqual([s.text for s in stitched], ["a", "b", "c"])

    def test_hard_split_overlap_is_deduped(self):
        # Chunk 1 starts 3s before chunk 0 ended; the repeated segment must be
        # dropped, keeping the earlier copy that had leading context.
        results = [
            (ChunkPlan(0, 0.0, 100.0, is_hard_split=False),
             [seg(0, 90.0, 100.0, "overlapping words")]),
            (ChunkPlan(1, 97.0, 200.0, is_hard_split=True),
             [seg(0, 0.0, 3.0, "overlapping words"), seg(1, 3.0, 13.0, "new words")]),
        ]
        stitched = stitch_chunk_segments(results)
        self.assertEqual([s.text for s in stitched], ["overlapping words", "new words"])

    def test_silence_aligned_chunks_are_never_deduped(self):
        # Non-hard-split chunks cannot overlap, so nothing should be dropped
        # even if timestamps look close.
        results = [
            (ChunkPlan(0, 0.0, 100.0), [seg(0, 95.0, 100.0, "end of one")]),
            (ChunkPlan(1, 100.0, 200.0), [seg(0, 0.0, 5.0, "start of two")]),
        ]
        stitched = stitch_chunk_segments(results)
        self.assertEqual(len(stitched), 2)

    def test_orders_by_chunk_start_regardless_of_input_order(self):
        # Parallel transcription means chunks can complete out of order.
        results = [
            (ChunkPlan(1, 300.0, 400.0), [seg(0, 0.0, 4.0, "second")]),
            (ChunkPlan(0, 0.0, 100.0), [seg(0, 0.0, 5.0, "first")]),
        ]
        stitched = stitch_chunk_segments(results)
        self.assertEqual([s.text for s in stitched], ["first", "second"])

    def test_preserves_quality_signals_and_speaker(self):
        results = [(ChunkPlan(0, 10.0, 100.0), [seg(0, 0.0, 5.0, "hi", speaker="agent")])]
        stitched = stitch_chunk_segments(results)
        self.assertEqual(stitched[0].speaker, "agent")
        self.assertAlmostEqual(stitched[0].avg_logprob, -0.2)
        self.assertAlmostEqual(stitched[0].compression_ratio, 1.3)

    def test_empty_input(self):
        self.assertEqual(stitch_chunk_segments([]), [])

    def test_chunk_with_no_segments(self):
        results = [
            (ChunkPlan(0, 0.0, 100.0), []),
            (ChunkPlan(1, 100.0, 200.0), [seg(0, 0.0, 5.0, "only text")]),
        ]
        stitched = stitch_chunk_segments(results)
        self.assertEqual(len(stitched), 1)
        self.assertAlmostEqual(stitched[0].start, 100.0)


if __name__ == "__main__":
    unittest.main()


class TestWholeFileByDefault(unittest.TestCase):
    """Splitting is opt-in. Every seam risks losing or duplicating words, and
    the earlier silence-trimming split dropped 9 seconds of a 311s call."""

    def test_chunking_is_disabled_by_default(self):
        from app.core.config import settings
        self.assertFalse(settings.STT_ALLOW_CHUNKING)

    def test_typical_call_is_a_single_chunk(self):
        for minutes in (1, 5, 10, 30, 60):
            chunks = plan_chunks(minutes * 60.0, [], max_seconds=1e9)
            self.assertEqual(len(chunks), 1, f"{minutes}min should be one piece")

    def test_lower_bitrates_extend_single_request_capacity(self):
        from app.services.audio_service import (
            FALLBACK_BITRATES,
            MAX_SINGLE_REQUEST_BYTES,
        )
        # Each fallback must actually buy capacity, in descending order.
        kbps = [int(b.rstrip("k")) for b in FALLBACK_BITRATES]
        self.assertEqual(kbps, sorted(kbps, reverse=True))
        lowest_hours = MAX_SINGLE_REQUEST_BYTES * 8 / (kbps[-1] * 1000) / 3600
        # The lowest fallback should cover a full working day's longest call.
        self.assertGreater(lowest_hours, 4.0)
