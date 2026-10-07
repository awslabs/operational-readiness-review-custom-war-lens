import json
import unittest

from helpers import V136, sample_rules

from orrlens.rules import (evaluate, generate_rules, identifiers, legacy_max_risk, prove, prove_rule_properties,
                           risk_of, tokenize)


class SampleRulesReproduced(unittest.TestCase):
    """The six worked sample questions' riskRules must be reproduced exactly from their tiers."""

    def test_each_sample_rule_set_is_reproduced_exactly(self):
        qs = sample_rules()
        self.assertEqual(len(qs), 6)
        for q in qs:
            with self.subTest(q["id"]):
                self.assertEqual(generate_rules(q["statements"], q["max_risk"]), q["riskRules"])

    def test_each_sample_rule_set_satisfies_every_property(self):
        for q in sample_rules():
            with self.subTest(q["id"]):
                rules = generate_rules(q["statements"], q["max_risk"])
                self.assertEqual(prove(q["id"], q["statements"], rules, q["max_risk"]), [])
                ids = [s["id"] for s in q["statements"]] + ["none_no"]
                label = "HIGH_RISK" if q["max_risk"] == "HIGH" else "MEDIUM_RISK"
                self.assertEqual(prove_rule_properties(q["id"], ids, rules, label), [])

    def test_none_guard_variant_still_proves(self):
        for q in sample_rules():
            with self.subTest(q["id"]):
                rules = generate_rules(q["statements"], q["max_risk"], none_guard=True)
                self.assertTrue(all("!none_no" in r["condition"] for r in rules if r["condition"] != "default"))
                self.assertEqual(prove(q["id"], q["statements"], rules, q["max_risk"], none_guard=True), [])


class LegacyRulesFlagged(unittest.TestCase):
    """The tier-agnostic prover must flag the known-bad v1.3.6 rule sets."""

    @classmethod
    def setUpClass(cls):
        doc = json.loads(V136.read_text())
        cls.qs = {q["id"]: q for p in doc["pillars"] for q in p["questions"]}

    def fails(self, qid):
        q = self.qs[qid]
        return prove_rule_properties(qid, [c["id"] for c in q["choices"]], q["riskRules"],
                                     legacy_max_risk(q["title"]))

    def test_releases_deployment_fails(self):
        f = " ".join(self.fails("releases_deployment"))
        self.assertIn("HIGH_RISK is unreachable", f)
        self.assertIn("negation not allowed", f)
        self.assertIn("selecting only noneofthese gives MEDIUM_RISK", f)

    def test_architecture_services_used_fails(self):
        f = " ".join(self.fails("architecture_services_used"))
        self.assertIn("not monotone: adding thirdParty", f)
        self.assertIn("HIGH_RISK is unreachable", f)

    def test_releases_manual_changes_has_no_default(self):
        f = " ".join(self.fails("releases_manual_changes"))
        self.assertIn("default is not the last rule", f)
        self.assertIn("references the None choice", f)

    def test_unused_choices_are_flagged(self):
        f = " ".join(self.fails("architecture_defensive_throttling"))
        self.assertIn("choice queueing never changes the risk", f)
        self.assertIn("choice async_execution never changes the risk", f)

    def test_legacy_max_risk_from_title(self):
        self.assertEqual(legacy_max_risk("Health Checks (H)"), "HIGH_RISK")
        self.assertEqual(legacy_max_risk("Recovery Objectives (M)"), "MEDIUM_RISK")


class Evaluator(unittest.TestCase):
    def test_and_binds_tighter_than_or(self):
        self.assertTrue(evaluate("a || b && c", {"a"}))
        self.assertFalse(evaluate("a || b && c", {"b"}))
        self.assertTrue(evaluate("(a || b) && c", {"b", "c"}))

    def test_negation_and_double_negation(self):
        self.assertTrue(evaluate("!a", set()))
        self.assertFalse(evaluate("!a", {"a"}))
        self.assertTrue(evaluate("!!a", {"a"}))
        self.assertTrue(evaluate("!(a && b)", {"a"}))

    def test_whitespace_and_nested_parentheses(self):
        self.assertTrue(evaluate("  ((a))&&(b||  c) ", {"a", "c"}))

    def test_default_and_unknown_identifiers(self):
        self.assertTrue(evaluate("default", set()))
        self.assertTrue(evaluate(" default ", {"x"}))
        self.assertFalse(evaluate("unknown_choice", {"a"}))

    def test_malformed_conditions_raise(self):
        for bad in ("a &&", "(a || b", "a b", "a & b", "a ||| b", ")a("):
            with self.subTest(bad):
                with self.assertRaises((ValueError, IndexError)):
                    evaluate(bad, {"a", "b"})

    def test_tokenize_and_identifiers(self):
        self.assertEqual(tokenize("a&&!b"), ["a", "&&", "!", "b"])
        self.assertEqual(identifiers("(a || b) && !c"), {"a", "b", "c"})
        self.assertEqual(identifiers("default"), set())

    def test_first_true_rule_wins(self):
        rules = [{"condition": "a", "risk": "NO_RISK"}, {"condition": "a || b", "risk": "MEDIUM_RISK"},
                 {"condition": "default", "risk": "HIGH_RISK"}]
        self.assertEqual(risk_of(rules, {"a", "b"}), "NO_RISK")
        self.assertEqual(risk_of(rules, {"b"}), "MEDIUM_RISK")
        self.assertEqual(risk_of(rules, set()), "HIGH_RISK")
        self.assertEqual(risk_of(rules[:2], set()), "UNMATCHED")


class Generator(unittest.TestCase):
    def st(self, *pairs):
        return [{"id": i, "tier": t} for i, t in pairs]

    def test_medium_rule_omitted_when_equal_to_no_risk(self):
        rules = generate_rules(self.st(("a_x", "core"), ("a_y", "core")), "HIGH")
        self.assertEqual([r["risk"] for r in rules], ["NO_RISK", "HIGH_RISK"])

    def test_two_alt_groups_and_scope(self):
        sts = self.st(("a_s", "scope"), ("a_c", "core"), ("a_p", "alt:A"), ("a_q", "alt:A"), ("a_r", "alt:B"),
                      )
        sts.append({"id": "a_t", "tier": "alt:B"})
        rules = generate_rules(sts, "HIGH")
        self.assertEqual(rules[0]["condition"], "a_s || (a_c && a_p && a_q && a_r && a_t)")
        self.assertEqual(rules[1]["condition"], "a_c && (a_p || a_q) && (a_r || a_t)")
        self.assertEqual(prove("q", sts, rules, "HIGH"), [])

    def test_prover_rejects_a_hand_written_non_monotone_rule(self):
        sts = self.st(("a_x", "core"), ("a_y", "sec"))
        bad = [{"condition": "a_x && a_y", "risk": "NO_RISK"}, {"condition": "a_x && !a_y", "risk": "MEDIUM_RISK"},
               {"condition": "default", "risk": "HIGH_RISK"}]
        f = " ".join(prove("q", sts, bad, "HIGH"))
        self.assertIn("negation not allowed", f)

    def test_prover_rejects_none_reference_and_wrong_default(self):
        sts = self.st(("a_x", "core"))
        bad = [{"condition": "a_x", "risk": "NO_RISK"}, {"condition": "none_no", "risk": "HIGH_RISK"},
               {"condition": "default", "risk": "MEDIUM_RISK"}]
        f = " ".join(prove("q", sts, bad, "HIGH"))
        self.assertIn("references none_no", f)
        self.assertIn("default risk MEDIUM_RISK != max risk HIGH_RISK", f)


if __name__ == "__main__":
    unittest.main()
