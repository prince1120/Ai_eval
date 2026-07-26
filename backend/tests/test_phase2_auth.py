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

TEST_DB_URL_2 = settings.TEST_DATABASE_URL
test_engine_2 = create_async_engine(TEST_DB_URL_2)
TestingSessionLocal2 = async_sessionmaker(
    bind=test_engine_2, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db_2():
    async with TestingSessionLocal2() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class TestPhase2AuthAndMultiTenancy(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db_session] = override_get_db_2

        async def init_db():
            async with test_engine_2.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)

        asyncio.run(init_db())
        cls.client = TestClient(app)

    def test_auth_and_multi_tenant_isolation(self):
        # 1. Register Organization A
        res_a = self.client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Org Alpha",
                "email": "admin@alpha.com",
                "password": "Password123!",
            },
        )
        self.assertEqual(res_a.status_code, 201)
        data_a = res_a.json()
        token_a = data_a["access_token"]
        org_a_id = data_a["organization"]["id"]

        # 2. Register Organization B
        res_b = self.client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Org Beta",
                "email": "admin@beta.com",
                "password": "Password123!",
            },
        )
        self.assertEqual(res_b.status_code, 201)
        data_b = res_b.json()
        token_b = data_b["access_token"]
        org_b_id = data_b["organization"]["id"]

        self.assertNotEqual(org_a_id, org_b_id)

        # 3. Add extra member user to Org A using Org A admin token
        headers_a = {"Authorization": f"Bearer {token_a}"}
        res_add_a = self.client.post(
            "/api/v1/users/invite",
            headers=headers_a,
            json={
                "email": "member@alpha.com",
                "password": "Password123!",
                "role": "member",
            },
        )
        self.assertEqual(res_add_a.status_code, 201)

        # 4. List users for Org A (should have 2 users: admin@alpha.com, member@alpha.com)
        res_users_a = self.client.get("/api/v1/users", headers=headers_a)
        self.assertEqual(res_users_a.status_code, 200)
        users_a = res_users_a.json()
        self.assertEqual(len(users_a), 2)
        emails_a = [u["email"] for u in users_a]
        self.assertIn("admin@alpha.com", emails_a)
        self.assertIn("member@alpha.com", emails_a)

        # 5. List users for Org B (should only have 1 user: admin@beta.com)
        headers_b = {"Authorization": f"Bearer {token_b}"}
        res_users_b = self.client.get("/api/v1/users", headers=headers_b)
        self.assertEqual(res_users_b.status_code, 200)
        users_b = res_users_b.json()
        self.assertEqual(len(users_b), 1)
        self.assertEqual(users_b[0]["email"], "admin@beta.com")

        # 6. CRITICAL MULTI-TENANT ISOLATION PROOF:
        member_a_id = res_add_a.json()["id"]
        res_tamper = self.client.patch(
            f"/api/v1/users/{member_a_id}/role",
            headers=headers_b,
            json={"role": "admin"},
        )
        self.assertEqual(res_tamper.status_code, 404)
        self.assertEqual(res_tamper.json()["detail"], "User not found in organization")


if __name__ == "__main__":
    unittest.main()
