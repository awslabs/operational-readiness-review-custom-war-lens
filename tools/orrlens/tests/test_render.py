import unittest

from helpers import question, statement

from orrlens import config as C
from orrlens.render import description, dumps, helpful_text, none_text, render_question


class DescriptionTemplate(unittest.TestCase):
    def test_full_template_order(self):
        q = question("qq_one", "architecture", "qq_", [statement("qq_a", "core")],
                     category="Data recovery",
                     description={"question": "How do you restore?  ", "out_of_scope_if": "the workload stores no data.",
                                  "evidence_to_collect": "the last restore report."})
        self.assertEqual(description(q),
                         "Maximum risk: High (launch-blocking unless remediated or formally accepted). "
                         "Category: Data recovery. How do you restore? Out of scope if: the workload stores no data. "
                         "Evidence to collect: the last restore report.")

    def test_without_out_of_scope_and_medium(self):
        q = question("qq_two", "architecture", "qq_", [statement("qq_a", "sec")], max_risk="MEDIUM")
        d = description(q)
        self.assertTrue(d.startswith(C.RISK_TEXT["MEDIUM"] + " Category: Deployment safety. "))
        self.assertNotIn("Out of scope if", d)
        self.assertTrue(d.endswith("Evidence to collect: the runbook."))

    def test_folded_yaml_whitespace_is_normalized(self):
        q = question("qq_three", "architecture", "qq_", [statement("qq_a", "core")],
                     description={"question": "Line one\n  continues here?", "evidence_to_collect": "a\n b."})
        self.assertIn("Line one continues here? Evidence to collect: a b.", description(q))


class ChoiceText(unittest.TestCase):
    def test_helpful_text_parts_in_order(self):
        s = statement("qq_a", "core", platform_notes="EC2: x.", partition_notes="as of 2026-10-06 y.",
                      reader_note="z.")
        self.assertEqual(helpful_text(s), "Good looks like: Good practice is in place. Platform notes: EC2: x. "
                                          "Partition notes: as of 2026-10-06 y. Reader note: z.")

    def test_none_choice_and_pes_lesson(self):
        q = question("qq_four", "architecture", "qq_", [statement("qq_a", "core"), statement("qq_b", "sec")],
                     pes_lesson={"statement": "qq_b", "month": "Dec 2021", "url": "https://aws.amazon.com/message/12721/",
                                 "lesson": "shed excess work early."})
        r = render_question(q)
        none = r["choices"][-1]
        self.assertEqual(none["id"], "none_no")
        self.assertEqual(none["helpfulResource"]["displayText"], none_text("HIGH"))
        self.assertNotIn("improvementPlan", none)
        extra = r["choices"][1]["additionalResources"][0]
        self.assertEqual(extra["type"], "HELPFUL_RESOURCE")
        self.assertEqual(extra["content"][0]["displayText"],
                         "Related AWS Post-Event Summary (Dec 2021): shed excess work early.")
        self.assertEqual([x["risk"] for x in r["riskRules"]], ["NO_RISK", "MEDIUM_RISK", "HIGH_RISK"])

    def test_dumps_is_ascii_and_deterministic(self):
        doc = {"b": "caf\u00e9", "a": [1, 2]}
        self.assertEqual(dumps(doc), dumps(doc))
        self.assertTrue(dumps(doc).isascii())
        self.assertTrue(dumps(doc, minify=True).endswith("\n"))
        self.assertNotIn(" ", dumps({"a": [1, 2]}, minify=True))


if __name__ == "__main__":
    unittest.main()
