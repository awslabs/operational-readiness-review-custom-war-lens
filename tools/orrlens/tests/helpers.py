"""Shared helpers for the orrlens unit tests (run: python3 -m unittest discover -s tools/orrlens/tests)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

TESTS = Path(__file__).resolve().parent
TOOLS = TESTS.parents[1]
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import yaml  # noqa: E402

FIXTURES = TESTS / "fixtures"
V136 = REPO / "wafr-operational-readiness-lens" / "orr-v1.3.6-PUBLISHED.json"


def sample_rules():
    return json.loads((FIXTURES / "sample_rules.json").read_text())["questions"]


def statement(sid, tier, **kw):
    s = {
        "id": sid,
        "tier": tier,
        "title": f"Statement {sid}",
        "concept": sid.replace("_", "-"),
        "good": "Good practice is in place.",
        "helpful_url": "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html",
        "improvement": "Put the practice in place.",
        "improvement_url": "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html",
    }
    if tier == "core" or tier.startswith("alt:"):
        s["severity_basis"] = "deviation: this test statement is rated higher than the Framework on purpose."
    s.update(kw)
    return s


def question(qid, pillar, prefix, statements, max_risk="HIGH", **kw):
    q = {
        "schema": "orrlens/question/1",
        "id": qid,
        "pillar": pillar,
        "order": 10,
        "title": f"Question {qid}",
        "max_risk": max_risk,
        "priority": "P0",
        "core_path": False,
        "category": "Deployment safety",
        "lineage": [],
        "choice_prefix": prefix,
        "description": {"question": "Is the practice in place?", "evidence_to_collect": "the runbook."},
        "helpful": {"display_text": "Well-Architected Framework",
                    "url": "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html"},
        "statements": statements,
    }
    q.update(kw)
    return q


class TempRepo:
    """A throwaway repository root with lens-src/ and an optional v1 folder."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def close(self):
        self._tmp.cleanup()

    def write(self, rel, content):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if not isinstance(content, str):
            content = yaml.safe_dump(content, sort_keys=False) if rel.endswith((".yaml", ".yml")) else \
                json.dumps(content, indent=2)
        p.write_text(content)
        return p

    def lens(self, key="core", version="2.0.0", pillars=("architecture",)):
        self.write(f"lens-src/{key}/lens.yaml", {
            "schema": "orrlens/lens/1", "key": key, "name": f"Test lens {key}", "version": version,
            "file_stem": f"orr-{key}", "description": "Test lens {version}.", "none_exclusive_guard": False,
            "pillars": [{"id": p, "name": f"01 - {p}"} for p in pillars]})

    def question(self, key, q):
        self.write(f"lens-src/{key}/{q['pillar']}/{q['id']}.yaml", q)

    def v1(self, version, questions):
        """questions: {question_id: [choice ids]} in one pillar named architecture."""
        doc = {"schemaVersion": "2021-11-01", "name": "v1", "description": "v1", "pillars": [{
            "id": "architecture", "name": "01 - Architecture", "questions": [
                {"id": qid, "title": f"{qid} (H)", "description": "d", "choices": [
                    {"id": c, "title": c, "improvementPlan": {"displayText": "x"}} for c in choices],
                 "riskRules": [{"condition": "default", "risk": "HIGH_RISK"}]}
                for qid, choices in questions.items()]}]}
        self.write(f"wafr-operational-readiness-lens/orr-v{version}-PUBLISHED.json", doc)
