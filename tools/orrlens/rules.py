"""Risk-rule generation from statement tiers, a safe condition evaluator, and exhaustive property proofs."""

from __future__ import annotations

import itertools
import re

from .config import NONE_ID

RISK_ORDER = {"NO_RISK": 0, "MEDIUM_RISK": 1, "HIGH_RISK": 2}
MAX_RISK_LABEL = {"HIGH": "HIGH_RISK", "MEDIUM": "MEDIUM_RISK"}


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _and(ids):
    return " && ".join(ids)


def _or(ids):
    return " || ".join(ids)


def _group(expr: str) -> str:
    """Parenthesize an expression that contains a top-level OR when it is combined with AND."""
    return f"({expr})" if "||" in expr else expr


def tier_sets(statements):
    scope = [s["id"] for s in statements if s["tier"] == "scope"]
    core = [s["id"] for s in statements if s["tier"] == "core"]
    sec = [s["id"] for s in statements if s["tier"] == "sec"]
    alts: dict[str, list[str]] = {}
    for s in statements:
        if s["tier"].startswith("alt:"):
            alts.setdefault(s["tier"][4:], []).append(s["id"])
    non_scope = [s["id"] for s in statements if s["tier"] != "scope"]
    return scope, core, alts, sec, non_scope


def generate_rules(statements, max_risk: str, none_guard: bool = False):
    """Return the riskRules list for one question (see lens-src/SCHEMA.md, "Tiers and generated rules").

    1. NO_RISK     = OR(scope statements) OR AND(all non-scope statements)
    2. MEDIUM_RISK = AND(core) AND OR(each alt group); only for HIGH-capped questions, and only when something
                     optional remains beyond it (a secondary statement, or an alt group with more than one member)
    3. default     = HIGH_RISK, or MEDIUM_RISK for MEDIUM-capped questions
    """
    scope, core, alts, sec, non_scope = tier_sets(statements)

    all_practices = _and(non_scope)
    if scope:
        parts = list(scope)
        if non_scope:
            parts.append(f"({all_practices})" if len(non_scope) > 1 else all_practices)
        no_risk = _or(parts)
    else:
        no_risk = all_practices
    rules = [{"condition": no_risk, "risk": "NO_RISK"}]

    if max_risk == "HIGH":
        alt_exprs = [_or(ids) for _, ids in sorted(alts.items())]
        if sec or alts:
            if not core and len(alt_exprs) == 1:
                medium = alt_exprs[0]
            else:
                medium = _and(list(core) + [_group(e) for e in alt_exprs])
            rules.append({"condition": medium, "risk": "MEDIUM_RISK"})
        rules.append({"condition": "default", "risk": "HIGH_RISK"})
    else:
        rules.append({"condition": "default", "risk": "MEDIUM_RISK"})

    if none_guard:
        for r in rules:
            if r["condition"] != "default":
                r["condition"] = f"{_group(r['condition'])} && !{NONE_ID}"
    return rules


# ---------------------------------------------------------------------------
# Safe evaluation of WA Tool conditions: identifiers, !, &&, ||, parentheses
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"\s*(\(|\)|&&|\|\||!|[A-Za-z_][A-Za-z0-9_]*)")


def tokenize(cond: str):
    pos, out = 0, []
    cond = cond.strip()
    while pos < len(cond):
        m = _TOKEN.match(cond, pos)
        if not m:
            raise ValueError(f"cannot parse condition at {pos}: {cond!r}")
        out.append(m.group(1))
        pos = m.end()
        while pos < len(cond) and cond[pos].isspace():
            pos += 1
    return out


def identifiers(cond: str):
    if cond.strip() == "default":
        return set()
    return {t for t in tokenize(cond) if t not in ("(", ")", "&&", "||", "!")}


def evaluate(cond: str, selected: set) -> bool:
    if cond.strip() == "default":
        return True
    tokens = tokenize(cond)
    if not tokens:
        raise ValueError("empty condition")
    pos = 0

    def parse_or():
        nonlocal pos
        val = parse_and()
        while pos < len(tokens) and tokens[pos] == "||":
            pos += 1
            rhs = parse_and()
            val = val or rhs
        return val

    def parse_and():
        nonlocal pos
        val = parse_not()
        while pos < len(tokens) and tokens[pos] == "&&":
            pos += 1
            rhs = parse_not()
            val = val and rhs
        return val

    def parse_not():
        nonlocal pos
        if pos < len(tokens) and tokens[pos] == "!":
            pos += 1
            return not parse_not()
        return parse_atom()

    def parse_atom():
        nonlocal pos
        if pos >= len(tokens):
            raise ValueError(f"unexpected end of condition {cond!r}")
        tok = tokens[pos]
        if tok == "(":
            pos += 1
            val = parse_or()
            if pos >= len(tokens) or tokens[pos] != ")":
                raise ValueError(f"missing ) in {cond!r}")
            pos += 1
            return val
        if tok in (")", "&&", "||", "!"):
            raise ValueError(f"expected a choice id, got {tok!r} in {cond!r}")
        pos += 1
        return tok in selected

    result = parse_or()
    if pos != len(tokens):
        raise ValueError(f"trailing tokens in {cond!r}")
    return result


def risk_of(rules, selected: set) -> str:
    for r in rules:
        if evaluate(r["condition"], selected):
            return r["risk"]
    return "UNMATCHED"


# ---------------------------------------------------------------------------
# Property proofs (exhaustive truth tables; at most 5 choices = 32 states)
# ---------------------------------------------------------------------------

def prove(question_id: str, statements, rules, max_risk: str, none_guard: bool = False):
    """Return a list of failure strings; empty means every property holds."""
    fails = []
    ids = [s["id"] for s in statements]
    scope, core, alts, sec, non_scope = tier_sets(statements)
    max_label = MAX_RISK_LABEL[max_risk]
    choice_ids = set(ids) | {NONE_ID}

    # Format
    if len(rules) > 3:
        fails.append("more than 3 rules")
    risks = [r["risk"] for r in rules]
    if len(set(risks)) != len(risks):
        fails.append("a risk level is used by more than one rule")
    conds = [" ".join(r["condition"].split()) for r in rules]
    if len(set(conds)) != len(conds):
        fails.append("two rules have the same condition")
    for r in rules:
        try:
            evaluate(r["condition"], set())
        except (ValueError, IndexError) as exc:
            return [f"{question_id}: unparseable condition {r['condition']!r}: {exc}"]
    if rules[-1]["condition"] != "default":
        fails.append("default is not the last rule")
    if sum(1 for r in rules if r["condition"] == "default") != 1:
        fails.append("exactly one default rule is required")
    for r in rules:
        unknown = identifiers(r["condition"]) - choice_ids
        if unknown:
            fails.append(f"rule references unknown ids {sorted(unknown)}")
        if "!" in r["condition"]:
            if not none_guard or r["condition"].count("!") != 1 or f"!{NONE_ID}" not in r["condition"]:
                fails.append(f"negation not allowed: {r['condition']}")
        if NONE_ID in identifiers(r["condition"]) and not none_guard:
            fails.append("a rule references none_no")
    if rules[-1]["risk"] != max_label:
        fails.append(f"default risk {rules[-1]['risk']} != max risk {max_label}")

    # None of these
    if risk_of(rules, {NONE_ID}) != max_label:
        fails.append("selecting only none_no does not give the maximum risk")
    if none_guard:
        for n in range(1, len(ids) + 1):
            for combo in itertools.combinations(ids, n):
                if risk_of(rules, set(combo) | {NONE_ID}) != max_label:
                    fails.append("none_no combined with other choices does not give the maximum risk")
                    break

    # Endpoints
    if risk_of(rules, set(ids)) != "NO_RISK":
        fails.append("selecting every statement does not give NO_RISK")
    for s in scope:
        if risk_of(rules, {s}) != "NO_RISK":
            fails.append(f"scope statement {s} alone does not give NO_RISK")

    # Monotonicity and effect over all non-empty subsets of statements
    states = [frozenset(c) for n in range(0, len(ids) + 1) for c in itertools.combinations(ids, n)]
    table = {st: risk_of(rules, set(st)) for st in states if st}
    for st in states:
        for s in ids:
            if s in st:
                continue
            bigger = st | {s}
            if st and RISK_ORDER[table[bigger]] > RISK_ORDER[table[st]]:
                fails.append(f"not monotone: adding {s} to {sorted(st)} raises risk")
    table[frozenset()] = risk_of(rules, set())   # nothing selected falls through to default
    for s in ids:
        if not any(table[st | {s}] != table[st] for st in states if s not in st):
            fails.append(f"statement {s} never changes the risk")

    # Tier meaning
    full = set(non_scope)
    for c in core:
        if risk_of(rules, full - {c}) != "HIGH_RISK":
            fails.append(f"dropping core {c} does not give HIGH")
    for s in sec:
        want = "MEDIUM_RISK"
        if risk_of(rules, full - {s}) != want:
            fails.append(f"dropping secondary {s} does not give MEDIUM")
    for grp, members in alts.items():
        if risk_of(rules, full - set(members)) != "HIGH_RISK":
            fails.append(f"dropping alt group {grp} does not give HIGH")
    # Without every core and one of each alt group, the score is the maximum risk regardless of secondaries
    for st in states:
        if not st or set(st) & set(scope):
            continue
        has_core = set(core) <= set(st)
        has_alts = all(set(m) & set(st) for m in alts.values())
        if not (has_core and has_alts) and table[st] != max_label:
            fails.append(f"incomplete selection {sorted(st)} scores {table[st]} instead of {max_label}")
    # Exact equivalence with the tier definition, for every subset of the choices (including none_no)
    all_choices = list(ids) + [NONE_ID]
    for n in range(0, len(all_choices) + 1):
        for combo in itertools.combinations(all_choices, n):
            sel = set(combo)
            want = expected_risk(statements, max_risk, none_guard, sel)
            got = risk_of(rules, sel)
            if got != want:
                fails.append(f"selection {sorted(sel)} scores {got}; the tier definition gives {want}")
    # Deduplicate while keeping order
    seen, out = set(), []
    for f in fails:
        if f not in seen:
            seen.add(f)
            out.append(f"{question_id}: {f}")
    return out


def expected_risk(statements, max_risk: str, none_guard: bool, selected: set) -> str:
    """The risk that the tier definition (lens-src/SCHEMA.md, "Tiers and generated rules") gives a selection.

    An oracle written independently of generate_rules: prove() compares the generated rules with it on every
    subset of choices, so a rule set that satisfies the listed properties but not the tier meaning still fails.
    """
    scope, core, alts, _sec, non_scope = tier_sets(statements)
    max_label = MAX_RISK_LABEL[max_risk]
    if none_guard and NONE_ID in selected:
        return max_label
    sel = set(selected) - {NONE_ID}
    if (set(scope) & sel) or (non_scope and set(non_scope) <= sel):
        return "NO_RISK"
    if max_risk == "HIGH" and set(core) <= sel and all(set(m) & sel for m in alts.values()):
        return "MEDIUM_RISK"
    return max_label


# ---------------------------------------------------------------------------
# Tier-agnostic property proofs for any published rule set (used on the legacy v1 files)
# ---------------------------------------------------------------------------

def none_choice_ids(choice_ids):
    """Choices that act as "None of these": the spec's _no suffix, plus the legacy v1 id noneofthese."""
    return [c for c in choice_ids if c.endswith("_no") or c == "noneofthese"]


def legacy_max_risk(title: str) -> str:
    """The maximum risk a v1 question claims in its title: (H) -> HIGH_RISK, (M) -> MEDIUM_RISK."""
    m = re.search(r"\((H|M|L)\)\s*$", title or "")
    return {"H": "HIGH_RISK", "M": "MEDIUM_RISK", "L": "MEDIUM_RISK"}.get(m.group(1) if m else "H")


def prove_rule_properties(question_id: str, choice_ids, rules, max_label: str):
    """Check the risk-rule properties that do not depend on tiers, for an arbitrary rule set.

    Properties: format (at most 3 rules, one per level, default last, known identifiers, no negation, None not
    referenced); "None of these" alone gives the maximum risk; the maximum risk is reachable; all practices give
    NO_RISK; adding a practice never raises the risk; every practice changes the risk in at least one state.
    Returns failure strings; empty means every property holds.
    """
    fails = []
    nones = none_choice_ids(choice_ids)
    practices = [c for c in choice_ids if c not in nones]
    known = set(choice_ids)

    if len(rules) > 3:
        fails.append("more than 3 rules")
    risks = [r.get("risk") for r in rules]
    if len(set(risks)) != len(risks):
        fails.append("a risk level is used by more than one rule")
    if not rules or rules[-1].get("condition") != "default":
        fails.append("default is not the last rule")
    if sum(1 for r in rules if r.get("condition") == "default") != 1:
        fails.append("exactly one default rule is required")
    parsed = []
    for r in rules:
        cond = r.get("condition", "")
        try:
            ids = identifiers(cond)
            evaluate(cond, set())
        except (ValueError, IndexError) as exc:
            fails.append(f"unparseable condition {cond!r}: {exc}")
            continue
        parsed.append(r)
        if ids - known:
            fails.append(f"rule references unknown ids {sorted(ids - known)}")
        if "!" in cond:
            fails.append(f"negation not allowed: {cond}")
        if ids & set(nones):
            fails.append(f"a rule references the None choice: {cond}")
    if len(parsed) != len(rules):
        return [f"{question_id}: {f}" for f in fails]

    def risk(sel):
        return risk_of(rules, set(sel))

    for n in nones:
        if risk({n}) != max_label:
            fails.append(f"selecting only {n} gives {risk({n})}, not the maximum risk {max_label}")
    states = [frozenset(c) for k in range(0, len(practices) + 1) for c in itertools.combinations(practices, k)]
    table = {st: risk(st) for st in states}
    reachable = {v for st, v in table.items() if st} | {risk({n}) for n in nones}
    if max_label not in reachable:
        fails.append(f"{max_label} is unreachable")
    if practices and table[frozenset(practices)] != "NO_RISK":
        fails.append(f"selecting every practice gives {table[frozenset(practices)]}, not NO_RISK")
    for st in states:
        if not st:
            continue
        for c in practices:
            if c in st:
                continue
            if RISK_ORDER.get(table[st | {c}], 3) > RISK_ORDER.get(table[st], 3):
                fails.append(f"not monotone: adding {c} to {sorted(st)} raises {table[st]} to {table[st | {c}]}")
    for c in practices:
        if not any(table[st | {c}] != table[st] for st in states if c not in st):
            fails.append(f"choice {c} never changes the risk")
    if "UNMATCHED" in table.values():
        fails.append("some selections match no rule")
    seen, out = set(), []
    for f in fails:
        if f not in seen:
            seen.add(f)
            out.append(f"{question_id}: {f}")
    return out
