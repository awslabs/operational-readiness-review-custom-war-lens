"""Every check that `python3 -m tools.orrlens check` runs. Each check returns (failures, notes)."""

from __future__ import annotations

import datetime
import fnmatch
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config as C
from . import data as D
from . import docs as DOCS
from . import registry as REG
from .addon import load_addon
from .export import WORDING_EXEMPT, ExportError, export_files, load_denylist, sensitive_patterns, wording_scan
from .model import discover_lens_keys, load_lens, overlays_allowed
from .render import description, dumps, render_lens, t
from .rules import generate_rules, prove
from .schema import validate as schema_validate
from .textscan import (ServiceMatcher, bare_hosts, decode_text, extract_urls, gov_availability_claims, host_allowed,
                       language_problems, placeholder_problems, rendered_strings, strip_statement_reader_notes,
                       url_allowed)

BP_IN_TEXT = re.compile(r"^((?:OPS|SEC|REL|PERF|COST|SUS)\d{2}-BP\d{2})\b")
AS_OF = re.compile(r"\b(?:as of|checked) (20\d\d-\d\d-\d\d)\b", re.I)
# A partition note for a statement that names a service missing from AWS GovCloud (US) must offer what to do there.
# A heuristic: a note that only says "not available" has none of these words.
GOV_ALTERNATIVE = re.compile(r"\b(?:there|instead|use|using|attach|script|run|rehearse|record|keep|request|engage|"
                             r"route|serve|schedule|compute|write|scan|test|add|deploy|choose|replace|protect|apply|"
                             r"build|host|open|alarm)\b|(?<!not )\b(?:is|are) available\b", re.I)


def valid_as_of(text: str) -> bool:
    """True when text has an 'as of YYYY-MM-DD' (or 'checked YYYY-MM-DD') and every such date is a real date."""
    dates = AS_OF.findall(text or "")
    if not dates:
        return False
    for d in dates:
        try:
            datetime.date.fromisoformat(d)
        except ValueError:
            return False
    return True


def statement_index(ctx) -> dict:
    """(lens_key, question_id, statement_id) -> statement source, for every valid question."""
    out = {}
    for lens in ctx.all_lenses():
        for q in lens.valid_questions:
            for s in q["statements"]:
                out[(lens.key, q["id"], s["id"])] = s
    return out


@dataclass
class Context:
    root: Path
    lenses: list
    addon: object | None
    rendered: dict = field(default_factory=dict)
    addon_doc: dict | None = None
    _data: dict = field(default_factory=dict)

    def data(self, name):
        if name not in self._data:
            loader = {"wa": D.load_wa_bps, "partitions": D.load_partitions, "lifecycle": D.load_lifecycle,
                      "builder": D.load_builder_allowlist}[name]
            self._data[name] = loader(self.root)
        return self._data[name]

    def all_rendered(self):
        """(lens_key, doc) for every rendered lens, plus the add-on template."""
        out = [(k, d) for k, d in self.rendered.items()]
        if self.addon_doc is not None:
            out.append(("addon", self.addon_doc))
        return out

    def all_lenses(self):
        return list(self.lenses) + ([self.addon] if self.addon is not None else [])


def make_context(root: Path, lens_filter: str | None = None) -> Context:
    keys = discover_lens_keys(root)
    if lens_filter not in (None, "all"):
        keys = [k for k in keys if k == lens_filter]
    lenses = [load_lens(root, k) for k in keys]
    addon = load_addon(root) if lens_filter in (None, "all", "addon") else None
    ctx = Context(root=root, lenses=lenses, addon=addon)
    for lens in lenses:
        ctx.rendered[lens.key] = render_lens(lens)
    if addon is not None and addon.meta.get("pillars"):
        ctx.addon_doc = render_lens(addon)
    return ctx


def _where_statement(lens_key, q, s):
    return f"{lens_key}/{q['id']}/{s['id']}"


# ---------------------------------------------------------------------------
# source, schema, limits, rules
# ---------------------------------------------------------------------------

def check_source(ctx):
    fails, notes = [], []
    for lens in ctx.all_lenses():
        fails += lens.errors
        notes.append(f"{lens.key}: {len(lens.questions)} question files, {len(lens.valid_questions)} valid")
    if ctx.addon is None:
        notes.append(f"{C.ADDON_SOURCE} does not exist yet; the add-on template is skipped")
    return fails, notes


def check_schema(ctx):
    fails, notes = [], []
    engine = None
    for key, doc in ctx.all_rendered():
        if not doc.get("pillars"):
            notes.append(f"{key}: no valid questions yet; schema validation skipped")
            continue
        errs, engine = schema_validate(doc)
        fails += [f"{key}: {e}" for e in errs]
    if engine:
        notes.append(f"validated with {engine} against tools/orrlens/schema/custom-lens.schema.json")
    return fails, notes


def _len_fail(fails, where, what, value, limit):
    if value is not None and len(value) > limit:
        fails.append(f"{where}: {what} is {len(value)} characters (limit {limit})")


_RESTRICTED_BAD = re.compile(r"(?!" + C.RESTRICTED_FIELD_CHARS + r").", re.S)


def _charset_fail(fails, where, what, value):
    """ImportLens rejects some characters in names, titles and descriptions (gate G4)."""
    if not value:
        return
    bad = sorted(set(_RESTRICTED_BAD.findall(value)))
    if bad:
        fails.append(f"{where}: {what} contains characters ImportLens rejects: {' '.join(repr(b) for b in bad)}")


def check_limits(ctx):
    fails, notes = [], []
    id_re = re.compile(r"^[a-z0-9_]{3,64}$")
    for key, doc in ctx.all_rendered():
        _len_fail(fails, key, "lens name", doc["name"], C.MAX_LENS_NAME)
        _len_fail(fails, key, "lens description", doc["description"], C.MAX_LENS_DESCRIPTION)
        _charset_fail(fails, key, "lens name", doc["name"])
        _charset_fail(fails, key, "lens description", doc["description"])
        if len(doc["pillars"]) > C.MAX_PILLARS:
            fails.append(f"{key}: {len(doc['pillars'])} pillars (limit {C.MAX_PILLARS})")
        for p in doc["pillars"]:
            pw = f"{key}/{p['id']}"
            if not id_re.match(p["id"]):
                fails.append(f"{pw}: pillar id must be 3-64 characters of [a-z0-9_]")
            _len_fail(fails, pw, "pillar name", p["name"], C.MAX_TITLE)
            _charset_fail(fails, pw, "pillar name", p["name"])
            if len(p["questions"]) > C.MAX_QUESTIONS_PER_PILLAR:
                fails.append(f"{pw}: {len(p['questions'])} questions (limit {C.MAX_QUESTIONS_PER_PILLAR})")
            for q in p["questions"]:
                qw = f"{key}/{q['id']}"
                if not id_re.match(q["id"]):
                    fails.append(f"{qw}: question id must be 3-64 characters of [a-z0-9_]")
                _len_fail(fails, qw, "title", q["title"], C.MAX_TITLE)
                _len_fail(fails, qw, "description", q.get("description"), C.MAX_DESCRIPTION)
                _charset_fail(fails, qw, "title", q["title"])
                _charset_fail(fails, qw, "description", q.get("description"))
                hr = q.get("helpfulResource") or {}
                _len_fail(fails, qw, "question helpful text", hr.get("displayText"), C.MAX_QUESTION_HELPFUL)
                _len_fail(fails, qw, "question helpful URL", hr.get("url"), C.MAX_CHOICE_TEXT)
                if len(q["choices"]) > C.MAX_CHOICES_PER_QUESTION:
                    fails.append(f"{qw}: {len(q['choices'])} choices (limit {C.MAX_CHOICES_PER_QUESTION})")
                n_st = sum(1 for c in q["choices"] if c["id"] != C.NONE_ID)
                if n_st > C.MAX_STATEMENTS:
                    fails.append(f"{qw}: {n_st} statements (lens policy limit {C.MAX_STATEMENTS})")
                if len(q["riskRules"]) > C.MAX_RULES:
                    fails.append(f"{qw}: {len(q['riskRules'])} risk rules (limit {C.MAX_RULES})")
                for c in q["choices"]:
                    cw = f"{qw}/{c['id']}"
                    if not id_re.match(c["id"]):
                        fails.append(f"{cw}: choice id must be 3-64 characters of [a-z0-9_]")
                    _len_fail(fails, cw, "title", c["title"], C.MAX_TITLE)
                    _charset_fail(fails, cw, "title", c["title"])
                    for k in ("helpfulResource", "improvementPlan"):
                        r = c.get(k) or {}
                        _len_fail(fails, cw, f"{k} text", r.get("displayText"), C.MAX_CHOICE_TEXT)
                        _len_fail(fails, cw, f"{k} URL", r.get("url"), C.MAX_CHOICE_TEXT)
                    for a in c.get("additionalResources", []):
                        if len(a["content"]) > C.MAX_ADDITIONAL_PER_TYPE:
                            fails.append(f"{cw}: {len(a['content'])} {a['type']} entries "
                                         f"(limit {C.MAX_ADDITIONAL_PER_TYPE})")
                        for item in a["content"]:
                            _len_fail(fails, cw, "additional resource text", item.get("displayText"), C.MAX_CHOICE_TEXT)
                            _len_fail(fails, cw, "additional resource URL", item.get("url"), C.MAX_CHOICE_TEXT)
        size, size_min = len(dumps(doc).encode()), len(dumps(doc, minify=True).encode())
        if size > C.LENS_SIZE_BUDGET:
            fails.append(f"{key}: lens file is {size} bytes (budget {C.LENS_SIZE_BUDGET}; hard limit 500 KB)")
        n_q = sum(len(p["questions"]) for p in doc["pillars"])
        notes.append(f"{key}: {n_q} questions; {size:,} bytes pretty, {size_min:,} minified "
                     f"(budget {C.LENS_SIZE_BUDGET:,})")
    for lens in ctx.lenses:
        if not version_name_ok(lens.version):
            fails.append(f"{lens.key}: version name {lens.version!r} must be 1-{C.VERSION_NAME_MAX} "
                         "alphanumerics and periods")
    return fails, notes


def version_name_ok(v: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9.]+$", v or "")) and len(v) <= C.VERSION_NAME_MAX


def check_rules(ctx):
    fails, notes = [], []
    n = 0
    for lens in ctx.all_lenses():
        guard = bool(lens.meta.get("none_exclusive_guard"))
        doc = ctx.rendered.get(lens.key) if lens.key != "addon" else ctx.addon_doc
        rendered = {q["id"]: q for p in (doc or {}).get("pillars", []) for q in p["questions"]}
        for q in lens.valid_questions:
            rules = generate_rules(q["statements"], q["max_risk"], guard)
            fails += [f"{lens.key}/{f}" for f in prove(q["id"], q["statements"], rules, q["max_risk"], guard)]
            if rendered.get(q["id"], {}).get("riskRules") != rules:
                fails.append(f"{lens.key}/{q['id']}: rendered riskRules differ from the generated rules")
            n += 1
    notes.append(f"proved the risk-rule properties on {n} questions (exhaustive truth tables)")
    return fails, notes


# ---------------------------------------------------------------------------
# severity basis, ownership
# ---------------------------------------------------------------------------

def check_severity(ctx):
    fails, notes = [], []
    wa = ctx.data("wa")
    if wa is not None:
        fails += wa.problems
    entries = wa.entries if wa is not None else {}
    scoring = ctx.root / "docs" / "scoring.md"
    scoring_text = scoring.read_text(encoding="utf-8") if scoring.exists() else None
    n_dev = 0
    for lens in ctx.all_lenses():
        for q in lens.valid_questions:
            for s in q["statements"]:
                where = _where_statement(lens.key, q, s)
                basis = t(s.get("severity_basis"))
                is_floor = s["tier"] == "core" or s["tier"].startswith("alt:")
                if is_floor and not basis:
                    fails.append(f"{where}: core and alt statements need a severity_basis")
                m = re.match(r"^wa:(\S+) \(High\)$", basis)
                if basis.startswith("wa:"):
                    if not m:
                        fails.append(f"{where}: severity_basis must read 'wa:<BP-ID> (High)'")
                    elif wa is None:
                        fails.append(f"{where}: cannot verify {basis}: {C.DATA_WA_BPS} does not exist")
                    elif m.group(1) not in entries:
                        fails.append(f"{where}: {m.group(1)} is not in {C.DATA_WA_BPS}")
                    elif entries[m.group(1)]["level_of_risk"] != "High":
                        fails.append(f"{where}: {m.group(1)} has level of risk "
                                     f"{entries[m.group(1)]['level_of_risk']} in {C.DATA_WA_BPS}, not High")
                if basis.startswith("deviation:") and lens.key != "addon":
                    n_dev += 1
                    if scoring_text is not None and s["id"] not in scoring_text:
                        fails.append(f"{where}: deviation is not listed in docs/scoring.md")
                bp = s.get("wa_bp")
                if bp:
                    if wa is None:
                        fails.append(f"{where}: cannot verify wa_bp {bp}: {C.DATA_WA_BPS} does not exist")
                    elif bp not in entries:
                        fails.append(f"{where}: wa_bp {bp} is not in {C.DATA_WA_BPS}")
            # Question-level citation: a display text that starts with a BP id must link that BP's page
            h = q.get("helpful") or {}
            mm = BP_IN_TEXT.match(t(h.get("display_text")))
            if mm and wa is not None:
                bp = mm.group(1)
                if bp not in entries:
                    fails.append(f"{lens.key}/{q['id']}: helpful text cites {bp}, which is not in {C.DATA_WA_BPS}")
                elif entries[bp]["url"] and _bp_page(entries[bp]["url"]) != _bp_page(h.get("url")):
                    fails.append(f"{lens.key}/{q['id']}: helpful text cites {bp} but links {h.get('url')}, "
                                 f"not {entries[bp]['url']}")
    if n_dev and scoring_text is None:
        fails.append(f"{n_dev} deviation statements, but docs/scoring.md does not exist")
    if wa is None:
        notes.append(f"{C.DATA_WA_BPS} does not exist yet")
    else:
        notes.append(f"{C.DATA_WA_BPS}: {len(entries)} best practices")
    return fails, notes


def _bp_page(url) -> str:
    """The page name of a Well-Architected best-practice URL; framework/ and pillar URLs share it."""
    u = str(url or "").split("#")[0]
    if "/wellarchitected/" not in u:
        return u
    return u.rstrip("/").rsplit("/", 1)[-1]


def check_ownership(ctx):
    fails, notes = [], []
    owners: dict = {}
    for lens in ctx.lenses:
        for q in lens.valid_questions:
            for s in q["statements"]:
                owners.setdefault(s["concept"], []).append(_where_statement(lens.key, q, s))
    for concept, where in sorted(owners.items()):
        if len(where) > 1:
            fails.append(f"concept {concept} is owned by {len(where)} statements: {', '.join(where)}")
    notes.append(f"{len(owners)} concepts")
    return fails, notes


# ---------------------------------------------------------------------------
# partitions, lifecycle, language, internal wording
# ---------------------------------------------------------------------------

def _statement_text(doc, qid, sid, statement=None, problems=None):
    """Rendered text of one choice, without its exempt reader notes (see strip_statement_reader_notes)."""
    for p in doc.get("pillars", []):
        for q in p["questions"]:
            if q["id"] != qid:
                continue
            for c in q["choices"]:
                if c["id"] != sid:
                    continue
                fields = [("title", c["title"]),
                          ("helpfulResource.displayText", (c.get("helpfulResource") or {}).get("displayText", "")),
                          ("improvementPlan.displayText", (c.get("improvementPlan") or {}).get("displayText", ""))]
                for a in c.get("additionalResources", []):
                    fields += [(f"additionalResources.{a['type']}", i.get("displayText", "")) for i in a["content"]]
                parts = []
                for fld, text in fields:
                    body, probs = strip_statement_reader_notes(fld, text, statement or {})
                    parts.append(body)
                    if problems is not None:
                        problems += [f"{fld}: {pr}" for pr in probs]
                return " ".join(parts)
    return ""


def check_partitions(ctx):
    fails, notes = [], []
    df = ctx.data("partitions")
    if df is None:
        return [f"{C.DATA_PARTITIONS} does not exist"], notes
    fails += df.problems
    matcher = ServiceMatcher(df.entries, D.not_services(df))
    unregistered: dict = {}
    for key, doc in ctx.all_rendered():
        for where, fld, text, _sid, _qid in rendered_strings(doc, key):
            if fld.endswith(".url"):
                continue
            for name in matcher.unregistered(text):
                unregistered.setdefault(name, []).append(f"{where} {fld}")
    for name, where in sorted(unregistered.items()):
        more = f" (and {len(where) - 2} more)" if len(where) > 2 else ""
        fails.append(f"'{name}' is not registered in {C.DATA_PARTITIONS}: {'; '.join(where[:2])}{more}")
    gov_na = {k for k, e in df.entries.items() if e.get("aws-us-gov") == "not available"}
    for lens in ctx.all_lenses():
        doc = ctx.rendered.get(lens.key) if lens.key != "addon" else ctx.addon_doc
        if not doc:
            continue
        for q in lens.valid_questions:
            q_notes = [t(s.get("partition_notes")) for s in q["statements"]]
            q_named = matcher.services_named(f"{t(q['title'])} {description(q)}") & gov_na
            if q_named and not any("AWS GovCloud (US)" in pn and valid_as_of(pn) for pn in q_notes):
                fails.append(f"{lens.key}/{q['id']}: the question title or description names "
                             f"{', '.join(sorted(q_named))} (not available in AWS GovCloud (US)) but no statement "
                             "has dated partition_notes for AWS GovCloud (US)")
            for s in q["statements"]:
                where = _where_statement(lens.key, q, s)
                pn = t(s.get("partition_notes"))
                if pn and not valid_as_of(pn):
                    fails.append(f"{where}: partition_notes must be dated with a real date ('as of YYYY-MM-DD')")
                if not (s["tier"] == "core" or s["tier"].startswith("alt:")):
                    continue
                text = _statement_text(doc, q["id"], s["id"], s)
                named = matcher.services_named(text) & gov_na
                if named and ("AWS GovCloud (US)" not in pn or not GOV_ALTERNATIVE.search(pn)):
                    fails.append(f"{where}: names {', '.join(sorted(named))} (not available in AWS GovCloud (US)) "
                                 "but partition_notes offer no AWS GovCloud (US) alternative (say what to use or do "
                                 "there)")
    fails += partition_claim_problems(ctx, df, matcher)
    notes.append(f"{C.DATA_PARTITIONS}: {len(df.entries)} services, {len(gov_na)} not available in aws-us-gov")
    return fails, notes


def _claim_problem(where, key, available, subject, df):
    recorded = df.entries.get(key, {}).get("aws-us-gov")
    if available and recorded == "not available":
        return (f"{where}: says {key} is available in AWS GovCloud (US) ('{subject}'), but {C.DATA_PARTITIONS} "
                "records it as not available there")
    if not available and recorded == "available":
        return (f"{where}: says {key} is not available in AWS GovCloud (US) ('{subject}'), but {C.DATA_PARTITIONS} "
                "records it as available there; correct the text, or the data if the service is not available")
    return None


def _claim_files(root: Path):
    seen = set()
    for g in C.PARTITION_CLAIM_FILE_GLOBS:
        for p in sorted(root.glob(g)):
            rel = str(p.relative_to(root))
            if p.is_file() and rel not in seen and rel not in C.PARTITION_CLAIM_SKIP and not rel.startswith("private/"):
                seen.add(rel)
                yield rel, p


def partition_claim_problems(ctx, df, matcher) -> list:
    """Text that calls a service available (or not available) in AWS GovCloud (US) against the partition data.

    Rendered lens text is checked string by string; repository prose paragraph by paragraph (lines joined), so a
    sentence wrapped over several lines is still read whole.
    """
    fails = []
    for key, doc in ctx.all_rendered():
        for where, fld, text, _sid, _qid in rendered_strings(doc, key):
            if fld.endswith(".url"):
                continue
            for svc, available, subject in gov_availability_claims(text, matcher):
                f = _claim_problem(f"{where} {fld}", svc, available, subject, df)
                if f:
                    fails.append(f)
    for rel, path in _claim_files(ctx.root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        line = 1
        for para in re.split(r"(\n[ \t]*\n)", text):
            if para.strip() and not re.fullmatch(r"\n[ \t]*\n", para):
                for svc, available, subject in gov_availability_claims(para, matcher):
                    f = _claim_problem(f"{rel}:{line}", svc, available, subject, df)
                    if f:
                        fails.append(f)
            line += para.count("\n")
    return fails


def _lifecycle_regexes(df):
    out = []
    for name, e in df.entries.items():
        pats = list(e["patterns"])
        if not pats:   # without explicit patterns, match the name and aliases literally
            pats = [r"(?<![A-Za-z0-9])" + re.escape(x) + r"(?![A-Za-z0-9])" for x in [name] + e["aliases"] if x]
        for p in pats:
            try:
                out.append((name, re.compile(p, re.I), "text"))
            except re.error as exc:
                out.append((name, None, f"invalid pattern {p!r}: {exc}"))
        for p in e["url_patterns"]:
            try:
                out.append((name, re.compile(p, re.I), "url"))
            except re.error as exc:
                out.append((name, None, f"invalid url pattern {p!r}: {exc}"))
    return out


USAGE_PLAN = re.compile(r"usage[- ]plans?", re.I)
BEST_EFFORT = re.compile(r"best[- ]effort", re.I)
HARD_CONTROL = re.compile(r"(?<!not )(?<!never )(?<!no )(?<!not a )\b(?:hard|block\w*|enforc\w*|guarantee\w*)\b", re.I)


def usage_plan_problems(text: str) -> list:
    """API Gateway usage plans must be called best-effort in the same sentence, and never a hard or blocking control."""
    out = []
    for sentence in re.split(r"(?<=[.!?;])\s+", text or ""):
        if not USAGE_PLAN.search(sentence):
            continue
        if not BEST_EFFORT.search(sentence):
            out.append("mentions API Gateway usage plans without saying, in the same sentence, that they are "
                       "best-effort")
        elif re.search(r"\bnot\s+best[- ]effort", sentence, re.I):
            out.append("says API Gateway usage plans are not best-effort")
        else:
            m = HARD_CONTROL.search(sentence)
            if m:
                out.append(f"presents API Gateway usage plans as a hard or blocking control ('{m.group(0)}')")
    return out


def _statement_has_reader_note(statement) -> bool:
    if not statement:
        return False
    if statement.get("reader_note"):
        return True
    return "Reader note:" in t(statement.get("improvement"))


def check_lifecycle(ctx):
    fails, notes = [], []
    df = ctx.data("lifecycle")
    if df is None:
        return [f"{C.DATA_LIFECYCLE} does not exist"], notes
    fails += df.problems
    notes += df.warnings
    rxs = _lifecycle_regexes(df)
    fails += [f"{C.DATA_LIFECYCLE}: {name}: {kind}" for name, rx, kind in rxs if rx is None]
    rxs = [r for r in rxs if r[1] is not None]
    no_urls = sorted(n for n, e in df.entries.items() if not e["url_patterns"])
    if no_urls:
        fails.append(f"{C.DATA_LIFECYCLE}: entries without url_patterns: {', '.join(no_urls)}")
    sts = statement_index(ctx)
    for key, doc in ctx.all_rendered():
        for where, fld, text, sid, qid in rendered_strings(doc, key):
            is_url = fld.endswith(".url")
            statement = sts.get((key, qid, sid)) if sid else None
            if is_url:
                body = text
            else:
                body, probs = strip_statement_reader_notes(fld, text, statement)
                fails += [f"{where} {fld}: {pr}" for pr in probs]
            for name, rx, kind in rxs:
                if (kind == "url") != is_url:
                    continue
                m = rx.search(body)
                if not m:
                    continue
                if is_url and _statement_has_reader_note(statement):
                    continue
                e = df.entries[name]
                if is_url:
                    fails.append(f"{where} {fld}: links documentation of {name} ({e['status']} {e['effective']}) "
                                 "without a reader note on the statement")
                else:
                    fails.append(f"{where} {fld}: names '{m.group(0)}' ({name}: {e['status']} {e['effective']}) "
                                 "outside a 'Reader note:'")
            if not is_url:
                fails += [f"{where} {fld}: {pr}" for pr in usage_plan_problems(body)]
    notes.append(f"{C.DATA_LIFECYCLE}: {len(df.entries)} services")
    return fails, notes


def _language_files(root: Path):
    seen = set()
    for g in C.LANGUAGE_FILE_GLOBS:
        for p in sorted(root.glob(g)):
            rel = str(p.relative_to(root))
            if p.is_file() and rel not in seen and not rel.startswith("private/"):
                seen.add(rel)
                yield rel, p


def check_language(ctx):
    fails, notes = [], []
    for key, doc in ctx.all_rendered():
        for where, fld, text, _sid, _qid in rendered_strings(doc, key):
            if fld.endswith(".url"):
                if not url_allowed(text):
                    fails.append(f"{where} {fld}: URL is not https on an allowlisted host: {text}")
                continue
            for kind, detail in language_problems(text):
                fails.append(f"{where} {fld}: {kind}: {detail}")
            for u in extract_urls(text):
                if not url_allowed(u):
                    fails.append(f"{where} {fld}: URL is not https on an allowlisted host: {u}")
            for h in bare_hosts(text):
                if not host_allowed(h):
                    fails.append(f"{where} {fld}: names a host that is not on the allowlist: {h}")
    n = 0
    for rel, path in _language_files(ctx.root):
        n += 1
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            fails.append(f"{rel}: not UTF-8 text")
            continue
        for ln, line in enumerate(lines, 1):
            for kind, detail in language_problems(line):
                fails.append(f"{rel}:{ln}: {kind}: {detail}")
    notes.append(f"scanned the rendered lens text and {n} repository text files")
    return fails, notes


def check_wording(ctx):
    pats, problems = load_denylist(ctx.root / C.DENYLIST_FILE)
    builtin = sensitive_patterns()
    try:
        files = export_files(ctx.root, include_untracked=True)
    except ExportError as exc:
        return [str(exc)], []
    if pats is None:
        hits = wording_scan(ctx.root, files, builtin)
        return hits, [f"{C.DENYLIST_FILE} not present (public clone): only the {len(builtin)} built-in "
                      f"sensitive-data patterns ran over {len(files)} files"]
    hits = wording_scan(ctx.root, files, pats + builtin)
    return problems + hits, [f"{len(pats)} denylist patterns and {len(builtin)} built-in patterns over "
                             f"{len(files)} exportable files"]


def check_placeholders(ctx):
    """Leftover placeholders ({{...}} template tokens, a release-date fill-in, TBD markers) in exportable files.

    Python sources are skipped (their braces and markers are code); the published v1 files are already public.
    """
    try:
        files = export_files(ctx.root, include_untracked=True)
    except ExportError as exc:
        return [str(exc)], []
    fails, n = [], 0
    for rel in files:
        if rel.endswith(".py") or rel.lower().endswith(C.BINARY_EXTENSIONS):
            continue
        if any(fnmatch.fnmatch(rel, pat) for pat in WORDING_EXEMPT):
            continue
        text = decode_text((ctx.root / rel).read_bytes())
        if text is None:
            continue        # the wording check reports files it cannot read
        n += 1
        for ln, line in enumerate(text.splitlines(), 1):
            for kind, match in placeholder_problems(line):
                fails.append(f"{rel}:{ln}: leftover {kind}: {match}")
    return fails, [f"scanned {n} exportable text files (Python sources excluded)"]


# ---------------------------------------------------------------------------
# ids, reproducibility, docs
# ---------------------------------------------------------------------------

def check_ids(ctx):
    fails = REG.check_ids(ctx.root, ctx.lenses, overlays_allowed())
    reg = REG.load_registry(ctx.root) or {}
    counts = {k: len(reg.get(k) or {}) for k in ("pillars", "questions", "choices")}
    return fails, [f"{C.IDS_FILE}: {counts['pillars']} pillars, {counts['questions']} questions, "
                   f"{counts['choices']} choices"]


def expected_outputs(ctx) -> dict:
    """Relative path -> expected bytes for every generated lens file in dist/ and the add-on template."""
    out = {}
    for lens in ctx.lenses:
        doc = ctx.rendered[lens.key]
        stem = f"{lens.meta.get('file_stem')}-{lens.version}"
        out[f"dist/{stem}.json"] = dumps(doc)
        out[f"dist/{stem}.min.json"] = dumps(doc, minify=True)
    if ctx.addon_doc is not None:
        out[C.ADDON_OUTPUT] = dumps(ctx.addon_doc)
    return out


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def check_reproducibility(ctx):
    fails, notes = [], []
    blocked = [lens.key for lens in ctx.all_lenses() if lens.errors]
    expected = expected_outputs(ctx)
    for rel, content in expected.items():
        lens_key = "addon" if rel == C.ADDON_OUTPUT else next(
            (lz.key for lz in ctx.lenses if rel.startswith(f"dist/{lz.meta.get('file_stem')}-")), None)
        if lens_key in blocked:
            fails.append(f"{rel}: cannot be built while {lens_key} has source errors")
            continue
        path = ctx.root / rel
        if not path.exists():
            fails.append(f"{rel} is missing; run `python3 -m tools.orrlens build`")
        elif path.read_text(encoding="utf-8") != content:
            fails.append(f"{rel} differs from a fresh build; run `python3 -m tools.orrlens build`")
    if not (ctx.root / C.ADDON_SOURCE).exists() and (ctx.root / C.ADDON_OUTPUT).exists():
        fails.append(f"{C.ADDON_OUTPUT} exists but {C.ADDON_SOURCE} does not")
    dist = ctx.root / "dist"
    if dist.is_dir():
        for p in sorted(dist.glob("*.json")):
            rel = f"dist/{p.name}"
            if rel not in expected and p.name != "manifest.json":
                notes.append(f"{rel} is not produced by the current sources (older version?)")
        from .manifest import build_manifest, sha256sums  # local import: manifest imports this module
        man = dist / "manifest.json"
        if man.exists():
            try:
                have = json.loads(man.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                have = None
            want = build_manifest(ctx, source_commit=None)
            if _strip_commit(have) != _strip_commit(want):
                fails.append("dist/manifest.json differs from the current build; run `python3 -m tools.orrlens manifest`")
        sums = dist / "SHA256SUMS"
        if sums.exists() and sums.read_text(encoding="utf-8") != sha256sums(
                {Path(r).name: c for r, c in expected.items() if r.startswith("dist/")}):
            fails.append("dist/SHA256SUMS differs from the current build; run `python3 -m tools.orrlens manifest`")
    # Copies of the current release in wafr-operational-readiness-lens/ must equal dist/
    v1dir = ctx.root / C.V1_DIR
    for lens in ctx.lenses:
        stem, ver = lens.meta.get("file_stem"), lens.version
        for suffix in (".json", ".min.json"):
            want = expected.get(f"dist/{stem}-{ver}{suffix}")
            for name in (f"{stem}-{ver}{suffix}", f"{stem}{suffix}"):
                p = v1dir / name
                if p.exists() and want is not None and p.read_text(encoding="utf-8") != want:
                    fails.append(f"{C.V1_DIR}/{name} differs from dist/{stem}-{ver}{suffix}")
    return fails, notes


def _strip_commit(m):
    if not isinstance(m, dict):
        return m
    m = json.loads(json.dumps(m))
    for k in ("source_commit", "source_dirty"):
        m.pop(k, None)
    for lens in m.get("lenses", []):
        for k in ("source_commit", "source_dirty"):
            lens.pop(k, None)
    return m


def check_docs(ctx):
    return DOCS.check_fresh(ctx.root, ctx.lenses, ctx.rendered, ctx.data("wa")), []


def check_links(ctx):
    from .links import run_links
    result = run_links(ctx.root, changed_only=None, strict_redirects=False, quiet=True)
    return result["fails"], result["notes"]


CHECKS = [
    ("source", check_source),
    ("schema", check_schema),
    ("limits", check_limits),
    ("rules", check_rules),
    ("severity", check_severity),
    ("ownership", check_ownership),
    ("partitions", check_partitions),
    ("lifecycle", check_lifecycle),
    ("language", check_language),
    ("wording", check_wording),
    ("placeholders", check_placeholders),
    ("ids", check_ids),
    ("reproducibility", check_reproducibility),
    ("docs", check_docs),
    ("links", check_links),          # network; skipped with --offline
]
NETWORK_CHECKS = {"links"}
# Checks that are about the whole repository; they always see every lens, even with --lens.
CROSS_LENS_CHECKS = {"ownership", "wording", "placeholders", "ids", "reproducibility", "docs", "links"}


def run(ctx, only=None, skip=None, offline=False, full_ctx=None):
    """Yield (name, fails, notes) for each selected check. full_ctx (every lens) serves the cross-lens checks."""
    for name, fn in CHECKS:
        if only and name not in only:
            continue
        if skip and name in skip:
            continue
        if offline and name in NETWORK_CHECKS:
            continue
        try:
            fails, notes = fn(full_ctx if (full_ctx is not None and name in CROSS_LENS_CHECKS) else ctx)
        except Exception as exc:  # a check must never crash the others
            fails, notes = [f"internal error in the {name} check: {type(exc).__name__}: {exc}"], []
        yield name, fails, notes
