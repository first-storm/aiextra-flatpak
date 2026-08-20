"""`aiextra.py plan` — the one document CI reads to decide what to run."""

import json
import unittest

from support import CliTestCase

BOTH_ARCHES = {
    "include": [
        {"arch": "x86_64", "runner": "ubuntu-latest"},
        {"arch": "aarch64", "runner": "ubuntu-24.04-arm"},
    ]
}
X86_ONLY = {"include": [{"arch": "x86_64", "runner": "ubuntu-latest"}]}


class PlanMatrix(CliTestCase):
    def test_matrix_covers_the_union_of_the_targeted_applications(self):
        self.fixture.add_app("org.example.Both", arches="x86_64\naarch64\n")
        self.fixture.add_app("org.example.Intel", arches="x86_64\n")

        plan = self.json_stdout(self.run_cli("plan", "--all"))

        self.assertEqual(plan["apps"], ["org.example.Both", "org.example.Intel"])
        self.assertEqual(plan["arches"], ["x86_64", "aarch64"])
        self.assertEqual(plan["matrix"], BOTH_ARCHES)

    def test_single_architecture_application_allocates_only_its_runner(self):
        self.fixture.add_app("org.example.Both", arches="x86_64\naarch64\n")
        self.fixture.add_app("org.example.Intel", arches="x86_64\n")

        plan = self.json_stdout(self.run_cli("plan", "org.example.Intel"))

        self.assertEqual(plan["apps"], ["org.example.Intel"])
        self.assertEqual(plan["matrix"], X86_ONLY)

    def test_architecture_order_follows_the_registry_not_the_file(self):
        self.fixture.add_app("org.example.Reversed", arches="aarch64\nx86_64\n")

        plan = self.json_stdout(self.run_cli("plan", "--all"))

        self.assertEqual(plan["matrix"], BOTH_ARCHES)


class PlanRuntimes(CliTestCase):
    def test_runtimes_are_derived_from_the_manifests(self):
        self.fixture.add_app("org.example.Alpha", runtime_version="25.08")

        plan = self.json_stdout(self.run_cli("plan", "--all"))

        self.assertEqual(
            plan["runtimes"],
            [
                "org.electronjs.Electron2.BaseApp//25.08",
                "org.freedesktop.Platform//25.08",
                "org.freedesktop.Sdk//25.08",
            ],
        )

    def test_runtimes_from_several_versions_are_all_listed_once(self):
        self.fixture.add_app("org.example.Old", runtime_version="24.08")
        self.fixture.add_app("org.example.New", runtime_version="25.08")

        plan = self.json_stdout(self.run_cli("plan", "--all"))

        self.assertIn("org.freedesktop.Platform//24.08", plan["runtimes"])
        self.assertIn("org.freedesktop.Platform//25.08", plan["runtimes"])
        self.assertEqual(len(plan["runtimes"]), len(set(plan["runtimes"])))


class PlanGithubOutput(CliTestCase):
    def test_plan_is_published_to_the_github_output_file(self):
        self.fixture.add_app("org.example.Both", arches="x86_64\naarch64\n")

        result = self.run_cli("plan", "--all", with_github_output=True)
        self.assertOk(result)
        pairs = self.github_output_pairs()

        self.assertEqual(pairs["apps"], "org.example.Both")
        self.assertEqual(json.loads(pairs["matrix"]), BOTH_ARCHES)
        self.assertIn("org.freedesktop.Platform//25.08", pairs["runtimes"])

    def test_apps_output_is_always_an_explicit_list_never_empty_for_all(self):
        # The old tooling used "" to mean both "no targets" and "every target",
        # so an update run that found nothing rebuilt everything.
        self.fixture.add_app("org.example.Alpha")
        self.fixture.add_app("org.example.Beta")

        result = self.run_cli("plan", "--all", with_github_output=True)
        self.assertOk(result)

        self.assertEqual(
            self.github_output_pairs()["apps"], "org.example.Alpha org.example.Beta"
        )


if __name__ == "__main__":
    unittest.main()
