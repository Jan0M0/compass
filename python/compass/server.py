# -*- coding: utf-8 -*-
"""Compass HTTP service.

Runs on 127.0.0.1 by default. It never calls a model: the user's agent does the
reasoning and sends structured results here. This service owns schema, storage,
versions, rendering, and distribution.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import date
from typing import Callable

from . import auth, config, db, dialogue, radar, resume as resume_mod, schema, scoring, validate, views

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

STATUSES = schema.STATUSES
NEXT_STATES = {
    "new": {"shortlisted", "dropped"},
    "shortlisted": {"tailored", "dropped"},
    "tailored": {"applied", "dropped"},
    "applied": {"replied", "interview", "rejected", "dropped"},
    "replied": {"interview", "rejected", "dropped"},
    "interview": {"offer", "rejected", "dropped"},
    "offer": set(), "rejected": set(), "dropped": set(),
}

SKILL_WORDS = [
    "Excel", "Word", "PPT", "Python", "SQL", "Tableau", "PowerBI", "SPSS", "R",
    "数据分析", "数据清洗", "可视化", "爬虫", "文案", "新媒体", "短视频", "剪辑",
    "Photoshop", "PS", "Canva", "小红书", "抖音", "公众号", "活动策划", "用户调研",
    "竞品分析", "需求分析", "产品原型", "Axure", "Figma", "英语", "四六级", "雅思",
    "沟通", "项目管理", "社团", "运营", "市场", "销售", "客服", "财务", "会计",
]
RISK_WORDS = [
    "收费", "押金", "培训费", "培训贷", "贷款", "刷单", "打字员", "日结",
    "在家兼职", "无薪", "免费实习", "先交钱", "购买设备", "垫付", "拉人头",
]
GRADE_WORDS = ["大一", "大二", "大三", "大四", "研一", "研二", "研三",
               "2026届", "2027届", "2028届", "2029届", "2030届"]
CITY_LIST = [
    "北京", "上海", "广州", "深圳", "杭州", "宁波", "南京", "苏州", "成都", "重庆",
    "武汉", "西安", "长沙", "合肥", "厦门", "福州", "青岛", "济南", "天津", "郑州",
    "南昌", "昆明", "无锡", "佛山", "东莞", "珠海", "嘉兴", "绍兴", "温州", "金华",
]

DEFAULT_PROFILE = {
    "version": 1, "name": "", "school": "", "major": "", "grade": "",
    "graduation_year": None, "cities": [], "remote_ok": True,
    "directions": [], "skills": [], "toolchain": [], "languages": [],
    "available": {"days_per_week": 3, "months": 3, "start": ""},
    "contact": {"phone": "", "email": "", "wechat": "", "portfolio": ""},
    "weekly_target": 8, "target_companies": [], "dealbreakers": [],
}
DEFAULT_SELF = {
    "version": 1, "facts": {}, "interests": [], "strengths": [], "values": [],
    "dislikes": [], "constraints": [], "experiments": [], "questions": [],
    "people": [], "preferences": {}, "sources": [],
}
DEFAULT_EXPLORE = {"version": 1, "paths": [], "missions": []}


def _json_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def _parse_days(text: str):
    cn = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
          "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7}
    for p in (r"每\s*周[^，。；\n]{0,6}?([一二三四五六七1-7])\s*天",
              r"([1-7])\s*天\s*/\s*周"):
        m = re.search(p, text)
        if m:
            return cn.get(m.group(1))
    return None


def _parse_salary(text: str) -> str:
    for p in (r"(\d{2,4})\s*[-~—至]\s*(\d{2,4})\s*元?\s*/\s*天",
              r"(\d{2,4})\s*元?\s*/\s*天"):
        m = re.search(p, text)
        if m:
            return m.group(0).strip()
    return ""


def _parse_city(text: str) -> str:
    if "远程" in text:
        return "远程"
    for c in CITY_LIST:
        if c in text:
            return c
    return ""


def _parse_duration(text: str):
    m = re.search(r"(?:至少|连续|实习期)?\s*([1-9]|1[0-2])\s*个月", text)
    return int(m.group(1)) if m else None


def _parse_deadline(text: str) -> str:
    m = re.search(r"截止(?:日期|时间)?[：:\s]*(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


def _prepare_job(body: dict, profile: dict) -> dict:
    jd = str(body.get("jd_raw") or "")
    title = str(body.get("title") or "").strip()
    company = str(body.get("company") or "").strip()
    if not title:
        raise ValueError("title 必填")
    if not company:
        raise ValueError("company 必填")
    text = f"{title}\n{jd}"
    days = body.get("days_per_week") or _parse_days(jd)
    months = body.get("duration_months") or _parse_duration(jd)
    job = {
        "company": company,
        "title": title,
        "city": str(body.get("city") or "") or _parse_city(jd),
        "salary": str(body.get("salary") or "") or _parse_salary(jd),
        "days_per_week": int(days) if days else None,
        "duration_months": int(months) if months else None,
        "degree": str(body.get("degree") or ""),
        "grade_hint": [g for g in GRADE_WORDS if g in text],
        "source": str(body.get("source") or ""),
        "url": str(body.get("url") or ""),
        "deadline": str(body.get("deadline") or "") or _parse_deadline(jd),
        "posted_at": str(body.get("posted_at") or ""),
        "jd_raw": jd,
        "skills_hit": [w for w in SKILL_WORDS if w in text],
        "risk_flags": [w for w in RISK_WORDS if w in text
                       and not any(x in jd for x in ("不收费", "无需押金", "不收取任何费用"))],
        "notes": str(body.get("notes") or ""),
        "status": body.get("status") if body.get("status") in STATUSES else "new",
        "priority": "",
        "match_score": 0,
        "match_reasons": [],
        "gaps": [],
        "eligibility": "unknown",
        "created_at": body.get("created_at") or db.now(),
        "updated_at": db.now(),
        "applied_at": body.get("applied_at") or "",
        "events": [],
    }
    if job.get("match_score") and body.get("match_score"):
        job["match_score"] = int(body["match_score"])
    return scoring.score_one(job, profile)


def _dedupe(jobs: list[dict], job: dict) -> bool:
    url = (job.get("url") or "").rstrip("/").lower()
    for j in jobs:
        if url and (j.get("url") or "").rstrip("/").lower() == url:
            return True
        if (j.get("company") == job.get("company") and j.get("title") == job.get("title")):
            return True
    return False


def _next_job_id(jobs: list[dict]) -> str:
    prefix = f"job_{date.today():%Y%m%d}_"
    nums = [0]
    for j in jobs:
        if str(j.get("id", "")).startswith(prefix):
            try:
                nums.append(int(str(j["id"]).rsplit("_", 1)[1]))
            except (IndexError, ValueError):
                pass
    return f"{prefix}{max(nums) + 1:03d}"


def _next_id(prefix: str, items: list[dict]) -> str:
    nums = [0]
    for x in items:
        try:
            nums.append(int(str(x.get("id", "")).split("_")[-1]))
        except ValueError:
            pass
    return f"{prefix}_{max(nums) + 1:03d}"


def _check_text(profile: dict, jobs: list[dict]) -> str:
    active = [j for j in jobs if j["status"] not in ("rejected", "dropped", "offer")]
    urgent, follow, todo, interviews = [], [], [], []
    for j in active:
        left = views._days_until(j.get("deadline"))
        if left is not None and 0 <= left <= 3 and j["status"] != "applied":
            urgent.append((left, j))
        if j["status"] == "applied":
            d = views._last_event_days(j)
            if d is not None and d >= 5:
                follow.append((d, j))
        if j["status"] == "tailored":
            todo.append(("简历已定制，等你去投", j))
        elif j["status"] == "shortlisted":
            todo.append(("需要定制简历/招呼语", j))
        elif j["status"] == "new" and j.get("match_score", 0) >= 75:
            todo.append(("高匹配新岗位，先判断", j))
        if j["status"] in ("interview", "replied"):
            interviews.append(j)

    lines = [f"【Compass】{date.today().month}月{date.today().day}日 · {profile.get('name') or '你'}"]
    if not jobs:
        lines += ["", "岗位池还是空的。先做一件小事：让 agent「帮我找实习」，或者粘贴一个 JD 说「帮我记一个岗位」。"]
        return "\n".join(lines)
    if urgent:
        lines.append("\n🔴 快截止了")
        for left, j in sorted(urgent, key=lambda x: x[0]):
            lines.append(f"· {j['company']} · {j['title']}（{'今天' if left == 0 else f'还剩 {left} 天'}截止）")
    if interviews:
        lines.append("\n📅 面试/沟通中")
        for j in interviews:
            lines.append(f"· {j['company']} · {j['title']}")
    if todo:
        lines.append("\n🟡 今天可以推进")
        for reason, j in todo[:6]:
            lines.append(f"· {j['company']} · {j['title']} — {reason}")
    if follow:
        lines.append("\n🟠 投了没动静，该跟进")
        for d, j in sorted(follow, key=lambda x: -x[0])[:5]:
            lines.append(f"· {j['company']} · {j['title']}（已 {d} 天）")
    stats = views._stats(profile, jobs)
    lines.append(f"\n📊 本周投递 {stats['this_week']}/{stats['weekly_target']}")
    return "\n".join(lines)


class Handler(BaseHTTPRequestHandler):
    server_version = "Compass/1.0"

    # ---------- helpers ----------
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8", headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code: int, obj, headers=None):
        self._send(code, _json_bytes(obj), headers=headers)

    def _error(self, code: int, message: str):
        self._json(code, {"error": message})

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("请求体必须是 UTF-8 JSON")

    def _pat(self) -> str:
        head = self.headers.get("Authorization", "")
        if head.lower().startswith("bearer "):
            return head[7:].strip()
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if qs.get("token"):
            return qs["token"][0]
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        if "compass_pat" in cookie:
            return cookie["compass_pat"].value
        return ""

    def _user(self, con, required: bool = True):
        token = self._pat()
        if not token:
            if required:
                self._error(401, "missing PAT")
            return None
        user = db.get_user_by_pat(con, auth.hash_token(token))
        if not user and required:
            self._error(401, "invalid PAT")
        return user

    def _user_by_handle(self, con, handle: str):
        return db.get_user(con, handle)

    # ---------- routing ----------
    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_PUT(self):
        self._route("PUT")

    def do_DELETE(self):
        self._route("DELETE")

    def _route(self, method: str):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            if method == "GET" and path == "/health":
                return self._json(200, {"ok": True, "service": "compass", "version": 1})
            if method == "GET" and path == "/schema":
                return self._json(200, schema.DOCUMENT)
            if method == "GET" and path == "/.well-known/compass.json":
                return self._json(200, schema.DOCUMENT)
            if method == "GET" and path == "/llms.txt":
                text = (
                    "# Compass\n\n"
                    "Compass is an agent-operated career exploration and job-hunting service.\n"
                    "The agent reasons; Compass stores, validates, versions, renders, and shares.\n\n"
                    f"Schema: {config.BASE_URL}/schema\n"
                    f"Health: {config.BASE_URL}/health\n"
                    "Auth: Authorization: Bearer cmp_pat_... (identity credential, not an AI credit)\n"
                    "Views: /u/{handle}, /u/{handle}/explore, /u/{handle}/resume/{id}/v/{n}\n"
                    "Shares: /s/{slug} (read-only, revocable)\n"
                )
                return self._send(200, text.encode("utf-8"), "text/plain; charset=utf-8")
            if method == "POST" and path == "/auth/claim":
                return self._claim()
            if path.startswith("/s/"):
                return self._share_view(path[3:])
            if path.startswith("/u/"):
                return self._user_view(path, qs)
            if path.startswith("/api/"):
                return self._api(method, path, qs)
            if method == "GET" and path == "/":
                return self._send(200, b"Compass service. See /schema", "text/plain; charset=utf-8")
            self._error(404, "not found")
        except ValueError as exc:
            self._error(400, str(exc))
        except Exception as exc:  # noqa: BLE001
            self._error(500, f"internal error: {exc}")

    # ---------- auth ----------
    def _claim(self):
        body = self._body()
        handle = str(body.get("handle") or "").strip().lower()
        if not auth.valid_handle(handle):
            raise ValueError("handle 需为 2-32 位小写字母/数字/连字符")
        token = auth.new_token()
        with db.connect() as con:
            if db.get_user(con, handle):
                return self._error(409, "handle 已被占用")
            uid = db.create_user(con, handle, auth.hash_token(token))
            db.kv_set(con, uid, "profile", DEFAULT_PROFILE)
            db.kv_set(con, uid, "self", DEFAULT_SELF)
            db.kv_set(con, uid, "explore", DEFAULT_EXPLORE)
            db.kv_set(con, uid, "stories", {"stories": []})
        self._json(200, {
            "handle": handle,
            "token": token,
            "dashboard": f"{config.BASE_URL}/u/{handle}",
            "note": "PAT 是认账凭证，不是 AI 额度。只保存在本机。",
        })

    # ---------- API ----------
    def _api(self, method: str, path: str, qs: dict):
        with db.connect() as con:
            user = self._user(con)
            if not user:
                return
            uid = user["id"]
            handle = user["handle"]

            if path == "/api/whoami" and method == "GET":
                return self._json(200, {"handle": handle, "dashboard": f"/u/{handle}"})

            if path == "/api/next" and method == "GET":
                self_data = db.kv_get(con, uid, "self", DEFAULT_SELF)
                exp = db.kv_get(con, uid, "explore", DEFAULT_EXPLORE)
                return self._json(200, dialogue.next_step(self_data, exp))

            if path == "/api/explore/suggest" and method == "GET":
                self_data = db.kv_get(con, uid, "self", DEFAULT_SELF)
                exp = db.kv_get(con, uid, "explore", DEFAULT_EXPLORE)
                return self._json(200, {"suggestions": views._suggestions(self_data, exp)})

            if path == "/api/explore/add-suggested" and method == "POST":
                self_data = db.kv_get(con, uid, "self", DEFAULT_SELF)
                exp = db.kv_get(con, uid, "explore", DEFAULT_EXPLORE)
                existing = {m.get("title") for m in exp.get("missions", [])}
                picks = [m for m in views._suggestions(self_data, exp) if m.get("title") not in existing]
                for m in picks:
                    m["id"] = _next_id("m", exp.setdefault("missions", []))
                    m["status"] = "todo"
                    exp["missions"].append(m)
                db.kv_set(con, uid, "explore", exp)
                return self._json(200, {"added": len(picks)})

            if path == "/api/radar" and method == "POST":
                body = self._body()
                keyword = str(body.get("keyword") or "").strip()
                city = str(body.get("city") or "").strip()
                if not keyword:
                    raise ValueError("keyword 必填")
                profile = db.kv_get(con, uid, "profile", DEFAULT_PROFILE)
                candidates = radar.collect(
                    keyword, city,
                    pages=int(body.get("pages") or 1),
                    detail=bool(body.get("detail", True)),
                    limit=int(body.get("limit") or 30),
                )
                existing = db.list_jobs(con, uid)
                added = []
                for c in candidates:
                    tags = c.get("tags") or []
                    payload = {
                        "company": c.get("company"), "title": c.get("title"),
                        "city": c.get("city"), "salary": c.get("salary"),
                        "days_per_week": c.get("days_per_week"),
                        "duration_months": c.get("duration_months"),
                        "degree": c.get("degree"), "deadline": c.get("deadline"),
                        "source": "实习僧", "url": c.get("url"),
                        "jd_raw": (c.get("jd_raw") or "") + "\n标签：" + " / ".join(tags),
                    }
                    try:
                        job = _prepare_job(payload, profile)
                    except ValueError:
                        continue
                    if _dedupe(existing, job):
                        continue
                    job["id"] = _next_job_id(existing)
                    db.save_job(con, uid, job, is_new=True)
                    existing.append(job)
                    added.append({"id": job["id"], "company": job["company"],
                                  "title": job["title"], "score": job["match_score"]})
                return self._json(200, {"found": len(candidates), "added": len(added), "jobs": added})

            if path in ("/api/profile", "/api/self", "/api/explore", "/api/stories"):
                kind = path.split("/")[-1]
                if method == "GET":
                    return self._json(200, db.kv_get(con, uid, kind, {}))
                if method == "PUT":
                    body = self._body()
                    if not isinstance(body, dict):
                        raise ValueError("body 必须是对象")
                    checker = {
                        "profile": validate.profile,
                        "self": validate.self_profile,
                        "explore": validate.explore,
                        "stories": validate.stories,
                    }.get(kind)
                    issues = checker(body) if checker else []
                    if issues:
                        return self._json(400, {"error": "schema 校验失败", "issues": issues})
                    if kind == "explore":
                        body.setdefault("paths", [])
                        body.setdefault("missions", [])
                        for p in body["paths"]:
                            p.setdefault("status", "considering")
                        for m in body["missions"]:
                            if not m.get("id"):
                                m["id"] = _next_id("m", body["missions"])
                            m.setdefault("status", "todo")
                    db.kv_set(con, uid, kind, body)
                    return self._json(200, {"ok": True, "kind": kind})

            if path == "/api/jobs" and method == "GET":
                status = (qs.get("status") or [""])[0]
                q = (qs.get("q") or [""])[0]
                return self._json(200, {"jobs": db.list_jobs(con, uid, status, q)})

            if path == "/api/jobs" and method == "POST":
                body = self._body()
                issues = validate.job(body)
                if issues:
                    return self._json(400, {"error": "schema 校验失败", "issues": issues})
                profile = db.kv_get(con, uid, "profile", DEFAULT_PROFILE)
                job = _prepare_job(body, profile)
                existing = db.list_jobs(con, uid)
                if _dedupe(existing, job):
                    return self._error(409, "岗位已存在（按链接或公司+岗位去重）")
                job["id"] = _next_job_id(existing)
                db.save_job(con, uid, job, is_new=True)
                return self._json(200, {"job": job})

            if path.startswith("/api/jobs/"):
                parts = path.split("/")
                job_id = parts[3]
                job = db.get_job(con, uid, job_id)
                if not job:
                    return self._error(404, "岗位不存在")
                if len(parts) == 4 and method == "GET":
                    job["events"] = db.job_events(con, job_id)
                    return self._json(200, job)
                if len(parts) == 5 and parts[4] == "advance" and method == "POST":
                    body = self._body()
                    target = str(body.get("to") or "")
                    if target not in STATUSES:
                        raise ValueError(f"未知状态：{target}")
                    old = job["status"]
                    if target != old and not body.get("force") and target not in NEXT_STATES.get(old, set()):
                        return self._error(400, f"不允许从 {old} 到 {target}")
                    job["status"] = target
                    if target == "applied":
                        job["applied_at"] = db.now()
                    db.save_job(con, uid, job, is_new=False)
                    db.add_event(con, job_id, "status", old, target, str(body.get("note") or ""))
                    return self._json(200, {"job": job})

            if path == "/api/score" and method == "POST":
                body = self._body()
                profile = db.kv_get(con, uid, "profile", DEFAULT_PROFILE)
                jobs = db.list_jobs(con, uid)
                target = body.get("id")
                for j in jobs:
                    if target and j["id"] != target:
                        continue
                    scoring.score_one(j, profile)
                    db.save_job(con, uid, j, is_new=False)
                return self._json(200, {"ok": True, "scored": 1 if target else len(jobs)})

            if path == "/api/check" and method == "GET":
                profile = db.kv_get(con, uid, "profile", DEFAULT_PROFILE)
                return self._json(200, {"text": _check_text(profile, db.list_jobs(con, uid))})

            if path == "/api/resume" and method == "POST":
                body = self._body()
                job_id = body.get("job_id") or None
                style = body.get("style") or "both"
                if style not in ("visual", "ats", "both"):
                    raise ValueError("style 必须是 visual / ats / both")
                profile = db.kv_get(con, uid, "profile", DEFAULT_PROFILE)
                stories = db.kv_get(con, uid, "stories", {"stories": []}).get("stories", [])
                job = None
                if job_id:
                    job = db.get_job(con, uid, job_id)
                    if not job:
                        return self._error(404, "岗位不存在")
                data = body.get("data") or resume_mod.build_data(profile, stories, job)
                if body.get("data"):
                    issues = validate.resume(data)
                    if issues:
                        return self._json(400, {"error": "resume schema 校验失败", "issues": issues})
                data = resume_mod.fill_from_profile(resume_mod.normalize(data), profile)
                rec = db.get_or_create_resume(con, uid, job_id, data.get("headline") or (job or {}).get("title", "简历"))
                version = db.next_version(con, rec["id"])
                styles = ["visual", "ats"] if style == "both" else [style]
                out = {}
                for s in styles:
                    html_body = resume_mod.render_visual(data, profile) if s == "visual" else resume_mod.render_ats(data, profile)
                    db.save_resume_version(con, rec["id"], version, s, data, html_body)
                    out[s] = f"/u/{handle}/resume/{rec['id']}/v/{version}?style={s}"
                return self._json(200, {"resume_id": rec["id"], "version": version, "views": out})

            if path.startswith("/api/resume/") and method == "GET":
                rid = path.split("/")[3]
                return self._json(200, {"versions": db.list_resume_versions(con, rid)})

            if path == "/api/share" and method == "POST":
                body = self._body()
                kind = str(body.get("kind") or "")
                if kind not in ("dashboard", "explore", "resume"):
                    raise ValueError("kind 必须是 dashboard / explore / resume")
                slug = auth.new_share_slug()
                con.execute(
                    "INSERT INTO shares(slug,user_id,kind,target,version,created_at,revoked) VALUES(?,?,?,?,?,?,0)",
                    (slug, uid, kind, str(body.get("target") or ""), body.get("version"), db.now()),
                )
                return self._json(200, {"slug": slug, "url": f"/s/{slug}"})

            if path.startswith("/api/share/") and method == "DELETE":
                slug = path.split("/")[3]
                con.execute("UPDATE shares SET revoked=1 WHERE slug=? AND user_id=?", (slug, uid))
                return self._json(200, {"ok": True})

            self._error(404, "not found")

    # ---------- views ----------
    def _user_view(self, path: str, qs: dict):
        parts = path.strip("/").split("/")
        if len(parts) < 2:
            return self._error(404, "not found")
        handle = parts[1]
        with db.connect() as con:
            user = self._user_by_handle(con, handle)
            if not user:
                return self._error(404, "用户不存在")
            token = self._pat()
            viewer = db.get_user_by_pat(con, auth.hash_token(token)) if token else None
            allowed = bool(viewer and viewer["id"] == user["id"])
            # share token check
            if not allowed:
                st = (qs.get("share") or [""])[0]
                if st:
                    row = con.execute(
                        "SELECT * FROM shares WHERE slug=? AND revoked=0", (st,)
                    ).fetchone()
                    allowed = bool(row and row["user_id"] == user["id"])
            if not allowed:
                return self._send(
                    401,
                    "<meta charset='utf-8'><h2>需要访问凭证</h2>"
                    "<p>用 <code>compass open</code> 打开，或在 URL 后加 <code>?token=你的PAT</code>。</p>".encode("utf-8"),
                    "text/html; charset=utf-8",
                )
            profile = db.kv_get(con, user["id"], "profile", DEFAULT_PROFILE)
            uid = user["id"]
            if len(parts) == 2:
                jobs = db.list_jobs(con, uid)
                for j in jobs:
                    j["events"] = db.job_events(con, j["id"])
                html = views.dashboard(profile, jobs, handle)
                headers = {"Set-Cookie": f"compass_pat={token}; HttpOnly; SameSite=Lax; Path=/"} if token else {}
                return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8", headers)
            if parts[2] == "explore":
                self_data = db.kv_get(con, uid, "self", DEFAULT_SELF)
                exp = db.kv_get(con, uid, "explore", DEFAULT_EXPLORE)
                html = views.explore(profile, self_data, exp, handle)
                return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if parts[2] == "resume" and len(parts) >= 4:
                rid = parts[3]
                style = (qs.get("style") or ["visual"])[0]
                version = None
                if len(parts) >= 6 and parts[4] == "v":
                    version = int(parts[5])
                row = (db.get_resume_version(con, rid, version, style) if version
                       else db.latest_resume_version(con, rid, style))
                if not row and style != "visual":
                    row = db.latest_resume_version(con, rid, "visual")
                if not row:
                    return self._error(404, "简历版本不存在")
                return self._send(200, row["html"].encode("utf-8"), "text/html; charset=utf-8")
        self._error(404, "not found")

    def _share_view(self, slug: str):
        with db.connect() as con:
            row = con.execute(
                "SELECT * FROM shares WHERE slug=? AND revoked=0", (slug,)
            ).fetchone()
            if not row:
                return self._error(404, "分享不存在或已撤销")
            user = con.execute("SELECT * FROM users WHERE id=?", (row["user_id"],)).fetchone()
            if not user:
                return self._error(404, "分享不存在")
            handle = user["handle"]
            profile = db.kv_get(con, user["id"], "profile", DEFAULT_PROFILE)
            kind = row["kind"]
            if kind == "dashboard":
                jobs = db.list_jobs(con, user["id"])
                for j in jobs:
                    j["events"] = db.job_events(con, j["id"])
                html = views.dashboard(profile, jobs, handle)
            elif kind == "explore":
                self_data = db.kv_get(con, user["id"], "self", DEFAULT_SELF)
                exp = db.kv_get(con, user["id"], "explore", DEFAULT_EXPLORE)
                html = views.explore(profile, self_data, exp, handle)
            elif kind == "resume":
                rid = row["target"] or ""
                style = "visual"
                version = row["version"]
                r = (db.get_resume_version(con, rid, version, style) if version
                     else db.latest_resume_version(con, rid, style))
                if not r:
                    return self._error(404, "简历版本不存在")
                html = r["html"]
            else:
                return self._error(404, "未知分享类型")
            return self._send(200, views.read_only(html, "只读分享").encode("utf-8"), "text/html; charset=utf-8")


def serve(host: str = "127.0.0.1", port: int = config.DEFAULT_PORT) -> None:
    db.init_db()
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Compass listening on http://{host}:{port}")
    print(f"schema: http://{host}:{port}/schema")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    serve()
