"""The `architectures` file is parsed in exactly one place; these pin its rules."""

import unittest

from support import CliTestCase


class ArchitectureValidation(CliTestCase):
    def reject(self, arches, needle):
        self.fixture.add_app("org.example.Alpha", arches=arches)
        result = self.run_cli("apps", "--all")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(needle, result.stderr)

    def test_missing_architectures_file_is_rejected(self):
        self.reject(None, "architectures")

    def test_empty_architectures_file_is_rejected(self):
        self.reject("", "empty")

    def test_whitespace_only_architectures_file_is_rejected(self):
        self.reject("\n\n  \n", "empty")

    def test_unknown_architecture_is_rejected(self):
        self.reject("x86_64\nriscv64\n", "riscv64")

    def test_duplicate_architecture_is_rejected(self):
        self.reject("x86_64\nx86_64\n", "Duplicate")


class ArchitectureParsing(CliTestCase):
    def accepts(self, arches):
        self.fixture.add_app("org.example.Alpha", arches=arches)
        result = self.run_cli("apps", "--all")
        self.assertOk(result)

    def test_final_line_without_a_trailing_newline_is_still_read(self):
        # The old shell tooling had three different parsers; the `while read`
        # one silently dropped this architecture, so an arch could lose its
        # runner while the other two parsers still saw it.
        self.fixture.add_app("org.example.Alpha", arches="x86_64\naarch64")

        result = self.run_cli("plan", "--all", with_github_output=True)

        self.assertOk(result)
        self.assertEqual(self.json_stdout(result)["arches"], ["x86_64", "aarch64"])

    def test_blank_lines_and_surrounding_whitespace_are_tolerated(self):
        self.accepts("\nx86_64  \n\n  aarch64\n\n")


class AppIdCoupling(CliTestCase):
    def test_manifest_declaring_a_different_app_id_is_rejected(self):
        # The classic copy-paste mistake when adding an application.
        self.fixture.add_app("org.example.Alpha", declared_app_id="org.example.Copied")

        result = self.run_cli("apps", "--all")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("org.example.Copied", result.stderr)


if __name__ == "__main__":
    unittest.main()
