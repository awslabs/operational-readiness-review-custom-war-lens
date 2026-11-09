"""The agent skill's stand-alone scorer (skills/orr-review/scripts/orr.py) agrees with the generator and the
lens sources, and its review commands work end to end on the built lens files."""

import contextlib
import datetime
import importlib.util
import io
import itertools
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from helpers import REPO, V136

from orrlens import checks as CK
from orrlens import config as C
from orrlens import docs as DOCS
from orrlens.rules import risk_of
from orrlens.textscan import placeholder_problems

SCRIPT = REPO / "skills" / "orr-review" / "scripts" / "orr.py"
_spec = importlib.util.spec_from_file_location("orr_skill", SCRIPT)
orr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orr)
CTX = CK.make_context(REPO)


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = orr.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Scorer(unittest.TestCase):
    def test_risk_rules_match_the_generator_on_every_answer(self):
        docs = list(CTX.rendered.values()) + [json.loads(V136.read_text(encoding="utf-8"))]
        n = 0
        for doc in docs:
            for p in doc["pillars"]:
                for q in p["questions"]:
                    ids = [c["id"] for c in q["choices"]]
                    for k in range(len(ids) + 1):
                        for combo in itertools.combinations(ids, k):
                            n += 1
                            self.assertEqual(orr.risk_of(q["riskRules"], set(combo)),
                                             risk_of(q["riskRules"], set(combo)), f"{q['id']} {combo}")
        self.assertGreater(n, 1000)

    def test_constants_match_the_lens_sources(self):
        lenses = {lens.key: lens for lens in CTX.lenses}
        self.assertEqual(set(orr.LENS_KEYS), set(lenses))
        for key, lens in lenses.items():
            self.assertEqual(orr.LENS_NAMES[key], lens.meta["name"])
            self.assertEqual(f"orr-{key}", lens.meta["file_stem"])
        core = {q["id"]: q for q in lenses["core"].questions}
        self.assertEqual(set(orr.CORE_PATH), {qid for qid, q in core.items() if q.get("core_path")})
        self.assertIn(orr.SCOPE_COMPLETE, [s["id"] for s in core[orr.SIGNOFF]["statements"]])
        self.assertEqual(orr.NONE_ID, C.NONE_ID)

    def test_acceptance_tags(self):
        today = datetime.date(2026, 11, 6)
        self.assertEqual(orr.exc_tag("EXC:RR-0142 exp:2027-03-31 role:authorizing-official", today),
                         ("RR-0142", "2027-03-31", "authorizing-official", False))
        self.assertTrue(orr.exc_tag("PLAN:x T-1 due:2026-12-01 EXC:RR-1 exp:2026-11-05 role:owner", today)[3])
        self.assertIsNone(orr.exc_tag("accepted by the owner", today))
        # Assembled at run time, so the wording check never sees a literal account ID in this file.
        self.assertEqual(orr.sensitive_hits("account " + "2109" + "87654321"), ["an AWS account ID"])
        self.assertEqual(orr.sensitive_hits("account 123456789012, run 20261106120000"), [])


REFS = REPO / DOCS.SKILL_DIR / "references"
RISK_IDS = {"No risk": "NO_RISK", "Medium": "MEDIUM_RISK", "High": "HIGH_RISK"}
# Quick custom chat agents keep at most 100K characters of reference text; keep each bundled file well under it.
REFERENCE_BUDGET = 60_000


def parse_lens_md(text):
    """question id -> (max risk, [choice ids], [(risk, condition)]) from a bundled lens-<key>.md, in file order."""
    out = {}
    for block in text.split("\n### `")[1:]:
        qid = block.split("`", 1)[0]
        max_risk = re.search(r"^Maximum risk: (High|Medium)\.", block, re.M).group(1)
        choices = re.findall(r"^- `([a-z0-9_]+)`", block, re.M)
        rules = []
        for risk, words in re.findall(r"^\d+\. (No risk|Medium|High): (.+)$", block, re.M):
            cond = "default" if words == "otherwise" else (
                words.replace("`", "").replace(" AND ", " && ").replace(" OR ", " || ").replace("NOT ", "!"))
            rules.append({"risk": RISK_IDS[risk], "condition": cond})
        out[qid] = (max_risk, choices, rules)
    return out


class BundledReferences(unittest.TestCase):
    """The plain-text lens in the skill (reference mode, for Amazon Quick) stays equal to the lens."""

    def test_references_are_current(self):
        files = DOCS.skill_files(REPO, CTX.lenses, CTX.rendered)
        self.assertEqual(len(files), 2 * len(CTX.lenses))
        for rel, content in files.items():
            with self.subTest(rel):
                self.assertEqual((REPO / rel).read_text(encoding="utf-8"), content,
                                 f"{rel} is stale; run python3 -m tools.orrlens docs")
                self.assertLessEqual(len(content), REFERENCE_BUDGET)
                self.assertTrue(content.isascii())

    def test_hand_scoring_matches_the_rules_on_every_answer(self):
        """Scoring the way each lens file tells the agent to gives the JSON rules' risk for every combination."""
        n = 0
        for lens in CTX.lenses:
            doc = CTX.rendered[lens.key]
            parsed = parse_lens_md((REFS / f"lens-{lens.key}.md").read_text(encoding="utf-8"))
            questions = [q for p in doc["pillars"] for q in p["questions"]]
            self.assertEqual(list(parsed), [q["id"] for q in questions])
            self.assertIn(f"# ORR lens: {doc['name']} {lens.version}\n", (REFS / f"lens-{lens.key}.md").read_text())
            for q in questions:
                max_risk, choices, rules = parsed[q["id"]]
                ids = [c["id"] for c in q["choices"]]
                self.assertEqual(choices, ids, q["id"])
                top = "HIGH_RISK" if max_risk == "High" else "MEDIUM_RISK"
                for k in range(len(ids) + 1):
                    for combo in itertools.combinations(ids, k):
                        sel = set(combo)
                        by_hand = top if C.NONE_ID in sel else orr.risk_of(rules, sel)
                        self.assertEqual(by_hand, orr.risk_of(q["riskRules"], sel), f"{q['id']} {combo}")
                        n += 1
        self.assertGreater(n, 800)

    def test_pillar_counts_are_stated(self):
        """The report's per-pillar counts come from the lens file, so the agent never counts questions itself."""
        for lens in CTX.lenses:
            text = (REFS / f"lens-{lens.key}.md").read_text(encoding="utf-8")
            doc = CTX.rendered[lens.key]
            for p in doc["pillars"]:
                self.assertIn(f"| {p['name']} | {len(p['questions'])} |\n", text)
            total = sum(len(p["questions"]) for p in doc["pillars"])
            self.assertIn(f"| All | {total} |\n", text)

    def test_every_plan_is_bundled(self):
        for lens in CTX.lenses:
            text = (REFS / f"plans-{lens.key}.md").read_text(encoding="utf-8")
            for p in CTX.rendered[lens.key]["pillars"]:
                for q in p["questions"]:
                    for c in q["choices"]:
                        plan = (c.get("improvementPlan") or {}).get("displayText")
                        if plan and c["id"] != C.NONE_ID:
                            self.assertIn(f"- `{c['id']}`: {' '.join(plan.split())}\n", text)

    def test_skill_names_every_bundled_file(self):
        skill = (REPO / DOCS.SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        for path in sorted(REFS.iterdir()):
            self.assertIn(f"references/{path.name}", skill.replace("<lens>", "core"), path.name)


class Review(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.lens_dir = self.tmp / "lenses"
        self.lens_dir.mkdir()
        for lens in CTX.lenses:
            src = REPO / "dist" / f"{lens.meta['file_stem']}-{lens.version}.json"
            shutil.copy(src, self.lens_dir / f"orr-{lens.key}.json")
        (self.lens_dir / "orr-event-0.9.0.json").write_text('{"name": "something else"}', encoding="utf-8")
        self.answers = str(self.tmp / "orr-answers.json")
        self.ld = ["--lens-dir", str(self.lens_dir)]

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_lens_discovery(self):
        found, notes = orr.find_lenses([self.lens_dir])
        self.assertEqual({k: v[0].version for k, v in found.items()},
                         {lens.key: lens.version for lens in CTX.lenses})
        self.assertTrue(any("orr-event-0.9.0.json" in n for n in notes))
        code, _, err = run("lenses", "--lens-dir", str(self.tmp / "missing"))
        self.assertEqual(code, 1)
        self.assertIn("releases/latest/download/orr-core.json", err)

    def test_review_flow(self):
        self.assertEqual(run("init", self.answers, "--workload", "demo", "--lens", "core,genai", *self.ld)[0], 0)
        self.assertEqual(run("init", self.answers, "--workload", "demo", *self.ld)[0], 1)   # never overwritten
        code, out, _ = run("answer", self.answers, "event_alarms", "--choices",
                           "slo_defined,slo_alarms_before_breach", *self.ld)
        self.assertEqual((code, out.split(" (")[0]), (0, "event_alarms: Medium"))
        self.assertEqual(run("answer", self.answers, "event_alarms", "--choices", "slo_defined,none_no",
                             *self.ld)[0], 1)
        self.assertEqual(run("answer", self.answers, "event_alarms", "--choices", "no_such_id", *self.ld)[0], 1)
        self.assertEqual(run("answer", self.answers, "event_gameday", "--not-applicable", " ", *self.ld)[0], 1)
        run("answer", self.answers, "well_architected", "--none", "--notes",
            "EXC:RR-9 exp:2020-01-31 role:business-owner", *self.ld)
        run("answer", self.answers, "gai_runaway_cost", "--not-applicable", "No model calls in this release", *self.ld)
        run("answer", self.answers, "readiness_signoff", "--choices", "rd_scope_complete", *self.ld)
        code, out, _ = run("status", self.answers, *self.ld)
        self.assertEqual(code, 0)
        self.assertIn("High 2, Medium 1, No risk 0, Not applicable 1", out)
        self.assertIn("EXPIRED", out)
        self.assertIn("rd_scope_complete is selected but", out)
        report = self.tmp / "orr-report.md"
        self.assertEqual(run("report", self.answers, "--out", str(report), *self.ld)[0], 0)
        text = report.read_text(encoding="utf-8")
        for needle in ("## High risks (2)", "### `event_alarms`", "`slo_alarm_quality`", "| `well_architected` | RR-9",
                       "expired", "- `gai_runaway_cost`: No model calls in this release",
                       "This report cannot support a go or no-go decision yet: 41 questions are unanswered."):
            self.assertIn(needle, text)
        self.assertTrue(text.isascii())
        self.assertEqual(placeholder_problems(text), [])

    def test_core_path_scope(self):
        run("init", self.answers, "--workload", "demo", "--scope", "core-path", *self.ld)
        self.assertEqual(run("answer", self.answers, "well_architected", "--none", *self.ld)[0], 1)  # off the path
        code, out, _ = run("status", self.answers, *self.ld)
        self.assertIn(f"0 of {len(orr.CORE_PATH)} answered", out)
        data = json.loads(Path(self.answers).read_text(encoding="utf-8"))
        self.assertEqual(data["scope"], "core-path")


if __name__ == "__main__":
    unittest.main()
