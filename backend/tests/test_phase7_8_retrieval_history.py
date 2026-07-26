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

TEST_DB_URL_7 = settings.TEST_DATABASE_URL
test_engine_7 = create_async_engine(TEST_DB_URL_7)
TestingSessionLocal7 = async_sessionmaker(
    bind=test_engine_7, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db_7():
    async with TestingSessionLocal7() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


mock_llm_7 = AsyncMock()


def override_get_llm_7():
    return mock_llm_7


class TestPhase7And8RetrievalHistory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db_session] = override_get_db_7
        app.dependency_overrides[get_llm_client] = override_get_llm_7

        async def init_db():
            async with test_engine_7.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)

        asyncio.run(init_db())
        cls.client = TestClient(app)

        # 1. Register Org & Admin
        res_reg = cls.client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "History Corp",
                "email": "admin@historycorp.com",
                "password": "Password123!",
            },
        )
        cls.token = res_reg.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

        # 2. Create Template v1 and activate
        res_tpl = cls.client.post(
            "/api/v1/templates",
            headers=cls.headers,
            json={
                "name": "Evolving Template",
                "parameters": [
                    {
                        "name": "P1",
                        "ai_instructions": "P1 instructions",
                        "weight": 1.0,
                    }
                ],
                "sections": [],
            },
        )
        cls.tpl_v1_id = res_tpl.json()["id"]
        cls.param_v1_id = res_tpl.json()["parameters"][0]["id"]
        cls.client.post(
            f"/api/v1/templates/{cls.tpl_v1_id}/activate", headers=cls.headers
        )

    def test_multi_version_history_and_retrieval(self):
        # 1. Submit Transcript
        res_t = self.client.post(
            "/api/v1/transcripts",
            headers=self.headers,
            json={"raw_text": "Sample conversation transcript text for testing analysis runs history."},
        )
        transcript_id = res_t.json()["id"]

        # Setup mock LLM for run 1 (against Template v1)
        mock_llm_7.generate_json.return_value = LLMResult(
            content={
                "parameters": {
                    f"param_{self.param_v1_id.replace('-', '')}": {
                        "score": 10.0,
                        "reason": "V1 test reason",
                    }
                },
                "sections": {},
            },
            raw_text="{}",
            model_used="gpt-4o",
            token_usage={"total_tokens": 100},
        )

        # Trigger Run 1 (against v1)
        res_run1 = self.client.post(
            f"/api/v1/transcripts/{transcript_id}/analyze",
            headers=self.headers,
            json={},
        )
        self.assertEqual(res_run1.status_code, 202)
        run1_id = res_run1.json()["id"]

        # 2. Update active template -> creates Template v2
        res_upd = self.client.put(
            f"/api/v1/templates/{self.tpl_v1_id}",
            headers=self.headers,
            json={"name": "Evolving Template (v2)"},
        )
        tpl_v2 = res_upd.json()
        self.assertEqual(tpl_v2["version"], 2)
        param_v2_id = tpl_v2["parameters"][0]["id"]

        # Setup mock LLM for run 2 (against Template v2)
        mock_llm_7.generate_json.return_value = LLMResult(
            content={
                "parameters": {
                    f"param_{param_v2_id.replace('-', '')}": {
                        "score": 8.0,
                        "reason": "V2 test reason",
                    }
                },
                "sections": {},
            },
            raw_text="{}",
            model_used="gpt-4o",
            token_usage={"total_tokens": 110},
        )

        # Trigger Run 2 (against v2)
        res_run2 = self.client.post(
            f"/api/v1/transcripts/{transcript_id}/analyze",
            headers=self.headers,
            json={},
        )
        self.assertEqual(res_run2.status_code, 202)
        run2_id = res_run2.json()["id"]

        # 3. Verify GET /analysis-runs/{run1_id}
        res_get_run1 = self.client.get(
            f"/api/v1/analysis-runs/{run1_id}", headers=self.headers
        )
        self.assertEqual(res_get_run1.status_code, 200)
        self.assertEqual(res_get_run1.json()["template_version"], 1)

        # 4. Verify GET /transcripts/{id}/analysis-runs returns both runs
        res_t_runs = self.client.get(
            f"/api/v1/transcripts/{transcript_id}/analysis-runs",
            headers=self.headers,
        )
        self.assertEqual(res_t_runs.status_code, 200)
        t_runs = res_t_runs.json()
        self.assertEqual(len(t_runs), 2)
        versions_recorded = [r["template_version"] for r in t_runs]
        self.assertIn(1, versions_recorded)
        self.assertIn(2, versions_recorded)

        # 5. Verify GET /analysis-runs?status=done
        res_filtered = self.client.get(
            "/api/v1/analysis-runs?status=done", headers=self.headers
        )
        self.assertEqual(res_filtered.status_code, 200)
        self.assertGreaterEqual(len(res_filtered.json()), 2)


if __name__ == "__main__":
    unittest.main()
