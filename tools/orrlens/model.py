"""Load and validate lens sources (lens-src/<lens>/lens.yaml and question files)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import config as C
from .textscan import url_allowed

ID_RE = re.compile(r"^[a-z0-9_]{3,64}$")
BP_RE = re.compile(r"^(OPS|SEC|REL|PERF|COST|SUS)\d{2}-BP\d{2}$")
TIER_RE = re.compile(r"^(scope|core|sec|alt:[A-Z])$")
BASIS_RE = re.compile(r"^(wa:(OPS|SEC|REL|PERF|COST|SUS)\d{2}-BP\d{2} \(High\)|wp-orr:.{20,}|deviation:.{20,})$")
MONTH_RE = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4}$")

QUESTION_KEYS = {
    "schema", "id", "pillar", "order", "title", "max_risk", "priority", "core_path", "category", "lineage",
    "choice_prefix", "description", "helpful", "statements", "pes_lesson",
}
STATEMENT_KEYS = {
    "id", "tier", "title", "concept", "severity_basis", "wa_bp", "large_scale", "good", "platform_notes",
    "partition_notes", "reader_note", "helpful_url", "improvement", "improvement_url", "additional_helpful",
    "additional_improvement",
}


@dataclass
class Lens:
    key: str
    path: Path
    meta: dict
    questions: list = field(default_factory=list)   # list of dicts (validated question sources)
    errors: list = field(default_factory=list)

    @property
    def version(self) -> str:
        return str(self.meta.get("version", "0.0.0"))

    @property
    def valid_questions(self) -> list:
        """Questions that passed source validation (only these are rendered)."""
        return [q for q in self.questions if q.get("_valid")]


def overlays_allowed() -> bool:
    """Forks that add x_<org>_ overlays set ORRLENS_ALLOW_OVERLAYS=1; upstream CI never does."""
    return os.environ.get("ORRLENS_ALLOW_OVERLAYS") == "1"


def _err(errors, where, msg):
    errors.append(f"{where}: {msg}")


def _text(v) -> str:
    return " ".join(str(v).split()) if v is not None else ""


def _check_url(errors, where, url):
    if not isinstance(url, str) or not url.startswith("https://"):
        _err(errors, where, f"URL must be https: {url!r}")
        return
    if url_allowed(url):
        return
    _err(errors, where, f"URL host not on the allowlist (or a GitHub organization outside AWS, or a path with "
                        f"'..', '//' or encoded dots): {url}")


def discover_lens_keys(root: Path) -> list:
    """Lens keys with a lens-src/<key>/lens.yaml, in LENS_ORDER first, then alphabetically."""
    keys = [p.parent.name for p in (root / "lens-src").glob("*/lens.yaml")]
    return sorted(keys, key=lambda k: (C.LENS_ORDER.index(k) if k in C.LENS_ORDER else 99, k))


def _load_yaml(path: Path, errors, where):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError, OSError) as exc:
        _err(errors, where, f"cannot parse YAML: {' '.join(str(exc).split())}")
        return None


def load_lens(root: Path, key: str) -> Lens:
    base = root / "lens-src" / key
    e: list = []
    meta = _load_yaml(base / "lens.yaml", e, f"{key}/lens.yaml")
    if not isinstance(meta, dict):
        if not e:
            _err(e, f"{key}/lens.yaml", "not a mapping")
        meta = {"name": key, "version": "0.0.0", "pillars": [], "file_stem": key, "description": ""}
    lens = Lens(key=key, path=base, meta=meta, errors=e)
    validate_lens_meta(meta, f"{key}/lens.yaml", e)
    pillar_ids = [p.get("id") for p in meta.get("pillars") or [] if isinstance(p, dict)]

    for f in sorted(base.glob("*/*.yaml")):
        where = f"{key}/{f.parent.name}/{f.name}"
        q = _load_yaml(f, e, where)
        if q is None and not (e and e[-1].startswith(where)):
            _err(e, where, "empty file")
        if q is None:
            continue
        before = len(e)
        validate_question(q, where, pillar_ids, f.parent.name, e)
        if not isinstance(q, dict):
            continue
        q["_file"] = str(f.relative_to(root))
        q["_valid"] = len(e) == before
        lens.questions.append(q)
    lens.questions.sort(key=lambda q: (pillar_ids.index(q["pillar"]) if q.get("pillar") in pillar_ids else 99,
                                       q.get("order") if type(q.get("order")) is int else 0,
                                       str(q.get("id", ""))))
    lens_level_checks(lens.questions, key, e)
    return lens


def validate_lens_meta(meta, where, e):
    if meta.get("schema") != "orrlens/lens/1":
        _err(e, where, "schema must be orrlens/lens/1")
    name = meta.get("name")
    if not isinstance(name, str) or not name or len(name) > C.MAX_LENS_NAME:
        _err(e, where, f"lens name missing or longer than {C.MAX_LENS_NAME}")
    desc = _text(meta.get("description", "")).replace("{version}", str(meta.get("version", "")))
    if not desc:
        _err(e, where, "description is required")
    if len(desc) > C.MAX_LENS_DESCRIPTION:
        _err(e, where, f"description {len(desc)} > {C.MAX_LENS_DESCRIPTION}")
    if not re.match(r"^\d+\.\d+\.\d+$", str(meta.get("version", ""))):
        _err(e, where, "version must be SemVer MAJOR.MINOR.PATCH")
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", str(meta.get("file_stem", ""))):
        _err(e, where, "file_stem must be lowercase letters, digits and hyphens")
    pillars = meta.get("pillars")
    if not isinstance(pillars, list) or not pillars:
        _err(e, where, "pillars must be a non-empty list")
        return
    if len(pillars) > C.MAX_PILLARS:
        _err(e, where, f"too many pillars ({len(pillars)} > {C.MAX_PILLARS})")
    seen = set()
    for p in pillars:
        if not isinstance(p, dict):
            _err(e, where, "each pillar must be a mapping with id and name")
            continue
        pid = str(p.get("id") or "")
        if not ID_RE.match(pid):
            _err(e, where, f"bad pillar id {pid!r}")
        if pid in seen:
            _err(e, where, f"duplicate pillar id {pid}")
        seen.add(pid)
        if not p.get("name") or len(str(p.get("name"))) > C.MAX_TITLE:
            _err(e, where, f"pillar {pid}: name missing or longer than {C.MAX_TITLE}")


def lens_level_checks(questions, key, e):
    """Uniqueness of question ids, choice prefixes and choice ids within one lens; questions per pillar."""
    seen_q, seen_prefix, seen_choice = set(), {}, {}
    per_pillar: dict = {}
    for q in questions:
        qid = q.get("id")
        if qid in seen_q:
            _err(e, key, f"duplicate question id {qid}")
        seen_q.add(qid)
        pre = q.get("choice_prefix")
        if pre in seen_prefix:
            _err(e, key, f"choice_prefix {pre} used by {seen_prefix[pre]} and {qid}")
        seen_prefix[pre] = qid
        for s in q.get("statements") or []:
            if not isinstance(s, dict):
                continue
            sid = s.get("id")
            if sid in seen_choice:
                _err(e, key, f"choice id {sid} used in {seen_choice[sid]} and {qid}")
            seen_choice[sid] = qid
        per_pillar.setdefault(q.get("pillar"), []).append(qid)
    for p, qs in per_pillar.items():
        if len(qs) > C.MAX_QUESTIONS_PER_PILLAR:
            _err(e, key, f"pillar {p} has {len(qs)} questions (> {C.MAX_QUESTIONS_PER_PILLAR})")


def validate_question(q, where, pillar_ids, folder, e, check_filename=True, allow_overlay=None):
    """Validate one question source. allow_overlay permits x_<org>_ ids (add-on lenses and overlay forks)."""
    overlay = overlays_allowed() if allow_overlay is None else allow_overlay
    if not isinstance(q, dict):
        _err(e, where, "not a mapping")
        return
    extra = set(q) - QUESTION_KEYS
    if extra:
        _err(e, where, f"unknown keys {sorted(extra)}")
    if q.get("schema") != "orrlens/question/1":
        _err(e, where, "schema must be orrlens/question/1")
    qid = str(q.get("id") or "")
    if not ID_RE.match(qid):
        _err(e, where, f"bad question id {qid!r}")
    if qid.startswith(C.RESERVED_PREFIX) and not overlay:
        _err(e, where, "x_ prefix is reserved for overlays")
    if check_filename and f"{qid}.yaml" != where.split("/")[-1]:
        _err(e, where, "file name must be <question id>.yaml")
    if q.get("pillar") not in pillar_ids:
        _err(e, where, f"pillar {q.get('pillar')!r} not in lens.yaml")
    if folder is not None and q.get("pillar") != folder:
        _err(e, where, "question file must live in its pillar folder")
    if type(q.get("order")) is not int:      # bool is a subclass of int; "order: true" is not an order
        _err(e, where, "order must be an integer")
    title = _text(q.get("title"))
    if not title or len(title) > C.MAX_TITLE:
        _err(e, where, "title missing or longer than 128")
    if re.search(r"\((H|M|L)\)\s*$", title or ""):
        _err(e, where, "no (H)/(M)/(L) tags in titles")
    if q.get("max_risk") not in ("HIGH", "MEDIUM"):
        _err(e, where, "max_risk must be HIGH or MEDIUM")
    if q.get("priority") not in ("P0", "P1"):
        _err(e, where, "priority must be P0 or P1")
    if not isinstance(q.get("core_path"), bool):
        _err(e, where, "core_path must be true or false")
    if q.get("category") not in C.CATEGORIES:
        _err(e, where, f"unknown category {q.get('category')!r}")
    if not isinstance(q.get("lineage"), list):
        _err(e, where, "lineage must be a list (use [] for a new topic)")
    pre = str(q.get("choice_prefix") or "")
    prefix_re = r"^(x_[a-z0-9]+_)?[a-z]{2,4}_$" if overlay else r"^[a-z]{2,4}_$"
    if not re.match(prefix_re, pre):
        _err(e, where, "choice_prefix must be 2-4 lowercase letters plus _"
             + (" (optionally after x_<org>_)" if overlay else ""))
    d = q.get("description") if isinstance(q.get("description"), dict) else {}
    if not d.get("question") or not d.get("evidence_to_collect"):
        _err(e, where, "description.question and description.evidence_to_collect are required")
    for k in ("question", "out_of_scope_if", "evidence_to_collect"):
        v = d.get(k)
        if v and not _text(v).endswith((".", "?")):
            _err(e, where, f"description.{k} must end with . or ?")
    h = q.get("helpful") if isinstance(q.get("helpful"), dict) else {}
    if not h.get("display_text") or len(_text(h.get("display_text"))) > C.MAX_QUESTION_HELPFUL:
        _err(e, where, "helpful.display_text missing or longer than 64")
    _check_url(e, where + " helpful.url", h.get("url"))

    sts = q.get("statements") or []
    if not isinstance(sts, list):
        _err(e, where, "statements must be a list")
        sts = []
    if not 1 <= len(sts) <= C.MAX_STATEMENTS:
        _err(e, where, f"needs 1-{C.MAX_STATEMENTS} statements")
    if not all(isinstance(s, dict) for s in sts):
        _err(e, where, "every statement must be a mapping")
        sts = [s for s in sts if isinstance(s, dict)]
    tiers = []
    for s in sts:
        sw = f"{where} {s.get('id')}"
        extra = set(s) - STATEMENT_KEYS
        if extra:
            _err(e, sw, f"unknown keys {sorted(extra)}")
        sid = str(s.get("id") or "")
        if not ID_RE.match(sid) or not sid.startswith(pre) or sid == C.NONE_ID or sid.endswith("_no"):
            _err(e, sw, "bad statement id (pattern, prefix, or _no suffix)")
        tier = str(s.get("tier") or "")
        if not TIER_RE.match(tier):
            _err(e, sw, f"bad tier {tier!r}")
        tiers.append(tier)
        if not _text(s.get("title")) or len(_text(s.get("title"))) > C.MAX_TITLE:
            _err(e, sw, "title missing or longer than 128")
        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", str(s.get("concept") or "")):
            _err(e, sw, "concept must be kebab-case")
        if tier in ("core",) or tier.startswith("alt:"):
            if not BASIS_RE.match(_text(s.get("severity_basis", ""))):
                _err(e, sw, "core/alt statements need severity_basis wa:<BP> (High) | wp-orr:<...> | deviation:<rationale>")
        if s.get("wa_bp") and not BP_RE.match(str(s["wa_bp"])):
            _err(e, sw, f"bad wa_bp {s['wa_bp']!r}")
        if s.get("large_scale") and tier != "sec":
            _err(e, sw, "large_scale applies to secondary statements only")
        for k in ("good", "improvement"):
            if not s.get(k):
                _err(e, sw, f"{k} is required")
        _check_url(e, sw + " helpful_url", s.get("helpful_url"))
        _check_url(e, sw + " improvement_url", s.get("improvement_url"))
        for k in ("additional_helpful", "additional_improvement"):
            items = s.get(k) or []
            if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
                _err(e, sw, f"{k} must be a list of display_text/url mappings")
                continue
            if len(items) > C.MAX_ADDITIONAL_PER_TYPE:
                _err(e, sw, f"{k} has more than {C.MAX_ADDITIONAL_PER_TYPE} entries")
            for item in items:
                if not item.get("display_text"):
                    _err(e, sw, f"{k} entry needs display_text")
                _check_url(e, sw + f" {k}", item.get("url"))
    ids = [s.get("id") for s in sts]
    if len(ids) != len(set(ids)):
        _err(e, where, "duplicate statement ids")
    has_floor = any(t == "core" or t.startswith("alt:") for t in tiers)
    if q.get("max_risk") == "HIGH" and not has_floor:
        _err(e, where, "HIGH-capped question needs a core or alt statement")
    if q.get("max_risk") == "MEDIUM" and has_floor:
        _err(e, where, "MEDIUM-capped question may use only scope and sec statements")
    groups = {}
    for t in tiers:
        if t.startswith("alt:"):
            groups[t] = groups.get(t, 0) + 1
    for g, n in groups.items():
        if n < 2:
            _err(e, where, f"alt group {g} needs at least two statements")
    pes = q.get("pes_lesson")
    if pes is not None and not isinstance(pes, dict):
        _err(e, where, "pes_lesson must be a mapping")
        pes = None
    if pes:
        if pes.get("statement") not in ids:
            _err(e, where, "pes_lesson.statement must be a statement id")
        if not MONTH_RE.match(str(pes.get("month", ""))):
            _err(e, where, "pes_lesson.month must look like 'Dec 2021'")
        if not str(pes.get("url", "")).startswith("https://aws.amazon.com/message/"):
            _err(e, where, "pes_lesson.url must be an AWS Post-Event Summary (https://aws.amazon.com/message/...)")
        if not pes.get("lesson"):
            _err(e, where, "pes_lesson.lesson is required")
