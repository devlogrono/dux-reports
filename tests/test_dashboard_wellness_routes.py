import os
import sqlite3
import tempfile
import unittest

from dux import create_app
from dux.models import Base


class DashboardWellnessRouteTest(unittest.TestCase):
    def setUp(self):
        Base.metadata.clear()

        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

        conn = sqlite3.connect(self.tmp.name)
        conn.execute(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                password_hash TEXT,
                role_id TEXT,
                state_id INTEGER,
                name TEXT,
                lastname TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO users (id, email, password_hash, state_id, name)
            VALUES ('test-user', 'test@example.com', '', 2, 'Test')
            """
        )
        conn.commit()
        conn.close()

        class TestConfig:
            SECRET_KEY = "test-secret"
            TESTING = True
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{self.tmp.name}"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            WTF_CSRF_ENABLED = False
            CACHE_TYPE = "SimpleCache"

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        Base.metadata.clear()
        os.unlink(self.tmp.name)

    def test_dashboard_wellness_route_renders_for_logged_user(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = "test-user"
            session["_fresh"] = True

        response = self.client.get("/dashboard/wellness/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Wellness", response.data)
        self.assertIn(b"Dashboard inicial de Wellness", response.data)


if __name__ == "__main__":
    unittest.main()
