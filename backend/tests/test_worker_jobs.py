"""Tests for the quota gating and reservation accounting in the worker jobs.

The DB, storage and STT service are all stubbed; what is under test is the
decision logic around quota: defer instead of fail, reserve conservatively,
refund what trimming saved.
"""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from arq import Retry

from app.core.quota import InMemoryQuotaBackend, QuotaGuard, QuotaLimit


class TestQuotaGatingBehaviour(unittest.TestCase):
    """A rate limit on a free tier is a scheduling event, not an error."""

    def test_exhausted_quota_produces_a_bounded_defer(self):
        from app.workers.jobs import transcribe_audio_job

        guard = QuotaGuard(
            "groq-whisper",
            [QuotaLimit("whisper_requests_per_minute", 1, 60)],
            backend=InMemoryQuotaBackend(),
        )
        asyncio.run(guard.consume({"whisper_requests_per_minute": 1}))

        storage = MagicMock()
        storage.download_audio = AsyncMock(return_value=b"\x00" * 8000)

        with patch("app.workers.jobs._whisper_guard", return_value=guard), \
             patch("app.services.storage_service.MinIOStorageService", return_value=storage):
            with self.assertRaises(Retry) as caught:
                asyncio.run(transcribe_audio_job(
                    {"redis": MagicMock()},
                    "11111111-1111-1111-1111-111111111111",
                    "22222222-2222-2222-2222-222222222222",
                    "org/audio.mp3",
                    "audio.mp3",
                ))

        # Deferred, not failed - and never longer than an hour, so a stale
        # window can't park a job indefinitely. arq stores the delay in ms.
        seconds = caught.exception.defer_score / 1000.0
        self.assertGreater(seconds, 0)
        self.assertLessEqual(seconds, 3600.0)

    def test_defer_is_at_least_five_seconds(self):
        # Guards against a hot retry loop when a window is about to roll over.
        limit = QuotaLimit("rpm", 1, 60)
        # 0.1s left in the window.
        self.assertAlmostEqual(limit.seconds_until_reset(59.9), 0.1, places=3)
        defer = max(5.0, min(limit.seconds_until_reset(59.9) + 1.0, 3600.0))
        self.assertEqual(defer, 5.0)


class TestReservationAccounting(unittest.TestCase):
    """Quota is reserved on the raw duration, then the unused part refunded."""

    def setUp(self):
        self.guard = QuotaGuard(
            "groq-whisper",
            [
                QuotaLimit("whisper_requests_per_minute", 100, 60),
                QuotaLimit("whisper_audio_seconds_per_hour", 7200, 3600),
                QuotaLimit("whisper_audio_seconds_per_day", 28800, 86400),
            ],
            backend=InMemoryQuotaBackend(),
        )

    def test_refund_returns_silence_savings_to_the_pool(self):
        estimated, billable = 600.0, 480.0

        asyncio.run(self.guard.consume({
            "whisper_requests_per_minute": 1,
            "whisper_audio_seconds_per_hour": int(estimated),
            "whisper_audio_seconds_per_day": int(estimated),
        }))
        after_reserve = asyncio.run(self.guard.snapshot())
        self.assertEqual(after_reserve["whisper_audio_seconds_per_hour"]["used"], 600)

        refund = int(max(0.0, estimated - billable))
        asyncio.run(self.guard.release({
            "whisper_audio_seconds_per_hour": refund,
            "whisper_audio_seconds_per_day": refund,
        }))

        after_refund = asyncio.run(self.guard.snapshot())
        self.assertEqual(after_refund["whisper_audio_seconds_per_hour"]["used"], 480)
        # The request itself is not refunded - it really was made.
        self.assertEqual(after_refund["whisper_requests_per_minute"]["used"], 1)

    def test_no_refund_when_nothing_was_trimmed(self):
        estimated = billable = 300.0
        asyncio.run(self.guard.consume({
            "whisper_audio_seconds_per_hour": int(estimated),
        }))
        refund = int(max(0.0, estimated - billable))
        self.assertEqual(refund, 0)
        snapshot = asyncio.run(self.guard.snapshot())
        self.assertEqual(snapshot["whisper_audio_seconds_per_hour"]["used"], 300)

    def test_overestimate_never_produces_negative_usage(self):
        # An underestimate (billable > estimated) must not credit quota back.
        estimated, billable = 100.0, 250.0
        asyncio.run(self.guard.consume({"whisper_audio_seconds_per_hour": int(estimated)}))
        refund = int(max(0.0, estimated - billable))
        self.assertEqual(refund, 0)


class TestWorkerConfiguration(unittest.TestCase):

    def test_both_jobs_are_registered(self):
        from app.workers.jobs import WorkerSettings, run_analysis_job, transcribe_audio_job

        self.assertIn(transcribe_audio_job, WorkerSettings.functions)
        self.assertIn(run_analysis_job, WorkerSettings.functions)

    def test_retries_are_enabled(self):
        from app.workers.jobs import WorkerSettings

        self.assertGreater(WorkerSettings.max_tries, 1)

    def test_job_names_match_the_registered_functions(self):
        # A typo here would enqueue jobs no worker ever picks up.
        from app.workers import jobs, queue

        registered = {f.__name__ for f in jobs.WorkerSettings.functions}
        self.assertIn(queue.TRANSCRIBE_JOB, registered)
        self.assertIn(queue.ANALYZE_JOB, registered)


class TestRedisSettings(unittest.TestCase):

    def test_parses_a_plain_redis_url(self):
        from app.workers.queue import redis_settings

        with patch("app.workers.queue.settings") as mock_settings:
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            s = redis_settings()
        self.assertEqual(s.host, "localhost")
        self.assertEqual(s.port, 6379)
        self.assertEqual(s.database, 0)

    def test_parses_credentials_database_and_tls(self):
        from app.workers.queue import redis_settings

        with patch("app.workers.queue.settings") as mock_settings:
            mock_settings.REDIS_URL = "rediss://:secret@cache.example.com:6380/3"
            s = redis_settings()
        self.assertEqual(s.host, "cache.example.com")
        self.assertEqual(s.port, 6380)
        self.assertEqual(s.database, 3)
        self.assertEqual(s.password, "secret")
        self.assertTrue(s.ssl)



class TestCompletedRunCache(unittest.TestCase):
    """The cache was previously an unbounded dict labelled 'LRU'."""

    def setUp(self):
        from app.services.analysis_service import COMPLETED_RUNS_CACHE
        COMPLETED_RUNS_CACHE.clear()

    def test_cache_is_bounded(self):
        from app.services.analysis_service import (
            COMPLETED_RUNS_CACHE,
            COMPLETED_RUNS_CACHE_MAX,
            _cache_completed_run,
        )
        for i in range(COMPLETED_RUNS_CACHE_MAX + 50):
            _cache_completed_run(f"org:{i}", MagicMock())
        self.assertEqual(len(COMPLETED_RUNS_CACHE), COMPLETED_RUNS_CACHE_MAX)

    def test_oldest_entries_are_evicted_first(self):
        from app.services.analysis_service import (
            COMPLETED_RUNS_CACHE,
            COMPLETED_RUNS_CACHE_MAX,
            _cache_completed_run,
        )
        for i in range(COMPLETED_RUNS_CACHE_MAX + 1):
            _cache_completed_run(f"org:{i}", MagicMock())
        self.assertNotIn("org:0", COMPLETED_RUNS_CACHE)
        self.assertIn(f"org:{COMPLETED_RUNS_CACHE_MAX}", COMPLETED_RUNS_CACHE)

    def test_invalidate_removes_an_entry(self):
        import uuid as _uuid
        from app.services.analysis_service import (
            COMPLETED_RUNS_CACHE,
            _cache_completed_run,
            invalidate_cached_run,
        )
        org, run = _uuid.uuid4(), _uuid.uuid4()
        _cache_completed_run(f"{org}:{run}", MagicMock())
        invalidate_cached_run(org, run)
        self.assertNotIn(f"{org}:{run}", COMPLETED_RUNS_CACHE)

if __name__ == "__main__":
    unittest.main()
