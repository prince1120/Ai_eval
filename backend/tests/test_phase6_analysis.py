import asyncio
import unittest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings
from app.core.database import get_db_session
from app.api.deps import get_llm_client
from app.main import app
from app.models.base import Base
from app.services.llm_client import LLMResult

if not settings.TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL is not set. Point it at a dedicated Postgres test "
        "database (never DATABASE_URL) before running the test suite."
    )

TEST_DB_URL_6 = settings.TEST_DATABASE_URL
test_engine_6 = create_async_engine(TEST_DB_URL_6)
TestingSessionLocal6 = async_sessionmaker(
    bind=test_engine_6, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db_6():
    async with TestingSessionLocal6() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


mock_llm_client = AsyncMock()


def override_get_llm_client():
    return mock_llm_client


class TestPhase6TranscriptAnalysis(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db_session] = override_get_db_6
        app.dependency_overrides[get_llm_client] = override_get_llm_client

        async def init_db():
            async with test_engine_6.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)

        asyncio.run(init_db())
        cls.client = TestClient(app)

        # 1. Register Org & Admin
        res_reg = cls.client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Analysis Corp",
                "email": "admin@analysiscorp.com",
                "password": "Password123!",
            },
        )
        cls.token = res_reg.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

        # 2. Create and activate active template
        res_tpl = cls.client.post(
            "/api/v1/templates",
            headers=cls.headers,
            json={
                "name": "Active Quality Template",
                "parameters": [
                    {
                        "name": "Clarity",
                        "ai_instructions": "Check clear speaking",
                        "weight": 1.0,
                        "min_score": 0,
                        "max_score": 10,
                    },
                    {
                        "name": "Politeness",
                        "ai_instructions": "Check polite tone",
                        "weight": 1.0,
                        "min_score": 0,
                        "max_score": 10,
                    },
                ],
                "sections": [
                    {
                        "name": "Summary Objections",
                        "ai_instructions": "Extract customer objections",
                    }
                ],
            },
        )
        cls.template_data = res_tpl.json()
        cls.template_id = cls.template_data["id"]

        # Activate template
        cls.client.post(
            f"/api/v1/templates/{cls.template_id}/activate", headers=cls.headers
        )

    def test_transcript_submission_and_analysis_pipeline(self):
        # 1. Submit Transcript
        res_t = self.client.post(
            "/api/v1/transcripts",
            headers=self.headers,
            json={
                "raw_text": "Agent: Hello thank you for calling. Customer: I am unhappy about delay. Agent: I sincerely apologize for the wait.",
                "source_call_id": "CALL-98765",
            },
        )
        self.assertEqual(res_t.status_code, 201)
        transcript_data = res_t.json()
        transcript_id = transcript_data["id"]

        # 2. Setup mock LLM response for parameters and sections
        param_clarity_id = self.template_data["parameters"][0]["id"]
        param_politeness_id = self.template_data["parameters"][1]["id"]
        section_id = self.template_data["sections"][0]["id"]

        mock_llm_client.generate_json.return_value = LLMResult(
            content={
                "parameters": {
                    f"param_{param_clarity_id.replace('-', '')}": {
                        "score": 10.0,
                        "reason": "Agent spoke very clearly",
                        "evidence": "Hello thank you for calling",
                        "suggestion": "Keep up the clear tone",
                    },
                    f"param_{param_politeness_id.replace('-', '')}": {
                        "score": 9.0,
                        "reason": "Agent apologized politely",
                        "evidence": "I sincerely apologize for the wait",
                        "suggestion": "",
                    },
                },
                "sections": {
                    f"section_{section_id.replace('-', '')}": "Customer expressed unhappiness about order delay"
                },
            },
            raw_text="{}",
            model_used="gpt-4o",
            token_usage={"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200},
        )

        # 3. Trigger Analysis - runs the evaluation inline and returns the
        # completed, fully-populated run.
        res_analyze = self.client.post(
            f"/api/v1/transcripts/{transcript_id}/analyze",
            headers=self.headers,
            json={},
        )
        self.assertEqual(res_analyze.status_code, 202)
        run_data = res_analyze.json()

        self.assertEqual(run_data["status"], "done")
        self.assertEqual(run_data["template_version"], 1)
        self.assertAlmostEqual(run_data["overall_score"], 95.0, places=1)
        self.assertEqual(len(run_data["parameter_results"]), 2)
        self.assertEqual(len(run_data["section_results"]), 1)
        self.assertEqual(
            run_data["section_results"][0]["extracted_content"],
            "Customer expressed unhappiness about order delay",
        )


if __name__ == "__main__":
    unittest.main()
