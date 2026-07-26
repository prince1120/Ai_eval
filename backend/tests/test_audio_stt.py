import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings
from app.core.database import get_db_session
from app.api.deps import get_stt_service, get_llm_client
from app.main import app
from app.models.base import Base
from app.services.llm_client import LLMResult

if not settings.TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL is not set. Point it at a dedicated Postgres test "
        "database (never DATABASE_URL) before running the test suite."
    )

TEST_DB_URL_STT = settings.TEST_DATABASE_URL
test_engine_stt = create_async_engine(TEST_DB_URL_STT)
TestingSessionLocalSTT = async_sessionmaker(
    bind=test_engine_stt, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db_stt():
    async with TestingSessionLocalSTT() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


mock_stt_service = AsyncMock()
mock_llm_stt = AsyncMock()


def override_stt():
    return mock_stt_service


def override_llm():
    return mock_llm_stt


class TestAudioSTTIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db_session] = override_get_db_stt
        app.dependency_overrides[get_stt_service] = override_stt
        app.dependency_overrides[get_llm_client] = override_llm

        async def init_db():
            async with test_engine_stt.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)

        asyncio.run(init_db())
        cls.client = TestClient(app)

        # Register User & Org
        res_reg = cls.client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "STT Corp",
                "email": "admin@sttcorp.com",
                "password": "Password123!",
            },
        )
        cls.token = res_reg.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_audio_file_upload_and_transcription(self):
        # Mock STT transcription response - must match the real dict shape
        # returned by STTService.transcribe_audio()
        mock_stt_service.transcribe_audio.return_value = {
            "raw_text": "Agent: Thank you for calling STT Corp. Customer: I want to update my account address.",
            "diarized_text": "Agent: Thank you for calling STT Corp. Customer: I want to update my account address.",
            "stt_usage": {"duration_seconds": 12.5, "estimated_cost_usd": 0.0001, "is_estimated": True},
            "stt_latency_ms": 250,
            "diarize_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "diarize_latency_ms": 0,
        }

        # Upload dummy audio file bytes
        dummy_audio = b"RIFF....WAVEfmt ....data...."
        files = {"file": ("customer_call_001.wav", dummy_audio, "audio/wav")}

        res = self.client.post(
            "/api/v1/transcripts/upload-audio",
            headers=self.headers,
            files=files,
        )

        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["source_call_id"], "customer_call_001.wav")
        self.assertIn("Customer: I want to update my account address", data["raw_text"])
        self.assertEqual(data["status"], "uploaded")


if __name__ == "__main__":
    unittest.main()
