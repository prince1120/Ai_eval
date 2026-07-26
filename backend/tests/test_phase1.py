import unittest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


class TestPhase1Skeleton(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_settings_load(self):
        self.assertTrue(settings.PROJECT_NAME)
        self.assertEqual(settings.API_V1_STR, "/api/v1")

    def test_health_check_endpoint(self):
        # This hits the real configured DATABASE_URL (no override, unlike the
        # other test files) - 200 when reachable, 503 when not, but either
        # way the body's "status"/http code must agree, and "database" must
        # accurately reflect which case occurred.
        response = self.client.get("/health")
        self.assertIn(response.status_code, (200, 503))
        data = response.json()
        if response.status_code == 200:
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["database"], "healthy")
        else:
            self.assertEqual(data["status"], "unhealthy")
            self.assertEqual(data["database"], "unhealthy")
        self.assertEqual(data["project"], settings.PROJECT_NAME)

    def test_api_v1_health_check_endpoint(self):
        response = self.client.get("/api/v1/health")
        self.assertIn(response.status_code, (200, 503))
        data = response.json()
        self.assertIn("database", data)


if __name__ == "__main__":
    unittest.main()
