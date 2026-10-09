"""Three-lens family (core, event, genai) and Well-Architected AI lens best-practice ids."""

import csv
import io
import unittest

import yaml
from helpers import REPO, TempRepo, question, statement

from orrlens import checks as CK
from orrlens import config as C
from orrlens import data as D
from orrlens import docs as DOCS
from orrlens import manifest as MAN
from orrlens import registry as REG
from orrlens.model import BASIS_RE, BP_RE, discover_lens_keys, validate_question
from orrlens.render import dumps

WA = "https://docs.aws.amazon.com/wellarchitected/latest"
WA_DATA = {
    "framework_version": "2024-11-06",
    "lenses": {"generative-ai": {"version": "2025-11-19"}, "agentic-ai": {"version": "2026-06-10"},
               "responsible-ai": {"version": "2025-11-19"}},
    "practices": {
        "REL05-BP02": {"title": "Throttle requests", "level_of_risk": "High",
                       "url": f"{WA}/reliability-pillar/rel_mitigate_interaction_failure_throttle_requests.html"},
        "GENOPS01-BP01": {"title": "Periodically evaluate functional performance", "level_of_risk": "High",
                          "lens": "generative-ai", "url": f"{WA}/generative-ai-lens/genops01-bp01.html"},
        "GENREL04-BP02": {"title": "Implement a model catalog", "level_of_risk": "Low",
                          "lens": "generative-ai", "url": f"{WA}/generative-ai-lens/genrel04-bp02.html"},
        "AGENTSEC02-BP01": {"title": "Implement tool authorization", "level_of_risk": "High",
                            "lens": "agentic-ai", "url": f"{WA}/agentic-ai-lens/agentsec02-bp01.html"},
        "RAISP01-BP01": {"title": "Detail your core AI system design in a system registry", "level_of_risk": "High",
                         "lens": "responsible-ai", "url": f"{WA}/responsible-ai-lens/raisp01-bp01.html"},
    },
}


class BestPracticeIds(unittest.TestCase):
    def test_framework_and_ai_lens_ids(self):
        for bp, src in (("REL05-BP02", "framework"), ("GENOPS01-BP01", "generative-ai"),
                        ("GENCOST05-BP01", "generative-ai"), ("AGENTSEC07-BP04", "agentic-ai"),
                        ("AGENTSUS01-BP01", "agentic-ai"), ("RAISP01-BP01", "responsible-ai"),
                        ("RAIMON01-BP02", "responsible-ai"), ("RAIUC05-BP01", "responsible-ai")):
            with self.subTest(bp):
                self.assertTrue(BP_RE.match(bp))
                self.assertTrue(BASIS_RE.match(f"wa:{bp} (High)"))
                self.assertEqual(C.wa_bp_source(bp), src)

    def test_malformed_ids_are_rejected(self):
        for bp in ("GENFOO01-BP01", "AGENT01-BP01", "RAIXX01-BP01", "GENOPS1-BP01", "genops01-bp01",
                   "GENOPS01-BP1", "XOPS01-BP01", "OPS01-BP01 ", "RAIRC"):
            with self.subTest(bp):
                self.assertIsNone(BP_RE.match(bp))
                self.assertIsNone(BASIS_RE.match(f"wa:{bp} (High)"))
                self.assertIsNone(C.wa_bp_source(bp))

    def test_question_validation_accepts_lens_ids(self):
        q = question("gai_q", "gai_models", "gq_", [
            statement("gq_one", "core", severity_basis="wa:AGENTSEC02-BP01 (High)", wa_bp="AGENTSEC02-BP01"),
            statement("gq_two", "sec", wa_bp="RAISP01-BP01")])
        e = []
        validate_question(q, "genai/gai_models/gai_q.yaml", ["gai_models"], "gai_models", e)
        self.assertEqual(e, [])
        q["statements"][1]["wa_bp"] = "GENFOO01-BP01"
        validate_question(q, "genai/gai_models/gai_q.yaml", ["gai_models"], "gai_models", e)
        self.assertTrue(any("bad wa_bp" in x for x in e), e)


class FamilyRepo(unittest.TestCase):
    """A temporary repository with three lenses, like core, event and genai."""

    def setUp(self):
        self.repo = TempRepo()
        r = self.repo
        r.lens("core", "2.0.0", pillars=("architecture",))
        r.lens("event", "1.0.0", pillars=("evt_prepare",))
        r.lens("genai", "1.0.0", pillars=("gai_models", "gai_operate"))
        r.question("core", question("arch_q", "architecture", "aq_", [statement("aq_one", "core")]))
        r.question("event", question("evt_q", "evt_prepare", "eq_", [statement("eq_one", "core")]))
        r.question("genai", question("gai_q", "gai_models", "gq_", [
            statement("gq_one", "core", severity_basis="wa:AGENTSEC02-BP01 (High)", wa_bp="AGENTSEC02-BP01"),
            statement("gq_two", "sec", wa_bp="GENOPS01-BP01")]))
        r.question("genai", question("gai_ops", "gai_operate", "go_", [
            statement("go_one", "core", severity_basis="wa:REL05-BP02 (High)", wa_bp="REL05-BP02")],
            helpful={"display_text": "GENOPS01-BP01 Periodically evaluate (Generative AI Lens)",
                     "url": f"{WA}/generative-ai-lens/genops01-bp01.html"}))
        r.write(C.DATA_WA_BPS, WA_DATA)
        r.write("docs/scoring.md", "Deviations: aq_one, eq_one.\n")

    def tearDown(self):
        self.repo.close()

    def ctx(self):
        return CK.make_context(self.repo.root)


class ThreeLenses(FamilyRepo):
    def test_order_and_render(self):
        self.repo.lens("aaa", "1.0.0", pillars=("aaa_pillar",))
        self.assertEqual(discover_lens_keys(self.repo.root), ["core", "event", "genai", "aaa"])
        (self.repo.root / "lens-src/aaa/lens.yaml").unlink()
        ctx = self.ctx()
        self.assertEqual([lz.key for lz in ctx.lenses], ["core", "event", "genai"])
        self.assertEqual(CK.check_source(ctx)[0], [])
        self.assertEqual(CK.check_rules(ctx)[0], [])
        self.assertEqual([p["id"] for p in ctx.rendered["genai"]["pillars"]], ["gai_models", "gai_operate"])

    def test_severity_accepts_high_ai_lens_basis_and_rejects_others(self):
        self.assertEqual(CK.check_severity(self.ctx())[0], [])
        self.repo.question("genai", question("gai_q", "gai_models", "gq_", [
            statement("gq_one", "core", severity_basis="wa:GENREL04-BP02 (High)"),
            statement("gq_two", "sec", wa_bp="AGENTOPS99-BP01")]))
        fails = " ".join(CK.check_severity(self.ctx())[0])
        self.assertIn("GENREL04-BP02 has level of risk Low", fails)
        self.assertIn("wa_bp AGENTOPS99-BP01 is not in", fails)

    def test_question_helpful_text_citing_a_lens_bp_must_link_its_page(self):
        self.repo.question("genai", question("gai_ops", "gai_operate", "go_", [
            statement("go_one", "core", severity_basis="wa:REL05-BP02 (High)")],
            helpful={"display_text": "GENOPS01-BP01 Periodically evaluate (Generative AI Lens)",
                     "url": f"{WA}/agentic-ai-lens/agentsec02-bp01.html"}))
        self.assertIn("helpful text cites GENOPS01-BP01 but links", " ".join(CK.check_severity(self.ctx())[0]))

    def test_family_cap_unique_stems_and_empty_pillars(self):
        r = self.repo
        r.lens("extra1", "1.0.0", pillars=("x1_p",))
        r.lens("extra2", "1.0.0", pillars=("x2_p",))
        r.question("extra1", question("x1_q", "x1_p", "xa_", [statement("xa_one", "core")]))
        r.question("extra2", question("x2_q", "x2_p", "xb_", [statement("xb_one", "core")]))
        fails = " ".join(CK.check_source(self.ctx())[0])
        self.assertIn(f"capped at {C.MAX_FAMILY_LENSES}", fails)
        (r.root / "lens-src/extra2/lens.yaml").unlink()
        r.write("lens-src/extra1/lens.yaml", dict(yaml.safe_load((r.root / "lens-src/genai/lens.yaml").read_text()),
                                                   key="extra1", pillars=[{"id": "x1_p", "name": "01 - X"},
                                                                          {"id": "x1_empty", "name": "02 - Y"}]))
        fails = " ".join(CK.check_source(self.ctx())[0])
        self.assertNotIn("capped", fails)
        self.assertIn("file_stem 'orr-genai' is also used by genai", fails)
        self.assertIn("name 'Test lens genai' is also used by genai", fails)
        self.assertIn("pillar x1_empty has no questions", fails)

    def test_family_rules_ignore_the_lens_filter(self):
        r = self.repo
        r.lens("extra1", "1.0.0", pillars=("x1_p",))
        r.lens("extra2", "1.0.0", pillars=("x2_p",))
        r.question("extra1", question("x1_q", "x1_p", "xa_", [statement("xa_one", "core")]))
        r.question("extra2", question("x2_q", "x2_p", "xb_", [statement("xb_one", "core")]))
        fails, notes = CK.check_source(CK.make_context(r.root, "genai"))
        self.assertIn(f"capped at {C.MAX_FAMILY_LENSES}", " ".join(fails))
        self.assertTrue(any("family rules checked all 5 lenses" in n for n in notes))

    def test_lens_without_questions_and_key_mismatch(self):
        r = self.repo
        for f in (r.root / "lens-src/genai").glob("*/*.yaml"):
            f.unlink()
        ctx = self.ctx()
        self.assertIn("genai: lens.yaml has no question files yet", CK.check_source(ctx)[0])
        self.assertTrue(any("cannot be built while genai" in f for f in CK.check_reproducibility(ctx)[0]))
        r.write("lens-src/genai/lens.yaml", dict(yaml.safe_load((r.root / "lens-src/genai/lens.yaml").read_text()),
                                                  key="gen"))
        self.assertTrue(any("key must equal the folder name 'genai'" in e for e in CK.check_source(self.ctx())[0]))


class WaData(FamilyRepo):
    def test_lens_field_versions_and_validation(self):
        df = D.load_wa_bps(self.repo.root)
        self.assertEqual(df.problems, [])
        self.assertEqual(df.entries["REL05-BP02"]["lens"], "framework")
        self.assertEqual(df.entries["REL05-BP02"]["framework_version"], "2024-11-06")
        g = df.entries["GENOPS01-BP01"]
        self.assertEqual((g["lens"], g["lens_version"], g["framework_version"]), ("generative-ai", "2025-11-19", ""))
        self.assertEqual(g["source_name"], "Generative AI Lens")

    def test_wrong_lens_wrong_url_and_unknown_lens(self):
        bad = {"lenses": {"generative-ai": {"version": "2025-11-19"}, "quantum": {"version": "x"}}, "practices": {
            "GENOPS01-BP01": {"title": "t", "level_of_risk": "High", "lens": "agentic-ai",
                              "url": f"{WA}/agentic-ai-lens/genops01-bp01.html"},
            "GENOPS02-BP01": {"title": "t", "level_of_risk": "High",
                              "url": f"{WA}/generative-ai-lens/genops02-bp01.html"},
            "GENOPS02-BP02": {"title": "t", "level_of_risk": "High", "lens": "generative-ai",
                              "url": f"{WA}/framework/genops02-bp02.html"},
            "AGENTOPS01-BP01": {"title": "t", "level_of_risk": "High", "lens": "agentic-ai",
                                "url": f"{WA}/agentic-ai-lens/agentops01-bp01.html"},
            "REL05-BP02": {"title": "t", "level_of_risk": "High", "lens": "fabric",
                           "url": f"{WA}/reliability-pillar/x.html"}}}
        self.repo.write(C.DATA_WA_BPS, bad)
        probs = " ".join(D.load_wa_bps(self.repo.root).problems)
        self.assertIn("lenses: unknown lens 'quantum'", probs)
        self.assertIn("GENOPS01-BP01 does not have the Agentic AI Lens id format (set lens: generative-ai)", probs)
        self.assertIn("GENOPS02-BP01 does not have the AWS Well-Architected Framework id format", probs)
        self.assertIn("GENOPS02-BP02: https://docs.aws.amazon.com/wellarchitected/latest/framework/genops02-bp02.html "
                      "is not a Generative AI Lens page", probs)
        self.assertIn("AGENTOPS01-BP01: no lens_version", probs)
        self.assertIn("REL05-BP02: unknown lens 'fabric'", probs)


class Docs(FamilyRepo):
    def test_csvs_carry_the_orr_lens_and_bp_source(self):
        ctx = self.ctx()
        files, _ = DOCS.generate(self.repo.root, ctx.lenses, ctx.rendered, ctx.data("wa"))
        own = list(csv.DictReader(io.StringIO(files["docs/ownership.csv"])))
        self.assertEqual(list(own[0]), ["concept", "owner_question", "statement", "v1_ids_absorbed", "orr_lens"])
        self.assertEqual({r["statement"]: r["orr_lens"] for r in own},
                         {"aq_one": "core", "eq_one": "event", "gq_one": "genai", "gq_two": "genai",
                          "go_one": "genai"})
        rows = {r["statement_id"]: r for r in csv.DictReader(io.StringIO(files["crosswalk/wa-bp-map.csv"]))}
        self.assertEqual(rows["gq_one"]["bp_source"], "Agentic AI Lens")
        self.assertEqual(rows["gq_one"]["bp_source_version"], "2026-06-10")
        self.assertEqual(rows["gq_one"]["framework_version"], "")
        self.assertEqual(rows["go_one"]["bp_source"], "AWS Well-Architected Framework")
        self.assertEqual((rows["go_one"]["framework_version"], rows["go_one"]["bp_source_version"]),
                         ("2024-11-06", "2024-11-06"))
        self.assertEqual(rows["gq_two"]["orr_lens"], "genai")
        q = files["docs/questions.md"]
        for name in ("Test lens core 2.0.0", "Test lens event 1.0.0", "Test lens genai 1.0.0"):
            self.assertIn(f"## {name}", q)

    def test_scoring_block_lists_deviations_of_every_lens(self):
        block = DOCS.scoring_block(self.ctx().lenses)
        for sid in ("aq_one", "eq_one"):
            self.assertIn(f"`{sid}`", block)


class ReleaseAssets(FamilyRepo):
    def test_manifest_and_staging_cover_every_lens(self):
        ctx = self.ctx()
        man = MAN.build_manifest(ctx, None)
        self.assertEqual([lz["key"] for lz in man["lenses"]], ["core", "event", "genai"])
        g = man["lenses"][2]
        self.assertEqual((g["file"], g["min_file"], g["latest_alias"], g["latest_min_alias"]),
                         ("orr-genai-1.0.0.json", "orr-genai-1.0.0.min.json", "orr-genai.json", "orr-genai.min.json"))
        self.assertEqual(set(CK.expected_outputs(ctx)), {f"dist/{s}{x}" for s in ("orr-core-2.0.0", "orr-event-1.0.0",
                                                                                   "orr-genai-1.0.0")
                                                          for x in (".json", ".min.json")})
        rel = self.repo.root / "build" / "release"
        MAN.write(ctx, rel)
        staged = {p.name for p in rel.iterdir()}
        for name in ("orr-genai-1.0.0.json", "orr-genai-1.0.0.min.json", "orr-genai.json", "orr-genai.min.json",
                     "orr-core.json", "orr-event.min.json", "manifest.json", "SHA256SUMS"):
            self.assertIn(name, staged)
        sums = (rel / "SHA256SUMS").read_text()
        self.assertIn("  orr-genai.min.json\n", sums)
        self.assertEqual((rel / "orr-genai.json").read_text(), dumps(ctx.rendered["genai"]))

    def test_release_copies_in_the_v1_folder(self):
        ctx = self.ctx()
        v1 = self.repo.root / C.V1_DIR
        v1.mkdir()
        exp = CK.expected_outputs(ctx)
        for rel, content in exp.items():
            if "genai" not in rel:
                (v1 / rel.split("/")[-1]).write_text(content)
        probs = CK.release_copy_problems(ctx)
        self.assertEqual(sorted(probs), [f"{C.V1_DIR}/orr-genai-1.0.0{x} does not exist yet (copy it at release)"
                                         for x in (".json", ".min.json")])
        for rel, content in exp.items():
            if "genai" in rel:
                (v1 / rel.split("/")[-1]).write_text(content)
        self.assertEqual(CK.release_copy_problems(ctx), [])
        (v1 / "orr-genai.json").write_text("{}\n")
        self.assertEqual(CK.release_copy_problems(ctx),
                         [f"{C.V1_DIR}/orr-genai.json differs from dist/orr-genai-1.0.0.json"])

    def test_ids_register_the_new_lens(self):
        lenses = self.ctx().lenses
        reg = REG.compute_registry(self.repo.root, lenses)
        self.assertEqual(reg["lenses"]["genai"], {"current_version": "1.0.0"})
        self.assertEqual(reg["pillars"]["gai_models"], {"lens": "genai", "introduced": "1.0.0", "status": "active"})
        self.assertEqual(reg["choices"]["gai_q/gq_one"]["lens"], "genai")
        self.assertEqual(reg["choices"]["gai_q/none_no"]["introduced"], "1.0.0")


class RepositoryData(unittest.TestCase):
    """The real lens-src/genai/lens.yaml and data/wa-best-practices.yaml."""

    def test_genai_lens_metadata(self):
        meta = yaml.safe_load((REPO / "lens-src/genai/lens.yaml").read_text())
        self.assertEqual((meta["key"], meta["name"], meta["file_stem"]),
                         ("genai", "ORR - Generative AI and Agents", "orr-genai"))
        # The version moves with each release; it must be SemVer and match the ID registry.
        self.assertRegex(meta["version"], r"^1\.\d+\.\d+$")
        ids = yaml.safe_load((REPO / "ids.yaml").read_text())
        self.assertEqual(ids["lenses"]["genai"]["current_version"], meta["version"])
        self.assertIs(meta["none_exclusive_guard"], True)
        self.assertEqual([(p["id"], p["name"]) for p in meta["pillars"]], [
            ("gai_models", "01 - Models, capacity and dependencies"),
            ("gai_release", "02 - Change safety and evaluation"),
            ("gai_operate", "03 - Operations and safeguards")])
        self.assertLessEqual(len(" ".join(meta["description"].split()).replace("{version}", meta["version"])),
                             C.MAX_LENS_DESCRIPTION)
        self.assertIn("genai", C.LENS_ORDER)

    def test_wa_data_file_is_clean_and_records_ai_lens_sources(self):
        df = D.load_wa_bps(REPO)
        self.assertEqual(df.problems, [])
        by_lens: dict = {}
        for e in df.entries.values():
            by_lens.setdefault(e["lens"], []).append(e)
        for lens in ("generative-ai", "agentic-ai", "responsible-ai"):
            with self.subTest(lens):
                self.assertTrue(by_lens.get(lens))
                self.assertTrue(all(e["lens_version"] for e in by_lens[lens]))


class GenAiLifecycleData(unittest.TestCase):
    """The generative AI entries of the real data/lifecycle-denylist.yaml match what they should, and only that."""

    @classmethod
    def setUpClass(cls):
        df = D.load_lifecycle(REPO)
        cls.rxs = CK._lifecycle_regexes(df)

    def hits(self, text):
        return {name for name, rx, kind in self.rxs if kind == "text" and rx is not None and rx.search(text)}

    def test_closed_and_preview_items_are_found(self):
        for text, name in (("Use SageMaker AI Ground Truth work teams.", "Amazon SageMaker Ground Truth"),
                           ("Route reviews to Amazon Augmented AI.", "Amazon SageMaker A2I (Augmented AI)"),
                           ("Enable SageMaker Debugger rules.", "Amazon SageMaker Debugger"),
                           ("Use the Mechanical Turk workforce.", "Amazon Mechanical Turk workforce for SageMaker AI"),
                           ("Turn on SageMaker AI data capture.", "Amazon SageMaker Model Monitor"),
                           ("Call InvokeInlineAgent with inline agents.", "Amazon Bedrock Agents Classic"),
                           ("Add the AMAZON.UserInput tool.", "Amazon Bedrock Agents Classic"),
                           ("Use latency-optimized inference.", "Amazon Bedrock latency-optimized inference (preview)"),
                           ("Review AgentCore insights.", "Amazon Bedrock AgentCore insights (preview)")):
            with self.subTest(text):
                self.assertIn(name, self.hits(text))

    def test_current_services_and_generic_words_are_not_matched(self):
        for text in ("Compare answers with ground truth data.", "Amazon Bedrock AgentCore harness inline function tools",
                     "agents on Amazon Bedrock AgentCore", "Amazon Bedrock Evaluations automated jobs",
                     "SageMaker AI shadow tests and inference components", "Amazon Bedrock Guardrails image filters"):
            with self.subTest(text):
                self.assertEqual(self.hits(text), set())


class GenAiPartitionData(unittest.TestCase):
    """Partition facts for the generative AI services and features, as recorded on 2026-10-07."""

    def test_govcloud_values(self):
        df = D.load_partitions(REPO)
        self.assertEqual(df.problems, [])
        gov = {k: e["aws-us-gov"] for k, e in df.entries.items()}
        for name, want in (("Amazon Bedrock", "available"), ("Amazon Bedrock AgentCore", "available"),
                           ("Amazon Bedrock AgentCore Policy", "available"),
                           ("Amazon Bedrock Knowledge Bases", "available"), ("Amazon Bedrock Evaluations", "available"),
                           ("Amazon Bedrock global cross-Region inference", "not available"),
                           ("Amazon Bedrock Guardrails organization-level enforcement", "not available"),
                           ("Amazon Bedrock Guardrails account-level enforcement", "available"),
                           ("Amazon Bedrock Guardrails Automated Reasoning checks", "not available"),
                           ("Amazon CloudWatch generative AI observability", "not available"),
                           ("Amazon CloudWatch Omni", "not available"), ("Amazon SageMaker AI", "available"),
                           ("Amazon Bedrock Reserved tier", "available"),
                           ("Strands Agents", "n/a")):
            with self.subTest(name):
                self.assertEqual(gov.get(name), want)
                if want != "n/a":
                    self.assertEqual(df.entries[name]["aws"], "available")


if __name__ == "__main__":
    unittest.main()
