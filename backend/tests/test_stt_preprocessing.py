"""Tests for the STT preprocessing path: ffmpeg fallback, chunk fan-out,
stitching into the returned payload, and billable-second accounting.

The Whisper API and ffmpeg are both stubbed, so these run anywhere.
"""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.services.audio_service import AudioInfo, AudioProcessingError, ChunkPlan
from app.services.stt_service import STTService, TranscriptSegment


def whisper_response(text, segments, language="hindi", duration=None):
    """Mimic a Groq verbose_json response object."""
    return type("Resp", (), {
        "text": text,
        "language": language,
        "duration": duration,
        "segments": segments,
    })()


def wseg(start, end, text, avg_logprob=-0.25):
    return {
        "start": start, "end": end, "text": text,
        "avg_logprob": avg_logprob, "no_speech_prob": 0.01, "compression_ratio": 1.3,
    }


class TestFfmpegFallback(unittest.TestCase):
    """Preprocessing is an optimisation; its absence must never fail an upload."""

    def _service(self):
        service = STTService(api_key="k", base_url="http://x", stt_model_name="whisper-large-v3")
        service.diarize_segments = AsyncMock(return_value={
            "turn_count": 1, "token_usage": {}, "latency_ms": 5,
            "model_name": "m", "method": "llm_turns",
        })
        return service

    @patch("app.services.audio_service.ffmpeg_available", return_value=False)
    def test_missing_ffmpeg_falls_back_to_whole_file(self, _mock_available):
        service = self._service()
        service._transcribe_with_retry = AsyncMock(return_value=whisper_response(
            "hello world", [wseg(0.0, 2.0, "hello world")], duration=2.0,
        ))

        result = asyncio.run(service.transcribe_audio(b"rawaudio", "call.mp3"))

        self.assertEqual(result["raw_text"], "hello world")
        self.assertEqual(result["stt_usage"]["chunk_count"], 1)
        # The original bytes went to the provider, untouched.
        self.assertEqual(result["stt_usage"]["processed_bytes"], len(b"rawaudio"))
        service._transcribe_with_retry.assert_awaited_once()

    @patch("app.services.audio_service.prepare_audio",
           side_effect=AudioProcessingError("corrupt file"))
    @patch("app.services.audio_service.ffmpeg_available", return_value=True)
    def test_preprocessing_failure_falls_back(self, _avail, _prepare):
        service = self._service()
        service._transcribe_with_retry = AsyncMock(return_value=whisper_response(
            "fallback text", [wseg(0.0, 1.0, "fallback text")], duration=1.0,
        ))

        result = asyncio.run(service.transcribe_audio(b"rawaudio", "call.mp3"))
        self.assertEqual(result["raw_text"], "fallback text")

    def test_preprocess_disabled_skips_ffmpeg_entirely(self):
        service = self._service()
        service._transcribe_with_retry = AsyncMock(return_value=whisper_response(
            "direct", [wseg(0.0, 1.0, "direct")], duration=1.0,
        ))
        result = asyncio.run(
            service.transcribe_audio(b"raw", "call.mp3", preprocess=False)
        )
        self.assertEqual(result["raw_text"], "direct")


class TestChunkedTranscription(unittest.TestCase):

    def _service(self):
        service = STTService(api_key="k", base_url="http://x", stt_model_name="whisper-large-v3")
        service.diarize_segments = AsyncMock(return_value={
            "turn_count": 2, "token_usage": {"total_tokens": 120}, "latency_ms": 40,
            "model_name": "m", "method": "llm_turns",
        })
        return service

    def _run_chunked(self, service, chunks, responses, duration=420.0):
        """Drive transcribe_audio with ffmpeg stubbed out."""
        info = AudioInfo(
            duration_seconds=duration, sample_rate=16000, channels=1,
            codec="opus", size_bytes=1000,
        )
        service._transcribe_with_retry = AsyncMock(side_effect=responses)

        with patch("app.services.audio_service.ffmpeg_available", return_value=True), \
             patch("app.services.audio_service.prepare_audio",
                   new=AsyncMock(return_value=(b"opusbytes", info, chunks))), \
             patch("app.services.audio_service.extract_chunk",
                   new=AsyncMock(return_value=b"chunkbytes")):
            return asyncio.run(service.transcribe_audio(b"rawaudio", "call.mp3"))

    def test_chunks_are_stitched_onto_the_original_timeline(self):
        # A call with a 3-minute hold: chunk 2 starts at 300s in real time, so
        # its local timestamps must be shifted or evidence links break.
        chunks = [ChunkPlan(0, 0.0, 120.0), ChunkPlan(1, 300.0, 420.0)]
        responses = [
            whisper_response("before hold", [wseg(0.0, 5.0, "before hold")]),
            whisper_response("after hold", [wseg(0.0, 4.0, "after hold")]),
        ]
        service = self._service()
        result = self._run_chunked(service, chunks, responses)

        segments = result["segments"]
        self.assertEqual(len(segments), 2)
        self.assertAlmostEqual(segments[0]["start"], 0.0)
        self.assertAlmostEqual(segments[1]["start"], 300.0)
        self.assertAlmostEqual(segments[1]["end"], 304.0)
        self.assertEqual(result["raw_text"], "before hold after hold")
        self.assertEqual(result["stt_usage"]["chunk_count"], 2)

    def test_one_stt_request_per_chunk(self):
        chunks = [ChunkPlan(i, i * 100.0, i * 100.0 + 90.0) for i in range(4)]
        responses = [
            whisper_response(f"part{i}", [wseg(0.0, 3.0, f"part{i}")]) for i in range(4)
        ]
        service = self._service()
        self._run_chunked(service, chunks, responses)
        self.assertEqual(service._transcribe_with_retry.await_count, 4)

    def test_diarization_runs_once_over_all_chunks(self):
        # Diarizing per chunk would let "agent" in chunk 1 become "customer"
        # in chunk 2, so it must happen once over the stitched timeline.
        chunks = [ChunkPlan(0, 0.0, 120.0), ChunkPlan(1, 300.0, 420.0)]
        responses = [
            whisper_response("a", [wseg(0.0, 5.0, "a")]),
            whisper_response("b", [wseg(0.0, 4.0, "b")]),
        ]
        service = self._service()
        self._run_chunked(service, chunks, responses)
        service.diarize_segments.assert_awaited_once()
        passed_segments = service.diarize_segments.await_args.args[0]
        self.assertEqual(len(passed_segments), 2)

    def test_billable_seconds_exclude_skipped_silence(self):
        # 420s recording, 180s of it hold music that never gets sent.
        chunks = [ChunkPlan(0, 0.0, 120.0), ChunkPlan(1, 300.0, 420.0)]
        responses = [
            whisper_response("a", [wseg(0.0, 5.0, "a")]),
            whisper_response("b", [wseg(0.0, 4.0, "b")]),
        ]
        service = self._service()
        result = self._run_chunked(service, chunks, responses, duration=420.0)

        usage = result["stt_usage"]
        self.assertAlmostEqual(usage["duration_seconds"], 420.0)
        self.assertAlmostEqual(usage["billable_seconds"], 240.0)
        self.assertAlmostEqual(usage["seconds_saved"], 180.0)
        # Cost must follow billable seconds, not wall-clock duration.
        expected = 240.0 * (0.111 / 3600)
        self.assertAlmostEqual(usage["estimated_cost_usd"], round(expected, 6), places=6)

    def test_dominant_language_wins_across_chunks(self):
        chunks = [ChunkPlan(i, i * 100.0, i * 100.0 + 90.0) for i in range(3)]
        responses = [
            whisper_response("a", [wseg(0.0, 3.0, "a")], language="hindi"),
            whisper_response("b", [wseg(0.0, 3.0, "b")], language="hindi"),
            whisper_response("c", [wseg(0.0, 3.0, "c")], language="english"),
        ]
        service = self._service()
        result = self._run_chunked(service, chunks, responses)
        self.assertIn("Hindi", result["detected_language"])

    def test_quality_scored_over_stitched_segments(self):
        chunks = [ChunkPlan(0, 0.0, 120.0), ChunkPlan(1, 300.0, 420.0)]
        responses = [
            whisper_response("clear", [wseg(0.0, 60.0, "clear", avg_logprob=-0.1)]),
            whisper_response("mud", [wseg(0.0, 60.0, "mud", avg_logprob=-1.8)]),
        ]
        service = self._service()
        result = self._run_chunked(service, chunks, responses)
        quality = result["quality"]
        self.assertEqual(quality["segment_count"], 2)
        # Equal-duration segments, one good one terrible -> lands in between.
        self.assertLess(quality["confidence"], 0.9)
        self.assertGreater(quality["confidence"], 0.0)

    def test_audio_hash_is_of_the_original_upload(self):
        # Dedup must key on what the user sent, not the transcoded derivative.
        from app.services.stt_service import sha256_digest
        chunks = [ChunkPlan(0, 0.0, 120.0)]
        responses = [whisper_response("a", [wseg(0.0, 5.0, "a")])]
        service = self._service()
        result = self._run_chunked(service, chunks, responses)
        self.assertEqual(result["audio_sha256"], sha256_digest(b"rawaudio"))


if __name__ == "__main__":
    unittest.main()
