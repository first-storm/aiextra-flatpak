#!/usr/bin/env python3
"""aiextra — the build system for this Flatpak wrapper repository.

One entry point, one source of truth per fact. See CLAUDE.md.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


def repo_root() -> Path:
    override = os.environ.get("AIEXTRA_REPO_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parent.parent


def log(message: str) -> None:
    """Progress goes to stderr so stdout stays machine readable."""
    print(message, file=sys.stderr)


class UsageError(Exception):
    """Anything the caller got wrong: bad targets, invalid repository data."""


MANIFEST_EXTENSIONS = (".yml", ".yaml")

# The single source of truth for which architectures exist and where they are
# built. Adding an architecture is one line here and nowhere else.
ARCH_RUNNERS = {
    "x86_64": "ubuntu-latest",
    "aarch64": "ubuntu-24.04-arm",
}


@dataclass(frozen=True)
class App:
    """One package unit under manifests/<app-id>/."""

    app_id: str
    directory: Path

    @property
    def architectures_file(self) -> Path:
        return self.directory / "architectures"

    @property
    def arches(self) -> list[str]:
        """The only parser for `architectures`, in registry order."""
        path = self.architectures_file
        if not path.is_file():
            raise UsageError(
                f"Missing architecture config for '{self.app_id}' ({path})"
            )
        seen: list[str] = []
        for line in path.read_text().splitlines():
            arch = line.strip()
            if not arch:
                continue
            if arch not in ARCH_RUNNERS:
                raise UsageError(
                    f"Unsupported architecture '{arch}' for '{self.app_id}' ({path})"
                )
            if arch in seen:
                raise UsageError(
                    f"Duplicate architecture '{arch}' for '{self.app_id}' ({path})"
                )
            seen.append(arch)
        if not seen:
            raise UsageError(
                f"Architecture config for '{self.app_id}' is empty ({path})"
            )
        return [arch for arch in ARCH_RUNNERS if arch in seen]

    @property
    def metadata(self) -> dict:
        """The manifest, parsed as YAML rather than scanned line by line."""
        with self.manifest.open(encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    @property
    def manifest(self) -> Path:
        for extension in MANIFEST_EXTENSIONS:
            candidate = self.directory / f"{self.app_id}{extension}"
            if candidate.is_file():
                return candidate
        raise UsageError(
            f"No application manifest found for '{self.app_id}' in {self.directory}"
        )


def discover_apps(root: Path) -> list[App]:
    manifests_dir = root / "manifests"
    if not manifests_dir.is_dir():
        raise UsageError(f"No manifests directory at {manifests_dir}")
    apps = [
        App(app_id=entry.name, directory=entry)
        for entry in sorted(manifests_dir.iterdir())
        if entry.is_dir()
    ]
    if not apps:
        raise UsageError(f"No applications found under {manifests_dir}")
    return apps


def normalize_target(token: str, root: Path) -> str:
    """Turn any way of naming an application into its app ID."""
    text = token.strip()
    for extension in MANIFEST_EXTENSIONS:
        if text.endswith(extension):
            text = text[: -len(extension)]
            break
    path = Path(text)
    if path.is_absolute():
        try:
            path = path.relative_to(root)
        except ValueError:
            raise UsageError(f"Target '{token}' is outside {root}") from None
    parts = [part for part in path.parts if part not in (".", "manifests")]
    if not parts:
        raise UsageError(f"Target '{token}' does not name an application")
    return parts[0]


def split_targets(raw_targets: list[str]) -> list[str]:
    """Accept comma- and space-separated lists inside a single argument."""
    tokens: list[str] = []
    for raw in raw_targets:
        tokens.extend(token for token in raw.replace(",", " ").split() if token)
    return tokens


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
    )


def app_ids_changed_since(root: Path, base: str) -> list[str] | None:
    """App IDs touched since `base`, or None when everything must be rebuilt."""
    if git(root, "rev-parse", "--verify", f"{base}^{{commit}}").returncode != 0:
        log(f"Base revision '{base}' is unknown; planning every application.")
        return None
    diff = git(root, "diff", "--name-only", f"{base}..HEAD")
    if diff.returncode != 0:
        log("Could not diff against the base revision; planning every application.")
        return None
    app_ids: list[str] = []
    for line in diff.stdout.splitlines():
        parts = Path(line.strip()).parts
        if len(parts) < 3 or parts[0] != "manifests":
            log(f"Change outside manifests ({line}); planning every application.")
            return None
        if parts[1] not in app_ids:
            app_ids.append(parts[1])
    return app_ids


def select_apps(args: argparse.Namespace, root: Path) -> list[App]:
    """Resolve exactly one target mode into a concrete, validated app list."""
    available = {app.app_id: app for app in discover_apps(root)}
    since = getattr(args, "since", None)
    if since:
        changed = app_ids_changed_since(root, since)
        if changed is None:
            selected = list(available.values())
        else:
            # A deleted application shows up in the diff but has nothing left
            # to build, so it drops out rather than failing the run.
            selected = [available[a] for a in sorted(changed) if a in available]
    elif args.all:
        selected = list(available.values())
    else:
        wanted: list[str] = []
        for token in split_targets(args.targets):
            app_id = normalize_target(token, root)
            if app_id not in available:
                raise UsageError(
                    f"Unknown application '{app_id}' (from target '{token}')"
                )
            if app_id not in wanted:
                wanted.append(app_id)
        selected = [available[app_id] for app_id in sorted(wanted)]
    for app in selected:
        validate(app)
    return selected


def add_target_arguments(
    parser: argparse.ArgumentParser, *, with_since: bool = False
) -> None:
    """Target selection is always explicit; the modes are mutually exclusive."""
    parser.add_argument("--all", action="store_true", help="every application")
    if with_since:
        parser.add_argument(
            "--since",
            metavar="REV",
            help="applications changed since this git revision",
        )
    parser.add_argument("targets", nargs="*", help="application IDs")


def resolve_target_mode(args: argparse.Namespace) -> None:
    """Exactly one target mode, always. Never an empty string standing in."""
    modes = [
        name
        for name, chosen in (
            ("--all", args.all),
            ("--since", bool(getattr(args, "since", None))),
            ("named applications", bool(args.targets)),
        )
        if chosen
    ]
    if len(modes) > 1:
        raise UsageError(f"{' and '.join(modes)} cannot be combined")
    if not modes:
        raise UsageError("Name at least one application, or pass --all")


def validate(app: App) -> None:
    """Every check that must hold before an app is considered usable."""
    declared = app.metadata.get("app-id")
    if declared and declared != app.app_id:
        raise UsageError(
            f"{app.manifest} declares app-id '{declared}', expected '{app.app_id}'"
        )
    app.arches  # noqa: B018 - raises UsageError when the config is invalid


def runtime_refs(app: App) -> list[str]:
    """The exact `flatpak install` arguments this application needs."""
    metadata = app.metadata
    runtime_version = str(metadata.get("runtime-version", ""))
    base_version = str(metadata.get("base-version", runtime_version))
    refs = []
    for name, version in (
        (metadata.get("runtime"), runtime_version),
        (metadata.get("sdk"), runtime_version),
        (metadata.get("base"), base_version),
    ):
        if name and version:
            refs.append(f"{name}//{version}")
    return refs


def emit(payload: dict) -> None:
    """The one place a result reaches both a human and GitHub Actions."""
    print(json.dumps(payload, indent=2))
    output_file = os.environ.get("GITHUB_OUTPUT")
    if not output_file:
        return
    with open(output_file, "a", encoding="utf-8") as handle:
        for key, value in payload.items():
            if isinstance(value, list):
                rendered = " ".join(str(item) for item in value)
            elif isinstance(value, (dict, bool)):
                rendered = json.dumps(value, separators=(",", ":"))
            else:
                rendered = str(value)
            handle.write(f"{key}={rendered}\n")


def cmd_plan(args: argparse.Namespace, root: Path) -> int:
    apps = select_apps(args, root)
    selected_arches = {arch for app in apps for arch in app.arches}
    arches = [arch for arch in ARCH_RUNNERS if arch in selected_arches]
    runtimes: list[str] = []
    for app in apps:
        for ref in runtime_refs(app):
            if ref not in runtimes:
                runtimes.append(ref)
    emit(
        {
            "apps": [app.app_id for app in apps],
            "arches": arches,
            "matrix": {
                "include": [
                    {"arch": arch, "runner": ARCH_RUNNERS[arch]} for arch in arches
                ]
            },
            "runtimes": sorted(runtimes),
        }
    )
    return EXIT_OK


def ostree_repo() -> str:
    return os.environ.get("AIEXTRA_OSTREE_REPO", "repo")


def native_arch() -> str:
    result = subprocess.run(
        ["flatpak", "--default-arch"], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise UsageError("Could not determine the native Flatpak architecture")
    return result.stdout.strip()


def builder_command(app: App, root: Path) -> list[str]:
    """The flatpak-builder invocation. Its exact shape is what clients see."""
    command = [
        "flatpak-builder",
        "--force-clean",
        "--disable-rofiles-fuse",
        f"--repo={ostree_repo()}",
    ]
    key_id = os.environ.get("GPG_KEY_ID")
    gnupg_home = os.environ.get("GNUPGHOME")
    if key_id and gnupg_home:
        command += [f"--gpg-sign={key_id}", f"--gpg-homedir={gnupg_home}"]
    command += [f"build-{app.app_id}", str(app.manifest.relative_to(root))]
    return command


def cmd_build(args: argparse.Namespace, root: Path) -> int:
    apps = select_apps(args, root)
    arch = native_arch()
    if args.arch and args.arch != arch:
        raise UsageError(f"Machine architecture is {arch}, requested {args.arch}")

    succeeded, skipped, failed = [], [], []
    for app in apps:
        if arch not in app.arches:
            log(f"Skipping {app.app_id}: {arch} is not configured")
            skipped.append(app.app_id)
            continue
        log(f"::group::Building {app.app_id} for {arch}")
        result = subprocess.run(builder_command(app, root), cwd=str(root))
        log("::endgroup::")
        if result.returncode == 0:
            succeeded.append(app.app_id)
        else:
            log(f"Build failed: {app.app_id}")
            failed.append(app.app_id)

    emit(
        {
            "arch": arch,
            "succeeded": succeeded,
            "skipped": skipped,
            "failed": failed,
            "succeeded_count": len(succeeded),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
        }
    )
    return EXIT_FAILED if failed else EXIT_OK


# Everything flatpak-builder publishes for one application and architecture.
# The extension refs use the app ID with hyphens mangled to underscores, so
# com.example.a-b ships as app/com.example.a-b and runtime/com.example.a_b.Debug.
REF_PREFIXES = (
    "app/{app_id}/{arch}",
    "runtime/{extension_id}.Debug/{arch}",
    "runtime/{extension_id}.Locale/{arch}",
)


def ostree(root: Path, subcommand: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["ostree", subcommand, f"--repo={ostree_repo()}", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


def prune_app(app: App, root: Path) -> tuple[list[str], bool]:
    """Remove this app's refs for architectures it no longer configures."""
    removed: list[str] = []
    ok = True
    for arch in ARCH_RUNNERS:
        if arch in app.arches:
            continue
        for template in REF_PREFIXES:
            prefix = template.format(
                app_id=app.app_id,
                extension_id=app.app_id.replace("-", "_"),
                arch=arch,
            )
            listing = ostree(root, "refs", "--list", prefix)
            if listing.returncode != 0:
                log(f"Could not list refs under {prefix}: {listing.stderr.strip()}")
                ok = False
                continue
            refs = [
                line.strip() for line in listing.stdout.splitlines() if line.strip()
            ]
            if not refs:
                continue
            deletion = ostree(root, "refs", "--delete", prefix)
            if deletion.returncode != 0:
                log(f"Could not delete refs under {prefix}: {deletion.stderr.strip()}")
                ok = False
                continue
            log(f"Removed unsupported refs: {' '.join(refs)}")
            removed.extend(refs)
    return removed, ok


def cmd_prune(args: argparse.Namespace, root: Path) -> int:
    removed: list[str] = []
    failed: list[str] = []
    for app in select_apps(args, root):
        app_removed, ok = prune_app(app, root)
        removed.extend(app_removed)
        if not ok:
            failed.append(app.app_id)
    emit({"removed": removed, "failed": failed, "failed_count": len(failed)})
    return EXIT_FAILED if failed else EXIT_OK


DEFAULT_GIT_IDENTITY = "41898282+github-actions[bot]@users.noreply.github.com"


def checker_command(root: Path) -> list[str]:
    """Prefer a locally installed checker; otherwise the Flathub image."""
    if shutil.which("flatpak-external-data-checker"):
        return ["flatpak-external-data-checker"]
    name = os.environ.get("GIT_AUTHOR_NAME", "flatpak-external-data-checker")
    email = os.environ.get("GIT_AUTHOR_EMAIL", DEFAULT_GIT_IDENTITY)
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{root}:/repo",
        "-w",
        "/repo",
        "-e",
        f"GIT_AUTHOR_NAME={name}",
        "-e",
        f"GIT_COMMITTER_NAME={name}",
        "-e",
        f"GIT_AUTHOR_EMAIL={email}",
        "-e",
        f"GIT_COMMITTER_EMAIL={email}",
        "ghcr.io/flathub/flatpak-external-data-checker:latest",
    ]


def cmd_check(args: argparse.Namespace, root: Path) -> int:
    apps = select_apps(args, root)

    # A failing checker is rolled back with `git reset --hard`. Refusing to
    # start on a dirty tree is what keeps that from destroying local work.
    status = git(root, "status", "--porcelain")
    if status.returncode != 0:
        raise UsageError(f"{root} is not a git repository")
    if status.stdout.strip():
        raise UsageError(
            "Working tree has uncommitted changes; commit or stash them first"
        )

    checker = checker_command(root)
    updated: list[str] = []
    failed: list[str] = []
    for app in apps:
        head_before = git(root, "rev-parse", "HEAD").stdout.strip()
        log(f"::group::Checking {app.app_id}")
        command = [*checker, "--update", "--commit-to-current-branch"]
        command.append(str(app.manifest.relative_to(root)))
        result = subprocess.run(command, cwd=str(root))
        log("::endgroup::")
        if result.returncode != 0:
            log(f"Check failed: {app.app_id}")
            failed.append(app.app_id)
            # Only ever discards what this checker just wrote.
            git(root, "reset", "--hard", head_before)
            git(root, "clean", "-fdq")
            continue
        if git(root, "rev-parse", "HEAD").stdout.strip() != head_before:
            log(f"Update committed for {app.app_id}")
            updated.append(app.app_id)

    emit(
        {
            "updated": updated,
            "failed": failed,
            "updated_count": len(updated),
            "failed_count": len(failed),
        }
    )
    return EXIT_FAILED if failed else EXIT_OK


def cmd_apps(args: argparse.Namespace, root: Path) -> int:
    for app in select_apps(args, root):
        print(app.app_id)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aiextra")
    sub = parser.add_subparsers(dest="verb", required=True)

    apps = sub.add_parser("apps", help="list resolved application IDs")
    add_target_arguments(apps, with_since=True)
    apps.set_defaults(func=cmd_apps)

    plan = sub.add_parser("plan", help="emit the build plan as JSON")
    add_target_arguments(plan, with_since=True)
    plan.set_defaults(func=cmd_plan)

    build = sub.add_parser("build", help="build applications into the OSTree repo")
    add_target_arguments(build)
    build.add_argument("--arch", help="assert the machine's native architecture")
    build.set_defaults(func=cmd_build)

    prune = sub.add_parser("prune", help="drop refs for unconfigured architectures")
    add_target_arguments(prune)
    prune.set_defaults(func=cmd_prune)

    check = sub.add_parser("check", help="run flatpak-external-data-checker")
    add_target_arguments(check)
    check.set_defaults(func=cmd_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        resolve_target_mode(args)
        return args.func(args, repo_root())
    except UsageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
