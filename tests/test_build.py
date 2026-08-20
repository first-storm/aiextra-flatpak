"""`aiextra.py build` — invoking flatpak-builder and reporting per-app results."""

import unittest

from support import CliTestCase


class BuildInvocation(CliTestCase):
    def setUp(self):
        super().setUp()
        self.fixture.add_app("org.example.Alpha")
        self.stub("flatpak", stdout="x86_64")
        self.stub("flatpak-builder")

    def test_flatpak_builder_is_called_exactly_as_before(self):
        # Locked deliberately: the published OSTree refs and repository layout
        # that installed clients already track depend on this argv.
        self.assertOk(self.run_cli("build", "--all"))

        self.assertEqual(
            self.calls("flatpak-builder"),
            [
                "--force-clean --disable-rofiles-fuse --repo=repo "
                "build-org.example.Alpha "
                "manifests/org.example.Alpha/org.example.Alpha.yml"
            ],
        )

    def test_signing_arguments_are_added_when_both_gpg_variables_are_set(self):
        self.assertOk(
            self.run_cli(
                "build",
                "--all",
                env={"GPG_KEY_ID": "DEADBEEF", "GNUPGHOME": "/tmp/gnupg"},
            )
        )

        self.assertEqual(
            self.calls("flatpak-builder"),
            [
                "--force-clean --disable-rofiles-fuse --repo=repo "
                "--gpg-sign=DEADBEEF --gpg-homedir=/tmp/gnupg "
                "build-org.example.Alpha "
                "manifests/org.example.Alpha/org.example.Alpha.yml"
            ],
        )

    def test_a_lone_gpg_variable_does_not_produce_a_half_signed_build(self):
        self.assertOk(self.run_cli("build", "--all", env={"GPG_KEY_ID": "DEADBEEF"}))

        self.assertNotIn("gpg", self.calls("flatpak-builder")[0])


class BuildArchitectureHandling(CliTestCase):
    def setUp(self):
        super().setUp()
        self.stub("flatpak", stdout="x86_64")
        self.stub("flatpak-builder")

    def test_application_not_configured_for_this_architecture_is_skipped(self):
        self.fixture.add_app("org.example.Intel", arches="x86_64\n")
        self.fixture.add_app("org.example.Arm", arches="aarch64\n")

        result = self.run_cli("build", "--all", with_github_output=True)

        self.assertOk(result)
        payload = self.json_stdout(result)
        self.assertEqual(payload["succeeded"], ["org.example.Intel"])
        self.assertEqual(payload["skipped"], ["org.example.Arm"])
        self.assertEqual(payload["failed"], [])
        self.assertEqual(len(self.calls("flatpak-builder")), 1)

    def test_requested_architecture_must_match_the_machine(self):
        self.fixture.add_app("org.example.Alpha")

        result = self.run_cli("build", "--all", "--arch", "aarch64")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(self.calls("flatpak-builder"), [])


class BuildResults(CliTestCase):
    def setUp(self):
        super().setUp()
        self.fixture.add_app("org.example.Alpha")
        self.fixture.add_app("org.example.Beta")
        self.fixture.add_app("org.example.Gamma")
        self.stub("flatpak", stdout="x86_64")
        self.stub("flatpak-builder", fail_when="build-org.example.Beta")

    def test_one_failure_does_not_stop_the_remaining_applications(self):
        result = self.run_cli("build", "--all", with_github_output=True)

        self.assertEqual(result.returncode, 1)
        payload = self.json_stdout_allowing_failure(result)
        self.assertEqual(
            payload["succeeded"], ["org.example.Alpha", "org.example.Gamma"]
        )
        self.assertEqual(payload["failed"], ["org.example.Beta"])
        self.assertEqual(len(self.calls("flatpak-builder")), 3)

    def test_counts_and_failures_reach_the_github_output_file(self):
        self.run_cli("build", "--all", with_github_output=True)

        pairs = self.github_output_pairs()
        self.assertEqual(pairs["succeeded_count"], "2")
        self.assertEqual(pairs["failed_count"], "1")
        self.assertEqual(pairs["failed"], "org.example.Beta")


if __name__ == "__main__":
    unittest.main()
