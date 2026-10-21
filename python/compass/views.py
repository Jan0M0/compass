# -*- coding: utf-8 -*-
"""Server-rendered URL views.

The service owns presentation; the agent never regenerates a local HTML file.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

from . import scoring

TEMPLATES = Path(__file__).parent / "templates"

STATUS_LABEL = {
    "new": "待判断", "shortlisted": "已入选", "tailored": "已定制",
    "applied": "已投递", "replied": "已回复", "interview": "面试中",
    "offer": "已录用", "rejected": "未通过", "dropped": "已放弃",
}
STATUS_ORDER = list(STATUS_LABEL)
NEXT_ACTION = {
    "new": "先判断值不值得投", "shortlisted": "定制简历与招呼语",
    "tailored": "去平台投递", "applied": "等回复，5 天后跟进",
    "replied": "约面试时间", "interview": "准备面试",
    "offer": "谈条件 / 决定去不去", "rejected": "记录原因，复盘",
    "dropped": "—",
}
WEEKLY_QUESTIONS = [
    "最近有什么事，你做的时候会忘记看手机？",
    "这周有没有哪一天过得特别快？那天在干什么？",
    "有没有什么事，做完之后你是有劲的，而不是被抽干的？",
    "别人夸过你什么，而你自己也觉得「这确实是我」？",
    "你最不能接受的工作状态是什么？",
    "你有没有一件事，一直想做但没开始？为什么没开始？",
    "如果选错了，最坏会怎样？能不能回头？",
    "你羡慕过谁？羡慕 TA 的结果，还是 TA 的日常？",
    "如果接下来半年只能验证一件事，你会选什么？",
    "最近有什么让你开心的小事？",
]


def _days_until(value: str | None):
    if not value:
        return None
    try:
        d = date.fromisoformat(value[:10])
    except ValueError:
        return None
    return (d - date.today()).days


def _last_event_days(job: dict):
    stamps = [e.get("at") for e in job.get("events", []) if e.get("at")]
    if not stamps:
        return None
    try:
        return (date.today() - date.fromisoformat(max(stamps)[:10])).days
    except ValueError:
        return None


def _stats(profile: dict, jobs: list[dict]) -> dict:
    counts = Counter(j["status"] for j in jobs)
    week_start = date.today().fromordinal(date.today().toordinal() - date.today().weekday())
    applied_week = 0
    for j in jobs:
        if not j.get("applied_at"):
            continue
        try:
            if date.fromisoformat(j["applied_at"][:10]) >= week_start:
                applied_week += 1
        except ValueError:
            pass
    return {
        "total": len(jobs),
        "applied": sum(counts.get(s, 0) for s in ("applied", "replied", "interview", "offer")),
        "interview": sum(counts.get(s, 0) for s in ("interview", "offer")),
        "offer": counts.get("offer", 0),
        "this_week": applied_week,
        "weekly_target": profile.get("weekly_target") or 8,
        "by_status": {s: counts.get(s, 0) for s in STATUS_ORDER},
    }


def _today(jobs: list[dict]) -> list[dict]:
    items = []
    for j in jobs:
        if j["status"] in ("rejected", "dropped", "offer"):
            continue
        left = _days_until(j.get("deadline"))
        if left is not None and 0 <= left <= 3 and j["status"] != "applied":
            items.append({"kind": "urgent", "job": j["id"],
                          "text": f"{j['company']} · {j['title']} — {'今天' if left == 0 else f'还剩 {left} 天'}截止"})
        if j["status"] == "tailored":
            items.append({"kind": "todo", "job": j["id"], "text": f"{j['company']} · {j['title']} — 简历已定制，去投递"})
        elif j["status"] == "shortlisted":
            items.append({"kind": "todo", "job": j["id"], "text": f"{j['company']} · {j['title']} — 定制简历/招呼语"})
        elif j["status"] == "new" and j.get("match_score", 0) >= 75:
            items.append({"kind": "todo", "job": j["id"], "text": f"{j['company']} · {j['title']} — 高匹配，先判断"})
        if j["status"] == "applied":
            d = _last_event_days(j)
            if d is not None and d >= 5:
                items.append({"kind": "follow", "job": j["id"], "text": f"{j['company']} · {j['title']} — 已投 {d} 天，该跟进"})
        if j["status"] in ("interview", "replied"):
            items.append({"kind": "interview", "job": j["id"], "text": f"{j['company']} · {j['title']} — 准备面试"})
    order = {"urgent": 0, "interview": 1, "todo": 2, "follow": 3}
    items.sort(key=lambda x: order.get(x["kind"], 9))
    return items[:12]


def _inject(template: str, payload: dict, handle: str, extra: dict | None = None) -> str:
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    html = template.replace("/*__DATA__*/", blob)
    html = html.replace("{{EXPLORE_URL}}", f"/u/{handle}/explore")
    html = html.replace("{{DASHBOARD_URL}}", f"/u/{handle}")
    for k, v in (extra or {}).items():
        html = html.replace("{{" + k + "}}", v)
    return html


def dashboard(profile: dict, jobs: list[dict], handle: str) -> str:
    payload = {
        "generated_at": date.today().isoformat() + "T00:00:00",
        "profile": profile,
        "jobs": jobs,
        "stats": _stats(profile, jobs),
        "today": _today(jobs),
        "next_action": NEXT_ACTION,
        "status_label": STATUS_LABEL,
        "status_order": STATUS_ORDER,
    }
    tpl = (TEMPLATES / "dashboard.html").read_text(encoding="utf-8")
    return _inject(tpl, payload, handle)


def _completion(self_data: dict) -> dict:
    return {
        "兴趣": [len(self_data.get("interests") or []), 3],
        "优势": [len(self_data.get("strengths") or []), 3],
        "价值": [len(self_data.get("values") or []), 3],
        "约束": [len(self_data.get("constraints") or []), 3],
        "实验": [len(self_data.get("experiments") or []), 3],
    }


def _suggestions(self_data: dict, explore: dict) -> list[dict]:
    out = []
    if not self_data.get("interests"):
        out.append({"title": "能量取证：最近 3 个月，你自愿花时间做的事",
                    "why": "兴趣不是「我喜欢什么」，而是「我不用人催也会去做」。",
                    "how": "列 5 件事：做了什么、花了多久、做完更有劲还是更累。",
                    "time": "20 分钟", "cost": "0"})
    if self_data.get("interests") and not self_data.get("strengths"):
        out.append({"title": "优势取证：问 2 个了解你的人",
                    "why": "自己说的优势容易是想象，别人观察到的更可靠。",
                    "how": "问同一句：「你觉得我做什么事比同龄人轻松？」记录原话。",
                    "time": "30 分钟", "cost": "0"})
    if not self_data.get("values"):
        out.append({"title": "价值排序：你愿意为什么付出代价",
                    "why": "方向不是「哪个好」，而是「你愿意承担哪种代价」。",
                    "how": "稳定、收入、自主、成长、影响力、关系、清闲、名声，两两比较，留下前 3。",
                    "time": "20 分钟", "cost": "0"})
    if not self_data.get("constraints"):
        out.append({"title": "约束清单：和家里聊一次底线",
                    "why": "不考虑约束的规划是幻想；但约束不等于判决。",
                    "how": "问清：家里能支持到什么时候、对城市/行业有没有硬要求、你最不能接受什么。",
                    "time": "40 分钟", "cost": "0"})
    if not explore.get("paths"):
        out.append({"title": "路径扫盲：读 5 个不同方向的岗位 JD",
                    "why": "没见过的东西无法选择。",
                    "how": "从实习僧/BOSS 各找 1 个：运营、产品、数据、人力、设计。标出让你兴奋/反感的词。",
                    "time": "1 小时", "cost": "0"})
    if not self_data.get("experiments"):
        out.append({"title": "3 小时小实验：做一个小产出",
                    "why": "想不清楚的事，做一次比想十次有用。",
                    "how": "选一个方向，产出一样东西：一篇分析、一张图、一个表格、一次访谈。",
                    "time": "3 小时", "cost": "0-50 元"})
    return out[:4]


def explore(profile: dict, self_data: dict, explore_data: dict, handle: str) -> str:
    existing = [m for m in (explore_data.get("missions") or []) if m.get("status") in ("todo", "doing")]
    seen = {m.get("title") for m in existing}
    suggested = [m for m in _suggestions(self_data, explore_data) if m.get("title") not in seen]
    payload = {
        "generated_at": date.today().isoformat() + "T00:00:00",
        "profile": profile,
        "self": self_data,
        "explore": explore_data,
        "completion": _completion(self_data),
        "suggestions": (existing + suggested)[:4],
        "weekly_question": WEEKLY_QUESTIONS[date.today().isocalendar()[1] % len(WEEKLY_QUESTIONS)],
    }
    tpl = (TEMPLATES / "explore.html").read_text(encoding="utf-8")
    return _inject(tpl, payload, handle)


def read_only(html: str, label: str = "只读分享") -> str:
    banner = (
        '<div style="position:fixed;left:0;right:0;bottom:0;padding:8px 14px;'
        'background:#0d1b2a;color:#fff;font:12px/1.6 -apple-system,\'PingFang SC\',sans-serif;'
        'text-align:center;z-index:9999">' + label + " · 由 Compass 生成 · 内容来自本人素材库</div>"
    )
    html = html.replace("<body>", "<body><style>.navlink,.nav{display:none}</style>", 1)
    return html.replace("</body>", banner + "</body>")
