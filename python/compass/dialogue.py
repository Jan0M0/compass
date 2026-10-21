# -*- coding: utf-8 -*-
"""Guided exploration state machine.

The product decides *what to ask next*; the agent decides *how to say it*.
This keeps the middle from becoming either a questionnaire or a free-for-all.
"""
from __future__ import annotations

STAGES = [
    {
        "key": "energy",
        "question": "最近三个月，有没有什么事是你不用人催也会去做的？哪怕很小。",
        "why": "兴趣的可靠证据是「不用催也会做」，不是「我觉得我喜欢」。",
        "record": "compass self --add-interest '{\"name\":\"...\",\"evidence\":\"...\",\"energy\":\"高|中|低\",\"confidence\":\"确认|猜测\"}'",
        "need": "至少 1 条有具体证据的兴趣",
    },
    {
        "key": "strengths",
        "question": "有没有哪件事，你做起来比身边人轻松一点？哪怕只是做表格比别人快。",
        "why": "优势要靠别人观察和过去产出佐证，不能只靠自我评价。",
        "record": "compass self --add-strength '{\"name\":\"...\",\"evidence\":\"...\",\"confidence\":\"确认|猜测\"}'",
        "need": "至少 1 条有证据的优势",
    },
    {
        "key": "dislikes",
        "question": "有没有什么事，你一想到要做就烦？或者被怎样对待会让你很难受？",
        "why": "排除法和选择法一样重要；知道不要什么，能省掉很多试错。",
        "record": "compass self --merge '{\"dislikes\":[{\"name\":\"...\",\"evidence\":\"...\"}]}'",
        "need": "至少 1 条明确不喜欢（没有也可以写「暂无」）",
    },
    {
        "key": "values",
        "question": "如果只能保住两样：稳定、收入、自主、成长、影响力、关系、清闲——你留哪两个？",
        "why": "方向不是「哪个好」，而是「你愿意承担哪种代价」。",
        "record": "compass self --add-value '{\"name\":\"...\",\"rank\":1,\"note\":\"...\"}'",
        "need": "至少 2 条价值排序",
    },
    {
        "key": "constraints",
        "question": "家里对你有什么硬要求吗？比如城市、行业、时间。没有也可以直说。",
        "why": "不考虑约束的规划是幻想；但约束不等于判决，先写清楚。",
        "record": "compass self --add-constraint '{\"name\":\"...\",\"type\":\"家庭|经济|城市|身体|时间\",\"note\":\"...\"}'",
        "need": "至少 1 条现实约束（没有也可以写「无」）",
    },
    {
        "key": "exposure",
        "question": "有没有一个你完全不了解、但有点好奇的行业？我们挑一个，看看它每天在做什么。",
        "why": "没见过的东西无法选择；先用真实信息建立直觉。",
        "record": "compass explore --path '{\"name\":\"...\",\"status\":\"considering\",\"note\":\"...\"}'",
        "need": "至少 1 个在考虑的方向",
    },
    {
        "key": "experiment",
        "question": "这周能不能做一件 3 小时内能做完的小事，验证一下刚才那个方向？",
        "why": "想不清楚的事，做一次比想十次有用。",
        "record": "compass explore --add-mission '{\"title\":\"...\",\"why\":\"...\",\"how\":\"...\",\"time\":\"3小时\",\"cost\":\"0\"}'",
        "need": "至少 1 个进行中的实验",
    },
    {
        "key": "review",
        "question": "上次那个小实验，做完你是更有劲还是更累？",
        "why": "不复盘的实验只是经历，不会变成判断。",
        "record": "compass explore --done <id> --result \"...\" --energy 高|中|低 --learned \"...\"",
        "need": "完成 1 次复盘",
    },
]


def _stage(key: str) -> dict:
    for i, s in enumerate(STAGES):
        if s["key"] == key:
            return {**s, "index": i + 1, "total": len(STAGES)}
    return {**STAGES[0], "index": 1, "total": len(STAGES)}


def next_step(self_data: dict, explore_data: dict) -> dict:
    interests = self_data.get("interests") or []
    strengths = self_data.get("strengths") or []
    dislikes = self_data.get("dislikes") or []
    values = self_data.get("values") or []
    constraints = self_data.get("constraints") or []
    paths = explore_data.get("paths") or []
    experiments = self_data.get("experiments") or []
    missions = explore_data.get("missions") or []

    if not interests:
        return _stage("energy")
    if not strengths:
        return _stage("strengths")
    if not dislikes:
        return _stage("dislikes")
    if len(values) < 2:
        return _stage("values")
    if not constraints:
        return _stage("constraints")
    if not paths:
        return _stage("exposure")

    todo = [m for m in missions if m.get("status") != "done"]
    if todo:
        m = todo[0]
        return {
            "key": "mission",
            "question": f"上次说的「{m.get('title', '那个实验')}」做了吗？做到哪一步？",
            "why": "先看上一个实验的结果，再决定下一步；不要同时开三个。",
            "record": f"compass explore --done {m.get('id', '<id>')} --result \"...\" --energy 高|中|低 --learned \"...\"",
            "need": "完成或明确放弃这个实验",
            "index": len(STAGES),
            "total": len(STAGES),
            "mission_id": m.get("id"),
        }

    if not experiments:
        return _stage("experiment")

    return _stage("review")
