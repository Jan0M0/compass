# -*- coding: utf-8 -*-
"""Deterministic match scoring. No model calls."""
from __future__ import annotations

import re
from datetime import date, datetime

DIRECTION_KEYWORDS = {
    "产品": ["产品", "产品经理", "产品运营", "用户研究", "用户调研", "需求分析", "原型", "PRD", "交互"],
    "运营": ["运营", "新媒体", "内容", "社群", "活动", "用户增长", "电商运营", "直播", "小红书", "抖音", "公众号"],
    "数据": ["数据", "分析", "BI", "报表", "SQL", "Excel", "统计", "指标", "可视化", "数据运营"],
    "市场": ["市场", "品牌", "营销", "推广", "公关", "商务", "BD", "渠道"],
    "设计": ["设计", "UI", "UX", "视觉", "平面", "插画"],
    "人力": ["HR", "人力", "招聘", "培训", "员工关系"],
    "财务": ["财务", "会计", "审计", "税务", "出纳"],
    "技术": ["开发", "前端", "后端", "测试", "算法", "Python", "Java", "运维"],
    "法务": ["法务", "合规", "合同"],
    "行政": ["行政", "助理", "文秘", "办公室"],
}
HIGH_GRADE = ["大三", "大四", "研一", "研二", "研三"]


def _text(job: dict) -> str:
    return " ".join([
        job.get("title", ""), job.get("company", ""), job.get("jd_raw", ""),
        " ".join(job.get("skills_hit", []) or []),
    ])


def _hits(text: str, words) -> list[str]:
    return [w for w in words if w and w in text]


def _days_since(value: str | None):
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value).date()
    except ValueError:
        try:
            d = datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return (date.today() - d).days


def score_one(job: dict, profile: dict) -> dict:
    text = _text(job)
    reasons, gaps = [], []
    score = 0.0

    best_dir, best_hits = "", []
    for d in profile.get("directions") or []:
        hits = _hits(text, DIRECTION_KEYWORDS.get(d, [d]))
        if len(hits) > len(best_hits):
            best_dir, best_hits = d, hits
    if best_hits:
        score += min(30, 12 + 4 * len(best_hits))
        reasons.append(f"方向命中「{best_dir}」：{'、'.join(best_hits[:4])}")
    else:
        gaps.append("岗位描述与目标方向没有明显交集")

    grade_hint = " ".join(job.get("grade_hint") or [])
    degree = job.get("degree") or ""
    my_year = profile.get("graduation_year")
    eligibility, grade_score = "maybe", 12
    if any(k in grade_hint for k in ["大一", "大二"]) or "接受大一大二" in text or "不限年级" in text:
        grade_score, eligibility = 20, "eligible"
        reasons.append("明确接受大一/大二或不限年级")
    elif any(k in grade_hint for k in HIGH_GRADE):
        grade_score, eligibility = 0, "ineligible"
        gaps.append(f"岗位偏好：{'、'.join([g for g in HIGH_GRADE if g in grade_hint])}")
    elif my_year:
        years = [int(y) for y in re.findall(r"(20\d{2})届", text)]
        if years and my_year not in years:
            grade_score, eligibility = 0, "ineligible"
            gaps.append(f"岗位面向 {years[0]} 届，你是 {my_year} 届")
        elif years:
            grade_score, eligibility = 20, "eligible"
            reasons.append(f"岗位面向 {my_year} 届")
    if degree in ("硕士", "博士"):
        grade_score = min(grade_score, 5)
        gaps.append(f"学历要求：{degree}")
    score += grade_score

    cities = profile.get("cities") or []
    job_city = job.get("city") or ""
    if job_city and job_city in cities:
        score += 15
        reasons.append(f"城市匹配：{job_city}")
    elif any(c in job_city for c in cities) or job_city in ("远程", "全国"):
        if job_city in ("远程", "全国") and profile.get("remote_ok"):
            score += 13
            reasons.append("支持远程/全国")
        else:
            score += 10
            reasons.append(f"城市接近：{job_city}")
    elif not job_city:
        score += 6
        gaps.append("岗位未写城市，需确认")
    else:
        gaps.append(f"城市不在偏好内：{job_city}")

    my_skills = [s.lower() for s in (profile.get("skills") or [])]
    hit = [s for s in (job.get("skills_hit") or []) if s.lower() in my_skills]
    if hit:
        score += min(15, 5 * len(hit))
        reasons.append(f"技能命中：{'、'.join(hit[:5])}")
    else:
        missing = (job.get("skills_hit") or [])[:5]
        if missing:
            gaps.append(f"岗位提到但你未填写的技能：{'、'.join(missing)}")

    avail = profile.get("available") or {}
    my_days = avail.get("days_per_week") or 0
    job_days = job.get("days_per_week")
    if job_days:
        if my_days and job_days <= my_days:
            score += 10
            reasons.append(f"每周 {job_days} 天，你能到 {my_days} 天")
        elif my_days:
            score += max(0, 10 - 4 * (job_days - my_days))
            gaps.append(f"岗位要每周 {job_days} 天，你只有 {my_days} 天")
        else:
            score += 5
    else:
        score += 6

    my_months = avail.get("months") or 0
    job_months = job.get("duration_months")
    if job_months and my_months:
        if job_months <= my_months:
            score += 5
        else:
            score += 1
            gaps.append(f"岗位要 {job_months} 个月，你能做 {my_months} 个月")
    else:
        score += 3

    posted_days = _days_since(job.get("posted_at"))
    if posted_days is None:
        score += 3
    elif posted_days <= 7:
        score += 5
        reasons.append("近 7 天内发布")
    elif posted_days <= 30:
        score += 2

    if job.get("risk_flags"):
        score -= 25
    score = max(0, min(100, round(score)))
    if eligibility == "ineligible":
        score = min(score, 40)

    job["match_score"] = score
    job["match_reasons"] = reasons
    job["gaps"] = gaps
    job["eligibility"] = eligibility
    job["priority"] = "A" if score >= 75 and eligibility != "ineligible" else "B" if score >= 55 else "C"
    return job
