"""Release-safety checks: leftover placeholders, GovCloud availability claims against the partition data, and
release notes that skip an Unreleased section."""

import subprocess
import unittest

from helpers import TempRepo, question, statement

from orrlens import checks as CK
from orrlens import config as C
from orrlens.release_notes import ReleaseNotesError, absolutize_links, notes_for, sections
from orrlens.textscan import ServiceMatcher, gov_availability_claims, placeholder_problems

# Placeholder tokens are assembled at run time, so this file never contains them literally.
LB, RB = "{" * 2, "}" * 2
RELEASE_DATE_TOKEN = "<release" + " date>"


class Placeholders(unittest.TestCase):
    def test_leftovers_are_found(self):
        for text in (f"Advisory ({RELEASE_DATE_TOKEN}): the change takes effect later.",
                     f"Released on {LB}RELEASE_DATE{RB}.", f"Version {LB} version {RB}", "<Release-Date>",
                     "Owner: TBD", "TODO add the link", "<insert the blog post URL>", "[release date]", "<date>"):
            with self.subTest(text):
                self.assertTrue(placeholder_problems(text), text)

    def test_format_tokens_and_actions_expressions_pass(self):
        for text in ("group: ci-$" + LB + " github.ref " + RB, "EXC:<register-id> exp:YYYY-MM-DD role:<approver-role>",
                     "Name milestones ORR-<yyyy-mm>-<purpose>.", "wa:<BP-ID> (High), wp-orr:<example question>",
                     "dist/<file_stem>-<version>.json", "## [1.3.6] - 2023-09-13", "A todo list and a mandate.",
                     "releases/latest/download/<file>"):
            with self.subTest(text):
                self.assertEqual(placeholder_problems(text), [])

    def test_check_scans_exportable_text_but_not_python_or_private_files(self):
        repo = TempRepo()
        try:
            root = repo.root
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True, capture_output=True)
            repo.write("README.md", f"# Lens\n\nAdvisory ({RELEASE_DATE_TOKEN}): read this.\n")
            repo.write("docs/notes.md", "Fine text.\n")
            repo.write("tools/x.py", f"s = '{LB}name{RB}'  # TODO\n")
            repo.write("private/RELEASE.md", f"Homepage: {RELEASE_DATE_TOKEN}\n")
            repo.write(".github/workflows/ci.yml", "group: ci-$" + LB + " github.ref " + RB + "\n")
            ctx = CK.make_context(root)
            fails, _ = CK.check_placeholders(ctx)
            self.assertEqual(len(fails), 1, fails)
            self.assertTrue(fails[0].startswith("README.md:3: leftover placeholder"), fails)
        finally:
            repo.close()


ENTRIES = {
    "AWS Shield Advanced": {"aliases": ["Shield Advanced"], "aws-us-gov": "not available"},
    "Amazon CloudFront": {"aliases": ["CloudFront"], "aws-us-gov": "not available"},
    "AWS WAF": {"aliases": [], "aws-us-gov": "available"},
    "AWS CodePipeline": {"aliases": ["CodePipeline"], "aws-us-gov": "available"},
    "AWS Lambda": {"aliases": ["Lambda"], "aws-us-gov": "available"},
    "AWS Backup": {"aliases": [], "aws-us-gov": "available"},
    "AWS Backup restore testing": {"aliases": [], "aws-us-gov": "not available"},
    "AWS GovCloud (US)": {"aliases": ["GovCloud"], "aws-us-gov": "n/a"},
}


def claims(text):
    m = ServiceMatcher(ENTRIES, [])
    return {(k, avail) for k, avail, _ in gov_availability_claims(text, m)}


class GovCloudClaims(unittest.TestCase):
    def test_subject_lists_and_both_polarities(self):
        self.assertEqual(claims("Partition notes: Shield Advanced and CloudFront are not available in AWS GovCloud (US) "
                                "as of 2026-10-06."),
                         {("AWS Shield Advanced", False), ("Amazon CloudFront", False)})
        self.assertEqual(claims("AWS WAF is available in AWS GovCloud (US) as of 2026-10-06."), {("AWS WAF", True)})
        self.assertEqual(claims("In AWS GovCloud (US) as of 2026-10-06, CodePipeline is available, but Shield "
                                "Advanced is not available there."),
                         {("AWS CodePipeline", True), ("AWS Shield Advanced", False)})

    def test_features_of_a_service_are_not_claims_about_the_service(self):
        for text in ("AWS CodePipeline cross-Region actions are not available in AWS GovCloud (US) as of 2026-10-06.",
                     "Lambda JSON log formatting is not available in AWS GovCloud (US) as of 2026-10-06.",
                     "AWS WAF is available in AWS GovCloud (US), but the AWS WAF example feature is not available "
                     "there."):
            with self.subTest(text):
                self.assertNotIn(False, {a for k, a in claims(text) if k in ("AWS CodePipeline", "AWS Lambda", "AWS WAF")})
        # The longest registered name wins: the feature entry, not the service
        self.assertEqual(claims("AWS Backup restore testing is not available in AWS GovCloud (US)."),
                         {("AWS Backup restore testing", False)})

    def test_other_regions_are_not_govcloud_claims(self):
        self.assertEqual(claims("CloudFront is not available in China Regions, and AWS WAF is available there."), set())


PARTITIONS = {"schema": "orrlens/partition-availability/1", "as_of": "2026-10-06", "entries": [
    {"name": "Amazon CloudFront", "aliases": ["CloudFront"], "aws": "available", "aws-us-gov": "not available",
     "as_of": "2026-10-06"},
    {"name": "AWS WAF", "aws": "available", "aws-us-gov": "available", "as_of": "2026-10-06"},
    {"name": "AWS GovCloud (US)", "aliases": ["GovCloud"], "aws": "available", "aws-us-gov": "n/a",
     "as_of": "2026-10-06"}]}


class PartitionClaimCheck(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()
        self.repo.lens("core", "2.0.0", pillars=("architecture",))
        self.repo.write(C.DATA_PARTITIONS, PARTITIONS)

    def tearDown(self):
        self.repo.close()

    def ctx(self, partition_notes):
        sts = [statement("aq_one", "core", good="Attach AWS WAF to the load balancer.",
                         partition_notes=partition_notes), statement("aq_two", "sec")]
        self.repo.question("core", question("arch_q", "architecture", "aq_", sts))
        return CK.make_context(self.repo.root)

    def test_text_contradicting_the_data_fails_in_both_directions(self):
        f = " ".join(CK.check_partitions(self.ctx("AWS WAF is not available in AWS GovCloud (US) as of 2026-10-06; "
                                                  "there, use rate limits in the application."))[0])
        self.assertIn("says AWS WAF is not available in AWS GovCloud (US)", f)
        f = " ".join(CK.check_partitions(self.ctx("AWS WAF and CloudFront are available in AWS GovCloud (US) as of "
                                                  "2026-10-06."))[0])
        self.assertIn("says Amazon CloudFront is available in AWS GovCloud (US)", f)
        self.assertNotIn("AWS WAF is available", f)

    def test_consistent_text_passes(self):
        fails, _ = CK.check_partitions(self.ctx("AWS WAF is available in AWS GovCloud (US) as of 2026-10-06, and "
                                                "CloudFront is not available there."))
        self.assertEqual(fails, [])

    def test_repository_prose_is_checked_paragraph_by_paragraph(self):
        ctx = self.ctx("AWS WAF is available in AWS GovCloud (US) as of 2026-10-06.")
        self.repo.write("docs/govcloud.md", "# GovCloud\n\nFine.\n\nIn short, AWS WAF is not\navailable in AWS "
                                            "GovCloud (US).\n")
        fails = CK.check_partitions(ctx)[0]
        self.assertEqual(len(fails), 1, fails)
        self.assertTrue(fails[0].startswith("docs/govcloud.md:5: says AWS WAF is not available"), fails)


class ReleaseNotesUnreleased(unittest.TestCase):
    CL = ("# Changelog\n\n## [Unreleased] - 2099-01-15\n\n- Work in progress.\n\n"
          "## [2099-01-15] core 2.0.0 and event 1.0.0\n\n- Core.\n\n"
          "## [event 1.0.0] - 2099-01-15 (companion lens)\n\n- Event.\n\n"
          "## [1.3.6] - 2023-09-13\n\n- Old.\n")

    def test_unreleased_is_skipped_even_when_dated(self):
        text = notes_for(self.CL, "release-2099-01-15")
        self.assertNotIn("Unreleased", text)
        self.assertNotIn("Work in progress", text)

    def test_every_section_dated_with_the_release_day_is_included_in_order(self):
        text = notes_for(self.CL, "release-2099-01-15")
        self.assertIn("- Core.", text)
        self.assertIn("- Event.", text)
        self.assertLess(text.index("- Core."), text.index("- Event."))
        self.assertNotIn("- Old.", text)
        self.assertEqual([d for _, d, _ in sections(self.CL)], ["2099-01-15", "2099-01-15", "2023-09-13"])

    def test_only_an_unreleased_section_is_an_error(self):
        with self.assertRaises(ReleaseNotesError):
            notes_for("# Changelog\n\n## [Unreleased] - 2099-01-15\n\n- Work in progress.\n", "release-2099-01-15")
        with self.assertRaises(ReleaseNotesError):
            notes_for("# Changelog\n\n## [unreleased]\n\n- Work.\n", "release-2099-01-15")


class ReleaseNotesRelativeLinks(unittest.TestCase):
    """A relative link in a release body resolves against /releases/tag/<tag>/, so it must be absolutized."""

    TAG = "release-2099-01-15"
    BASE = f"{C.SELF_REPO_URL}/blob/{TAG}/"

    def test_relative_targets_are_rewritten_to_the_tag(self):
        self.assertEqual(absolutize_links("see [guide](MIGRATION.md).", self.TAG),
                         f"see [guide]({self.BASE}MIGRATION.md).")
        self.assertEqual(absolutize_links("[x](docs/scoring.md#not-applicable)", self.TAG),
                         f"[x]({self.BASE}docs/scoring.md#not-applicable)")
        self.assertEqual(absolutize_links("[x](./docs/faq.md)", self.TAG), f"[x]({self.BASE}docs/faq.md)")

    def test_absolute_anchor_and_mail_targets_are_left_alone(self):
        for target in ("https://docs.aws.amazon.com/x.html", "http://example.com/y",
                       "mailto:opensource-codeofconduct@amazon.com", "#how-200-scores", "//cdn.example.com/z"):
            text = f"[x]({target})"
            self.assertEqual(absolutize_links(text, self.TAG), text, target)

    def test_notes_for_absolutizes(self):
        cl = "# Changelog\n\n## [2099-01-15] core 2.0.0\n\n- See [`MIGRATION.md`](MIGRATION.md).\n"
        text = notes_for(cl, self.TAG)
        self.assertIn(f"({self.BASE}MIGRATION.md)", text)
        self.assertNotIn("](MIGRATION.md)", text)


if __name__ == "__main__":
    unittest.main()
