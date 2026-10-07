import unittest

from helpers import TempRepo, question, statement

from orrlens import registry as REG
from orrlens.model import load_lens


class IdsBase(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()
        r = self.repo
        r.v1("1.3.5", {"old_only": ["oo_a", "noneofthese"], "kept_q": ["choice_a", "noneofthese"],
                       "merged_q": ["mq_a", "noneofthese"]})
        r.v1("1.3.6", {"kept_q": ["choice_a", "choice_b", "noneofthese"], "merged_q": ["mq_a", "noneofthese"],
                       "split_q": ["sq_a", "noneofthese"], "architecture_plane_redundency": ["x_a", "noneofthese"]})
        r.lens("core", "2.0.0", pillars=("architecture",))
        r.question("core", question("kept_q", "architecture", "kq_", [statement("kq_new", "core")],
                                    lineage=["kept_q", "merged_q", "split_q"]))
        r.question("core", question("new_q", "architecture", "nq_", [statement("nq_one", "core")],
                                    lineage=["split_q", "architecture_plane_redundency"]))

    def tearDown(self):
        self.repo.close()

    def lenses(self):
        return [load_lens(self.repo.root, "core")]

    def fails(self):
        return REG.check_ids(self.repo.root, self.lenses())


class Registry(IdsBase):
    def test_seed_statuses_and_history(self):
        reg = REG.compute_registry(self.repo.root, self.lenses())
        q, c = reg["questions"], reg["choices"]
        self.assertEqual(q["kept_q"], {"lens": "core", "introduced": "1.3.5", "status": "active"})
        self.assertEqual(q["old_only"]["status"], "retired")
        self.assertEqual(q["old_only"]["retired"], "1.3.6")       # left the lens before v1.3.6
        self.assertEqual(q["merged_q"]["retired"], "2.0.0")
        self.assertEqual(q["new_q"], {"lens": "core", "introduced": "2.0.0", "status": "active"})
        self.assertEqual(c["kept_q/choice_a"]["status"], "retired")  # v1 choice ids never carry over
        self.assertEqual(c["kept_q/choice_b"]["introduced"], "1.3.6")
        self.assertEqual(c["kept_q/kq_new"]["status"], "active")
        self.assertEqual(c["kept_q/none_no"]["status"], "active")
        self.assertEqual(reg["reserved"]["prefixes"]["x_"]["status"], "reserved")

    def test_update_is_deterministic_and_idempotent(self):
        t1, changed1 = REG.update(self.repo.root, self.lenses())
        t2, changed2 = REG.update(self.repo.root, self.lenses())
        self.assertTrue(changed1)
        self.assertFalse(changed2)
        self.assertEqual(t1, t2)
        self.assertEqual(self.fails(), [])

    def test_unpublished_ids_disappear_and_published_history_is_kept(self):
        REG.update(self.repo.root, self.lenses())
        # An id introduced in the unreleased current version vanishes again when its source goes away
        (self.repo.root / "lens-src/core/architecture/new_q.yaml").unlink()
        reg = REG.compute_registry(self.repo.root, self.lenses(), REG.load_registry(self.repo.root))
        self.assertNotIn("new_q", reg["questions"])
        # An id retired in an earlier version stays retired with its version, even if it comes back
        existing = REG.load_registry(self.repo.root)
        existing["questions"]["gone_q"] = {"lens": "core", "status": "retired", "introduced": "1.9.0",
                                           "retired": "1.9.5"}
        self.repo.question("core", question("gone_q", "architecture", "gq_", [statement("gq_one", "core")]))
        reg = REG.compute_registry(self.repo.root, self.lenses(), existing)
        self.assertEqual(reg["questions"]["gone_q"]["status"], "retired")
        self.assertEqual(reg["questions"]["gone_q"]["retired"], "1.9.5")


class IdsCheck(IdsBase):
    def setUp(self):
        super().setUp()
        REG.update(self.repo.root, self.lenses())

    def test_clean_repo_passes(self):
        self.assertEqual(self.fails(), [])

    def test_stale_registry_is_reported(self):
        self.repo.question("core", question("another_q", "architecture", "aq_", [statement("aq_one", "core")]))
        self.assertTrue(any("out of date" in f for f in self.fails()))

    def test_reusing_a_permanently_retired_id_fails(self):
        self.repo.question("core", question("architecture_plane_redundency", "architecture", "pr_",
                                            [statement("pr_one", "core")]))
        REG.update(self.repo.root, self.lenses())
        f = " ".join(self.fails())
        self.assertIn("architecture_plane_redundency was retired in 2.0.0 and cannot be reused", f)

    def test_reusing_an_id_that_left_before_v136_fails(self):
        self.repo.question("core", question("old_only", "architecture", "oo_", [statement("oo_new", "core")]))
        REG.update(self.repo.root, self.lenses())
        f = " ".join(self.fails())
        self.assertIn("old_only", f)
        self.assertIn("left the lens before v1.3.6", f)

    def test_v1_choice_id_collision_in_kept_question(self):
        self.repo.question("core", question("kept_q", "architecture", "choice_",
                                            [statement("choice_a", "core")], lineage=["kept_q", "merged_q", "split_q"]))
        REG.update(self.repo.root, self.lenses())
        self.assertTrue(any("were used by v1 in the same question" in f for f in self.fails()))

    def test_lineage_must_name_v136_questions_and_cover_them(self):
        self.repo.question("core", question("new_q", "architecture", "nq_", [statement("nq_one", "core")],
                                            lineage=["not_a_v1_id"]))
        REG.update(self.repo.root, self.lenses())
        f = " ".join(self.fails())
        self.assertIn("lineage entry 'not_a_v1_id' is not a v1.3.6 question id", f)
        self.assertIn("architecture_plane_redundency appears in no v2 lineage", f)

    def test_reserved_prefix_and_none_suffix(self):
        self.repo.question("core", question("x_acme_q", "architecture", "xa_", [statement("xa_one_no", "core")]))
        f = " ".join(REG.check_ids(self.repo.root, self.lenses()))
        self.assertIn("x_acme_q: the x_ prefix is reserved", f)
        self.assertIn("only the generated None choice", f)

    def test_dispositions(self):
        rows = {r[0]: r for r in REG.dispositions(self.repo.root, self.lenses())}
        self.assertEqual(rows["kept_q"][2], "keep")
        self.assertEqual(rows["merged_q"][2], "merge")
        self.assertEqual(rows["split_q"][2], "split")
        self.assertEqual([t for t, _ in rows["split_q"][3]], ["kept_q", "new_q"])


if __name__ == "__main__":
    unittest.main()
