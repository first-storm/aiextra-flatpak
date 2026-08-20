"""`aiextra.py apps` — resolving and validating which applications exist."""

import unittest

from support import CliTestCase


class AppsListing(CliTestCase):
    def test_all_lists_every_application_sorted(self):
        self.fixture.add_app("org.example.Beta")
        self.fixture.add_app("org.example.Alpha")

        result = self.run_cli("apps", "--all")

        self.assertOk(result)
        self.assertEqual(
            result.stdout.split(), ["org.example.Alpha", "org.example.Beta"]
        )


class AppsValidation(CliTestCase):
    def test_application_directory_without_a_manifest_is_rejected(self):
        self.fixture.add_app("org.example.Alpha")
        (self.fixture.root / "manifests" / "org.example.Orphan").mkdir()

        result = self.run_cli("apps", "--all")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("org.example.Orphan", result.stderr)


class AppsTargetSelection(CliTestCase):
    def setUp(self):
        super().setUp()
        self.fixture.add_app("org.example.Alpha")
        self.fixture.add_app("org.example.Beta")
        self.fixture.add_app("org.example.Gamma")

    def test_named_application_is_resolved(self):
        result = self.run_cli("apps", "org.example.Beta")

        self.assertOk(result)
        self.assertEqual(result.stdout.split(), ["org.example.Beta"])

    def test_targets_may_be_written_as_paths_and_deduplicated(self):
        result = self.run_cli(
            "apps",
            "org.example.Beta",
            "manifests/org.example.Alpha",
            "manifests/org.example.Beta/",
            "manifests/org.example.Alpha/org.example.Alpha.yml",
            str(self.fixture.root / "manifests" / "org.example.Gamma"),
        )

        self.assertOk(result)
        self.assertEqual(
            result.stdout.split(),
            ["org.example.Alpha", "org.example.Beta", "org.example.Gamma"],
        )

    def test_a_single_argument_may_carry_a_comma_or_space_separated_list(self):
        result = self.run_cli("apps", "org.example.Gamma, org.example.Alpha")

        self.assertOk(result)
        self.assertEqual(
            result.stdout.split(), ["org.example.Alpha", "org.example.Gamma"]
        )

    def test_unknown_application_is_rejected(self):
        result = self.run_cli("apps", "org.example.Nope")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("org.example.Nope", result.stderr)

    def test_selecting_no_target_mode_at_all_is_a_usage_error(self):
        result = self.run_cli("apps")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_all_cannot_be_combined_with_named_targets(self):
        result = self.run_cli("apps", "--all", "org.example.Alpha")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
