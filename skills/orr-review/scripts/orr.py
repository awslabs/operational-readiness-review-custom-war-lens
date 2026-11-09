#!/usr/bin/env python3
"""orr.py: run an Operational Readiness Review (ORR) with the ORR lens files, from any agent or terminal.

Standard library only (Python 3.9 or later). It reads the lens JSON files and the answers file you name, writes
only the answers file and the report file you name, and makes no network calls.

Commands (python3 orr.py <command> --help for the options of each):
  lenses                          list the lens files found, with their versions
  questions [--lens KEY]          list the questions in review order
  show QUESTION_ID                print one question: description, evidence to collect, statements and rules
  init ANSWERS --workload NAME    start an answers file
  answer ANSWERS QUESTION_ID ...  record statements, None of these, or not applicable, with notes
  status ANSWERS                  progress, risk counts, warnings and the next question
  report ANSWERS --out FILE       write the findings report (Markdown)

Lens files are found in --lens-dir folders, or else in the current folder, ./dist and
./wafr-operational-readiness-lens. They are the release files orr-core.json, orr-event.json and orr-genai.json
(or their versioned names, such as orr-core-2.0.4.json).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

FORMAT = "orr-answers/1"
RELEASES = "https://github.com/awslabs/operational-readiness-review-custom-war-lens/releases/latest/download/"
LENS_KEYS = ("core", "event", "genai")
LENS_NAMES = {
    "core": "AWS Operational Readiness Review",
    "event": "ORR - Mission-Critical Event Readiness",
    "genai": "ORR - Generative AI and Agents",
}
NONE_ID = "none_no"
SIGNOFF = "readiness_signoff"
SCOPE_COMPLETE = "rd_scope_complete"
# The published 15-question core path (README "Core path and full core"). The lens JSON does not mark it, so it is
# listed here; a unit test keeps this list equal to the core_path flags in lens-src/.
CORE_PATH = (
    "architecture_rpo_rto", "architecture_data_corruption", "event_expiring_materials",
    "architecture_edge_protection", "architecture_defensive_throttling", "architecture_load_testing",
    "event_resilience_recoveries", "architecture_recovery_dependencies", "architecture_hybrid_connectivity",
    "releases_manual_changes", "releases_staged_deployments", "releases_deployment_rollback", "event_alarms",
    "event_oncall_rotation", "readiness_signoff",
)
RISK_LABEL = {"HIGH_RISK": "High", "MEDIUM_RISK": "Medium", "NO_RISK": "No risk"}
UNANSWERED, NOT_APPLICABLE = "Unanswered", "Not applicable"
STATES = ("High", "Medium", "No risk", NOT_APPLICABLE, UNANSWERED)
FILE_RE = re.compile(r"^orr-(core|event|genai)(?:-(\d+\.\d+\.\d+))?(\.min)?\.json$")
VERSION_RE = re.compile(r"\bcustom lens (\d+\.\d+\.\d+)\b")
MAX_RISK_RE = re.compile(r"Maximum risk: (High|Medium)")
EXC_RE = re.compile(r"\bEXC:(\S+)\s+exp:(\d{4}-\d{2}-\d{2})\s+role:(\S+)")
# Notes appear in reports; warn when they look like they hold an AWS account ID or an ARN (123456789012 is the
# documentation example ID).
SENSITIVE = (
    ("an AWS account ID", re.compile(r"(?<![0-9A-Za-z])(?!123456789012(?![0-9]))\d{12}(?![0-9A-Za-z])")),
    ("an ARN", re.compile(r"\barn:aws[a-z-]*:", re.I)),
)


class Problem(Exception):
    """A user-facing error: printed without a traceback, exit status 1."""


# ---------------------------------------------------------------------------
# Risk rules: the WA custom lens condition language (choice ids, &&, ||, !, parentheses, "default")
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"\s*(\(|\)|&&|\|\||!|[A-Za-z_][A-Za-z0-9_]*)")


def evaluate(cond: str, selected) -> bool:
    cond = cond.strip()
    if cond == "default":
        return True
    tokens, pos = [], 0
    while pos < len(cond):
        m = _TOKEN.match(cond, pos)
        if not m:
            raise ValueError(f"cannot parse rule condition {cond!r}")
        tokens.append(m.group(1))
        pos = m.end()

    def any_of(i):
        val, i = all_of(i)
        while i < len(tokens) and tokens[i] == "||":
            rhs, i = all_of(i + 1)
            val = val or rhs
        return val, i

    def all_of(i):
        val, i = negated(i)
        while i < len(tokens) and tokens[i] == "&&":
            rhs, i = negated(i + 1)
            val = val and rhs
        return val, i

    def negated(i):
        if i >= len(tokens):
            raise ValueError(f"unexpected end of rule condition {cond!r}")
        tok = tokens[i]
        if tok == "!":
            val, i = negated(i + 1)
            return not val, i
        if tok == "(":
            val, i = any_of(i + 1)
            if i >= len(tokens) or tokens[i] != ")":
                raise ValueError(f"missing ) in rule condition {cond!r}")
            return val, i + 1
        if tok in (")", "&&", "||"):
            raise ValueError(f"expected a choice id, got {tok!r} in rule condition {cond!r}")
        return tok in selected, i + 1

    val, end = any_of(0)
    if end != len(tokens):
        raise ValueError(f"trailing text in rule condition {cond!r}")
    return val


def risk_of(rules, selected) -> str:
    """The risk of the first rule whose condition holds (the WA Tool's evaluation order)."""
    for r in rules:
        if evaluate(r["condition"], selected):
            return r["risk"]
    return "UNMATCHED"


# ---------------------------------------------------------------------------
# Lens files
# ---------------------------------------------------------------------------

def _vkey(version: str):
    try:
        return tuple(int(x) for x in version.split("."))
    except ValueError:
        return (-1,)


class Lens:
    def __init__(self, key, doc, version, path):
        self.key, self.doc, self.version, self.path = key, doc, version, path
        self.name = doc["name"]
        self.questions = {}   # id -> (pillar name, question)
        for p in doc["pillars"]:
            for q in p["questions"]:
                self.questions[q["id"]] = (p["name"], q)


def lens_dirs(args):
    if args.lens_dir:
        return [Path(d).expanduser() for d in args.lens_dir]
    cwd = Path.cwd()
    return [cwd, cwd / "dist", cwd / "wafr-operational-readiness-lens"]


def find_lenses(dirs):
    """key -> [Lens, ...], highest version first (pretty-printed before minified), plus notes on skipped files."""
    found, notes = {}, []
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            m = FILE_RE.match(p.name)
            if not m or not p.is_file():
                continue
            key = m.group(1)
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                notes.append(f"skipped {p}: {exc}")
                continue
            if not isinstance(doc, dict) or doc.get("name") != LENS_NAMES[key] or not isinstance(doc.get("pillars"),
                                                                                                    list):
                notes.append(f"skipped {p}: not the {LENS_NAMES[key]} lens file")
                continue
            vm = VERSION_RE.search(doc.get("description", ""))
            version = vm.group(1) if vm else (m.group(2) or "unknown")
            found.setdefault(key, []).append((_vkey(version), not m.group(3), Lens(key, doc, version, p)))
    out = {}
    for key, cands in found.items():
        cands.sort(key=lambda c: (c[0], c[1]), reverse=True)
        seen, ordered = set(), []
        for _, _, lens in cands:
            if lens.version not in seen:
                seen.add(lens.version)
                ordered.append(lens)
        out[key] = ordered
    return out, notes


def missing_lens_message(dirs, keys) -> str:
    files = ", ".join(f"orr-{k}.json" for k in keys)
    return ("No ORR lens file found for " + ", ".join(keys) + " in: " + ", ".join(str(d) for d in dirs) + ".\n"
            f"Download {files} and SHA256SUMS from the latest release into the review folder, for example\n"
            f"  {RELEASES}orr-core.json\n  {RELEASES}SHA256SUMS\n"
            "then check them with: sha256sum --ignore-missing -c SHA256SUMS (macOS: shasum -a 256 --ignore-missing"
            " -c SHA256SUMS).\nOr pass --lens-dir with a folder that holds them, such as the dist/ folder of a "
            "clone of the repository.")


def load_lenses(args, keys, want=None):
    """One Lens per key: the version recorded in the answers file when it is available, else the highest."""
    dirs = lens_dirs(args)
    found, _ = find_lenses(dirs)
    missing = [k for k in keys if k not in found]
    if missing:
        raise Problem(missing_lens_message(dirs, missing))
    out, notes = {}, []
    for k in keys:
        cands = found[k]
        pick = next((c for c in cands if want and c.version == want.get(k)), cands[0])
        if want and want.get(k) and pick.version != want[k]:
            notes.append(f"the answers were recorded with {LENS_NAMES[k]} {want[k]}; scoring with {pick.version} "
                         f"({pick.path.name}). Check CHANGELOG.md for what changed between them.")
        out[k] = pick
    return out, notes


# ---------------------------------------------------------------------------
# Answers
# ---------------------------------------------------------------------------

def read_answers(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Problem(f"{path} does not exist; create it with: orr.py init {path} --workload NAME") from None
    except ValueError as exc:
        raise Problem(f"{path} is not valid JSON: {exc}") from None
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise Problem(f"{path} is not an ORR answers file (expected \"format\": \"{FORMAT}\")")
    lenses = data.get("lenses")
    if not isinstance(lenses, dict) or not lenses or any(k not in LENS_KEYS for k in lenses):
        raise Problem(f"{path}: \"lenses\" must map lens keys ({', '.join(LENS_KEYS)}) to versions")
    if not isinstance(data.get("answers"), dict):
        raise Problem(f"{path}: \"answers\" must be an object keyed by question id")
    return data


def write_answers(path: Path, data: dict):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def review_order(lenses, scope):
    """(lens, pillar name, question) in review order: core, then companions, and readiness_signoff last."""
    order, last = [], None
    for key in LENS_KEYS:
        if key not in lenses:
            continue
        for qid, (pillar, q) in lenses[key].questions.items():
            if key == "core" and scope == "core-path" and qid not in CORE_PATH:
                continue
            if qid == SIGNOFF:
                last = (lenses[key], pillar, q)
            else:
                order.append((lenses[key], pillar, q))
    return order + ([last] if last else [])


def state_of(q, ans):
    """(state, selected choice ids) for one question and its answer entry."""
    ans = ans or {}
    if ans.get("not_applicable"):
        return NOT_APPLICABLE, []
    chosen = [c for c in ans.get("choices") or [] if isinstance(c, str)]
    if not chosen:
        return UNANSWERED, []
    return RISK_LABEL.get(risk_of(q["riskRules"], set(chosen)), "Unmatched"), chosen


def exc_tag(notes: str, today: datetime.date):
    """(register id, expiry, role, expired) from an EXC: tag in the notes, or None."""
    m = EXC_RE.search(notes or "")
    if not m:
        return None
    try:
        expired = datetime.date.fromisoformat(m.group(2)) < today
    except ValueError:
        expired = True
    return m.group(1), m.group(2), m.group(3), expired


def sensitive_hits(text: str):
    return [label for label, rx in SENSITIVE if rx.search(text or "")]


class Review:
    """An answers file scored against the lens files."""

    def __init__(self, args, path: Path):
        self.path = path
        self.data = read_answers(path)
        self.scope = self.data.get("scope", "full")
        self.lenses, self.notes = load_lenses(args, [k for k in LENS_KEYS if k in self.data["lenses"]],
                                              self.data["lenses"])
        self.order = review_order(self.lenses, self.scope)
        self.rows = []    # (lens, pillar, question, state, chosen, answer entry)
        for lens, pillar, q in self.order:
            ans = self.data["answers"].get(q["id"])
            st, chosen = state_of(q, ans)
            self.rows.append((lens, pillar, q, st, chosen, ans or {}))

    def warnings(self):
        out = list(self.notes)
        known = {q["id"]: q for _, _, q in self.order}
        for qid, ans in self.data["answers"].items():
            if qid not in known:
                out.append(f"{qid}: not a question in this review's lenses and scope; it is ignored")
                continue
            ans = ans if isinstance(ans, dict) else {}
            ids = {c["id"] for c in known[qid]["choices"]}
            chosen = ans.get("choices") or []
            bad = [c for c in chosen if c not in ids]
            if bad:
                out.append(f"{qid}: unknown choice id(s) {', '.join(map(str, bad))}; they score as unselected")
            if NONE_ID in chosen and len(chosen) > 1:
                out.append(f"{qid}: None of these is recorded with other statements, which scores the maximum "
                           "risk; clear one or the other")
            if ans.get("not_applicable") and chosen:
                out.append(f"{qid}: marked not applicable and also has statements; not applicable wins")
            for label in sensitive_hits(ans.get("notes", "")):
                out.append(f"{qid}: the notes look like they hold {label}; link to evidence instead")
        unanswered = [q["id"] for _, _, q, st, _, _ in self.rows if st == UNANSWERED and q["id"] != SIGNOFF]
        signoff = next((r for r in self.rows if r[2]["id"] == SIGNOFF), None)
        if signoff and SCOPE_COMPLETE in signoff[4]:
            if self.scope == "core-path":
                out.append(f"{SIGNOFF}: {SCOPE_COMPLETE} is selected in a core-path review, which cannot meet it; "
                           "a go or no-go needs the full core")
            elif unanswered:
                out.append(f"{SIGNOFF}: {SCOPE_COMPLETE} is selected but {len(unanswered)} question(s) are "
                           f"unanswered ({', '.join(unanswered[:5])}{', ...' if len(unanswered) > 5 else ''})")
        if signoff and signoff[3] != UNANSWERED and unanswered:
            out.append(f"{SIGNOFF} is answered before other questions; answer it last")
        return out

    def next_question(self):
        return next((r for r in self.rows if r[3] == UNANSWERED), None)

    def counts(self, rows=None):
        c = {s: 0 for s in STATES}
        for r in rows if rows is not None else self.rows:
            c[r[3]] = c.get(r[3], 0) + 1
        return c

    def lens_line(self):
        return "; ".join(f"{lens.name} {lens.version}" for lens in self.lenses.values())


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def find_question(lenses, qid):
    for lens in lenses.values():
        if qid in lens.questions:
            pillar, q = lens.questions[qid]
            return lens, pillar, q
    raise Problem(f"unknown question id {qid}; list them with: orr.py questions")


def max_risk(q) -> str:
    m = MAX_RISK_RE.search(q.get("description", ""))
    return m.group(1) if m else "?"


def cmd_lenses(args):
    dirs = lens_dirs(args)
    found, notes = find_lenses(dirs)
    for n in notes:
        print(f"note: {n}")
    if not found:
        raise Problem(missing_lens_message(dirs, list(LENS_KEYS)))
    for key in LENS_KEYS:
        for i, lens in enumerate(found.get(key, [])):
            n_q = len(lens.questions)
            print(f"{key:6} {lens.version:8} {n_q:3} questions  {lens.path}{'' if i == 0 else '  (older)'}")
    for key in LENS_KEYS:
        if key not in found:
            print(f"{key:6} not found ({RELEASES}orr-{key}.json)")


def cmd_questions(args):
    keys = [args.lens] if args.lens else [k for k in LENS_KEYS]
    dirs = lens_dirs(args)
    found, _ = find_lenses(dirs)
    lenses = {k: found[k][0] for k in keys if k in found}
    if not lenses:
        raise Problem(missing_lens_message(dirs, keys))
    for lens, pillar, q in review_order(lenses, "core-path" if args.core_path else "full"):
        path = " core-path" if q["id"] in CORE_PATH and lens.key == "core" else ""
        print(f"{q['id']}\t{lens.key}\t{pillar}\tmax {max_risk(q)}{path}\t{q['title']}")


def cmd_show(args):
    dirs = lens_dirs(args)
    found, _ = find_lenses(dirs)
    if not found:
        raise Problem(missing_lens_message(dirs, list(LENS_KEYS)))
    lens, pillar, q = find_question({k: v[0] for k, v in found.items()}, args.question_id)
    desc = q["description"]
    for marker in ("Evidence to collect:", "Out of scope if:"):
        desc = desc.replace(f" {marker}", f"\n{marker}")
    print(f"{q['id']}  ({lens.name} {lens.version}, {pillar}{', core path' if q['id'] in CORE_PATH else ''})")
    print(f"Title: {q['title']}\n{desc}")
    hr = q.get("helpfulResource") or {}
    if hr.get("url"):
        print(f"Reference: {hr.get('displayText', '')} {hr['url']}")
    print("\nStatements (select each one that is true today and backed by evidence):")
    for c in q["choices"]:
        if c["id"] == NONE_ID:
            print(f"  [{NONE_ID}] None of these (scores the maximum risk; never combine it with a statement)")
            continue
        print(f"  [{c['id']}] {c['title']}")
        help_ = c.get("helpfulResource") or {}
        if help_.get("displayText"):
            print(f"      {help_['displayText']}")
        plan = c.get("improvementPlan") or {}
        if plan.get("displayText"):
            print(f"      Improvement plan: {plan['displayText']}" + (f" ({plan['url']})" if plan.get("url") else ""))
    print("\nRisk rules (the first rule that holds sets the risk):")
    for r in q["riskRules"]:
        print(f"  {RISK_LABEL.get(r['risk'], r['risk']):8} {r['condition']}")


def cmd_init(args):
    path = Path(args.answers)
    if path.exists() and not args.force:
        raise Problem(f"{path} already exists; resume it with: orr.py status {path} (or pass --force to replace it)")
    keys = [k.strip() for k in args.lens.split(",") if k.strip()]
    bad = [k for k in keys if k not in LENS_KEYS]
    if bad or not keys:
        raise Problem(f"--lens takes a comma-separated list of {', '.join(LENS_KEYS)}")
    lenses, _ = load_lenses(args, [k for k in LENS_KEYS if k in keys])
    data = {
        "format": FORMAT,
        "workload": args.workload,
        "milestone": args.milestone or "",
        "scope": args.scope,
        "started": datetime.date.today().isoformat(),
        "lenses": {k: lens.version for k, lens in lenses.items()},
        "answers": {},
    }
    write_answers(path, data)
    n = len(review_order(lenses, args.scope))
    print(f"created {path}: {args.workload}, {n} questions ({args.scope}); " + "; ".join(
        f"{lens.name} {lens.version}" for lens in lenses.values()))
    if args.milestone and not re.fullmatch(r"ORR-\d{4}-\d{2}-[a-z0-9-]+", args.milestone):
        print("note: milestone names usually follow ORR-<yyyy-mm>-<purpose>, for example ORR-2026-11-launch")
    if "core" not in lenses:
        print("note: the companion lenses assume a current core review of the same workload")


def cmd_answer(args):
    path = Path(args.answers)
    review = Review(args, path)
    lens, _pillar, q = find_question(review.lenses, args.question_id)
    qid = q["id"]
    if qid not in {r[2]["id"] for r in review.rows}:
        raise Problem(f"{qid} is not in this review's scope ({review.scope})")
    entry = dict(review.data["answers"].get(qid) or {})
    if args.clear:
        entry = {}
    elif args.none:
        entry.pop("not_applicable", None)
        entry["choices"] = [NONE_ID]
    elif args.not_applicable is not None:
        if not args.not_applicable.strip():
            raise Problem("--not-applicable needs a reason")
        entry.pop("choices", None)
        entry["not_applicable"] = args.not_applicable.strip()
    elif args.choices is not None:
        ids = [c["id"] for c in q["choices"] if c["id"] != NONE_ID]
        chosen = [c.strip() for c in args.choices.split(",") if c.strip()]
        if NONE_ID in chosen:
            raise Problem("use --none for None of these; it never combines with a statement")
        bad = [c for c in chosen if c not in ids]
        if bad:
            raise Problem(f"{qid} has no statement {', '.join(bad)}; its statements are {', '.join(ids)}")
        if not chosen:
            raise Problem("--choices needs at least one statement id (use --none if none is true today)")
        entry.pop("not_applicable", None)
        entry["choices"] = [c for c in ids if c in chosen]
    if args.notes is not None:
        entry["notes"] = args.notes
    if entry:
        review.data["answers"][qid] = entry
    else:
        review.data["answers"].pop(qid, None)
    write_answers(path, review.data)
    st, chosen = state_of(q, entry)
    line = f"{qid}: {st}"
    if st in ("High", "Medium"):
        missing = [c["id"] for c in q["choices"] if c["id"] not in chosen and c["id"] != NONE_ID]
        line += f" (not selected: {', '.join(missing)})"
    print(line)
    for label in sensitive_hits(entry.get("notes", "")):
        print(f"warning: the notes look like they hold {label}; remove it and link to evidence instead")


def cmd_status(args):
    review = Review(args, Path(args.answers))
    c = review.counts()
    total = len(review.rows)
    done = total - c[UNANSWERED]
    print(f"{review.data.get('workload', '')}: {review.lens_line()} ({review.scope}); {done} of {total} answered")
    print(", ".join(f"{s} {c[s]}" for s in STATES))
    highs = [r for r in review.rows if r[3] == "High"]
    if highs:
        print("High risks:")
        today = datetime.date.today()
        for lens, _p, q, _st, _ch, ans in highs:
            tag = exc_tag(ans.get("notes", ""), today)
            acc = "" if not tag else (f"  accepted {tag[0]} until {tag[1]}" if not tag[3] else
                                      f"  acceptance {tag[0]} EXPIRED {tag[1]}")
            print(f"  {q['id']} ({lens.key}): {q['title']}{acc}")
    for w in review.warnings():
        print(f"warning: {w}")
    nxt = review.next_question()
    if nxt:
        print(f"Next: {nxt[2]['id']} ({nxt[0].key}, {nxt[1]}): {nxt[2]['title']}")
    else:
        print("Every question is answered or marked not applicable. Write the report with: orr.py report")


def _md(text) -> str:
    return " ".join(str(text or "").split()).replace("|", "\\|")


def render_report(review: Review, today: datetime.date) -> str:
    d = review.data
    c = review.counts()
    total = len(review.rows)
    preliminary = review.scope == "core-path"
    out = [f"# ORR findings: {_md(d.get('workload'))}", "",
           "| Item | Value |", "|---|---|",
           f"| Workload | {_md(d.get('workload'))} |",
           f"| Milestone | {_md(d.get('milestone')) or 'none recorded'} |",
           f"| Review | {'Core path (preliminary: a go or no-go needs the full core)' if preliminary else 'Full'} |",
           f"| Lenses | {_md(review.lens_line())} |",
           f"| Started | {_md(d.get('started'))} |",
           f"| Report date | {today.isoformat()} |",
           f"| Progress | {total - c[UNANSWERED]} of {total} questions answered or not applicable |", "",
           "## Summary", "", "| Lens | Pillar | " + " | ".join(STATES) + " |",
           "|---|---|" + "---|" * len(STATES)]
    groups = {}
    for r in review.rows:
        groups.setdefault((r[0].name, r[1]), []).append(r)
    for (lname, pillar), rows in groups.items():
        gc = review.counts(rows)
        out.append(f"| {_md(lname)} | {_md(pillar)} | " + " | ".join(str(gc[s]) for s in STATES) + " |")
    out.append("| **All** | | " + " | ".join(f"**{c[s]}**" for s in STATES) + " |")

    signoff = next((r for r in review.rows if r[2]["id"] == SIGNOFF), None)
    out += ["", "## Readiness decision", ""]
    if signoff:
        out.append(f"`{SIGNOFF}` scores **{signoff[3]}**. The go or no-go decision belongs to the accountable "
                   "owner; record it, with its date, in your own records.")
    else:
        out.append("The core lens is not part of this review, so `readiness_signoff` was not answered.")
    if c[UNANSWERED]:
        out += ["", f"This report cannot support a go or no-go decision yet: {c[UNANSWERED]} questions are "
                    "unanswered."]
    if preliminary:
        out += ["", "This is a core-path review, so its result is preliminary."]
    warns = review.warnings()
    if warns:
        out += ["", "Warnings:", ""] + [f"- {_md(w)}" for w in warns]

    def risk_section(title, state):
        rows = [r for r in review.rows if r[3] == state]
        out.extend(["", f"## {title} ({len(rows)})", ""])
        if not rows:
            out.append("None.")
        for lens, pillar, q, _st, chosen, ans in rows:
            out.extend([f"### `{q['id']}`: {_md(q['title'])}", "", f"{_md(lens.name)}, {_md(pillar)}."])
            tag = exc_tag(ans.get("notes", ""), today) if state == "High" else None
            if tag:
                out.append(f"Accepted as {tag[0]} by role {tag[2]}, expiry {tag[1]}"
                           + (" (**expired**: the risk is open again)." if tag[3] else "."))
            if NONE_ID in chosen:
                out.append("Answered None of these.")
            missing = [ch for ch in q["choices"] if ch["id"] not in chosen and ch["id"] != NONE_ID]
            if missing:
                out.extend(["", "Not in place:", ""])
                for ch in missing:
                    plan = ch.get("improvementPlan") or {}
                    line = f"- `{ch['id']}`: {_md(ch['title'])}."
                    if plan.get("displayText"):
                        line += f" Improvement plan: {_md(plan['displayText'])}"
                        if plan.get("url"):
                            line += f" ({plan['url']})"
                    out.append(line)
            if ans.get("notes"):
                out.extend(["", f"Notes: {_md(ans['notes'])}"])
            out.append("")

    risk_section("High risks", "High")
    accepted = []
    for lens, _p, q, st, _ch, ans in review.rows:
        tag = exc_tag(ans.get("notes", ""), today) if st == "High" else None
        if tag:
            accepted.append(f"| `{q['id']}` | {_md(tag[0])} | {_md(tag[2])} | {tag[1]} | "
                            f"{'expired' if tag[3] else 'current'} |")
    out += ["## Accepted risks", ""]
    out += (["| Question | Register ID | Approver role | Expiry | Status |", "|---|---|---|---|---|"] + accepted
            if accepted else ["None recorded. Record an acceptance in the question notes as "
                              "`EXC:<register-id> exp:YYYY-MM-DD role:<approver-role>`."])
    risk_section("Medium risks", "Medium")
    na = [r for r in review.rows if r[3] == NOT_APPLICABLE]
    out += [f"## Not applicable ({len(na)})", ""]
    out += [f"- `{r[2]['id']}`: {_md(r[5].get('not_applicable'))}" for r in na] or ["None."]
    un = [r for r in review.rows if r[3] == UNANSWERED]
    out += ["", f"## Unanswered ({len(un)})", ""]
    out += [f"- `{r[2]['id']}` ({r[0].key}): {_md(r[2]['title'])}" for r in un] or ["None."]
    out += ["", "## All answers", "", "| Question | Lens | Risk | Selected |", "|---|---|---|---|"]
    for lens, _p, q, st, chosen, ans in review.rows:
        sel = ", ".join(f"`{x}`" for x in chosen) if chosen else ("" if st != NOT_APPLICABLE else "not applicable")
        out.append(f"| `{q['id']}` | {lens.key} | {st} | {sel} |")
    out += ["", "## About this report", "",
            "Scored by orr.py with the risk rules in the lens files, the same rules the AWS Well-Architected Tool "
            "applies to the imported lens. High means launch-blocking unless remediated or formally accepted in "
            "writing by the accountable owner. Medium means fix on a plan. This report is guidance; it is not an "
            "AWS certification, compliance attestation or audit, and it does not mean AWS reviewed the workload. "
            "It holds the review notes, so share it only through approved channels. Source: "
            "https://github.com/awslabs/operational-readiness-review-custom-war-lens", ""]
    return "\n".join(out)


def cmd_report(args):
    review = Review(args, Path(args.answers))
    text = render_report(review, datetime.date.today())
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    c = review.counts()
    print(f"wrote {out}: " + ", ".join(f"{s} {c[s]}" for s in STATES))


def main(argv=None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--lens-dir", action="append", metavar="DIR",
                        help="folder with the lens JSON files (repeatable; default: ., ./dist, "
                             "./wafr-operational-readiness-lens)")
    ap = argparse.ArgumentParser(prog="orr.py", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lenses", parents=[common], help="list the lens files found")
    p = sub.add_parser("questions", parents=[common], help="list the questions in review order")
    p.add_argument("--lens", choices=LENS_KEYS)
    p.add_argument("--core-path", action="store_true", help="only the 15 core-path questions of the core lens")
    p = sub.add_parser("show", parents=[common], help="print one question")
    p.add_argument("question_id")
    p = sub.add_parser("init", parents=[common], help="start an answers file")
    p.add_argument("answers")
    p.add_argument("--workload", required=True, help="a workload name with nothing sensitive in it")
    p.add_argument("--lens", default="core", help="comma-separated: core, event, genai (default core)")
    p.add_argument("--scope", choices=("full", "core-path"), default="full",
                   help="full (needed for a go or no-go) or core-path (triage and check-ins)")
    p.add_argument("--milestone", help="for example ORR-2026-11-launch")
    p.add_argument("--force", action="store_true", help="replace an existing answers file")
    p = sub.add_parser("answer", parents=[common], help="record one question's answer")
    p.add_argument("answers")
    p.add_argument("question_id")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--choices", help="comma-separated statement ids that are true today")
    g.add_argument("--none", action="store_true", help="None of these is true today")
    g.add_argument("--not-applicable", metavar="REASON", help="the whole question does not apply, with the reason")
    g.add_argument("--clear", action="store_true", help="remove the answer (and its notes)")
    p.add_argument("--notes", help="short notes with links to evidence; replaces earlier notes")
    p = sub.add_parser("status", parents=[common], help="progress, risks, warnings and the next question")
    p.add_argument("answers")
    p = sub.add_parser("report", parents=[common], help="write the findings report")
    p.add_argument("answers")
    p.add_argument("--out", required=True, help="Markdown file to write, for example orr-report.md")
    args = ap.parse_args(argv)
    if args.cmd == "answer" and not (args.choices is not None or args.none or args.not_applicable is not None
                                     or args.clear or args.notes is not None):
        ap.error("answer needs --choices, --none, --not-applicable, --clear or --notes")
    try:
        {"lenses": cmd_lenses, "questions": cmd_questions, "show": cmd_show, "init": cmd_init,
         "answer": cmd_answer, "status": cmd_status, "report": cmd_report}[args.cmd](args)
    except Problem as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
