from datetime import date
import os
import sqlite3
import tempfile
import unittest

from dux import create_app
from dux.controllers.dashboard_wellness_controller import _build_summary
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
        conn.execute(
            """
            CREATE TABLE futbolistas (
                identificacion TEXT PRIMARY KEY,
                nombre TEXT,
                apellido TEXT,
                competicion TEXT,
                genero TEXT,
                id_estado INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE wellness (
                id INTEGER PRIMARY KEY,
                id_jugadora TEXT,
                fecha_sesion DATE,
                tipo TEXT,
                turno TEXT,
                recuperacion INTEGER,
                fatiga INTEGER,
                sueno INTEGER,
                stress INTEGER,
                dolor INTEGER,
                minutos_sesion INTEGER,
                rpe REAL,
                ua REAL,
                observacion TEXT,
                fecha_hora_registro DATETIME,
                usuario TEXT,
                estatus_id INTEGER
            )
            """
        )
        conn.execute(
            """
            INSERT INTO futbolistas (
                identificacion, nombre, apellido, competicion, genero, id_estado
            )
            VALUES ('player-1', 'Alexia', 'Test', '1FF', 'F', 1)
            """
        )
        today = date.today().isoformat()

        conn.execute(
            """
            INSERT INTO wellness (
                id, id_jugadora, fecha_sesion, tipo, turno, recuperacion, fatiga,
                sueno, stress, dolor, minutos_sesion, rpe, ua, observacion,
                fecha_hora_registro, usuario, estatus_id
            )
            VALUES (
                1, 'player-1', ?, 'checkOut', 'mañana', 4, 3,
                5, 2, 1, 60, 5, 300, '', ?, 'test', 2
            )
            """,
            (today, f"{today} 09:00:00"),
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
        self.assertIn(b"Registros de Wellness y RPE", response.data)
        self.assertIn(b"Test, Alexia", response.data)
        self.assertIn(b"1FF", response.data)
        self.assertIn(b"checkOut", response.data)
        self.assertIn(b"15.0/25", response.data)
        self.assertIn(b"0/1", response.data)
        self.assertIn(b"300.0", response.data)

    def test_build_summary_uses_legacy_wellness_kpis(self):
        records = [
            {
                "id_jugadora": "player-risk",
                "nombre_jugadora": "Risk Player",
                "tipo": "checkOut",
                "recuperacion": 4,
                "energia": 4,
                "sueno": 4,
                "stress": 4,
                "dolor": 4,
                "wellness_score": 20,
                "rpe": 6,
                "ua": 360,
            },
            {
                "id_jugadora": "player-ok",
                "nombre_jugadora": "Ok Player",
                "tipo": "checkOut",
                "recuperacion": 1,
                "energia": 1,
                "sueno": 1,
                "stress": 1,
                "dolor": 1,
                "wellness_score": 5,
                "rpe": 4,
                "ua": 200,
            },
        ]

        summary = _build_summary(records)

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["wellness_promedio"], 12.5)
        self.assertEqual(summary["wellness_estado"], "en fatiga")
        self.assertEqual(summary["rpe_promedio"], 5.0)
        self.assertEqual(summary["rpe_estado"], "moderado")
        self.assertEqual(summary["ua_total"], 560)
        self.assertEqual(summary["alertas_count"], 1)
        self.assertEqual(summary["alertas_total_jugadoras"], 2)
        self.assertEqual(summary["alertas_pct"], 50.0)


if __name__ == "__main__":
    unittest.main()
