"""Shared primitives for the aiextra CLI tests.

Every test drives the CLI as a subprocess, so the seam under test is the
command line contract only: argv in, stdout/stderr/exit code/$GITHUB_OUTPUT
out, plus the argv recorded by PATH stubs. Nothing here reaches inside
tools/aiextra.py.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "tools" / "aiextra.py"

MANIFEST_TEMPLATE = textwrap.dedent(
    """\
    app-id: {app_id}
    runtime: org.freedesktop.Platform
    runtime-version: '{runtime_version}'
    sdk: org.freedesktop.Sdk
    base: org.electronjs.Electron2.BaseApp
    base-version: '{runtime_version}'
    command: {app_id}
    modules:
      - name: {app_id}
        buildsystem: simple
    """
)


class FixtureRepo:
    """A throwaway repository root that looks like this project to the CLI."""

    def __init__(self, root: Path) -> None:
        self.root = root
        (self.root / "manifests").mkdir(parents=True, exist_ok=True)

    def add_app(
        self,
        app_id: str,
        arches: str | None = "x86_64\naarch64\n",
        declared_app_id: str | None = None,
        runtime_version: str = "25.08",
        extension: str = ".yml",
    ) -> Path:
        app_dir = self.root / "manifests" / app_id
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / f"{app_id}{extension}").write_text(
            MANIFEST_TEMPLATE.format(
                app_id=declared_app_id or app_id,
                runtime_version=runtime_version,
            )
        )
        if arches is not None:
            (app_dir / "architectures").write_text(arches)
        return app_dir


class CliTestCase(unittest.TestCase):
    """Base class wiring up a temp dir, a fixture repo and a stub PATH."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aiextra-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.fixture = FixtureRepo(self.tmp / "repo-root")
        self.stub_dir = self.tmp / "stubs"
        self.stub_dir.mkdir()
        self.calls_dir = self.tmp / "calls"
        self.calls_dir.mkdir()
        self.github_output = self.tmp / "github_output"
        self.github_output.write_text("")

    # -- stubs ---------------------------------------------------------

    def stub(
        self,
        name: str,
        *,
        stdout: str = "",
        exit_code: int = 0,
        fail_when: str | None = None,
        responses: list[tuple[str, str]] | None = None,
        body: str = "",
    ) -> None:
        """Put an executable on PATH that records its argv and then exits.

        `fail_when` makes the stub exit 1 only for invocations whose argv
        contains that substring, so a single application can be made to fail.
        `responses` maps an argv substring to the stdout for that invocation;
        the first match wins and anything unmatched prints `stdout`.
        """
        path = self.stub_dir / name
        script = [
            "#!/usr/bin/env bash",
            f'printf "%s\\n" "$*" >> {self.calls_dir}/{name}.calls',
        ]
        for needle, reply in responses or []:
            script += [
                f'case "$*" in *"{needle}"*)',
                "cat <<'AIEXTRA_STUB_EOF'",
                reply,
                "AIEXTRA_STUB_EOF",
                "exit 0 ;; esac",
            ]
        script += [
            "cat <<'AIEXTRA_STUB_EOF'",
            stdout,
            "AIEXTRA_STUB_EOF",
        ]
        if body:
            script.append(body)
        if fail_when:
            script.append(f'case "$*" in *"{fail_when}"*) exit 1 ;; esac')
        script += [f"exit {exit_code}", ""]
        path.write_text("\n".join(script))
        path.chmod(0o755)

    def calls(self, name: str) -> list[str]:
        """Every invocation of a stub, as the joined argv string."""
        path = self.calls_dir / f"{name}.calls"
        if not path.exists():
            return []
        return path.read_text().splitlines()

    # -- git -----------------------------------------------------------

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=str(self.fixture.root),
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null"},
        ).stdout.strip()

    def init_git(self) -> str:
        """Make the fixture repo a real git repo with one initial commit."""
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        return self.commit("initial")

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    # -- driving the CLI ----------------------------------------------

    def run_cli(
        self,
        *args: str,
        repo_root: Path | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        with_github_output: bool = False,
    ) -> subprocess.CompletedProcess:
        full_env = dict(os.environ)
        full_env["AIEXTRA_REPO_ROOT"] = str(repo_root or self.fixture.root)
        full_env["PATH"] = f"{self.stub_dir}{os.pathsep}{full_env['PATH']}"
        full_env.pop("GITHUB_OUTPUT", None)
        if with_github_output:
            full_env["GITHUB_OUTPUT"] = str(self.github_output)
        if env:
            full_env.update(env)
        return subprocess.run(
            ["python3", str(CLI), *args],
            capture_output=True,
            text=True,
            cwd=str(cwd or self.fixture.root),
            env=full_env,
        )

    # -- assertions ----------------------------------------------------

    def assertOk(self, result: subprocess.CompletedProcess) -> None:
        self.assertEqual(
            result.returncode,
            0,
            f"expected exit 0\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def json_stdout(self, result: subprocess.CompletedProcess) -> dict:
        self.assertOk(result)
        return json.loads(result.stdout)

    def json_stdout_allowing_failure(self, result) -> dict:
        return json.loads(result.stdout)

    def github_output_pairs(self) -> dict[str, str]:
        pairs: dict[str, str] = {}
        for line in self.github_output.read_text().splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                pairs[key] = value
        return pairs
