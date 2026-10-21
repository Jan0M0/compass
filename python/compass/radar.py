# -*- coding: utf-8 -*-
"""Deterministic job collection from Shixiseng public pages.

No model calls, no login, no browser. The service runs this on demand.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
BASE = "https://www.shixiseng.com"
LIST = BASE + "/interns?keyword={kw}&city={city}&page={page}"
CITY_LIST = [
    "北京", "上海", "广州", "深圳", "杭州", "宁波", "南京", "苏州", "成都", "重庆",
    "武汉", "西安", "长沙", "合肥", "厦门", "福州", "青岛", "济南", "天津", "郑州",
]


def html_unescape(text: str) -> str:
    if not text:
        return ""

    def repl(m):
        try:
            ch = chr(int(m.group(1), 16))
        except ValueError:
            return ""
        return "" if 0xE000 <= ord(ch) <= 0xF8FF else ch

    text = re.sub(r"&#x([0-9a-fA-F]+);?", repl, text)
    text = re.sub(r"&#(\d+);?", lambda m: chr(int(m.group(1))), text)
    return text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()


def strip_pua(text: str) -> str:
    return re.sub("[\\ue000-\\uf8ff]", "", text or "").strip()


def fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9", "Referer": BASE + "/",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def split_top_level(text: str, sep: str = ",") -> list[str]:
    parts, buf, depth, quote, esc = [], [], 0, None, False
    for ch in text:
        if quote:
            buf.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                quote = None
            continue
        if ch in ('"', "'"):
            quote = ch
            buf.append(ch)
        elif ch in "([{":
            depth += 1
            buf.append(ch)
        elif ch in ")]}":
            depth -= 1
            buf.append(ch)
        elif ch == sep and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    return parts


def js_string(token: str) -> str:
    token = token.strip()
    if not token:
        return ""
    if token[0] in ('"', "'") and token[-1] == token[0]:
        body = token[1:-1]
        try:
            return json.loads('"' + body.replace('"', '\\"') + '"')
        except json.JSONDecodeError:
            body = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), body)
            return body.replace("\\/", "/").replace('\\"', '"')
    return token


def js_lit(token: str):
    token = (token or "").strip()
    if token in ("void 0", "undefined", "null"):
        return None
    if token == "true":
        return True
    if token == "false":
        return False
    if token.startswith('"') or token.startswith("'"):
        return js_string(token)
    if re.fullmatch(r"-?\d+(\.\d+)?", token):
        return float(token) if "." in token else int(token)
    return token


def parse_nuxt(html: str):
    start = html.find("__NUXT__=")
    if start < 0:
        return None, []
    end = html.find("</script>", start)
    seg = html[start:end] if end > 0 else html[start:start + 500000]
    m = re.match(r"__NUXT__=\(function\(([^)]*)\)\{", seg)
    if not m:
        return None, []
    params = [p.strip() for p in m.group(1).split(",")]
    r = seg.find("return ", m.end())
    if r < 0:
        return None, []

    outer_close = seg.rfind(")")
    call_close = seg.rfind(")", 0, outer_close)
    if call_close < 0:
        return None, []
    depth, args_start = 0, -1
    for idx in range(call_close - 1, -1, -1):
        ch = seg[idx]
        if ch == ")":
            depth += 1
        elif ch == "(":
            if depth == 0:
                args_start = idx
                break
            depth -= 1
    if args_start < 0 or args_start <= r:
        return None, []

    obj = seg[r + 7:args_start].rstrip()
    if obj.endswith(")"):
        obj = obj[:-1].rstrip()
    args = split_top_level(seg[args_start + 1:call_close], ",")
    return obj, dict(zip(params, args))


def resolve(token: str, env: dict):
    token = (token or "").strip()
    if not token:
        return ""
    if re.fullmatch(r"[A-Za-z_$][\w$]*", token) and token in env:
        return js_lit(env[token])
    return js_lit(token)


def field(block: str, key: str):
    m = re.search(
        rf"(?<![\w$]){key}:\s*(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|"
        rf"[A-Za-z_$][\w$]*|-?\d+(?:\.\d+)?|true|false|null|void 0)",
        block,
    )
    return m.group(1) if m else ""


def array_field(block: str, key: str, env: dict) -> list[str]:
    m = re.search(rf"(?<![\w$]){key}:\s*\[(.*?)\]", block, re.S)
    if not m:
        return []
    out = []
    for token in split_top_level(m.group(1), ","):
        val = resolve(token, env)
        if isinstance(val, str) and val:
            out.append(html_unescape(val))
    return out


def parse_jobs(html: str) -> list[dict]:
    obj, env = parse_nuxt(html)
    if not obj:
        return []
    blocks = re.findall(r"\{ad_type:.*?(?=\},\{ad_type:|\}\],total:)", obj, re.S)
    jobs = []
    for b in blocks:
        uuid = js_string(field(b, "uuid"))
        if not uuid.startswith("inn_"):
            continue
        title = html_unescape(str(resolve(field(b, "name"), env)))
        title = re.sub(r"[（(]\s*[)）]", "", title).strip()
        company = html_unescape(str(resolve(field(b, "cname"), env)))
        city = resolve(field(b, "city"), env)
        minsal = resolve(field(b, "minsalary"), env)
        maxsal = resolve(field(b, "maxsalary"), env)
        degree = resolve(field(b, "degree"), env)
        tags = array_field(b, "i_tags", env) + array_field(b, "c_tags", env)
        salary = ""
        try:
            lo, hi = int(minsal), int(maxsal)
            if not (lo == 0 and hi == 0):
                salary = f"{lo}元/天" if lo == hi else f"{lo}-{hi}元/天"
        except (TypeError, ValueError):
            pass
        jobs.append({
            "uuid": uuid,
            "title": strip_pua(title),
            "company": strip_pua(company),
            "city": city if isinstance(city, str) and not re.search(r"[\\ue000-\\uf8ff]", city) else "",
            "salary": salary,
            "degree": degree if isinstance(degree, str) else "",
            "tags": [t for t in tags if t],
            "url": f"{BASE}/intern/{uuid}",
        })
    return jobs


def detail_field(html: str, key: str) -> str:
    m = re.search(
        r"\b[A-Za-z]\." + re.escape(key) +
        r'=("(?:[^"\\]|\\.)*"|true|false|-?\d+(?:\.\d+)?|\[[^\]]*\])',
        html,
    )
    if not m:
        return ""
    token = m.group(1)
    return js_string(token) if token.startswith('"') else token


def parse_detail(html: str) -> dict:
    info = detail_field(html, "info")
    if info:
        info = re.sub(r"<br\s*/?>", "\n", info, flags=re.I)
        info = re.sub(r"</(p|div|li|h\d)>", "\n", info, flags=re.I)
        info = re.sub(r"<[^>]+>", "", info)
        info = html_unescape(info)
        info = re.sub(r"[ \t]+", " ", info)
        info = re.sub(r"\n{3,}", "\n\n", info).strip()

    city = detail_field(html, "city")
    address = detail_field(html, "address")
    if not city and address:
        first = re.split(r"\s*[-/－—]\s*", address)[0].strip()
        if 2 <= len(first) <= 6:
            city = first
    for c in CITY_LIST:
        if c in (city or ""):
            city = c
            break

    attraction = []
    m = re.search(r"\b[A-Za-z]\.attraction=\[(.*?)\]", html, re.S)
    if m:
        for token in split_top_level(m.group(1), ","):
            val = js_lit(token)
            if isinstance(val, str) and val:
                attraction.append(html_unescape(val))

    days = detail_field(html, "day")
    months = detail_field(html, "month")
    return {
        "title": strip_pua(detail_field(html, "iname")),
        "company": strip_pua(detail_field(html, "cname")),
        "city": city,
        "salary": detail_field(html, "salary_desc").replace("/天", "元/天"),
        "days_per_week": int(days) if days.isdigit() else None,
        "duration_months": int(months) if months.isdigit() else None,
        "degree": detail_field(html, "degree"),
        "deadline": detail_field(html, "endtime"),
        "jd_raw": info,
        "attraction": attraction,
        "address": address,
    }


def collect(keyword: str, city: str, pages: int = 1, detail: bool = True, limit: int = 30) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()
    for page in range(1, max(1, pages) + 1):
        url = LIST.format(kw=urllib.parse.quote(keyword), city=urllib.parse.quote(city), page=page)
        html = fetch(url)
        for c in parse_jobs(html):
            if c["uuid"] in seen:
                continue
            seen.add(c["uuid"])
            if len(found) >= limit:
                return found
            if detail:
                try:
                    d = parse_detail(fetch(c["url"]))
                    for k in ("title", "company", "city", "salary", "days_per_week",
                              "duration_months", "degree", "deadline", "jd_raw"):
                        if d.get(k):
                            c[k] = d[k]
                    c["tags"] = list(dict.fromkeys((c.get("tags") or []) + (d.get("attraction") or [])))
                    time.sleep(0.6)
                except Exception:  # noqa: BLE001
                    pass
            found.append(c)
        time.sleep(1.2)
    return found
