# -*- coding: utf-8 -*-
"""Resume data building and rendering (visual + ATS)."""
from __future__ import annotations

import html
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from . import scoring

TITLES_ZH = {
    "summary": "概述",
    "education": "教育背景",
    "focus": "当前方向",
    "projects": "项目经历",
    "business": "业务接触",
    "competencies": "核心能力",
    "skills": "技能",
    "toolchain": "工具链",
    "links": "作品与链接",
    "languages": "语言",
}
TITLES_EN = {
    "summary": "Summary",
    "education": "Education",
    "focus": "Current Focus",
    "projects": "Projects",
    "business": "Business Exposure",
    "competencies": "Core Competencies",
    "skills": "Skills",
    "toolchain": "Toolchain",
    "links": "Links",
    "languages": "Languages",
}


def select_stories(stories: list[dict], job: dict | None, limit: int = 5) -> list[dict]:
    if not job:
        return stories[:limit]
    text = scoring._text(job).lower()
    ranked = []
    for s in stories:
        words = [w.lower() for w in (s.get("skills") or [])]
        words += [w.lower() for w in (s.get("title", "").split())]
        hits = sum(1 for w in words if w and w in text)
        ranked.append((hits, s))
    ranked.sort(key=lambda x: -x[0])
    picked = [s for h, s in ranked if h > 0][:limit]
    if len(picked) < limit:
        picked += [s for _, s in ranked if s not in picked][:limit - len(picked)]
    return picked


def build_data(profile: dict, stories: list[dict], job: dict | None) -> dict:
    directions = profile.get("directions") or []
    target = (job.get("title") if job else "") or (
        f"{directions[0]}实习生" if directions else "实习"
    )
    avail = profile.get("available") or {}
    selected = select_stories(stories, job)
    projects = [{
        "name": s.get("title", ""),
        "role": " · ".join([x for x in [s.get("org"), s.get("role")] if x]),
        "bullets": s.get("bullets") or [],
    } for s in selected]

    # 能力标签：素材里出现的技能优先，其次画像技能
    comps = []
    for s in selected:
        for k in (s.get("skills") or []):
            if k not in comps:
                comps.append(k)
    for k in (profile.get("skills") or []):
        if k not in comps:
            comps.append(k)
    comps = comps[:9]

    skills = list(profile.get("skills") or [])
    gy = profile.get("graduation_year")
    period = profile.get("education_period") or (f"{int(gy) - 4} – {gy}" if gy else "")
    return {
        "job_id": job.get("id", "") if job else "",
        "lang": profile.get("resume_lang", "zh"),
        "headline": f"{target} · {profile.get('major','')} · {profile.get('grade','')}".strip(" ·"),
        "summary": (
            f"{profile.get('school','')}{profile.get('major','')}{profile.get('grade','')}，"
            f"目标岗位：{target}。每周可到岗 {avail.get('days_per_week','?')} 天，"
            f"可连续实习 {avail.get('months','?')} 个月。"
        ).strip(),
        "education": {
            "school": profile.get("school", ""),
            "college": profile.get("college", ""),
            "period": period,
            "major": profile.get("major", ""),
            "note": profile.get("education_note", ""),
        },
        "focus": directions or [],
        "projects": projects,
        "business_exposure": [],
        "competencies": comps,
        "skill_groups": list(profile.get("skill_groups") or []),
        "toolchain": list(profile.get("toolchain") or []),
        "links": {
            "title": "作品与链接",
            "items": list(profile.get("links") or []),
            "url": (profile.get("contact") or {}).get("portfolio", ""),
        },
        "languages": list(profile.get("languages") or []),
    }


def normalize(data: dict) -> dict:
    """兼容旧版 experiences/skills 结构。"""
    if "projects" not in data:
        data["projects"] = [{
            "name": e.get("title", ""),
            "role": " · ".join([x for x in [e.get("org"), e.get("role")] if x]),
            "bullets": e.get("bullets") or [],
        } for e in data.get("experiences", [])]
    if "skill_groups" not in data and data.get("skills"):
        data["skill_groups"] = []
    data.setdefault("education", {})
    data.setdefault("focus", [])
    data.setdefault("business_exposure", [])
    data.setdefault("competencies", data.get("skills") or [])
    data.setdefault("toolchain", [])
    data.setdefault("links", {"title": "作品与链接", "items": [], "url": ""})
    data.setdefault("languages", [])
    data.setdefault("lang", "zh")
    return data


def fill_from_profile(data: dict, profile: dict) -> dict:
    """补齐旧数据/手动数据里缺的教育信息和抬头，不从空白处编造。"""
    edu = data.setdefault("education", {})
    edu["school"] = edu.get("school") or profile.get("school", "")
    edu["college"] = edu.get("college") or profile.get("college", "")
    edu["major"] = edu.get("major") or profile.get("major", "")
    if not edu.get("period"):
        gy = profile.get("graduation_year")
        edu["period"] = profile.get("education_period") or (
            f"{int(gy) - 4} – {gy}" if gy else ""
        )
    if not data.get("headline"):
        data["headline"] = " · ".join(x for x in [
            profile.get("major"), profile.get("grade")
        ] if x)
    if not data.get("summary"):
        avail = profile.get("available") or {}
        data["summary"] = (
            f"{profile.get('school','')}{profile.get('major','')}{profile.get('grade','')}，"
            f"每周可到岗 {avail.get('days_per_week','?')} 天，"
            f"可连续实习 {avail.get('months','?')} 个月。"
        )
    return data


def esc(v) -> str:
    return html.escape(str(v or ""))


def titles(data: dict) -> dict:
    base = TITLES_EN if data.get("lang") == "en" else TITLES_ZH
    base = dict(base)
    base.update(data.get("section_titles") or {})
    return base


def contact_line(profile: dict) -> str:
    c = profile.get("contact") or {}
    city = profile.get("city") or (profile.get("cities") or [""])[0]
    bits = [city, c.get("phone"), c.get("email"), c.get("portfolio")]
    bits = [esc(x) for x in bits if x]
    return '<span class="sep">|</span>'.join(f"<span>{b}</span>" for b in bits)


def render_visual(data: dict, profile: dict) -> str:
    t = titles(data)
    edu = data.get("education") or {}
    name = profile.get("name") or "姓名"

    focus = "".join(f'<span class="focus-tag">{esc(x)}</span>' for x in data.get("focus", []))

    projects_html = ""
    for p in data.get("projects", []):
        bullets = "".join(f"<li>{esc(b)}</li>" for b in p.get("bullets", []) if b)
        projects_html += f"""
        <div class="project">
          <div class="project-header">
            <span class="project-name">{esc(p.get('name'))}</span>
            <span class="project-role">{esc(p.get('role'))}</span>
          </div>
          <ul>{bullets or '<li class="muted">（待补充：做了什么、怎么做的、结果如何）</li>'}</ul>
        </div>"""

    business = ""
    if data.get("business_exposure"):
        items = "".join(f"<li>{esc(x)}</li>" for x in data["business_exposure"])
        business = f'<div class="section"><div class="section-title">{esc(t["business"])}</div><div class="project"><ul>{items}</ul></div></div>'

    comps = "".join(f'<span class="comp-tag">{esc(x)}</span>' for x in data.get("competencies", []))
    comp_title = t["competencies"] if data.get("skill_groups") else t["skills"]

    skills_html = ""
    for g in data.get("skill_groups", []):
        if not g.get("text"):
            continue
        skills_html += f"""<div class="skill-group"><div class="skill-cat">{esc(g.get('category'))}</div>
        <div class="skill-text">{esc(g.get('text'))}</div></div>"""

    toolchain = "".join(f'<span class="comp-tag">{esc(x)}</span>' for x in data.get("toolchain", []))

    links = data.get("links") or {}
    links_html = ""
    if links.get("items") or links.get("url"):
        items = "".join(f"<div>▸ {esc(x)}</div>" for x in links.get("items", []))
        url = f'<div class="link-url">{esc(links.get("url"))}</div>' if links.get("url") else ""
        links_html = f'<div class="section"><div class="section-title">{esc(links.get("title") or t["links"])}</div><div class="link-box">{items}{url}</div></div>'

    langs_html = ""
    if data.get("languages"):
        rows = "".join(
            f'<div class="info-row"><span class="info-label">{esc(x.get("name"))}</span>'
            f'<span class="info-value">{esc(x.get("level"))}</span></div>'
            for x in data["languages"]
        )
        langs_html = f'<div class="section"><div class="section-title">{esc(t["languages"])}</div>{rows}</div>'

    return f"""<!DOCTYPE html>
<html lang="{'en' if data.get('lang') == 'en' else 'zh-CN'}">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(name)} — Resume</title>
<style>
  @page {{ margin: 0; size: A4; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 9.5pt; line-height: 1.5; color: #1a1a2e; background: #f0f0f0; padding: 20px; }}
  .page {{ width: 210mm; min-height: 297mm; margin: 0 auto; padding: 12mm 15mm; background: #fff;
    box-shadow: 0 2px 8px rgba(0,0,0,.08); box-sizing: border-box; }}
  .header {{ text-align: center; margin-bottom: 10px; }}
  .name {{ font-size: 26pt; font-weight: 700; letter-spacing: 3px; color: #0d1b2a; }}
  .title-line {{ font-size: 10pt; font-weight: 600; color: #1b3a5c; letter-spacing: 1.5px; margin-top: 2px; }}
  .contact {{ margin-top: 4px; font-size: 8.5pt; color: #555; }}
  .contact span {{ margin: 0 6px; }} .contact .sep {{ color: #ccc; }}
  .summary {{ text-align: center; font-size: 8.5pt; color: #444; line-height: 1.55; margin: 8px 0 12px; padding: 0 10px; }}
  .section {{ margin-bottom: 10px; }}
  .section-title {{ font-size: 8.5pt; font-weight: 700; letter-spacing: 2px; text-transform: uppercase;
    color: #1b3a5c; margin-bottom: 5px; padding-bottom: 2px; border-bottom: 1.5px solid #1b3a5c; }}
  .two-col {{ display: flex; gap: 16px; align-items: flex-start; }}
  .col-left {{ flex: 3; }} .col-right {{ flex: 2; }}
  .edu-row {{ display: flex; justify-content: space-between; align-items: baseline; }}
  .edu-school {{ font-weight: 600; font-size: 10pt; }}
  .edu-date {{ font-size: 8.5pt; color: #666; }}
  .edu-major {{ font-size: 9pt; color: #333; }}
  .focus-tags {{ display: flex; flex-wrap: wrap; gap: 5px; }}
  .focus-tag {{ font-size: 7.5pt; padding: 3px 8px; background: #0d1b2a; color: #fff; border-radius: 3px;
    font-weight: 500; white-space: nowrap; }}
  .project {{ margin-bottom: 9px; }}
  .project-header {{ display: flex; justify-content: space-between; align-items: baseline; }}
  .project-name {{ font-weight: 700; font-size: 10pt; color: #0d1b2a; }}
  .project-role {{ font-size: 8pt; color: #888; font-style: italic; }}
  .project ul {{ list-style: none; padding-left: 0; margin-top: 2px; }}
  .project li {{ position: relative; padding-left: 11px; font-size: 8.5pt; line-height: 1.45; margin-bottom: 1px; }}
  .project li::before {{ content: "▸"; position: absolute; left: 0; font-size: 7pt; color: #1b3a5c; }}
  .project li.muted {{ color: #98a0ae; }}
  .skill-group {{ margin-bottom: 4px; }}
  .skill-cat {{ font-size: 8pt; font-weight: 700; color: #1b3a5c; margin-bottom: 1px; }}
  .skill-text {{ font-size: 8pt; color: #444; line-height: 1.4; }}
  .comp-row {{ display: flex; flex-wrap: wrap; gap: 3px; margin-top: 2px; }}
  .comp-tag {{ font-size: 7.5pt; padding: 2px 7px; background: #e8edf4; color: #1b3a5c;
    border-radius: 3px; font-weight: 500; white-space: nowrap; }}
  .info-row {{ display: flex; justify-content: space-between; font-size: 8.5pt; padding: 1px 0; }}
  .info-label {{ color: #555; }} .info-value {{ color: #222; font-weight: 500; }}
  .link-box {{ font-size: 7.5pt; color: #444; line-height: 1.5; }}
  .link-url {{ margin-top: 2px; color: #888; }}
  @media print {{ body {{ background: #fff; padding: 0; }}
    .page {{ box-shadow: none; padding: 12mm 15mm; }} }}
</style></head>
<body><div class="page">
  <div class="header">
    <div class="name">{esc(name)}</div>
    <div class="title-line">{esc(data.get('headline'))}</div>
    <div class="contact">{contact_line(profile)}</div>
  </div>

  <div class="summary">{esc(data.get('summary'))}</div>

  <div class="two-col">
    <div class="col-left">
      <div class="section">
        <div class="section-title">{esc(t['education'])}</div>
        <div class="edu-row"><span class="edu-school">{esc(edu.get('school'))}{(' · ' + esc(edu.get('college'))) if edu.get('college') else ''}</span>
          <span class="edu-date">{esc(edu.get('period'))}</span></div>
        <div class="edu-major">{esc(edu.get('major'))}{(' · ' + esc(edu.get('note'))) if edu.get('note') else ''}</div>
      </div>

      {f'<div class="section"><div class="section-title">{esc(t["focus"])}</div><div class="focus-tags">{focus}</div></div>' if focus else ''}

      <div class="section">
        <div class="section-title">{esc(t['projects'])}</div>
        {projects_html or '<div class="project"><ul><li class="muted">（还没有素材。先让罗盘帮你把课程项目、社团、比赛整理成 STAR 故事。）</li></ul></div>'}
      </div>

      {business}
    </div>

    <div class="col-right">
      {f'<div class="section"><div class="section-title">{esc(comp_title)}</div><div class="comp-row">{comps}</div></div>' if comps else ''}
      {f'<div class="section"><div class="section-title">{esc(t["skills"])}</div>{skills_html}</div>' if skills_html else ''}
      {f'<div class="section"><div class="section-title">{esc(t["toolchain"])}</div><div class="comp-row">{toolchain}</div></div>' if toolchain else ''}
      {links_html}
      {langs_html}
      <div class="section"><div class="section-title"> </div>
        <div style="font-size:7pt;color:#aaa;line-height:1.5;">Sapphire Jan · 罗盘<br>内容来自本人素材库，未编造</div></div>
    </div>
  </div>
</div></body></html>"""


def render_ats(data: dict, profile: dict) -> str:
    """ATS-safe：单栏、标准标题、无标签/双栏/图标，方便机器解析。"""
    t = titles(data)
    edu = data.get("education") or {}
    name = profile.get("name") or "姓名"
    c = profile.get("contact") or {}
    city = profile.get("city") or (profile.get("cities") or [""])[0]
    contact = " | ".join(esc(x) for x in
                          [city, c.get("phone"), c.get("email"), c.get("portfolio")] if x)

    def section(title, body):
        return f'<h2>{esc(title)}</h2>{body}' if body else ""

    projects = ""
    for p in data.get("projects", []):
        bullets = "".join(f"<li>{esc(b)}</li>" for b in p.get("bullets", []) if b)
        head = " — ".join([x for x in [p.get("name"), p.get("role")] if x])
        projects += f"<div class='item'><div class='item-head'>{esc(head)}</div><ul>{bullets}</ul></div>"

    skills = " · ".join(g.get("text", "") for g in data.get("skill_groups", []) if g.get("text"))
    comps = " · ".join(data.get("competencies", []))
    langs = "；".join(f"{x.get('name')}：{x.get('level')}" for x in data.get("languages", []))

    education = " — ".join(esc(x) for x in [edu.get("school"), edu.get("college"), edu.get("major")] if x)
    if edu.get("period"):
        education += f"（{esc(edu['period'])}）"

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>{esc(name)} — Resume</title>
<style>
  @page {{ size: A4; margin: 16mm 18mm; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: "PingFang SC","Microsoft YaHei",Arial,sans-serif; color:#111; font-size:10.5pt;
    line-height:1.55; background:#fff; padding:16px; max-width:190mm; margin:0 auto; }}
  h1 {{ font-size:20pt; margin-bottom:2px; }}
  .headline {{ font-size:11pt; color:#333; margin-bottom:4px; }}
  .contact {{ font-size:9.5pt; color:#444; margin-bottom:12px; }}
  h2 {{ font-size:11pt; margin:14px 0 6px; padding-bottom:2px; border-bottom:1px solid #999; }}
  .item {{ margin-bottom:10px; }}
  .item-head {{ font-weight:600; font-size:10.5pt; }}
  ul {{ margin:3px 0 0 18px; }}
  li {{ font-size:10pt; margin-bottom:2px; }}
  p {{ font-size:10pt; }}
  @media print {{ body {{ padding:0; }} }}
</style></head>
<body>
  <h1>{esc(name)}</h1>
  <div class="headline">{esc(data.get('headline'))}</div>
  <div class="contact">{contact}</div>
  {section(t['summary'], f"<p>{esc(data.get('summary'))}</p>")}
  {section(t['education'], f"<p>{education}</p>")}
  {section(t['projects'], projects)}
  {section(t['competencies'] if skills else t['skills'], f"<p>{esc(comps)}</p>") if comps else ''}
  {section(t['skills'], f"<p>{esc(skills)}</p>") if skills else ''}
  {section(t['business'], "".join(f"<p>{esc(x)}</p>" for x in data.get('business_exposure', []))) if data.get('business_exposure') else ''}
  {section(t['languages'], f"<p>{esc(langs)}</p>") if langs else ''}
</body></html>"""


