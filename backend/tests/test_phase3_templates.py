import asyncio
import unittest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings
from app.core.database import get_db_session
from app.main import app
from app.models.base import Base

if not settings.TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL is not set. Point it at a dedicated Postgres test "
        "database (never DATABASE_URL) before running the test suite."
    )

TEST_DB_URL_3 = settings.TEST_DATABASE_URL
test_engine_3 = create_async_engine(TEST_DB_URL_3)
TestingSessionLocal3 = async_sessionmaker(
    bind=test_engine_3, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db_3():
    async with TestingSessionLocal3() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class TestPhase3TemplateConfiguration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db_session] = override_get_db_3

        async def init_db():
            async with test_engine_3.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)

        asyncio.run(init_db())
        cls.client = TestClient(app)

        # Register test organization & admin user
        res = cls.client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Template Corp",
                "email": "admin@templatecorp.com",
                "password": "Password123!",
            },
        )
        data = res.json()
        cls.token = data["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_01_create_tiny_and_large_templates(self):
        # 1. Tiny Template (3 params)
        tiny_payload = {
            "name": "Standard Support Eval",
            "description": "3 parameter eval template",
            "parameters": [
                {
                    "name": "Greeting",
                    "ai_instructions": "Check if agent greeted politely",
                    "weight": 1.0,
                    "min_score": 0,
                    "max_score": 10,
                    "display_order": 1,
                },
                {
                    "name": "Empathy",
                    "ai_instructions": "Evaluate empathetic listening",
                    "weight": 2.0,
                    "min_score": 0,
                    "max_score": 10,
                    "display_order": 2,
                },
                {
                    "name": "Closing",
                    "ai_instructions": "Check polite call closure",
                    "weight": 1.0,
                    "min_score": 0,
                    "max_score": 10,
                    "display_order": 3,
                },
            ],
            "sections": [
                {
                    "name": "Customer Objections",
                    "ai_instructions": "Extract customer complaints or objections",
                    "display_order": 1,
                }
            ],
        }

        res_tiny = self.client.post(
            "/api/v1/templates", headers=self.headers, json=tiny_payload
        )
        self.assertEqual(res_tiny.status_code, 201)
        tiny_data = res_tiny.json()
        self.assertEqual(tiny_data["name"], "Standard Support Eval")
        self.assertEqual(len(tiny_data["parameters"]), 3)
        self.assertEqual(len(tiny_data["sections"]), 1)
        self.assertEqual(tiny_data["version"], 1)
        self.assertFalse(tiny_data["is_active"])

        # 2. Large Template (55 parameters!)
        large_params = [
            {
                "name": f"Parameter_{i}",
                "ai_instructions": f"Instructions for scoring parameter {i}",
                "weight": 1.0 if i % 2 == 0 else 1.5,
                "display_order": i,
            }
            for i in range(1, 56)
        ]
        large_payload = {
            "name": "Comprehensive Enterprise Call Eval",
            "description": "55 parameter enterprise scorecard",
            "parameters": large_params,
            "sections": [
                {
                    "name": "Competitor Mentions",
                    "ai_instructions": "Extract any competitor company names",
                    "display_order": 1,
                },
                {
                    "name": "Compliance Red Flags",
                    "ai_instructions": "Extract compliance violation quotes",
                    "display_order": 2,
                },
            ],
        }

        res_large = self.client.post(
            "/api/v1/templates", headers=self.headers, json=large_payload
        )
        self.assertEqual(res_large.status_code, 201)
        large_data = res_large.json()
        self.assertEqual(len(large_data["parameters"]), 55)
        self.assertEqual(len(large_data["sections"]), 2)

    def test_02_template_activation_and_versioning(self):
        # List templates to get ID of tiny template
        res_list = self.client.get("/api/v1/templates", headers=self.headers)
        self.assertEqual(res_list.status_code, 200)
        templates = res_list.json()
        tiny_tpl = next(t for t in templates if t["name"] == "Standard Support Eval")
        tiny_id = tiny_tpl["id"]

        # Activate template
        res_act = self.client.post(
            f"/api/v1/templates/{tiny_id}/activate", headers=self.headers
        )
        self.assertEqual(res_act.status_code, 200)
        act_data = res_act.json()
        self.assertTrue(act_data["is_active"])
        self.assertEqual(act_data["version"], 1)

        # Update active template -> should trigger version bump (create v2)
        res_upd = self.client.put(
            f"/api/v1/templates/{tiny_id}",
            headers=self.headers,
            json={"name": "Standard Support Eval (Updated)"},
        )
        self.assertEqual(res_upd.status_code, 200)
        upd_data = res_upd.json()
        self.assertEqual(upd_data["version"], 2)
        self.assertTrue(upd_data["is_active"])
        self.assertNotEqual(upd_data["id"], tiny_id)  # New template ID created for v2

        # Check v1 original template is now deactivated
        res_v1 = self.client.get(
            f"/api/v1/templates/{tiny_id}", headers=self.headers
        )
        self.assertEqual(res_v1.status_code, 200)
        self.assertFalse(res_v1.json()["is_active"])
        self.assertEqual(res_v1.json()["version"], 1)

    def test_03_parameter_reordering(self):
        # Get active template
        res_list = self.client.get("/api/v1/templates", headers=self.headers)
        active_tpl = next(t for t in res_list.json() if t["is_active"])
        tpl_id = active_tpl["id"]
        params = active_tpl["parameters"]

        # Reverse display orders
        reorder_payload = {
            "orders": [
                {"id": p["id"], "display_order": len(params) - idx}
                for idx, p in enumerate(params)
            ]
        }
        res_reorder = self.client.put(
            f"/api/v1/templates/{tpl_id}/parameters/reorder",
            headers=self.headers,
            json=reorder_payload,
        )
        self.assertEqual(res_reorder.status_code, 200)


if __name__ == "__main__":
    unittest.main()
