"""Fictional ICS-context Web training range. Run only in an approved lab."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE = Path(__file__).resolve().parent
MODES = {"safe", "idor", "sqli", "bp"}
BUILD_ID = "B01-2026.11.10-v7"
SEED_VERSION = "2"
PORTAL_FEATURES = {
    "solutions": "解决方案", "products": "产品与服务", "support": "技术支持",
    "contact": "联系我们", "news": "最新动态", "downloads": "资料下载",
}
DEVICE_SEED = [
    (101, "SIM-E01", "模拟空压机", "运行", 1),
    (102, "SIM-E02", "模拟水泵", "维护中", 2),
    (201, "SIM-E03", "模拟输送机", "待检查", 1),
]
RECORD_SEED = [
    (1, 101, "SIM-M01", "空压机巡检", "仅供教学的巡检记录", 1),
    (2, 102, "SIM-M02", "水泵保养", "仅供教学的保养记录", 2),
    (3, 201, "SIM-M03", "输送机复检", "仅供教学的复检记录", 1),
]
SEARCH_SEED = [
    (1, "SIM-E01", "巡检索引一", "公开教学索引"),
    (2, "SIM-E02", "保养索引二", "公开教学索引"),
    (3, "SIM-E03", "复检索引三", "公开教学索引"),
    (4, "SIM-E04", "告警索引四", "公开教学索引"),
]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=3)
        db.execute("PRAGMA query_only=ON")
        db.set_progress_handler(lambda: 1, 100000)
    else:
        db = sqlite3.connect(path, timeout=5)
        db.execute("PRAGMA foreign_keys=ON")
    db.row_factory = sqlite3.Row
    return db


def seed_digest(db: sqlite3.Connection) -> str:
    data = {
        "devices": [tuple(r) for r in db.execute("SELECT id,code,name,status,owner_id FROM devices ORDER BY id")],
        "records": [tuple(r) for r in db.execute("SELECT id,device_id,code,title,body,owner_id FROM records ORDER BY id")],
    }
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def seed_business(db: sqlite3.Connection) -> None:
    db.execute("DELETE FROM records")
    db.execute("DELETE FROM devices")
    db.executemany("INSERT INTO devices VALUES (?,?,?,?,?)", DEVICE_SEED)
    db.executemany("INSERT INTO records VALUES (?,?,?,?,?,?)", RECORD_SEED)


def reset_business(db: sqlite3.Connection, actor_id: int) -> tuple[str, str]:
    before = seed_digest(db)
    expected = hashlib.sha256(json.dumps({"devices": DEVICE_SEED, "records": RECORD_SEED}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    try:
        seed_business(db)
        after = seed_digest(db)
        if after != expected:
            raise RuntimeError("baseline_digest_mismatch")
        db.execute("INSERT INTO reset_events(at,actor_id,before_digest,after_digest,result) VALUES (?,?,?,?,?)",
                   (utcnow(), actor_id, before, after, "ok"))
        db.commit()
        return before, after
    except Exception:
        db.rollback()
        raise


def initialize(main_path: Path, search_path: Path, passwords: dict[str, str] | None = None) -> dict[str, str]:
    main_path.parent.mkdir(parents=True, exist_ok=True)
    search_path.parent.mkdir(parents=True, exist_ok=True)
    if passwords is None:
        passwords = {name: secrets.token_urlsafe(12) for name in ("maint_a", "maint_b", "admin", "reviewer")}
    db = connect(main_path)
    try:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('maint','admin','reviewer')));
        CREATE TABLE IF NOT EXISTS devices(id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL,
          name TEXT NOT NULL, status TEXT NOT NULL, owner_id INTEGER NOT NULL REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY, device_id INTEGER NOT NULL REFERENCES devices(id),
          code TEXT UNIQUE NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
          owner_id INTEGER NOT NULL REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS login_sessions(token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS audit_events(id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor_id INTEGER,
          action TEXT NOT NULL, target TEXT, result TEXT NOT NULL, mode TEXT NOT NULL, build_id TEXT NOT NULL,
          request_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reset_events(id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor_id INTEGER NOT NULL,
          before_digest TEXT NOT NULL, after_digest TEXT NOT NULL, result TEXT NOT NULL);
        """)
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            raise RuntimeError("Database already initialized; use a new path to avoid replacing users")
        for uid, name, role in ((1, "maint_a", "maint"), (2, "maint_b", "maint"), (3, "admin", "admin"), (4, "reviewer", "reviewer")):
            db.execute("INSERT INTO users VALUES (?,?,?,?)", (uid, name, generate_password_hash(passwords[name]), role))
        seed_business(db)
        db.commit()
    finally:
        db.close()
    search = connect(search_path)
    try:
        search.execute("CREATE TABLE IF NOT EXISTS training_search_records(code INTEGER PRIMARY KEY, device_code TEXT, title TEXT, summary TEXT)")
        search.execute("DELETE FROM training_search_records")
        search.executemany("INSERT INTO training_search_records VALUES (?,?,?,?)", SEARCH_SEED)
        search.commit()
    finally:
        search.close()
    return passwords


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder="static")
    app.config.update(
        SECRET_KEY=os.environ.get("LAB_SECRET") or secrets.token_hex(32),
        LAB_MODE=os.environ.get("LAB_MODE", "safe"),
        DB_PATH=str(BASE / "data" / "range.db"),
        SEARCH_DB_PATH=str(BASE / "data" / "training.db"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,
        MAX_CONTENT_LENGTH=65536,
    )
    if config:
        app.config.update(config)
    mode = app.config["LAB_MODE"]
    if mode not in MODES:
        raise ValueError("LAB_MODE must be safe, idor, sqli, or bp")
    main_path = Path(app.config["DB_PATH"]).resolve()
    search_path = Path(app.config["SEARCH_DB_PATH"]).resolve()
    if not main_path.is_file() or not search_path.is_file():
        raise RuntimeError("Initialize both databases before starting the server")
    failed_logins: dict[str, list[float]] = {}
    recent_registrations: dict[str, list[float]] = {}

    def db() -> sqlite3.Connection:
        if "db" not in g:
            g.db = connect(main_path)
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    def actor():
        token = session.get("token")
        if not token:
            return None
        return db().execute("SELECT u.id,u.username,u.role FROM login_sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires_at>?", (token, time.time())).fetchone()

    def audit(action: str, target: str, result: str, uid: int | None = None):
        db().execute("INSERT INTO audit_events(at,actor_id,action,target,result,mode,build_id,request_id) VALUES (?,?,?,?,?,?,?,?)",
                     (utcnow(), uid, action, target[:80], result, mode, BUILD_ID, g.request_id))
        db().commit()

    def require(role: str | None = None):
        def deco(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                user = actor()
                if not user:
                    return jsonify(error="login_required", request_id=g.request_id), 401
                if role and user["role"] not in (role, "admin"):
                    audit("deny", request.path, "forbidden", user["id"])
                    return jsonify(error="forbidden", request_id=g.request_id), 403
                return fn(user, *args, **kwargs)
            return wrapped
        return deco

    @app.before_request
    def start_request():
        g.request_id = secrets.token_hex(6)
        if request.method == "POST" and request.headers.get("Origin"):
            if request.headers["Origin"].rstrip("/") != request.host_url.rstrip("/"):
                return jsonify(error="bad_origin", request_id=g.request_id), 403

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/lab/status")
    def status():
        return jsonify(data={"mode": mode, "build_id": BUILD_ID, "seed_version": SEED_VERSION, "started_at": app.config.setdefault("STARTED_AT", utcnow())})

    @app.get("/healthz")
    def health():
        return jsonify(ok=True, mode=mode)

    @app.get("/api/portal/<feature>")
    def portal_feature(feature):
        title = PORTAL_FEATURES.get(feature)
        if title is None:
            return jsonify(error="not_found", request_id=g.request_id), 404
        return jsonify(data={"feature": feature, "title": title, "status": "coming_soon",
                             "message": "该功能正在开发中"})

    @app.post("/api/auth/login")
    def login():
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify(error="invalid_request", request_id=g.request_id), 400
        name, password = str(body.get("username", ""))[:80], str(body.get("password", ""))
        client = request.remote_addr or "local"
        recent = [t for t in failed_logins.get(client, []) if time.time() - t < 60]
        failed_logins[client] = recent
        if len(recent) >= 5:
            return jsonify(error="请稍后再试", request_id=g.request_id), 429
        row = db().execute("SELECT id,password_hash FROM users WHERE username=?", (name,)).fetchone()
        if not row or not check_password_hash(row["password_hash"], password):
            recent.append(time.time())
            audit("login", name, "denied")
            return jsonify(error="用户名或密码错误", request_id=g.request_id), 401
        failed_logins.pop(client, None)
        token = secrets.token_urlsafe(32)
        db().execute("INSERT INTO login_sessions VALUES (?,?,?)", (token, row["id"], time.time() + 1800))
        db().commit()
        session.clear()
        session["token"] = token
        session["csrf"] = secrets.token_urlsafe(24)
        audit("login", name, "ok", row["id"])
        return jsonify(data={"ok": True})

    @app.post("/api/auth/register")
    def register():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) != {"username", "password"}:
            return jsonify(error="只需填写账号和密码", request_id=g.request_id), 400
        name, password = body["username"], body["password"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{2,31}", name):
            return jsonify(error="账号须为3到32位英文字母、数字或下划线，且以字母开头", request_id=g.request_id), 400
        if not isinstance(password, str) or not 10 <= len(password) <= 128:
            return jsonify(error="密码长度须为10到128位", request_id=g.request_id), 400
        client = request.remote_addr or "local"
        recent = [t for t in recent_registrations.get(client, []) if time.time() - t < 3600]
        recent_registrations[client] = recent
        if len(recent) >= 5:
            return jsonify(error="注册次数过多，请稍后再试", request_id=g.request_id), 429
        try:
            db().execute("INSERT INTO users(username,password_hash,role) VALUES (?,?,?)",
                         (name, generate_password_hash(password), "maint"))
            db().commit()
        except sqlite3.IntegrityError:
            db().rollback()
            return jsonify(error="账号已存在", request_id=g.request_id), 409
        recent.append(time.time())
        audit("register", name, "ok")
        return jsonify(data={"ok": True, "username": name, "role": "maint"}), 201

    @app.get("/api/auth/me")
    @require()
    def me(user):
        return jsonify(data={"username": user["username"], "role": user["role"], "csrf": session["csrf"]})

    def check_csrf():
        return secrets.compare_digest(str(request.headers.get("X-CSRF-Token", "")), str(session.get("csrf", "!")))

    @app.post("/api/auth/logout")
    @require()
    def logout(user):
        if not check_csrf():
            return jsonify(error="csrf_required"), 403
        db().execute("DELETE FROM login_sessions WHERE token=?", (session["token"],))
        db().commit()
        audit("logout", user["username"], "ok", user["id"])
        session.clear()
        return jsonify(data={"ok": True})

    @app.get("/api/devices")
    @require()
    def devices(user):
        if user["role"] == "admin" or user["role"] == "reviewer":
            rows = db().execute("SELECT id,code,name,status FROM devices ORDER BY id").fetchall()
        else:
            rows = db().execute("SELECT id,code,name,status FROM devices WHERE owner_id=? ORDER BY id", (user["id"],)).fetchall()
        return jsonify(data=[dict(x) for x in rows])

    @app.get("/api/devices/<int:device_id>")
    @require()
    def device(user, device_id):
        row = db().execute("SELECT id,code,name,status,owner_id FROM devices WHERE id=?", (device_id,)).fetchone()
        if row is None:
            return jsonify(error="not_found"), 404
        if user["role"] == "maint" and row["owner_id"] != user["id"]:
            audit("deny", f"device:{device_id}", "forbidden", user["id"])
            return jsonify(error="forbidden"), 403
        return jsonify(data={k: row[k] for k in ("id", "code", "name", "status")})

    @app.get("/api/devices/<int:device_id>/records")
    @require()
    def device_records(user, device_id):
        device_row = db().execute("SELECT owner_id FROM devices WHERE id=?", (device_id,)).fetchone()
        if device_row is None:
            return jsonify(error="not_found"), 404
        if user["role"] == "maint" and device_row["owner_id"] != user["id"]:
            audit("deny", f"device_records:{device_id}", "forbidden", user["id"])
            return jsonify(error="forbidden"), 403
        owner_filter = "" if user["role"] != "maint" else " AND owner_id=?"
        params = (device_id,) if not owner_filter else (device_id, user["id"])
        rows = db().execute("SELECT id,code,title,device_id FROM records WHERE device_id=?" + owner_filter + " ORDER BY id", params).fetchall()
        return jsonify(data=[dict(x) for x in rows])

    @app.get("/api/records/<int:record_id>")
    @require()
    def record(user, record_id):
        row = db().execute("SELECT id,device_id,code,title,body,owner_id FROM records WHERE id=?", (record_id,)).fetchone()
        if row is None:
            return jsonify(error="not_found"), 404
        if mode != "idor" and user["role"] == "maint" and row["owner_id"] != user["id"]:
            audit("record_read", str(record_id), "forbidden", user["id"])
            return jsonify(error="forbidden"), 403
        audit("record_read", str(record_id), "ok", user["id"])
        return jsonify(data={k: row[k] for k in ("id", "device_id", "code", "title", "body")})

    @app.post("/api/training/report-preview")
    @require()
    def report_preview(user):
        """Independent T3 parameter-tampering exercise: client claims a preview role."""
        if not check_csrf():
            return jsonify(error="csrf_required"), 403
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or payload.get("preview_role") not in ("maint", "reviewer"):
            return jsonify(error="invalid_preview_role"), 400
        requested = payload["preview_role"]
        if mode == "bp":
            effective = requested  # Intentional lab-only trust of a client-controlled role field.
        else:
            effective = user["role"]
        if requested == "reviewer" and effective not in ("reviewer", "admin"):
            audit("report_preview", "restricted", "forbidden", user["id"])
            return jsonify(error="forbidden"), 403
        if requested == "reviewer" and effective in ("reviewer", "admin"):
            result = {"report_code": "SIM-R02", "title": "受限培训复核摘要", "content": "虚构班次复核通过；仅供教学"}
        else:
            result = {"report_code": "SIM-R01", "title": "普通维护预览", "content": "虚构设备均未连接真实系统"}
        audit("report_preview", result["report_code"], "ok", user["id"])
        return jsonify(data=result)

    @app.get("/api/training-search")
    @require()
    def training_search(user):
        q = request.args.get("q", "").strip()
        if not q or len(q) > 80:
            return jsonify(error="invalid_query"), 400
        search = connect(search_path, readonly=True)
        try:
            if mode == "sqli":
                # Intentional lab-only defect. The separate read-only DB contains only public synthetic index rows.
                rows = search.execute(f"SELECT code,device_code,title,summary FROM training_search_records WHERE code={q} LIMIT 20").fetchall()
            else:
                rows = search.execute("SELECT code,device_code,title,summary FROM training_search_records WHERE code=? LIMIT 20", (q,)).fetchall()
        except sqlite3.Error:
            audit("training_search", hashlib.sha256(q.encode()).hexdigest()[:12], "invalid", user["id"])
            return jsonify(error="invalid_query"), 400
        finally:
            search.close()
        audit("training_search", hashlib.sha256(q.encode()).hexdigest()[:12], "ok", user["id"])
        return jsonify(data=[dict(x) for x in rows])

    @app.get("/api/audit")
    @require("reviewer")
    def audit_list(user):
        rows = db().execute("SELECT id,at,actor_id,action,target,result,mode,build_id,request_id FROM audit_events ORDER BY id DESC LIMIT 100").fetchall()
        return jsonify(data=[dict(x) for x in rows])

    @app.post("/api/admin/reset")
    @require("admin")
    def reset(user):
        if not check_csrf():
            return jsonify(error="csrf_required"), 403
        conn = db()
        try:
            before, after = reset_business(conn, user["id"])
        except Exception:
            audit("reset", "business", "failed", user["id"])
            return jsonify(error="reset_failed"), 500
        audit("reset", "business", "ok", user["id"])
        return jsonify(data={"restored": True, "before_digest": before, "after_digest": after})

    return app
