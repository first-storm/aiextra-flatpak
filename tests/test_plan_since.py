"""`aiextra.py plan --since` — deriving targets from what a push changed."""

import unittest

from support import CliTestCase


class PlanSince(CliTestCase):
    def setUp(self):
        super().setUp()
        self.fixture.add_app("org.example.Alpha")
        self.fixture.add_app("org.example.Beta")
        self.base = self.init_git()

    def touch(self, relative_path):
        path = self.fixture.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("changed\n")

    def test_only_applications_touched_since_the_base_are_planned(self):
        self.touch("manifests/org.example.Beta/architectures")
        self.fixture.add_app("org.example.Beta", arches="x86_64\n")
        self.commit("update beta")

        plan = self.json_stdout(self.run_cli("plan", "--since", self.base))

        self.assertEqual(plan["apps"], ["org.example.Beta"])

    def test_a_change_outside_manifests_plans_every_application(self):
        self.touch("tools/aiextra.py")
        self.commit("touch tooling")

        plan = self.json_stdout(self.run_cli("plan", "--since", self.base))

        self.assertEqual(plan["apps"], ["org.example.Alpha", "org.example.Beta"])

    def test_a_push_that_changed_nothing_plans_nothing(self):
        # An empty plan must stay empty. The old tooling turned "no targets"
        # into "every target" here, so a no-op push rebuilt the whole repo.
        self.commit("empty")

        result = self.run_cli("plan", "--since", self.base, with_github_output=True)

        self.assertOk(result)
        self.assertEqual(self.json_stdout(result)["apps"], [])
        self.assertEqual(self.json_stdout(result)["matrix"], {"include": []})
        self.assertEqual(self.github_output_pairs()["apps"], "")

    def test_since_cannot_be_combined_with_other_target_modes(self):
        for extra in (["--all"], ["org.example.Alpha"]):
            with self.subTest(extra=extra):
                result = self.run_cli("plan", "--since", self.base, *extra)
                self.assertEqual(result.returncode, 2, result.stderr)

    def test_an_unknown_base_revision_falls_back_to_every_application(self):
        # GitHub sends an all-zero SHA for a branch's first push.
        plan = self.json_stdout(self.run_cli("plan", "--since", "0" * 40))

        self.assertEqual(plan["apps"], ["org.example.Alpha", "org.example.Beta"])

    def test_a_deleted_application_is_not_planned(self):
        import shutil

        shutil.rmtree(self.fixture.root / "manifests" / "org.example.Beta")
        self.commit("drop beta")

        plan = self.json_stdout(self.run_cli("plan", "--since", self.base))

        self.assertEqual(plan["apps"], [])


if __name__ == "__main__":
    unittest.main()
