# -*- coding: utf-8 -*-
"""Compass CLI — the single entry point an agent calls.

The CLI never reasons. It validates input shape, calls the service, and prints
the result or a URL. All state lives in the service.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from . import auth, config, db, handoff as handoff_mod, schema

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


# ---------- config / server lifecycle ----------
def _cfg() -> dict:
    return config.read_config()


def _base() -> str:
    cfg = _cfg()
    return cfg.get("base_url") or config.BASE_URL


def _token() -> str:
    cfg = _cfg()
    token = cfg.get("token") or os.environ.get("COMPASS_TOKEN", "")
    if not token:
        raise SystemExit("还没有登录。先跑：compass init --handle your-name")
    return token


def _request(method: str, path: str, body=None, token: str | None = None, timeout: int = 30):
    url = _base().rstrip("/") + path
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"error": raw}
        return exc.code, payload
    except urllib.error.URLError as exc:
        return 0, {"error": str(exc)}


def _healthy() -> bool:
    try:
        code, body = _request("GET", "/health", timeout=1)
        return code == 200 and body.get("service") == "compass"
    except Exception:  # noqa: BLE001
        return False


def _port_free(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _free_port(start: int) -> int:
    for p in range(start, start + 50):
        if _port_free(p):
            return p
    raise SystemExit("找不到可用端口")


def _spawn_server() -> None:
    cfg = _cfg()
    port = int(cfg.get("port") or config.DEFAULT_PORT)
    if not _port_free(port) or _healthy():
        port = _free_port(port + 1)
        cfg["port"] = port
        cfg["base_url"] = f"http://127.0.0.1:{port}"
        config.write_config(cfg)
    env = os.environ.copy()
    env["COMPASS_PORT"] = str(port)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent) + os.pathsep + env.get("PYTHONPATH", "")
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    proc = subprocess.Popen(
        [sys.executable, "-m", "compass.server"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs,
    )
    config.ensure_home()
    (config.HOME / "server.json").write_text(
        json.dumps({"pid": proc.pid, "port": port}, ensure_ascii=False), encoding="utf-8"
    )


def ensure_server() -> None:
    if _healthy():
        return
    _spawn_server()
    for _ in range(50):
        if _healthy():
            return
        time.sleep(0.1)
    raise SystemExit("服务没能启动。手动运行：compass serve")


def _print_url(path: str, with_token: bool = True) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        url = path
    else:
        url = _base().rstrip("/") + path
    if with_token:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}token={_token()}"
    return url


# ---------- commands ----------
def cmd_init(args) -> None:
    cfg = _cfg()
    if cfg.get("token") and not args.force:
        code, body = _request("GET", "/api/whoami", token=cfg["token"])
        if code == 200:
            print(f"已经登录：{body.get('handle')}")
            print("看板：" + _print_url(body.get("dashboard", "/")))
            return
    ensure_server()
    code, body = _request("POST", "/auth/claim", {"handle": args.handle})
    if code != 200:
        raise SystemExit(f"认领失败：{body.get('error')}")
    cfg.update({
        "handle": body["handle"],
        "token": body["token"],
        "base_url": _base(),
        "port": int(_cfg().get("port") or config.DEFAULT_PORT),
    })
    config.write_config(cfg)
    print(f"已创建身份：{body['handle']}")
    print(f"PAT 已写入 {config.CONFIG_PATH}（这是认账凭证，不是 AI 额度）")
    print("看板：" + _print_url(body["dashboard"]))


def cmd_login(args) -> None:
    ensure_server()
    code, body = _request("GET", "/api/whoami", token=args.token)
    if code != 200:
        raise SystemExit(f"PAT 无效：{body.get('error')}")
    cfg = _cfg()
    cfg.update({"handle": body["handle"], "token": args.token, "base_url": _base(),
                "port": int(_cfg().get("port") or config.DEFAULT_PORT)})
    config.write_config(cfg)
    print(f"已登录：{body['handle']}")


def cmd_whoami(args) -> None:
    ensure_server()
    code, body = _request("GET", "/api/whoami", token=_token())
    if code != 200:
        raise SystemExit(body.get("error"))
    print(json.dumps(body, ensure_ascii=False, indent=2))


SCHEMA_BRIEF = """COMPASS · 写入速查

身份
  compass state                          # 一次拿到：是否登录、画像完整度、待办、看板 URL
  compass init --handle <name>           # 只在未登录时用；先问用户用哪个名字

画像（profile）
  compass profile --set name=小雨 --set school=宁波工程学院
  compass profile --set cities='["杭州","宁波"]' --set directions='["产品","运营"]'
  compass profile --set skills='["Excel","PPT"]'
  compass profile --set available.days_per_week=3 --set available.months=3
  python 语法：字符串用引号包住，数组用 JSON

自我认知（self）
  compass self --add-interest '{"name":"写作","evidence":"...","energy":"高","confidence":"确认"}'
  compass self --add-strength '{"name":"...","evidence":"..."}'
  compass self --add-value '{"name":"自主性","rank":1,"note":"..."}'
  compass self --add-constraint '{"name":"...","type":"家庭","note":"..."}'
  compass self --add-question "我到底喜欢和人还是和数据打交道？"
  compass self --merge '{"values":[...],"constraints":[...]}'

素材（stories）
  compass stories --add '{"title":"课程项目","org":"...","bullets":["做了什么","结果"]}'

探索（explore）
  compass explore --suggest               # 3-4 个建议
  compass explore --add-suggested
  compass explore --done m_001 --result "..." --energy 高 --learned "..."
  compass explore --path '{"name":"内容运营","status":"testing","note":"..."}'
  compass explore --set-path 内容运营 --status ruled_out --note "..."

岗位（jobs）
  compass jobs radar --keyword 产品实习 --city 杭州 --pages 1
  compass jobs add --json '{"company":"...","title":"...","city":"杭州","jd_raw":"..."}'
  compass jobs list
  compass jobs show --id job_xxx
  compass jobs advance --id job_xxx --to applied --note "BOSS 投递"

简历（resume）
  compass resume --job job_xxx --style both
  → 返回 visual / ats 两个 URL

分享（share）
  compass share --kind dashboard|explore|resume --target <id>

字段名
  profile: name school college major grade graduation_year cities directions skills
           toolchain languages available{ days_per_week months start }
           contact{ phone email wechat portfolio } weekly_target
  self:    facts interests strengths values dislikes constraints experiments
           questions people preferences
  resume:  headline summary education focus projects business_exposure
           competencies skill_groups toolchain links languages
"""


def cmd_state(args) -> None:
    ensure_server()
    cfg = _cfg()
    out = {
        "service": "compass",
        "base_url": _base(),
        "logged_in": bool(cfg.get("token")),
        "handle": cfg.get("handle") or None,
    }
    if not out["logged_in"]:
        out["next"] = "compass init --handle <name>（先问用户用哪个名字）"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    code, profile = _request("GET", "/api/profile", token=_token())
    code, self_data = _request("GET", "/api/self", token=_token())
    code, explore = _request("GET", "/api/explore", token=_token())
    code, jobs = _request("GET", "/api/jobs", token=_token())
    profile = profile if isinstance(profile, dict) else {}
    self_data = self_data if isinstance(self_data, dict) else {}
    explore = explore if isinstance(explore, dict) else {}
    job_list = jobs.get("jobs", []) if isinstance(jobs, dict) else []
    counts = {}
    for j in job_list:
        counts[j.get("status", "new")] = counts.get(j.get("status", "new"), 0) + 1
    out.update({
        "dashboard": f"/u/{out['handle']}",
        "profile": {
            "name": profile.get("name") or "",
            "missing": [k for k in ("name", "school", "major", "grade", "cities", "directions")
                        if not profile.get(k)],
            "cities": profile.get("cities") or [],
            "directions": profile.get("directions") or [],
        },
        "self": {
            "interests": len(self_data.get("interests") or []),
            "strengths": len(self_data.get("strengths") or []),
            "values": len(self_data.get("values") or []),
            "constraints": len(self_data.get("constraints") or []),
            "experiments": len(self_data.get("experiments") or []),
            "open_questions": sum(1 for q in (self_data.get("questions") or [])
                                  if (q.get("status") if isinstance(q, dict) else "") != "answered"),
        },
        "explore": {
            "paths": len(explore.get("paths") or []),
            "missions_todo": sum(1 for m in (explore.get("missions") or []) if m.get("status") != "done"),
            "missions_done": sum(1 for m in (explore.get("missions") or []) if m.get("status") == "done"),
        },
        "jobs": {"total": len(job_list), "by_status": counts},
    })
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_next(args) -> None:
    ensure_server()
    code, body = _request("GET", "/api/next", token=_token())
    if code != 200:
        raise SystemExit(body.get("error"))
    print(json.dumps(body, ensure_ascii=False, indent=2))


def cmd_schema(args) -> None:
    if getattr(args, "brief", False):
        print(SCHEMA_BRIEF)
        return
    print(json.dumps(schema.DOCUMENT, ensure_ascii=False, indent=2))


def cmd_serve(args) -> None:
    from . import server
    db.init_db()
    server.serve(args.host, args.port)


def cmd_start(args) -> None:
    ensure_server()
    print(f"服务已在 {_base()} 运行")


def cmd_stop(args) -> None:
    path = config.HOME / "server.json"
    if not path.exists():
        print("没有记录的本地服务进程。")
        return
    info = json.loads(path.read_text(encoding="utf-8"))
    pid = info.get("pid")
    if not pid:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        else:
            os.kill(int(pid), 15)
        print(f"已停止服务进程 {pid}")
    except Exception as exc:  # noqa: BLE001
        print(f"停止失败：{exc}")
    path.unlink(missing_ok=True)


def cmd_status(args) -> None:
    print(f"base_url: {_base()}")
    print(f"healthy: {_healthy()}")
    cfg = _cfg()
    print(f"handle: {cfg.get('handle') or '（未登录）'}")
    print(f"db: {config.DB_PATH}")


def cmd_open(args) -> None:
    path = args.path or "/"
    if path == "/":
        cfg = _cfg()
        path = f"/u/{cfg.get('handle')}" if cfg.get("handle") else "/"
    url = _print_url(path, with_token=not args.no_token)
    print(url)
    if not args.print_only:
        webbrowser.open(url)


def _get_obj(kind: str) -> dict:
    code, body = _request("GET", f"/api/{kind}", token=_token())
    if code != 200:
        raise SystemExit(body.get("error"))
    return body


def _put_obj(kind: str, obj: dict) -> None:
    code, body = _request("PUT", f"/api/{kind}", obj, token=_token())
    if code != 200:
        raise SystemExit(body.get("error"))
    print(f"{kind} 已更新")


def cmd_profile(args) -> None:
    ensure_server()
    obj = _get_obj("profile")
    if args.show or not args.set:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
        return
    for pair in args.set:
        if "=" not in pair:
            raise SystemExit(f"格式应为 key=value：{pair}")
        key, raw = pair.split("=", 1)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        parts = key.split(".")
        cur = obj
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = value
    _put_obj("profile", obj)


def cmd_self(args) -> None:
    ensure_server()
    obj = _get_obj("self")
    changed = False
    if args.add_interest:
        obj.setdefault("interests", []).append(json.loads(args.add_interest)); changed = True
    if args.add_strength:
        obj.setdefault("strengths", []).append(json.loads(args.add_strength)); changed = True
    if args.add_value:
        obj.setdefault("values", []).append(json.loads(args.add_value)); changed = True
    if args.add_constraint:
        obj.setdefault("constraints", []).append(json.loads(args.add_constraint)); changed = True
    if args.add_question:
        obj.setdefault("questions", []).append({"q": args.add_question, "status": "open"}); changed = True
    if args.fact:
        for pair in args.fact:
            key, raw = pair.split("=", 1)
            obj.setdefault("facts", {})[key] = raw
        changed = True
    if args.merge:
        incoming = json.loads(args.merge)
        for k, v in incoming.items():
            if isinstance(v, list) and isinstance(obj.get(k), list):
                obj[k].extend(v)
            elif isinstance(v, dict) and isinstance(obj.get(k), dict):
                obj[k].update(v)
            else:
                obj[k] = v
        changed = True
    if changed:
        _put_obj("self", obj)
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_explore(args) -> None:
    ensure_server()
    obj = _get_obj("explore")
    self_obj = _get_obj("self")
    if args.suggest:
        code, body = _request("GET", "/api/explore/suggest", token=_token())
        if code == 200:
            for m in body.get("suggestions", []):
                print(f"· {m['title']}（{m.get('time','')}）")
                print(f"  {m.get('why','')}")
                print(f"  怎么做：{m.get('how','')}")
        return
    if args.add_suggested:
        code, body = _request("POST", "/api/explore/add-suggested", token=_token())
        if code != 200:
            raise SystemExit(body.get("error"))
        print(f"已加入 {body.get('added', 0)} 个实验")
        obj = _get_obj("explore")
    if args.add_mission:
        obj.setdefault("missions", []).append(json.loads(args.add_mission))
    if args.done:
        for m in obj.get("missions", []):
            if m.get("id") == args.done:
                m["status"] = "done"
                m["result"] = args.result or m.get("result", "")
                m["energy"] = args.energy or m.get("energy", "")
                m["learned"] = args.learned or m.get("learned", "")
                self_obj.setdefault("experiments", []).append({
                    "title": m.get("title", ""), "date": db.now()[:10],
                    "did": m.get("how", ""), "result": m.get("result", ""),
                    "energy": m.get("energy", ""), "learned": m.get("learned", ""),
                })
                _put_obj("self", self_obj)
                break
        else:
            raise SystemExit(f"没找到实验：{args.done}")
    if args.path:
        obj.setdefault("paths", []).append(json.loads(args.path))
    if args.set_path:
        for p in obj.get("paths", []):
            if p.get("name") == args.set_path:
                if args.status:
                    p["status"] = args.status
                if args.note:
                    p["note"] = args.note
                break
    if args.add_mission or args.done or args.path or args.set_path:
        _put_obj("explore", obj)
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_jobs(args) -> None:
    ensure_server()
    if args.action == "radar":
        payload = {
            "keyword": args.keyword, "city": args.city,
            "pages": args.pages, "detail": not args.no_detail, "limit": args.limit,
        }
        code, resp = _request("POST", "/api/radar", payload, token=_token(), timeout=300)
        if code != 200:
            raise SystemExit(resp.get("error"))
        print(f"扫描 {resp['found']} 条，新增 {resp['added']} 条")
        for j in resp.get("jobs", []):
            print(f"  {j['id']}  {j['score']:<4} {j['company']} · {j['title']}")
        return
    if args.action == "list":
        code, body = _request("GET", "/api/jobs", token=_token())
        if code != 200:
            raise SystemExit(body.get("error"))
        for j in body.get("jobs", []):
            print(f"{j['id']}  {j.get('priority','')}/{j.get('match_score',0):<4} "
                  f"{j.get('status',''):<11} {j.get('company','')[:16]:<18}{j.get('title','')[:26]}")
        return
    if args.action == "add":
        body = json.loads(args.json) if args.json else {}
        if args.file:
            body.update(json.loads(Path(args.file).read_text(encoding="utf-8")))
        if args.jd_file:
            body["jd_raw"] = Path(args.jd_file).read_text(encoding="utf-8")
        code, resp = _request("POST", "/api/jobs", body, token=_token())
        if code != 200:
            raise SystemExit(resp.get("error"))
        j = resp["job"]
        print(f"已录入：{j['id']}  {j['company']} · {j['title']}  {j.get('match_score')}分")
        return
    if args.action == "show":
        code, resp = _request("GET", f"/api/jobs/{args.id}", token=_token())
        if code != 200:
            raise SystemExit(resp.get("error"))
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return
    if args.action == "advance":
        code, resp = _request("POST", f"/api/jobs/{args.id}/advance",
                             {"to": args.to, "note": args.note or "", "force": args.force},
                             token=_token())
        if code != 200:
            raise SystemExit(resp.get("error"))
        print(f"{args.id} → {resp['job']['status']}")


def cmd_score(args) -> None:
    ensure_server()
    code, body = _request("POST", "/api/score", {"id": args.id} if args.id else {}, token=_token())
    if code != 200:
        raise SystemExit(body.get("error"))
    print(f"已重算 {body.get('scored')} 个岗位")


def cmd_check(args) -> None:
    ensure_server()
    code, body = _request("GET", "/api/check", token=_token())
    if code != 200:
        raise SystemExit(body.get("error"))
    print(body["text"])


def cmd_resume(args) -> None:
    ensure_server()
    payload = {"job_id": args.job or None, "style": args.style}
    if args.data:
        payload["data"] = json.loads(Path(args.data).read_text(encoding="utf-8"))
    code, body = _request("POST", "/api/resume", payload, token=_token())
    if code != 200:
        raise SystemExit(body.get("error"))
    print(f"简历 {body['resume_id']} · 版本 v{body['version']}")
    for style, path in body.get("views", {}).items():
        print(f"  {style}: {_print_url(path)}")


def cmd_stories(args) -> None:
    ensure_server()
    obj = _get_obj("stories")
    if args.add:
        obj.setdefault("stories", []).append(json.loads(args.add))
        _put_obj("stories", obj)
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_import(args) -> None:
    ensure_server()
    src = Path(args.src)
    counts = {}
    for kind in ("profile", "self", "explore", "stories"):
        path = src / f"{kind}.json"
        if not path.exists():
            continue
        obj = json.loads(path.read_text(encoding="utf-8"))
        code, resp = _request("PUT", f"/api/{kind}", obj, token=_token())
        if code != 200:
            raise SystemExit(resp.get("error"))
        counts[kind] = "ok"
    jobs_path = src / "jobs.json"
    if jobs_path.exists() and not args.no_jobs:
        jobs = json.loads(jobs_path.read_text(encoding="utf-8")).get("jobs", [])
        added = 0
        for j in jobs:
            payload = {
                "company": j.get("company"), "title": j.get("title"),
                "city": j.get("city"), "salary": j.get("salary"),
                "days_per_week": j.get("days_per_week"),
                "duration_months": j.get("duration_months"),
                "degree": j.get("degree"), "source": j.get("source"),
                "url": j.get("url"), "deadline": j.get("deadline"),
                "jd_raw": j.get("jd_raw"), "notes": j.get("notes"),
                "status": j.get("status"), "created_at": j.get("created_at"),
                "applied_at": j.get("applied_at"),
            }
            code, resp = _request("POST", "/api/jobs", payload, token=_token())
            if code == 200:
                added += 1
        counts["jobs"] = added
    _request("POST", "/api/score", {}, token=_token())
    print(json.dumps(counts, ensure_ascii=False, indent=2))


def cmd_handoff(args) -> None:
    if args.action in ("prompt", "interview"):
        print(handoff_mod.extract("PROMPT" if args.action == "prompt" else "INTERVIEW"))
        return

    if not args.file:
        raise SystemExit("用法：compass handoff import <文件.md>")
    ensure_server()
    src = Path(args.file).expanduser()
    if not src.exists():
        raise SystemExit(f"文件不存在：{src}")
    text = src.read_text(encoding="utf-8")
    try:
        payload = handoff_mod.parse_json_block(text)
    except (ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"解析失败：{exc}\n请让上一个 AI 按 references/handoff-protocol.md 的格式重新输出。")

    folder = config.HOME / "handoffs"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"handoff_{db.now()[:10]}_{src.stem}.md"
    dest.write_text(text, encoding="utf-8", newline="\n")

    self_data = _get_obj("self")
    profile = _get_obj("profile")
    summary = handoff_mod.merge(self_data, profile, payload)
    self_data.setdefault("sources", []).append({
        "type": "handoff", "date": db.now()[:10], "path": str(dest),
    })
    _put_obj("self", self_data)
    _put_obj("profile", profile)

    summary["saved"] = str(dest)
    summary["next"] = "先复述 5 条给用户确认；未经确认不能当事实使用。"
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def cmd_share(args) -> None:
    ensure_server()
    body = {"kind": args.kind, "target": args.target or "", "version": args.version}
    code, resp = _request("POST", "/api/share", body, token=_token())
    if code != 200:
        raise SystemExit(resp.get("error"))
    print("分享链接（只读，可撤销）：")
    print(_print_url(resp["url"], with_token=False))


def cmd_export(args) -> None:
    ensure_server()
    data = {}
    for kind in ("profile", "self", "explore", "stories"):
        code, body = _request("GET", f"/api/{kind}", token=_token())
        if code == 200:
            data[kind] = body
    code, body = _request("GET", "/api/jobs", token=_token())
    if code == 200:
        data["jobs"] = body.get("jobs", [])
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.stdout:
        print(text)
        return
    out = Path(args.out or "compass_export.json")
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"已导出：{out.resolve()}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="compass", description="Compass — agent-operated career service")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="认领 handle，创建身份")
    s.add_argument("--handle", required=True)
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("login", help="用已有 PAT 登录")
    s.add_argument("token")
    s.set_defaults(func=cmd_login)

    s = sub.add_parser("whoami", help="当前身份")
    s.set_defaults(func=cmd_whoami)

    s = sub.add_parser("state", help="一次拿到服务状态、画像完整度、待办与看板 URL")
    s.set_defaults(func=cmd_state)

    s = sub.add_parser("next", help="探索模式：返回下一个该问的问题")
    s.set_defaults(func=cmd_next)

    s = sub.add_parser("schema", help="打印服务 schema（agent 先读这个）")
    s.add_argument("--brief", action="store_true", help="只打印写入速查")
    s.set_defaults(func=cmd_schema)

    s = sub.add_parser("serve", help="前台启动服务")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=config.DEFAULT_PORT)
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser("start", help="后台启动服务")
    s.set_defaults(func=cmd_start)

    s = sub.add_parser("stop", help="停止后台服务")
    s.set_defaults(func=cmd_stop)

    s = sub.add_parser("status", help="服务状态")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("open", help="打开看板 URL")
    s.add_argument("path", nargs="?", default="")
    s.add_argument("--no-token", action="store_true")
    s.add_argument("--print-only", action="store_true")
    s.set_defaults(func=cmd_open)

    s = sub.add_parser("profile", help="查看/更新画像")
    s.add_argument("--show", action="store_true")
    s.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    s.set_defaults(func=cmd_profile)

    s = sub.add_parser("self", help="自我认知档案")
    s.add_argument("--fact", action="append", default=[])
    s.add_argument("--add-interest")
    s.add_argument("--add-strength")
    s.add_argument("--add-value")
    s.add_argument("--add-constraint")
    s.add_argument("--add-question")
    s.add_argument("--merge")
    s.set_defaults(func=cmd_self)

    s = sub.add_parser("explore", help="路径假设与实验")
    s.add_argument("--show", action="store_true")
    s.add_argument("--suggest", action="store_true")
    s.add_argument("--add-suggested", action="store_true")
    s.add_argument("--add-mission")
    s.add_argument("--done")
    s.add_argument("--result")
    s.add_argument("--energy")
    s.add_argument("--learned")
    s.add_argument("--path")
    s.add_argument("--set-path")
    s.add_argument("--status")
    s.add_argument("--note")
    s.set_defaults(func=cmd_explore)

    s = sub.add_parser("jobs", help="岗位池")
    s.add_argument("action", choices=["list", "add", "show", "advance", "radar"])
    s.add_argument("--json")
    s.add_argument("--file")
    s.add_argument("--jd-file")
    s.add_argument("--id")
    s.add_argument("--to")
    s.add_argument("--note")
    s.add_argument("--force", action="store_true")
    s.add_argument("--keyword")
    s.add_argument("--city")
    s.add_argument("--pages", type=int, default=1)
    s.add_argument("--no-detail", action="store_true")
    s.add_argument("--limit", type=int, default=30)
    s.set_defaults(func=cmd_jobs)

    s = sub.add_parser("score", help="确定性打分")
    s.add_argument("--id")
    s.set_defaults(func=cmd_score)

    s = sub.add_parser("check", help="今日待办")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("resume", help="生成并发布简历版本")
    s.add_argument("--job")
    s.add_argument("--style", default="both", choices=["visual", "ats", "both"])
    s.add_argument("--data")
    s.set_defaults(func=cmd_resume)

    s = sub.add_parser("stories", help="素材库（STAR 故事）")
    s.add_argument("--add")
    s.set_defaults(func=cmd_stories)

    s = sub.add_parser("import", help="从旧版 JSON 工作区导入")
    s.add_argument("--from", dest="src", required=True)
    s.add_argument("--no-jobs", action="store_true")
    s.set_defaults(func=cmd_import)

    s = sub.add_parser("handoff", help="交接：打印提示词 / 导入别的 AI 整理的画像")
    s.add_argument("action", choices=["prompt", "interview", "import"])
    s.add_argument("file", nargs="?", default="")
    s.set_defaults(func=cmd_handoff)

    s = sub.add_parser("share", help="生成只读分享链接")
    s.add_argument("--kind", default="dashboard", choices=["dashboard", "explore", "resume"])
    s.add_argument("--target")
    s.add_argument("--version", type=int)
    s.set_defaults(func=cmd_share)

    s = sub.add_parser("export", help="导出全部数据")
    s.add_argument("--out")
    s.add_argument("--stdout", action="store_true")
    s.set_defaults(func=cmd_export)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
