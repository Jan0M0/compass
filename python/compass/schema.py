# -*- coding: utf-8 -*-
"""Published schema. This is what the agent reads before writing anything.

Design order matters: schema -> API -> views.
"""
from __future__ import annotations

STATUSES = ["new", "shortlisted", "tailored", "applied", "replied", "interview", "offer", "rejected", "dropped"]

PROFILE = {
    "type": "object",
    "required": ["name", "school", "major", "grade"],
    "properties": {
        "name": {"type": "string"},
        "school": {"type": "string"},
        "college": {"type": "string"},
        "major": {"type": "string"},
        "grade": {"type": "string"},
        "graduation_year": {"type": "integer"},
        "cities": {"type": "array", "items": {"type": "string"}},
        "remote_ok": {"type": "boolean"},
        "directions": {"type": "array", "items": {"type": "string"}},
        "skills": {"type": "array", "items": {"type": "string"}},
        "toolchain": {"type": "array", "items": {"type": "string"}},
        "languages": {"type": "array", "items": {
            "type": "object", "properties": {"name": {"type": "string"}, "level": {"type": "string"}}
        }},
        "available": {
            "type": "object",
            "properties": {
                "days_per_week": {"type": "integer", "minimum": 1, "maximum": 7},
                "months": {"type": "integer", "minimum": 1, "maximum": 24},
                "start": {"type": "string"},
            },
        },
        "contact": {
            "type": "object",
            "properties": {
                "phone": {"type": "string"}, "email": {"type": "string"},
                "wechat": {"type": "string"}, "portfolio": {"type": "string"},
            },
        },
        "weekly_target": {"type": "integer", "minimum": 1, "maximum": 50},
    },
}

SELF = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}, "age": {"type": "string"},
                "school": {"type": "string"}, "major": {"type": "string"},
                "grade": {"type": "string"}, "city": {"type": "string"},
                "family_context": {"type": "string"}, "money_pressure": {"type": "string"},
                "health": {"type": "string"},
            },
        },
        "interests": {"type": "array", "items": {
            "type": "object", "required": ["name"],
            "properties": {
                "name": {"type": "string"}, "evidence": {"type": "string"},
                "energy": {"enum": ["高", "中", "低", ""]},
                "confidence": {"enum": ["确认", "猜测", ""]},
            },
        }},
        "strengths": {"type": "array", "items": {
            "type": "object", "required": ["name"],
            "properties": {"name": {"type": "string"}, "evidence": {"type": "string"},
                           "confidence": {"enum": ["确认", "猜测", ""]}},
        }},
        "values": {"type": "array", "items": {
            "type": "object", "required": ["name"],
            "properties": {"name": {"type": "string"}, "rank": {"type": "integer"}, "note": {"type": "string"}},
        }},
        "dislikes": {"type": "array", "items": {
            "type": "object", "properties": {"name": {"type": "string"}, "evidence": {"type": "string"}}
        }},
        "constraints": {"type": "array", "items": {
            "type": "object", "properties": {
                "name": {"type": "string"},
                "type": {"enum": ["家庭", "经济", "城市", "身体", "时间", ""]},
                "note": {"type": "string"},
            },
        }},
        "experiments": {"type": "array", "items": {
            "type": "object", "properties": {
                "title": {"type": "string"}, "date": {"type": "string"},
                "hypothesis": {"type": "string"}, "did": {"type": "string"},
                "result": {"type": "string"}, "energy": {"type": "string"}, "learned": {"type": "string"},
            },
        }},
        "questions": {"type": "array", "items": {
            "type": "object", "properties": {"q": {"type": "string"}, "status": {"type": "string"}}
        }},
        "people": {"type": "array", "items": {
            "type": "object", "properties": {
                "name": {"type": "string"}, "relation": {"type": "string"}, "useful_for": {"type": "string"}
            },
        }},
        "preferences": {"type": "object", "properties": {
            "tone": {"type": "string"}, "avoid": {"type": "array", "items": {"type": "string"}}
        }},
    },
}

EXPLORE = {
    "type": "object",
    "properties": {
        "paths": {"type": "array", "items": {
            "type": "object", "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "status": {"enum": ["considering", "testing", "ruled_out"]},
                "note": {"type": "string"},
            },
        }},
        "missions": {"type": "array", "items": {
            "type": "object", "required": ["title"],
            "properties": {
                "id": {"type": "string"}, "title": {"type": "string"},
                "why": {"type": "string"}, "how": {"type": "string"},
                "time": {"type": "string"}, "cost": {"type": "string"},
                "status": {"enum": ["todo", "doing", "done"]},
                "result": {"type": "string"}, "energy": {"type": "string"}, "learned": {"type": "string"},
            },
        }},
    },
}

JOB = {
    "type": "object",
    "required": ["company", "title"],
    "properties": {
        "company": {"type": "string"},
        "title": {"type": "string"},
        "city": {"type": "string"},
        "salary": {"type": "string"},
        "days_per_week": {"type": ["integer", "null"]},
        "duration_months": {"type": ["integer", "null"]},
        "degree": {"type": "string"},
        "source": {"type": "string"},
        "url": {"type": "string"},
        "deadline": {"type": "string"},
        "jd_raw": {"type": "string"},
        "notes": {"type": "string"},
    },
}

RESUME = {
    "type": "object",
    "required": ["headline", "summary", "projects"],
    "properties": {
        "lang": {"enum": ["zh", "en"]},
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "education": {
            "type": "object",
            "properties": {
                "school": {"type": "string"}, "college": {"type": "string"},
                "period": {"type": "string"}, "major": {"type": "string"}, "note": {"type": "string"},
            },
        },
        "focus": {"type": "array", "items": {"type": "string"}},
        "projects": {"type": "array", "items": {
            "type": "object", "required": ["name"],
            "properties": {
                "name": {"type": "string"}, "role": {"type": "string"},
                "bullets": {"type": "array", "items": {"type": "string"}},
            },
        }},
        "business_exposure": {"type": "array", "items": {"type": "string"}},
        "competencies": {"type": "array", "items": {"type": "string"}},
        "skill_groups": {"type": "array", "items": {
            "type": "object", "properties": {"category": {"type": "string"}, "text": {"type": "string"}}
        }},
        "toolchain": {"type": "array", "items": {"type": "string"}},
        "links": {"type": "object", "properties": {
            "title": {"type": "string"}, "items": {"type": "array", "items": {"type": "string"}},
            "url": {"type": "string"},
        }},
        "languages": {"type": "array", "items": {
            "type": "object", "properties": {"name": {"type": "string"}, "level": {"type": "string"}}
        }},
        "section_titles": {"type": "object"},
    },
}

DOCUMENT = {
    "service": "compass",
    "version": 1,
    "principle": "The agent reasons; the service stores, validates, renders, and distributes.",
    "auth": {
        "type": "PAT",
        "header": "Authorization: Bearer cmp_pat_...",
        "note": "PAT is an identity credential, not an AI credit.",
    },
    "objects": {
        "profile": PROFILE,
        "self": SELF,
        "explore": EXPLORE,
        "job": JOB,
        "resume": RESUME,
    },
    "statuses": STATUSES,
    "endpoints": {
        "GET /schema": "this document",
        "GET /health": "service health",
        "POST /auth/claim": {"body": {"handle": "string"}, "returns": {"token": "cmp_pat_..."}},
        "GET /api/whoami": "current user",
        "GET|PUT /api/profile": "profile object",
        "GET|PUT /api/self": "self object",
        "GET|PUT /api/explore": "explore object",
        "GET /api/jobs": "job list (?status=&q=)",
        "POST /api/jobs": "create job (job object)",
        "POST /api/radar": {"body": {"keyword": "string", "city": "string", "pages": "int", "detail": "boolean", "limit": "int"}, "note": "collects from Shixiseng public pages, no model"},
        "GET /api/explore/suggest": "suggest 3-4 low-cost experiments from current gaps",
        "POST /api/explore/add-suggested": "add suggestions as todo missions",
        "GET /api/jobs/{id}": "job detail + events",
        "POST /api/jobs/{id}/advance": {"body": {"to": "status", "note": "string"}},
        "POST /api/score": {"body": {"id": "optional job id"}},
        "GET /api/check": "today's actions",
        "POST /api/resume": {"body": {"job_id": "optional", "style": "visual|ats|both", "data": "optional resume object", "publish": "boolean"}},
        "GET /api/resume/{id}": "latest versions",
        "POST /api/share": {"body": {"kind": "dashboard|explore|resume", "target": "id", "version": "int"}},
        "DELETE /api/share/{slug}": "revoke",
    },
    "views": {
        "dashboard": "/u/{handle}",
        "explore": "/u/{handle}/explore",
        "resume": "/u/{handle}/resume/{id}",
        "resume_version": "/u/{handle}/resume/{id}/v/{n}",
        "share": "/s/{slug}",
    },
}
