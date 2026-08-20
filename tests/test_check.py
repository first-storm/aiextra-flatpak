"""`aiextra.py check` — running flatpak-external-data-checker over manifests."""

import unittest

from support import CliTestCase

CHECKER = "flatpak-external-data-checker"


class CheckWorkingTreeGuard(CliTestCase):
    def setUp(self):
        super().setUp()
        self.fixture.add_app("org.example.Alpha")
        self.init_git()
        self.stub(CHECKER)

    def test_a_dirty_working_tree_stops_the_run_before_anything_is_touched(self):
        # The checker's rollback is `git reset --hard`, which would otherwise
        # destroy uncommitted local work.
        (self.fixture.root / "uncommitted.txt").write_text("mine\n")

        result = self.run_cli("check", "--all")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(self.calls(CHECKER), [])

    def test_a_clean_working_tree_runs_the_checker(self):
        self.assertOk(self.run_cli("check", "--all"))

        self.assertEqual(
            self.calls(CHECKER),
            [
                "--update --commit-to-current-branch "
                "manifests/org.example.Alpha/org.example.Alpha.yml"
            ],
        )


class CheckResults(CliTestCase):
    def setUp(self):
        super().setUp()
        self.fixture.add_app("org.example.Alpha")
        self.fixture.add_app("org.example.Beta")
        self.init_git()

    def test_an_application_whose_checker_committed_is_reported_as_updated(self):
        self.stub(
            CHECKER,
            body=(
                'case "$*" in *Alpha*) '
                'git commit -q --allow-empty -m "update Alpha" ;; esac'
            ),
        )

        result = self.run_cli("check", "--all", with_github_output=True)

        self.assertOk(result)
        payload = self.json_stdout(result)
        self.assertEqual(payload["updated"], ["org.example.Alpha"])
        self.assertEqual(payload["failed"], [])
        self.assertEqual(self.github_output_pairs()["updated"], "org.example.Alpha")

    def test_a_run_that_found_nothing_reports_an_empty_update_list(self):
        self.stub(CHECKER)

        result = self.run_cli("check", "--all", with_github_output=True)

        self.assertOk(result)
        self.assertEqual(self.json_stdout(result)["updated"], [])
        self.assertEqual(self.github_output_pairs()["updated"], "")

    def test_a_failing_checker_is_rolled_back_and_the_run_continues(self):
        self.stub(
            CHECKER,
            body=(
                'case "$*" in *Alpha*) '
                'echo broken > half-written.txt; exit 1 ;; esac'
            ),
        )

        result = self.run_cli("check", "--all", with_github_output=True)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = self.json_stdout_allowing_failure(result)
        self.assertEqual(payload["failed"], ["org.example.Alpha"])
        self.assertEqual(len(self.calls(CHECKER)), 2)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_an_earlier_successful_update_survives_a_later_failure(self):
        self.stub(
            CHECKER,
            body=(
                'case "$*" in '
                '*Alpha*) git commit -q --allow-empty -m "update Alpha" ;; '
                '*Beta*) exit 1 ;; esac'
            ),
        )

        result = self.run_cli("check", "--all")

        self.assertEqual(result.returncode, 1)
        payload = self.json_stdout_allowing_failure(result)
        self.assertEqual(payload["updated"], ["org.example.Alpha"])
        self.assertEqual(payload["failed"], ["org.example.Beta"])
        self.assertIn("update Alpha", self.git("log", "--format=%s"))


if __name__ == "__main__":
    unittest.main()
