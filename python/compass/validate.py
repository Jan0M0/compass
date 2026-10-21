# -*- coding: utf-8 -*-
"""Lightweight schema validation. No dependencies, explicit error messages."""
from __future__ import annotations

STATUSES = {"new", "shortlisted", "tailored", "applied", "replied", "interview", "offer", "rejected", "dropped"}


def _str(obj, key, issues, required=False):
    v = obj.get(key)
    if v in (None, "") and not required:
        return
    if not isinstance(v, str):
        issues.append(f"{key} 必须是字符串")


def _list(obj, key, issues):
    if key in obj and not isinstance(obj[key], list):
        issues.append(f"{key} 必须是数组")


def profile(obj: dict) -> list[str]:
    issues: list[str] = []
    for k in ("name", "school", "college", "major", "grade"):
        _str(obj, k, issues)
    for k in ("cities", "directions", "skills", "toolchain", "languages"):
        _list(obj, k, issues)
    if "graduation_year" in obj and obj["graduation_year"] not in (None, ""):
        if not isinstance(obj["graduation_year"], int):
            issues.append("graduation_year 必须是整数")
    if "available" in obj and not isinstance(obj["available"], dict):
        issues.append("available 必须是对象")
    if "contact" in obj and not isinstance(obj["contact"], dict):
        issues.append("contact 必须是对象")
    return issues


def self_profile(obj: dict) -> list[str]:
    issues: list[str] = []
    for k in ("interests", "strengths", "values", "dislikes", "constraints",
              "experiments", "questions", "people"):
        _list(obj, k, issues)
    if "facts" in obj and not isinstance(obj["facts"], dict):
        issues.append("facts 必须是对象")
    return issues


def explore(obj: dict) -> list[str]:
    issues: list[str] = []
    _list(obj, "paths", issues)
    _list(obj, "missions", issues)
    for p in obj.get("paths", []) or []:
        if not isinstance(p, dict) or not p.get("name"):
            issues.append("paths[] 需要 name")
        elif p.get("status") not in (None, "", "considering", "testing", "ruled_out"):
            issues.append(f"path status 非法：{p.get('status')}")
    for m in obj.get("missions", []) or []:
        if not isinstance(m, dict) or not m.get("title"):
            issues.append("missions[] 需要 title")
        elif m.get("status") not in (None, "", "todo", "doing", "done"):
            issues.append(f"mission status 非法：{m.get('status')}")
    return issues


def stories(obj: dict) -> list[str]:
    issues: list[str] = []
    _list(obj, "stories", issues)
    for s in obj.get("stories", []) or []:
        if not isinstance(s, dict) or not s.get("title"):
            issues.append("stories[] 需要 title")
    return issues


def resume(obj: dict) -> list[str]:
    issues: list[str] = []
    for k in ("headline", "summary"):
        _str(obj, k, issues, required=True)
    if not isinstance(obj.get("projects"), list) or not obj["projects"]:
        issues.append("projects 必须是非空数组")
    else:
        for i, p in enumerate(obj["projects"]):
            if not isinstance(p, dict) or not p.get("name"):
                issues.append(f"projects[{i}] 需要 name")
            elif "bullets" in p and not isinstance(p["bullets"], list):
                issues.append(f"projects[{i}].bullets 必须是数组")
    if "competencies" in obj and not isinstance(obj["competencies"], list):
        issues.append("competencies 必须是数组")
    return issues


def job(obj: dict) -> list[str]:
    issues: list[str] = []
    for k in ("company", "title"):
        if not isinstance(obj.get(k), str) or not obj.get(k).strip():
            issues.append(f"{k} 必填")
    if "status" in obj and obj["status"] not in STATUSES:
        issues.append(f"status 非法：{obj['status']}")
    return issues
