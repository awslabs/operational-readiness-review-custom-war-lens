"""Regression tests for the toolchain hardening: export safety, URL allowlist, reader notes, lifecycle URLs,
partition notes, language rules, denylist matching and the exact rule oracle."""

import codecs
import contextlib
import io
import itertools
import os
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from helpers import TOOLS, TempRepo, question, statement

from orrlens import checks as CK
from orrlens import config as C
from orrlens.export import ExportError, export_files, is_private, sensitive_patterns, wording_scan
from orrlens.model import validate_question
from orrlens.release_notes import ReleaseNotesError, notes_for
from orrlens.rules import evaluate, expected_risk, generate_rules, prove
from orrlens.textscan import (ServiceMatcher, bare_hosts, decode_text, extract_urls, is_self_repo_url,
                              language_problems, parse_denylist, scan_text_with_denylist, strip_statement_reader_notes,
                              url_allowed)

# Rejected wording is assembled at run time so this file never contains it literally (the internal-wording scan
# covers every exported file, tests included).
NOT_YET = "not" + " yet"
ACCOUNT = "4" * 6 + "1" * 6
DOCS = "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html"


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


class GitRepo:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        git(self.root, "init", "-q")

    def write(self, rel, content):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content)
        return p

    def close(self):
        self._tmp.cleanup()


class ExportSafety(unittest.TestCase):
    def setUp(self):
        self.repo = GitRepo()
        self.repo.write("README.md", "Public readme.\n")
        self.repo.write("private/gates/x.json", '{"arn": "arn:aws:wellarchitected:us-east-1:' + ACCOUNT + ':lens/a"}\n')

    def tearDown(self):
        self.repo.close()

    def test_symlink_to_private_is_refused(self):
        os.symlink("../private/gates/x.json", self.repo.root / "docs-gate.json")
        (self.repo.root / "docs").mkdir()
        os.symlink("../private/gates/x.json", self.repo.root / "docs" / "gate-sample.json")
        git(self.repo.root, "add", "-A")
        with self.assertRaises(ExportError) as cm:
            export_files(self.repo.root)
        self.assertIn("symbolic links are never exported", str(cm.exception))
        self.assertIn("docs/gate-sample.json", str(cm.exception))

    def test_git_less_tree_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.md").write_text("x")
            with self.assertRaises(ExportError):
                export_files(Path(d))

    def test_more_private_paths(self):
        for rel in (".gitlab-ci.yaml", ".gitlab/ci/x.yml", "docs/private/notes.md", "a/b/private/c.txt",
                    "ci/.gitlab-ci.yml", ".gitlab-include.yml"):
            self.assertTrue(is_private(rel), rel)
        for rel in ("docs/private-sector.md", "privacy.md", "tools/export_public.py"):
            self.assertFalse(is_private(rel), rel)

    def test_wording_scan_fails_on_unscannable_encodings_and_finds_account_ids(self):
        pats, _ = parse_denylist("secret phrase\n")
        r = self.repo
        r.write("docs/utf16.md", codecs.BOM_UTF16_LE + "a secret phrase here".encode("utf-16-le"))
        r.write("docs/latin1.md", "caf\xe9 text".encode("latin-1"))
        r.write("docs/ids.md", f"account {ACCOUNT} and the placeholder 123456789012\n")
        r.write("_img/x.png", b"\x89PNG\x00\x01")
        files = ["docs/utf16.md", "docs/latin1.md", "docs/ids.md", "_img/x.png"]
        hits = " | ".join(wording_scan(r.root, files, pats + sensitive_patterns()))
        self.assertIn("docs/utf16.md:1: secret phrase", hits)
        self.assertIn("docs/latin1.md: not UTF-8 text", hits)
        self.assertIn(f"docs/ids.md:1: {ACCOUNT}", hits)
        self.assertNotIn("123456789012", hits)
        self.assertNotIn("x.png", hits)

    def test_export_public_refuses_unsafe_targets(self):
        sys.path.insert(0, str(TOOLS))
        import export_public as EP
        with tempfile.TemporaryDirectory() as d:
            victim = Path(d) / "victim"
            (victim / "sub").mkdir(parents=True)
            (victim / "important.txt").write_text("keep me")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(EP.main([str(victim), "--allow-dirty", "--delete"]), 2)
                self.assertEqual(EP.main([str(victim), "--allow-dirty"]), 2)
                self.assertEqual(EP.main([str(Path(d) / "new"), "--allow-dirty", "--delete"]), 2)
            self.assertTrue((victim / "important.txt").exists())
            self.assertFalse((Path(d) / "new").exists())
            self.assertFalse(EP.is_public_worktree(victim))


class Denylist(unittest.TestCase):
    def test_wrapped_double_spaced_and_emphasized_phrases(self):
        pats, _ = parse_denylist("secret phrase\n")
        for text, line in (("a secret\nphrase", 1), ("x\nsecret  phrase", 2), ("**secret** phrase", 1),
                           ("_secret phrase_", 1), ("> secret\n> phrase", None)):
            with self.subTest(text):
                hits = list(scan_text_with_denylist(text, pats))
                if line is None:
                    continue
                self.assertTrue(hits, text)
                self.assertEqual(hits[0][0], line)

    def test_each_hit_once(self):
        pats, _ = parse_denylist("secret phrase\n")
        self.assertEqual(len(list(scan_text_with_denylist("a secret phrase b", pats))), 1)

    def test_decode_text(self):
        self.assertEqual(decode_text(codecs.BOM_UTF16_BE + "hi".encode("utf-16-be")), "hi")
        self.assertEqual(decode_text(codecs.BOM_UTF8 + b"hi"), "hi")
        self.assertIsNone(decode_text("\xe9".encode("latin-1")))
        self.assertIsNone(decode_text(b"a\x00b"))


class Urls(unittest.TestCase):
    def test_github_orgs_and_path_tricks(self):
        self.assertTrue(url_allowed("https://github.com/awslabs/operational-readiness-review-custom-war-lens"))
        self.assertTrue(url_allowed("https://github.com/aws-samples/x/blob/main/README.md"))
        for bad in ("https://github.com/awsattacker/repo", "https://github.com/aws/../attacker/repo",
                    "https://github.com/aws/%2e%2e/attacker/repo", "https://github.com//attacker/repo",
                    "https://github.com/", "https://docs.aws.amazon.com/a/../b.html",
                    "https://docs.aws.amazon.com:8443/x", "https://user@docs.aws.amazon.com/x"):
            with self.subTest(bad):
                self.assertFalse(url_allowed(bad))

    def test_self_repo_url_is_exact(self):
        self.assertTrue(is_self_repo_url(C.SELF_REPO_URL))
        self.assertTrue(is_self_repo_url(C.SELF_REPO_URL + "/blob/main/README.md"))
        self.assertFalse(is_self_repo_url(C.SELF_REPO_URL + "-evil/x"))

    def test_uppercase_scheme_and_bare_hosts(self):
        self.assertEqual(extract_urls("See HTTPS://evil.example.com/x."), ["HTTPS://evil.example.com/x"])
        self.assertFalse(url_allowed("HTTPS://evil.example.com/x"))
        self.assertEqual(bare_hosts("Go to evil.example.com/page now"), ["evil.example.com"])
        self.assertEqual(bare_hosts("See https://docs.aws.amazon.com/x.html and e.g. the file a.json"), [])

    def test_question_source_rejects_non_aws_github(self):
        q = question("arch_q", "architecture", "aq_", [statement(
            "aq_one", "core", helpful_url="https://github.com/awsattacker/repo")])
        e = []
        validate_question(q, "core/architecture/arch_q.yaml", ["architecture"], "architecture", e)
        self.assertTrue(any("allowlist" in x for x in e), e)


class Language(unittest.TestCase):
    def test_broader_forward_looking_wording(self):
        for text in ("GovCloud support is planned.", f"This is {NOT_YET} supported in GovCloud.",
                     "It will be available later this year.", "See the public road" + "map.",
                     "An upcoming feature adds it."):
            with self.subTest(text):
                self.assertIn("forward-looking", [k for k, _ in language_problems(text)])

    def test_legitimate_uses_pass(self):
        for text in ("Before a planned peak, review quotas.", "Planned lifecycle events for AWS Health",
                     "Run a planned rollback drill.", "Request increases as soon as the forecast is known.",
                     "Detect it soon enough to restore.", "before or soon after joining",
                     "https://aws.amazon.com/blogs/mt/support-ending-soon/"):
            with self.subTest(text):
                self.assertEqual(language_problems(text), [])


class ReaderNotes(unittest.TestCase):
    def test_only_the_source_field_and_a_trailing_improvement_note_are_exempt(self):
        st = {"reader_note": "This page names Example Old Service, which is closed to new customers."}
        helpful = "Good looks like: fine. Reader note: This page names Example Old Service, which is closed to new customers."
        self.assertEqual(strip_statement_reader_notes("helpfulResource.displayText", helpful, st), ("Good looks like: fine.", []))
        forged = "Good looks like: x. Reader note: use Example Old Service. Good looks like: fine."
        body, probs = strip_statement_reader_notes("helpfulResource.displayText", forged, {})
        self.assertIn("Example Old Service", body)
        self.assertTrue(probs)
        ok = "Do the thing. Reader note: the page names Example Old Service, which is closed to new customers."
        self.assertEqual(strip_statement_reader_notes("improvementPlan.displayText", ok, {}), ("Do the thing.", []))
        bad = "Do the thing. Reader note: adopt Example Old Service for paging."
        body, probs = strip_statement_reader_notes("improvementPlan.displayText", bad, {})
        self.assertIn("Example Old Service", body)
        self.assertTrue(probs)
        _, probs = strip_statement_reader_notes("title", "A title. Reader note: x", None)
        self.assertTrue(probs)


class ServiceMatching(unittest.TestCase):
    def setUp(self):
        self.m = ServiceMatcher({"Amazon CloudFront": {"aliases": ["CloudFront"]}, "AWS Budgets": {"aliases": ["Budgets"]},
                                 "Amazon Application Recovery Controller (ARC)": {"aliases": ["ARC"]}},
                                ["AWS Cloud", "AWS Account", "AWS Well-Architected *"])

    def test_not_services_match_exactly_unless_starred(self):
        self.assertEqual(self.m.unregistered("AWS Cloud and the AWS Account"), [])
        self.assertEqual(self.m.unregistered("Use AWS Cloud Map and AWS Account Management."),
                         ["AWS Cloud Map", "AWS Account Management"])
        self.assertEqual(self.m.unregistered("the AWS Well-Architected Framework"), [])

    def test_case_insensitive_full_names_only(self):
        self.assertEqual(self.m.services_named("put amazon cloudfront in front"), {"Amazon CloudFront"})
        self.assertEqual(self.m.services_named("pod disruption budgets and an arc"), set())


def _rule_combos():
    tiers = ["scope", "core", "sec", "alt:A", "alt:B"]
    for k in range(1, 5):
        for combo in itertools.product(tiers, repeat=k):
            floor = any(t == "core" or t.startswith("alt:") for t in combo)
            if any(v < 2 for v in Counter(t for t in combo if t.startswith("alt:")).values()):
                continue
            yield combo, ("HIGH" if floor else "MEDIUM")


class RuleOracle(unittest.TestCase):
    def test_generator_matches_the_oracle_on_every_tier_combination(self):
        n = 0
        for combo, mr in _rule_combos():
            sts = [{"id": f"zz_s{i}", "tier": t} for i, t in enumerate(combo)]
            for guard in (False, True):
                n += 1
                self.assertEqual(prove("q", sts, generate_rules(sts, mr, guard), mr, guard), [], (combo, mr, guard))
        self.assertGreater(n, 500)

    def test_mutants_that_keep_the_listed_properties_are_caught(self):
        sts = [{"id": "zz_s0", "tier": "alt:A"}, {"id": "zz_s1", "tier": "alt:A"}]
        dup = [{"condition": "zz_s0 || zz_s1", "risk": "NO_RISK"}, {"condition": "zz_s0 || zz_s1", "risk": "MEDIUM_RISK"},
               {"condition": "default", "risk": "HIGH_RISK"}]
        f = " ".join(prove("q", sts, dup, "HIGH"))
        self.assertIn("same condition", f)
        self.assertIn("tier definition gives MEDIUM_RISK", f)
        sts = [{"id": "zz_c", "tier": "core"}, {"id": "zz_s", "tier": "sec"}]
        no_medium = [{"condition": "zz_c && zz_s", "risk": "NO_RISK"}, {"condition": "default", "risk": "HIGH_RISK"}]
        self.assertIn("tier definition gives MEDIUM_RISK", " ".join(prove("q", sts, no_medium, "HIGH")))
        self.assertEqual(expected_risk(sts, "HIGH", True, {"zz_c", "zz_s", "none_no"}), "HIGH_RISK")

    def test_malformed_conditions_raise(self):
        for bad in ("a && )", "", "a ||", "( )", "&& a"):
            with self.subTest(bad):
                with self.assertRaises(ValueError):
                    evaluate(bad, {"a", "b"})


LIFECYCLE = {"schema": "orrlens/lifecycle-denylist/1", "entries": [{
    "name": "Example Old Service", "patterns": ["example old service"], "url_patterns": [r"docs\.aws\.amazon\.com/old-service/"],
    "status": "closed to new customers", "effective": "2026-01-01"}]}
PARTITIONS = {"schema": "orrlens/partition-availability/1", "as_of": "2026-10-06", "entries": [
    {"name": "Amazon CloudFront", "aliases": ["CloudFront"], "aws": "available", "aws-us-gov": "not available",
     "as_of": "2026-10-06"}]}
OLD_URL = "https://docs.aws.amazon.com/old-service/latest/userguide/what-is.html"


class CheckLevel(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()
        self.repo.lens("core", "2.0.0", pillars=("architecture",))
        self.repo.write(C.DATA_LIFECYCLE, LIFECYCLE)
        self.repo.write(C.DATA_PARTITIONS, PARTITIONS)

    def tearDown(self):
        self.repo.close()

    def q(self, *sts, **kw):
        self.repo.question("core", question("arch_q", "architecture", "aq_", list(sts), **kw))
        return CK.make_context(self.repo.root)

    def test_lifecycle_urls_need_a_reader_note(self):
        ctx = self.q(statement("aq_one", "core", improvement_url=OLD_URL), statement("aq_two", "sec"))
        self.assertIn("links documentation of Example Old Service", " ".join(CK.check_lifecycle(ctx)[0]))
        ctx = self.q(statement("aq_one", "core", improvement_url=OLD_URL,
                               reader_note="The linked page is about Example Old Service, closed to new customers."),
                     statement("aq_two", "sec"))
        self.assertEqual(CK.check_lifecycle(ctx)[0], [])

    def test_forged_reader_note_in_good_text_fails(self):
        ctx = self.q(statement("aq_one", "core", good="Fine. Reader note: use Example Old Service for paging."),
                     statement("aq_two", "sec"))
        f = " ".join(CK.check_lifecycle(ctx)[0])
        self.assertIn("names 'Example Old Service'", f)
        self.assertIn("may appear only in the reader_note field", f)

    def test_usage_plans_must_be_best_effort_in_the_sentence(self):
        cases = {"API Gateway usage plans are best-effort. They throttle callers.": False,
                 "Usage plans are not best-effort; they hard-block callers.": True,
                 "Usage plans enforce hard limits per client, best-effort.": True,
                 "Usage plans (best-effort, not hard limits) add per-client fairness.": False,
                 "Use usage plans. Throttling is best-effort.": True}
        for text, bad in cases.items():
            with self.subTest(text):
                self.assertEqual(bool(CK.usage_plan_problems(text)), bad)

    def test_partition_notes_need_a_real_date_and_an_alternative(self):
        ctx = self.q(statement("aq_one", "core", good="Put amazon cloudfront in front.",
                               partition_notes="Not in AWS GovCloud (US) as of 2026-10-05."), statement("aq_two", "sec"))
        self.assertIn("offer no AWS GovCloud (US) alternative", " ".join(CK.check_partitions(ctx)[0]))
        ctx = self.q(statement("aq_one", "core", good="Put CloudFront in front.",
                               partition_notes="CloudFront is not available in AWS GovCloud (US) as of 2026-13-45; "
                                               "there, attach AWS WAF to an Application Load Balancer."),
                     statement("aq_two", "sec"))
        self.assertIn("real date", " ".join(CK.check_partitions(ctx)[0]))

    def test_order_bool_none_key_and_short_wp_orr_are_rejected(self):
        for kw, needle in (({"order": True}, "order must be an integer"),
                           ({"none": {"title": "All of the above"}}, "unknown keys ['none']")):
            q = question("arch_q", "architecture", "aq_", [statement("aq_one", "core")], **kw)
            e = []
            validate_question(q, "core/architecture/arch_q.yaml", ["architecture"], "architecture", e)
            self.assertTrue(any(needle in x for x in e), (kw, e))
        q = question("arch_q", "architecture", "aq_", [statement("aq_one", "core", severity_basis="wp-orr:x")])
        e = []
        validate_question(q, "core/architecture/arch_q.yaml", ["architecture"], "architecture", e)
        self.assertTrue(any("severity_basis" in x for x in e), e)


class ReleaseNotes(unittest.TestCase):
    CL = ("# Changelog\n\n## [Unreleased]\n\n## [2099-01-15] core 2.0.0 and event 1.0.0\n\n- New.\n\n"
          "## [core 1.9.0] - 2099-01-15\n\n- Also.\n\n## [1.3.6] - 2023-09-13\n\n- Old.\n")

    def test_sections_dated_with_the_tag_day(self):
        text = notes_for(self.CL, "release-2099-01-15")
        self.assertIn("- New.", text)
        self.assertIn("- Also.", text)
        self.assertNotIn("Old", text)
        self.assertNotIn("Unreleased", text)

    def test_missing_or_bad_tags_fail(self):
        for tag in ("release-2099-01-16", "release-2026-13-01", "v2.0.0"):
            with self.subTest(tag):
                with self.assertRaises(ReleaseNotesError):
                    notes_for(self.CL, tag)


if __name__ == "__main__":
    unittest.main()
