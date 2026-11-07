import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from lab import BASE, create_app, initialize, seed_digest

PASSWORDS = {"maint_a": "test-A-only", "maint_b": "test-B-only", "admin": "test-admin-only", "reviewer": "test-review-only"}


class LabTests(unittest.TestCase):
    def setUp(self):
        test_root = BASE / ".test_tmp"
        test_root.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=test_root)
        self.main = Path(self.tmp.name) / "range.db"
        self.search = Path(self.tmp.name) / "training.db"
        initialize(self.main, self.search, PASSWORDS)
        self.apps = {}

    def tearDown(self):
        self.tmp.cleanup()

    def client(self, mode="safe"):
        if mode not in self.apps:
            self.apps[mode] = create_app({"TESTING": True, "SECRET_KEY": "test-secret", "LAB_MODE": mode,
                                          "DB_PATH": str(self.main), "SEARCH_DB_PATH": str(self.search)})
        return self.apps[mode].test_client()

    def login(self, client, name="maint_a"):
        response = client.post("/api/auth/login", json={"username": name, "password": PASSWORDS[name]})
        self.assertEqual(response.status_code, 200)
        return client.get("/api/auth/me").json["data"]["csrf"]

    def db(self):
        return sqlite3.connect(self.main)

    def test_schema_and_seed(self):
        with closing(self.db()) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM users").fetchone()[0], 4)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM records").fetchone()[0], 3)
            self.assertEqual(c.execute("PRAGMA foreign_key_check").fetchall(), [])
        with closing(sqlite3.connect(self.search)) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM training_search_records").fetchone()[0], 4)
            self.assertEqual([x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")], ["training_search_records"])

    def test_initialization_never_overwrites_accounts(self):
        with self.assertRaises(RuntimeError):
            initialize(self.main, self.search, PASSWORDS)

    def test_missing_database_fails_closed(self):
        with self.assertRaises(RuntimeError):
            create_app({"DB_PATH": str(self.main), "SEARCH_DB_PATH": str(self.search) + "missing"})

    def test_invalid_mode_fails_closed(self):
        with self.assertRaises(ValueError):
            self.client("idor,sqli")

    def test_default_and_explicit_modes(self):
        for mode in ("safe", "idor", "sqli", "bp"):
            c = self.client(mode)
            self.assertEqual(c.get("/api/lab/status").json["data"]["mode"], mode)
            self.assertEqual(c.get("/healthz").status_code, 200)
            with c.get("/") as response:
                self.assertIn(b"app.js", response.data)

    def test_auth_and_logout_revocation(self):
        c = self.client()
        self.assertEqual(c.get("/api/devices").status_code, 401)
        self.assertEqual(c.post("/api/auth/login", json={"username": "maint_a", "password": "wrong"}).status_code, 401)
        csrf = self.login(c)
        self.assertEqual(c.get("/api/auth/me").json["data"]["role"], "maint")
        self.assertEqual(c.post("/api/auth/logout").status_code, 403)
        self.assertEqual(c.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code, 200)
        self.assertEqual(c.get("/api/auth/me").status_code, 401)

    def test_login_rate_limit(self):
        c = self.client()
        for _ in range(5):
            self.assertEqual(c.post("/api/auth/login", json={"username": "none", "password": "x"}).status_code, 401)
        self.assertEqual(c.post("/api/auth/login", json={"username": "none", "password": "x"}).status_code, 429)

    def test_bad_origin(self):
        c = self.client()
        self.assertEqual(c.post("/api/auth/login", json={}, headers={"Origin": "http://example.invalid"}).status_code, 403)

    def test_bad_login_body(self):
        c = self.client()
        self.assertEqual(c.post("/api/auth/login", json=["unexpected"]).status_code, 400)

    def test_devices_and_detail_are_scoped(self):
        for mode in ("safe", "idor", "sqli", "bp"):
            c = self.client(mode)
            self.login(c)
            self.assertEqual([x["id"] for x in c.get("/api/devices").json["data"]], [101, 201])
            self.assertEqual(c.get("/api/devices/102").status_code, 403)
            self.assertEqual(c.get("/api/devices/102/records").status_code, 403)
            self.assertEqual(c.get("/api/devices/999/records").status_code, 404)
            self.assertEqual(c.get("/api/devices/101/records").json["data"][0]["id"], 1)

    def test_idor_same_request_before_after(self):
        for mode, expected in (("safe", 403), ("idor", 200), ("sqli", 403), ("bp", 403)):
            c = self.client(mode)
            self.login(c)
            response = c.get("/api/records/2")
            self.assertEqual(response.status_code, expected)
            if expected == 403:
                self.assertNotIn("保养记录", response.get_data(as_text=True))
            self.assertEqual(c.get("/api/records/1").status_code, 200)
            self.assertEqual(c.get("/api/records/999").status_code, 404)

    def test_idor_second_identity_and_no_write(self):
        with closing(self.db()) as db:
            before = seed_digest(db)
        for mode, expected in (("safe", 403), ("idor", 200)):
            c = self.client(mode)
            self.login(c, "maint_b")
            self.assertEqual(c.get("/api/records/1").status_code, expected)
        with closing(self.db()) as db:
            self.assertEqual(seed_digest(db), before)

    def test_sqli_separate_read_only_data_and_retest(self):
        with closing(self.db()) as db:
            before = seed_digest(db)
        for mode, count in (("safe", 0), ("idor", 0), ("sqli", 4), ("bp", 0)):
            c = self.client(mode)
            self.login(c)
            normal = c.get("/api/training-search?q=1")
            self.assertEqual(len(normal.json["data"]), 1)
            response = c.get("/api/training-search?q=1%20OR%201=1")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json["data"]), count)
            self.assertNotIn("仅供教学的保养记录", response.get_data(as_text=True))
        with closing(self.db()) as db:
            self.assertEqual(seed_digest(db), before)

    def test_sqli_other_input_and_errors(self):
        for mode in ("safe", "sqli"):
            c = self.client(mode)
            self.login(c)
            self.assertEqual(c.get("/api/training-search?q=").status_code, 400)
            self.assertEqual(c.get("/api/training-search?q=" + "x" * 81).status_code, 400)
            r = c.get("/api/training-search?q=%27")
            self.assertIn(r.status_code, (200, 400))
            self.assertNotIn("sqlite3", r.get_data(as_text=True))

    def test_bp_preview_parameter_tampering(self):
        with closing(self.db()) as db:
            before = seed_digest(db)
        for mode, expected in (("safe", 403), ("idor", 403), ("sqli", 403), ("bp", 200)):
            client = self.client(mode)
            csrf = self.login(client)
            headers = {"X-CSRF-Token": csrf}
            ordinary = client.post("/api/training/report-preview", json={"preview_role": "maint"}, headers=headers)
            self.assertEqual(ordinary.status_code, 200)
            self.assertEqual(ordinary.json["data"]["report_code"], "SIM-R01")
            changed = client.post("/api/training/report-preview", json={"preview_role": "reviewer"}, headers=headers)
            self.assertEqual(changed.status_code, expected)
            if expected == 200:
                self.assertEqual(changed.json["data"]["report_code"], "SIM-R02")
            else:
                self.assertNotIn("受限培训复核摘要", changed.get_data(as_text=True))
            self.assertEqual(client.post("/api/training/report-preview", json={"preview_role": "reviewer"}).status_code, 403)
        with closing(self.db()) as db:
            self.assertEqual(seed_digest(db), before)

    def test_bp_preview_actual_reviewer(self):
        client = self.client("safe")
        csrf = self.login(client, "reviewer")
        response = client.post("/api/training/report-preview", json={"preview_role": "reviewer"}, headers={"X-CSRF-Token": csrf})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["data"]["report_code"], "SIM-R02")

    def test_audit_access_and_events(self):
        maint = self.client()
        self.login(maint)
        maint.get("/api/records/2")
        self.assertEqual(maint.get("/api/audit").status_code, 403)
        reviewer = self.client()
        self.login(reviewer, "reviewer")
        rows = reviewer.get("/api/audit").json["data"]
        self.assertTrue(any(x["action"] == "record_read" and x["result"] == "forbidden" for x in rows))
        self.assertFalse(any("test-A-only" in json.dumps(x) for x in rows))

    def test_reset_permissions_csrf_and_content(self):
        c = self.client()
        self.login(c)
        self.assertEqual(c.post("/api/admin/reset").status_code, 403)
        admin = self.client()
        csrf = self.login(admin, "admin")
        self.assertEqual(admin.post("/api/admin/reset").status_code, 403)
        with closing(self.db()) as db:
            db.execute("UPDATE devices SET status='changed' WHERE id=101")
            db.commit()
        result = admin.post("/api/admin/reset", headers={"X-CSRF-Token": csrf})
        self.assertEqual(result.status_code, 200)
        with closing(self.db()) as db:
            self.assertEqual(db.execute("SELECT status FROM devices WHERE id=101").fetchone()[0], "运行")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM reset_events").fetchone()[0], 1)
        self.assertNotEqual(result.json["data"]["before_digest"], result.json["data"]["after_digest"])

    def test_reset_failure_rolls_back(self):
        admin = self.client()
        csrf = self.login(admin, "admin")
        with closing(self.db()) as db:
            db.execute("CREATE TRIGGER stop_seed BEFORE INSERT ON devices BEGIN SELECT RAISE(ABORT,'blocked'); END")
            before = seed_digest(db)
            db.commit()
        self.assertEqual(admin.post("/api/admin/reset", headers={"X-CSRF-Token": csrf}).status_code, 500)
        with closing(self.db()) as db:
            self.assertEqual(seed_digest(db), before)


if __name__ == "__main__":
    unittest.main()
