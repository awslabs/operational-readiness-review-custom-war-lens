import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  (sets sys.path)

from orrlens.textscan import (ServiceMatcher, extract_urls, is_binary, language_problems, parse_denylist,
                              scan_text_with_denylist, strip_reader_notes, url_allowed)

# Phrases the language rules reject are assembled at run time, so this file never contains them literally
# (the internal-wording scan covers every exported file, tests included).
SOON = "coming" + " soon"
PLANNED = "being" + " planned"
QUARTER = "20" + "27 Q1"
ALLOW_OLD = "white" + "list"


class Denylist(unittest.TestCase):
    def test_comments_blank_lines_and_case(self):
        pats, problems = parse_denylist("# comment\n\n\\bfoo tool\\b\ncs:BarSystem\n  # indented comment\n")
        self.assertEqual(problems, [])
        self.assertEqual(len(pats), 2)
        hits = list(scan_text_with_denylist("line one\nuses the FOO TOOL here\nbarsystem and BarSystem\n", pats))
        self.assertEqual(hits, [(2, "FOO TOOL"), (3, "BarSystem")])

    def test_invalid_regex_is_reported_not_raised(self):
        pats, problems = parse_denylist("ok\n(unclosed\n")
        self.assertEqual(len(pats), 1)
        self.assertEqual(len(problems), 1)
        self.assertIn("line 2", problems[0])

    def test_binary_detection(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d) / "x.png"
            b.write_bytes(b"\x89PNG\x00\x01")
            t = Path(d) / "x.md"
            t.write_text("plain text")
            self.assertTrue(is_binary(b))
            self.assertFalse(is_binary(t))


class Language(unittest.TestCase):
    def test_dashes_and_non_ascii(self):
        kinds = [k for k, _ in language_problems("a \u2014 b \u2013 c \u00e9")]
        self.assertEqual(kinds, ["dash", "dash", "non-ascii"])

    def test_forward_looking_wording(self):
        for text in (f"Support is {SOON}.", f"A feature is {PLANNED}.", f"Expected in {QUARTER}.",
                     "Planned" + "  for next year", "It is not yet" + "  available."):
            with self.subTest(text):
                self.assertIn("forward-looking", [k for k, _ in language_problems(text)])
        self.assertEqual(language_problems("Available as of 2026-10-06 in AWS GovCloud (US)."), [])

    def test_inclusive_language(self):
        self.assertIn("inclusive-language", [k for k, _ in language_problems(f"Use an IP {ALLOW_OLD}.")])
        self.assertIn("inclusive-language", [k for k, _ in language_problems("the " + "mas" + "ter branch")])
        self.assertEqual(language_problems("Use an IP allowlist and the primary Region."), [])

    def test_urls(self):
        self.assertEqual(extract_urls("See <https://aws.amazon.com/message/12721/>, and (https://docs.aws.amazon.com/x.html)."),
                         ["https://aws.amazon.com/message/12721/", "https://docs.aws.amazon.com/x.html"])
        self.assertTrue(url_allowed("https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html"))
        self.assertTrue(url_allowed("https://github.com/aws-samples/sample-well-architected-custom-lens"))
        self.assertTrue(url_allowed("https://opentelemetry.io/docs/"))
        self.assertFalse(url_allowed("http://aws.amazon.com/"))
        self.assertFalse(url_allowed("https://github.com/someone/repo"))
        self.assertFalse(url_allowed("https://" + "console" + ".aws.amazon.com/wellarchitected"))
        self.assertFalse(url_allowed("https://example.com/"))
        self.assertFalse(url_allowed("https://docs.aws.amazon.com@evil.example/"))

    def test_reader_notes_are_stripped(self):
        text = ("Good looks like: use any paging tool. Partition notes: as of 2026-10-06. Reader note: this page "
                "names Example Old Service, which is closed to new customers.")
        self.assertNotIn("Example Old Service", strip_reader_notes(text))
        self.assertIn("Partition notes: as of 2026-10-06.", strip_reader_notes(text))
        mid = "Good looks like: a. Reader note: names Old Thing. Partition notes: b."
        self.assertEqual(strip_reader_notes(mid), "Good looks like: a.  Partition notes: b.")


class ServiceNames(unittest.TestCase):
    def setUp(self):
        entries = {
            "Amazon CloudFront": {"aliases": ["CloudFront"]},
            "AWS WAF": {"aliases": []},
            "Amazon API Gateway": {"aliases": ["API Gateway"]},
            "Amazon S3": {"aliases": []},
            "AWS Identity and Access Management": {"aliases": ["IAM"]},
            "Amazon Application Recovery Controller (ARC)": {"aliases": ["ARC"]},
            "AWS Distro for OpenTelemetry": {"aliases": ["ADOT"]},
        }
        self.m = ServiceMatcher(entries, ["AWS Region", "AWS Well-Architected *"])

    def test_registered_prefix_wins(self):
        self.assertEqual(self.m.unregistered("Use AWS WAF Anti-DDoS rules and Amazon CloudFront in front."), [])
        self.assertEqual(self.m.unregistered("Amazon S3-hosted artifacts"), [])

    def test_unregistered_names_are_reported(self):
        self.assertEqual(self.m.unregistered("Alarm with Amazon CloudWatch Synthetics canaries."),
                         ["Amazon CloudWatch Synthetics"])

    def test_ignored_terms_and_publications(self):
        self.assertEqual(self.m.unregistered("Each AWS Region; the AWS Well-Architected Framework; "
                                             "the AWS Security Blog."), [])

    def test_connectors_and_parentheticals(self):
        self.assertEqual(self.m.unregistered("AWS Identity and Access Management roles"), [])
        self.assertEqual(self.m.unregistered("Amazon Application Recovery Controller zonal shift"), [])
        self.assertEqual(self.m.unregistered("instrument with AWS Distro for OpenTelemetry"), [])
        self.assertEqual(self.m.candidates("AWS WAF and Amazon S3"), ["AWS WAF", "Amazon S3"])

    def test_services_named_by_alias(self):
        self.assertEqual(self.m.services_named("Put CloudFront and API Gateway in front."),
                         {"Amazon CloudFront", "Amazon API Gateway"})
        self.assertEqual(self.m.services_named("ARC zonal shift"), {"Amazon Application Recovery Controller (ARC)"})
        self.assertEqual(self.m.services_named("SEARCH and MARCH"), set())

    def test_lower_case_alias_matches_capitalized_at_sentence_start(self):
        m = ServiceMatcher({
            "Guardrails account-level enforcement": {"aliases": ["guardrail enforcement"]},
            "Guardrails organization-level enforcement": {"aliases": ["organization-level guardrail enforcement"]},
        }, [])
        spans = m.name_spans("Organization-level guardrail enforcement is not offered.")
        self.assertEqual([k for _s, _e, k in spans], ["Guardrails organization-level enforcement"])
        spans = m.name_spans("Guardrail enforcement covers four APIs.")
        self.assertEqual([k for _s, _e, k in spans], ["Guardrails account-level enforcement"])
        # Only the first letter may change case
        self.assertEqual(m.name_spans("GUARDRAIL ENFORCEMENT"), [])


if __name__ == "__main__":
    unittest.main()
