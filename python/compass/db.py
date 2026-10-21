# -*- coding: utf-8 -*-
"""SQLite storage for the Compass service."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  handle TEXT UNIQUE NOT NULL,
  pat_hash TEXT UNIQUE NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kv (
  user_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (user_id, kind),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  company TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  city TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'new',
  priority TEXT NOT NULL DEFAULT '',
  score INTEGER NOT NULL DEFAULT 0,
  data TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_jobs_user_status ON jobs(user_id, status);
CREATE INDEX IF NOT EXISTS idx_jobs_user_score ON jobs(user_id, score DESC);

CREATE TABLE IF NOT EXISTS job_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  at TEXT NOT NULL,
  type TEXT NOT NULL,
  from_status TEXT,
  to_status TEXT,
  note TEXT,
  FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_events_job ON job_events(job_id, at);

CREATE TABLE IF NOT EXISTS resumes (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  job_id TEXT,
  title TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  UNIQUE(user_id, job_id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS resume_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  resume_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  style TEXT NOT NULL,
  data TEXT NOT NULL,
  html TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(resume_id, version, style),
  FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS shares (
  slug TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  target TEXT,
  version INTEGER,
  created_at TEXT NOT NULL,
  revoked INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@contextmanager
def connect():
    config.ensure_home()
    con = sqlite3.connect(str(config.DB_PATH), timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=15000")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with connect() as con:
        con.executescript(SCHEMA)
        con.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', '1')"
        )


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def get_user(con, handle: str) -> dict | None:
    return row_to_dict(con.execute("SELECT * FROM users WHERE handle=?", (handle,)).fetchone())


def get_user_by_pat(con, pat_hash: str) -> dict | None:
    return row_to_dict(
        con.execute("SELECT * FROM users WHERE pat_hash=?", (pat_hash,)).fetchone()
    )


def create_user(con, handle: str, pat_hash: str) -> int:
    cur = con.execute(
        "INSERT INTO users(handle, pat_hash, created_at) VALUES(?,?,?)",
        (handle, pat_hash, now()),
    )
    return int(cur.lastrowid)


def kv_get(con, user_id: int, kind: str, default=None):
    row = con.execute(
        "SELECT json FROM kv WHERE user_id=? AND kind=?", (user_id, kind)
    ).fetchone()
    return json.loads(row["json"]) if row else default


def kv_set(con, user_id: int, kind: str, obj) -> None:
    con.execute(
        "INSERT INTO kv(user_id, kind, json, updated_at) VALUES(?,?,?,?) "
        "ON CONFLICT(user_id, kind) DO UPDATE SET json=excluded.json, updated_at=excluded.updated_at",
        (user_id, kind, json.dumps(obj, ensure_ascii=False), now()),
    )


def list_jobs(con, user_id: int, status: str = "", q: str = "") -> list[dict]:
    sql = "SELECT data FROM jobs WHERE user_id=?"
    args: list = [user_id]
    if status:
        sql += " AND status=?"
        args.append(status)
    if q:
        sql += " AND (company LIKE ? OR title LIKE ? OR city LIKE ?)"
        like = f"%{q}%"
        args += [like, like, like]
    sql += " ORDER BY score DESC, updated_at DESC"
    return [json.loads(r["data"]) for r in con.execute(sql, args).fetchall()]


def get_job(con, user_id: int, job_id: str) -> dict | None:
    row = con.execute(
        "SELECT data FROM jobs WHERE user_id=? AND id=?", (user_id, job_id)
    ).fetchone()
    return json.loads(row["data"]) if row else None


def save_job(con, user_id: int, job: dict, is_new: bool) -> None:
    now_s = now()
    job["updated_at"] = now_s
    con.execute(
        "INSERT INTO jobs(id,user_id,company,title,city,status,priority,score,data,created_at,updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET company=excluded.company,title=excluded.title,city=excluded.city,"
        "status=excluded.status,priority=excluded.priority,score=excluded.score,data=excluded.data,"
        "updated_at=excluded.updated_at",
        (
            job["id"], user_id, job.get("company", ""), job.get("title", ""),
            job.get("city", ""), job.get("status", "new"), job.get("priority", ""),
            int(job.get("match_score") or 0), json.dumps(job, ensure_ascii=False),
            job.get("created_at") or now_s, now_s,
        ),
    )
    if is_new:
        con.execute(
            "INSERT INTO job_events(job_id,at,type,note) VALUES(?,?,?,?)",
            (job["id"], now_s, "created", "录入岗位池"),
        )


def add_event(con, job_id: str, type_: str, from_status: str = "", to_status: str = "", note: str = "") -> None:
    con.execute(
        "INSERT INTO job_events(job_id,at,type,from_status,to_status,note) VALUES(?,?,?,?,?,?)",
        (job_id, now(), type_, from_status or None, to_status or None, note or None),
    )


def job_events(con, job_id: str) -> list[dict]:
    rows = con.execute(
        "SELECT at,type,from_status,to_status,note FROM job_events WHERE job_id=? ORDER BY at",
        (job_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_or_create_resume(con, user_id: int, job_id: str | None, title: str) -> dict:
    row = con.execute(
        "SELECT * FROM resumes WHERE user_id=? AND job_id IS ?", (user_id, job_id)
    ).fetchone()
    if row:
        return dict(row)
    rid = f"res_{user_id}_{job_id or 'default'}"
    con.execute(
        "INSERT INTO resumes(id,user_id,job_id,title,created_at) VALUES(?,?,?,?,?)",
        (rid, user_id, job_id, title, now()),
    )
    return {"id": rid, "user_id": user_id, "job_id": job_id, "title": title}


def next_version(con, resume_id: str) -> int:
    row = con.execute(
        "SELECT MAX(version) AS v FROM resume_versions WHERE resume_id=?", (resume_id,)
    ).fetchone()
    return int(row["v"] or 0) + 1


def save_resume_version(con, resume_id: str, version: int, style: str, data: dict, html: str) -> None:
    con.execute(
        "INSERT INTO resume_versions(resume_id,version,style,data,html,created_at) VALUES(?,?,?,?,?,?)",
        (resume_id, version, style, json.dumps(data, ensure_ascii=False), html, now()),
    )


def get_resume_version(con, resume_id: str, version: int, style: str) -> dict | None:
    row = con.execute(
        "SELECT * FROM resume_versions WHERE resume_id=? AND version=? AND style=?",
        (resume_id, version, style),
    ).fetchone()
    return dict(row) if row else None


def latest_resume_version(con, resume_id: str, style: str) -> dict | None:
    row = con.execute(
        "SELECT * FROM resume_versions WHERE resume_id=? AND style=? ORDER BY version DESC LIMIT 1",
        (resume_id, style),
    ).fetchone()
    return dict(row) if row else None


def list_resume_versions(con, resume_id: str) -> list[dict]:
    rows = con.execute(
        "SELECT version,style,created_at FROM resume_versions WHERE resume_id=? ORDER BY version DESC",
        (resume_id,),
    ).fetchall()
    return [dict(r) for r in rows]
