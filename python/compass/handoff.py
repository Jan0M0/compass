# -*- coding: utf-8 -*-
"""Handoff: move a user's self-knowledge from another AI into Compass.

The prompt is stored in references/handoff-protocol.md. Import merges only what
the handoff explicitly contains, marks provenance, and reports conflicts instead
of overwriting confirmed facts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REF = Path(__file__).resolve().parents[2] / "references" / "handoff-protocol.md"


def extract(marker: str) -> str:
    text = REF.read_text(encoding="utf-8")
    start = text.find(f"<!-- {marker}:START -->")
    end = text.find(f"<!-- {marker}:END -->")
    if start < 0 or end < 0:
        raise ValueError(f"提示词标记缺失：{marker}")
    return text[start + len(f"<!-- {marker}:START -->"):end].strip()


def parse_json_block(text: str) -> dict:
    m = re.search(r"```json\s*(.*?)```", text, re.S)
    if not m:
        raise ValueError("没有找到 ```json 摘要块")
    return json.loads(m.group(1))


def _canon(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def _merge_list(dst: list, src: list, kind: str = "") -> int:
    seen = {_canon(x) for x in dst}
    added = 0
    for item in src or []:
        if not isinstance(item, dict):
            continue
        item = dict(item)
        item.setdefault("source", "handoff")
        if kind in ("interests", "strengths") and not item.get("confidence"):
            item["confidence"] = "猜测"
        if _canon(item) not in seen:
            dst.append(item)
            seen.add(_canon(item))
            added += 1
    return added


def merge(self_data: dict, profile: dict, payload: dict) -> dict:
    summary = {"imported": {}, "filled_profile": [], "conflicts": []}

    facts = payload.get("facts") or {}
    sf = self_data.setdefault("facts", {})
    for k, v in facts.items():
        if not v:
            continue
        if sf.get(k) and sf[k] != v:
            summary["conflicts"].append(f"facts.{k}: 已有「{sf[k]}」，交接说「{v}」")
        elif not sf.get(k):
            sf[k] = v

    for key, profile_key in (("name", "name"), ("school", "school"), ("major", "major"),
                             ("grade", "grade"), ("city", "city")):
        v = facts.get(key)
        if not v:
            continue
        if profile.get(profile_key) and profile[profile_key] != v:
            summary["conflicts"].append(f"profile.{profile_key}: 已有「{profile[profile_key]}」，交接说「{v}」")
        elif not profile.get(profile_key):
            profile[profile_key] = v
            summary["filled_profile"].append(profile_key)

    if facts.get("city") and not profile.get("cities"):
        profile["cities"] = [facts["city"]]
        summary["filled_profile"].append("cities")

    for field in ("interests", "strengths", "values", "dislikes", "constraints", "experiments"):
        n = _merge_list(self_data.setdefault(field, []), payload.get(field) or [], field)
        summary["imported"][field] = n

    qs = []
    for q in payload.get("questions") or []:
        if isinstance(q, str):
            qs.append({"q": q, "status": "open", "source": "handoff"})
        elif isinstance(q, dict) and q.get("q"):
            q = dict(q)
            q.setdefault("status", "open")
            q.setdefault("source", "handoff")
            qs.append(q)
    summary["imported"]["questions"] = _merge_list(self_data.setdefault("questions", []), qs)

    prefs = payload.get("preferences") or {}
    sp = self_data.setdefault("preferences", {})
    for k, v in prefs.items():
        if not v:
            continue
        if sp.get(k) and sp[k] != v:
            summary["conflicts"].append(f"preferences.{k}: 已有「{sp[k]}」，交接说「{v}」")
        elif not sp.get(k):
            sp[k] = v

    return summary
