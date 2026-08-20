"""`aiextra.py prune` — dropping refs for architectures no longer configured."""

import unittest

from support import CliTestCase

ARM_REFS = "app/org.example.Intel/aarch64/master"


class Prune(CliTestCase):
    def setUp(self):
        super().setUp()
        self.fixture.add_app("org.example.Intel", arches="x86_64\n")

    def test_refs_for_unconfigured_architectures_are_removed(self):
        self.stub(
            "ostree",
            responses=[("--list app/org.example.Intel/aarch64", ARM_REFS)],
        )

        payload = self.json_stdout(self.run_cli("prune", "--all"))

        self.assertEqual(payload["removed"], [ARM_REFS])
        self.assertIn(
            "refs --repo=repo --delete app/org.example.Intel/aarch64",
            self.calls("ostree"),
        )

    def test_configured_architectures_are_never_listed_for_deletion(self):
        self.stub("ostree")

        self.assertOk(self.run_cli("prune", "--all"))

        self.assertFalse(
            [call for call in self.calls("ostree") if "x86_64" in call],
            "the configured architecture must never be considered for pruning",
        )

    def test_debug_and_locale_refs_are_pruned_alongside_the_app_ref(self):
        # The old shell tooling only ever matched the `app/` prefix, so debug
        # refs for a dropped architecture stayed on gh-pages forever.
        self.stub("ostree")

        self.assertOk(self.run_cli("prune", "--all"))

        listed = " ".join(self.calls("ostree"))
        self.assertIn("runtime/org.example.Intel.Debug/aarch64", listed)
        self.assertIn("runtime/org.example.Intel.Locale/aarch64", listed)

    def test_hyphenated_app_ids_use_the_mangled_debug_ref_name(self):
        # flatpak-builder publishes app/com.example.a-b/... but names the
        # extension refs runtime/com.example.a_b.Debug/..., so pruning by the
        # raw app ID would silently never match them.
        self.fixture.add_app("org.example.two-words", arches="x86_64\n")
        self.stub("ostree")

        self.assertOk(self.run_cli("prune", "org.example.two-words"))

        listed = " ".join(self.calls("ostree"))
        self.assertIn("app/org.example.two-words/aarch64", listed)
        self.assertIn("runtime/org.example.two_words.Debug/aarch64", listed)
        self.assertNotIn("runtime/org.example.two-words.Debug", listed)

    def test_nothing_is_deleted_when_there_are_no_matching_refs(self):
        self.stub("ostree")

        payload = self.json_stdout(self.run_cli("prune", "--all"))

        self.assertEqual(payload["removed"], [])
        self.assertFalse([c for c in self.calls("ostree") if "--delete" in c])

    def test_an_ostree_failure_is_reported_instead_of_being_swallowed(self):
        # Chained onto the build with `&&` inside an `if`, this used to be
        # invisible: set -e was disabled and the error became "Build failed".
        self.stub("ostree", exit_code=1)

        result = self.run_cli("prune", "--all", with_github_output=True)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(
            self.json_stdout_allowing_failure(result)["failed"], ["org.example.Intel"]
        )


if __name__ == "__main__":
    unittest.main()
