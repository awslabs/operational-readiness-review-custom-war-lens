import copy
import json
import unittest

from helpers import V136, TempRepo, question, statement

from orrlens import checks as CK
from orrlens import config as C
from orrlens.docs import apply_block, begin_marker, end_marker
from orrlens.export import is_private
from orrlens.schema import validate


class Fixture(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()
        self.repo.lens("core", "2.0.0", pillars=("architecture",))
        self.repo.question("core", question("arch_q", "architecture", "aq_",
                                            [statement("aq_one", "core"), statement("aq_two", "sec")]))

    def tearDown(self):
        self.repo.close()

    def ctx(self):
        return CK.make_context(self.repo.root)


class Limits(Fixture):
    def test_clean_fixture_passes(self):
        fails, _ = CK.check_limits(self.ctx())
        self.assertEqual(fails, [])

    def test_each_limit_is_enforced(self):
        ctx = self.ctx()
        doc = ctx.rendered["core"]
        q = doc["pillars"][0]["questions"][0]
        q["title"] = "t" * 129
        q["description"] = "d" * 1025
        q["helpfulResource"]["displayText"] = "h" * 65
        q["choices"][0]["helpfulResource"]["displayText"] = "c" * 1025
        q["choices"][0]["additionalResources"] = [{"type": "HELPFUL_RESOURCE", "content": [
            {"displayText": "x", "url": "https://aws.amazon.com/"}] * 6}]
        q["choices"] = q["choices"] + [copy.deepcopy(q["choices"][1]) for _ in range(3)]
        doc["description"] = "l" * 1025
        doc["pillars"][0]["questions"] = [q] + [copy.deepcopy(q) for _ in range(20)]
        fails = " ".join(CK.check_limits(ctx)[0])
        for needle in ("title is 129 characters (limit 128)", "description is 1025 characters (limit 1024)",
                       "question helpful text is 65 characters (limit 64)", "helpfulResource text is 1025",
                       "6 HELPFUL_RESOURCE entries (limit 5)", "5 statements (lens policy limit 4)",
                       "21 questions (limit 20)", "lens description is 1025"):
            with self.subTest(needle):
                self.assertIn(needle, fails)

    def test_importlens_character_set(self):
        ctx = self.ctx()
        doc = ctx.rendered["core"]
        q = doc["pillars"][0]["questions"][0]
        q["description"] = "Evidence to collect: the runbook; the test report."
        q["choices"][0]["title"] = 'A "quoted" title'
        q["choices"][0]["helpfulResource"]["displayText"] = "Helpful text may use ; and % freely."
        doc["name"] = "Lens [draft]"
        fails = " ".join(CK.check_limits(ctx)[0])
        self.assertIn("description contains characters ImportLens rejects: ';'", fails)
        self.assertIn("title contains characters ImportLens rejects: '\"'", fails)
        self.assertIn("lens name contains characters ImportLens rejects: '[' ']'", fails)
        self.assertNotIn("helpfulResource", fails)
        q["description"] = "Allowed: letters, digits - _ . , : / ( ) @ ! & # + ' ?\nand newlines."
        q["choices"][0]["title"] = "Plain title"
        doc["name"] = "Lens"
        self.assertEqual(CK.check_limits(ctx)[0], [])

    def test_size_budget_and_version_names(self):
        ctx = self.ctx()
        ctx.rendered["core"]["description"] = "x" * (C.LENS_SIZE_BUDGET + 1)
        self.assertIn("budget", " ".join(CK.check_limits(ctx)[0]))
        self.assertTrue(CK.version_name_ok("2.0.0rc1"))
        self.assertFalse(CK.version_name_ok("2.0.0-rc1"))
        self.assertFalse(CK.version_name_ok("1" * 33))


class SourceAndRules(Fixture):
    def test_rules_and_ownership_pass(self):
        ctx = self.ctx()
        self.assertEqual(CK.check_source(ctx)[0], [])
        self.assertEqual(CK.check_rules(ctx)[0], [])
        self.assertEqual(CK.check_ownership(ctx)[0], [])

    def test_duplicate_concept_fails_ownership(self):
        self.repo.question("core", question("arch_two", "architecture", "at_",
                                            [statement("at_one", "core", concept="aq-one")], order=20))
        self.assertIn("concept aq-one is owned by 2 statements", " ".join(CK.check_ownership(self.ctx())[0]))

    def test_broken_yaml_does_not_crash(self):
        self.repo.write("lens-src/core/architecture/bad_q.yaml", "id: [unclosed\n")
        ctx = self.ctx()
        self.assertTrue(any("cannot parse YAML" in e for e in CK.check_source(ctx)[0]))
        self.assertEqual(CK.check_rules(ctx)[0], [])

    def test_severity_basis_against_wa_data(self):
        self.repo.write(C.DATA_WA_BPS, {"framework_version": "2024-11-06", "practices": {
            "REL05-BP02": {"title": "Throttle requests", "url": "https://docs.aws.amazon.com/x.html",
                           "level_of_risk": "High"},
            "REL12-BP05": {"title": "Test resiliency using chaos engineering", "url": "https://docs.aws.amazon.com/y.html",
                           "level_of_risk": "Medium"}}})
        self.repo.question("core", question("arch_q", "architecture", "aq_", [
            statement("aq_one", "core", severity_basis="wa:REL12-BP05 (High)"),
            statement("aq_two", "core", severity_basis="wa:REL05-BP02 (High)", wa_bp="REL99-BP01")]))
        fails = " ".join(CK.check_severity(self.ctx())[0])
        self.assertIn("REL12-BP05 has level of risk Medium", fails)
        self.assertIn("wa_bp REL99-BP01 is not in", fails)
        self.assertNotIn("aq_two: REL05-BP02", fails)


class Schema(unittest.TestCase):
    def test_both_engines_agree_on_v136(self):
        doc = json.loads(V136.read_text())
        a, _ = validate(doc)
        b, engine = validate(doc, force_builtin=True)
        self.assertEqual(engine, "builtin")
        self.assertEqual(len(a), len(b))
        self.assertTrue(any("Url" in e for e in b))     # a real v1.3.6 defect: "Url" instead of "url"

    def test_builtin_catches_structural_errors(self):
        doc = {"schemaVersion": "2020-01-01", "name": "n", "description": "d", "pillars": [
            {"id": "p!", "name": "p", "questions": [{"id": "qqq", "title": "t", "choices": [
                {"id": "c_1", "title": "c"}], "riskRules": [{"condition": "default", "risk": "LOW"}]}]}]}
        errs = " ".join(validate(doc, force_builtin=True)[0])
        self.assertIn("must equal '2021-11-01'", errs)
        self.assertIn("does not match", errs)
        self.assertIn("'improvementPlan' is a required property", errs)
        self.assertIn("'LOW' is not one of", errs)


class DocsBlocksAndExport(unittest.TestCase):
    def test_apply_block_canonical_and_alias_markers(self):
        text = f"# T\n\n{begin_marker('migration-mapping')}\nold\n{end_marker('migration-mapping')}\n\nafter\n"
        out = apply_block(text, "migration-mapping", "| new |")
        self.assertIn("| new |", out)
        self.assertNotIn("old", out)
        self.assertTrue(out.endswith("after\n"))
        self.assertEqual(apply_block(out, "migration-mapping", "| new |"), out)
        alias = "x\n<!-- BEGIN GENERATED DEVIATIONS -->\n<!-- END GENERATED DEVIATIONS -->\ny\n"
        self.assertEqual(apply_block(alias, "scoring-deviations", "rows"),
                         "x\n<!-- BEGIN GENERATED DEVIATIONS -->\nrows\n<!-- END GENERATED DEVIATIONS -->\ny\n")
        self.assertIsNone(apply_block("no markers here", "scoring-deviations", "rows"))

    def test_private_paths_are_never_exported(self):
        for rel in ("private/denylist.txt", "private/gates/x.json", ".gitlab-ci.yml", "build/release/a.json",
                    "docs/notes.private.md"):
            self.assertTrue(is_private(rel), rel)
        for rel in ("README.md", "privacy.md", "docs/private-sector.md", "tools/export_public.py"):
            self.assertFalse(is_private(rel), rel)


if __name__ == "__main__":
    unittest.main()
