"""Render validated lens sources to WA Tool custom-lens JSON (deterministic)."""

from __future__ import annotations

import json

from . import config as C
from .rules import generate_rules


def t(v) -> str:
    """Normalize YAML folded/literal text to single-spaced text."""
    return " ".join(str(v).split()) if v is not None else ""


def description(q) -> str:
    d = q["description"]
    parts = [C.RISK_TEXT[q["max_risk"]], f"Category: {q['category']}.", t(d["question"])]
    if d.get("out_of_scope_if"):
        parts.append(f"Out of scope if: {t(d['out_of_scope_if'])}")
    parts.append(f"Evidence to collect: {t(d['evidence_to_collect'])}")
    return " ".join(parts)


def helpful_text(s) -> str:
    out = f"Good looks like: {t(s['good'])}"
    if s.get("platform_notes"):
        out += f" Platform notes: {t(s['platform_notes'])}"
    if s.get("partition_notes"):
        out += f" Partition notes: {t(s['partition_notes'])}"
    if s.get("reader_note"):
        out += f" Reader note: {t(s['reader_note'])}"
    return out


def none_text(max_risk: str) -> str:
    return (f"Select this if none of the statements above is true today. "
            f"The question then scores {C.RISK_WORD[max_risk]} risk.")


def render_question(q, none_guard: bool = False) -> dict:
    sts = q["statements"]
    pes = q.get("pes_lesson")
    choices = []
    for s in sts:
        c = {
            "id": s["id"],
            "title": t(s["title"]),
            "helpfulResource": {"displayText": helpful_text(s), "url": s["helpful_url"]},
            "improvementPlan": {"displayText": t(s["improvement"]), "url": s["improvement_url"]},
        }
        helpful_extra = [{"displayText": t(i["display_text"]), "url": i["url"]} for i in s.get("additional_helpful") or []]
        if pes and pes["statement"] == s["id"]:
            helpful_extra.append({
                "displayText": f"Related AWS Post-Event Summary ({pes['month']}): {t(pes['lesson'])}",
                "url": pes["url"],
            })
        improvement_extra = [{"displayText": t(i["display_text"]), "url": i["url"]}
                             for i in s.get("additional_improvement") or []]
        extra = []
        if helpful_extra:
            extra.append({"type": "HELPFUL_RESOURCE", "content": helpful_extra})
        if improvement_extra:
            extra.append({"type": "IMPROVEMENT_PLAN", "content": improvement_extra})
        if extra:
            c["additionalResources"] = extra
        choices.append(c)
    choices.append({
        "id": C.NONE_ID,
        "title": C.NONE_TITLE,
        "helpfulResource": {"displayText": none_text(q["max_risk"])},
    })
    return {
        "id": q["id"],
        "title": t(q["title"]),
        "description": description(q),
        "helpfulResource": {"displayText": t(q["helpful"]["display_text"]), "url": q["helpful"]["url"]},
        "choices": choices,
        "riskRules": generate_rules(sts, q["max_risk"], none_guard),
    }


def render_lens(lens, version: str | None = None) -> dict:
    meta = lens.meta
    ver = version or str(meta.get("version", ""))
    guard = bool(meta.get("none_exclusive_guard"))
    pillars = []
    for p in meta.get("pillars") or []:
        if not isinstance(p, dict):
            continue
        qs = [render_question(q, guard) for q in lens.valid_questions if q["pillar"] == p.get("id")]
        if qs:
            pillars.append({"id": p["id"], "name": t(p.get("name")), "questions": qs})
    return {
        "schemaVersion": C.SCHEMA_VERSION,
        "name": t(meta.get("name")),
        "description": t(meta.get("description")).replace("{version}", ver),
        "pillars": pillars,
    }


def dumps(doc: dict, minify: bool = False) -> str:
    if minify:
        return json.dumps(doc, ensure_ascii=True, separators=(",", ":")) + "\n"
    return json.dumps(doc, ensure_ascii=True, indent=2) + "\n"
