# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

This repository packages unofficial Flatpak wrappers for upstream-published Linux releases of AI desktop applications (currently ChatGPT `com.openai.ChatGPT`, Claude `com.anthropic.Claude`, ZCode `ai.z.ZCode`, and LobeHub Desktop `com.lobehub.lobehub-desktop`; more may be added, and they are not necessarily closed-source). All application package units reside in `manifests/<app-id>/`. The repository does not build any of those applications from source and must not vendor their `.deb` packages. The manifests declare those packages as architecture-specific `extra-data`; Flatpak downloads them from the vendors and verifies their size and SHA256 during end-user installation.

User-facing descriptions — `README.md`'s intro and `aiextra.flatpakrepo`'s `Comment`/`Description` — are deliberately app-agnostic so that adding an application does not require rewriting them. Keep them that way: the packaged apps are enumerated only in the README's `Apps` table.

Run commands below from the repository root.

## Build and validation commands

Install the build dependencies and the runtime used by manifests:

```sh
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install -y flathub \
  org.freedesktop.Platform//25.08 \
  org.freedesktop.Sdk//25.08 \
  org.electronjs.Electron2.BaseApp//25.08
```

All build-system operations go through one entry point, `tools/aiextra.py`. It
needs Python 3 and PyYAML (`python3-yaml` on Debian/Ubuntu).

Target selection is always one explicit mode — `--all`, `--since <rev>`, or
named app IDs — and never an empty string. Nothing can silently turn "no
targets" into "every target".

```sh
tools/aiextra.py apps  --all                    # resolve + validate every app
tools/aiextra.py apps  com.openai.ChatGPT       # ...or just some
tools/aiextra.py plan  --all                    # JSON: apps, arches, matrix, runtimes
tools/aiextra.py plan  --since HEAD~1           # apps changed since a revision
```

Build applications into a shared OSTree repo (`GPG_KEY_ID` + `GNUPGHOME` add
signing; omit both for unsigned local builds — a lone one is ignored):

```sh
tools/aiextra.py build --all
tools/aiextra.py build com.openai.ChatGPT
tools/aiextra.py prune --all       # drop refs for architectures no longer configured

flatpak build-update-repo \
  --gpg-sign="$GPG_KEY_ID" --gpg-homedir="$GNUPGHOME" repo
```

Exit codes are distinct: `0` success, `1` an operation failed (some app failed
to build or check), `2` a usage or validation error.

For targeted validation of a single application without publishing/signing:

```sh
flatpak-builder --force-clean --disable-rofiles-fuse build-com.openai.ChatGPT manifests/com.openai.ChatGPT/com.openai.ChatGPT.yml
```

The build system has a test suite under `tests/`, run with the stdlib test
runner (no third-party dependency):

```sh
python3 -m unittest discover -s tests -t tests          # everything
python3 -m unittest discover -s tests -t tests -k prune # one area
python3 -m unittest -t tests tests.test_build           # one file
```

Every test drives `tools/aiextra.py` as a subprocess against a throwaway
fixture repository (`AIEXTRA_REPO_ROOT`) with stubbed `flatpak`,
`flatpak-builder`, `ostree` and checker binaries on `PATH`. **The seam under
test is the command-line contract only** — argv in; stdout JSON, stderr, exit
code, `$GITHUB_OUTPUT` and the argv recorded by the stubs out. Nothing reaches
inside the module, so its internals stay free to change. Add tests at that
boundary; do not import functions from `tools/aiextra.py`.

`tests/test_build.py` pins the exact `flatpak-builder` argv on purpose: the
published OSTree refs that installed clients already track depend on it.

There is no linter or formatter configuration. Building one app remains the
targeted end-to-end validation. Generated state is ignored under
`.flatpak-builder/`, `build-*`, `repo/`, and `*.flatpak`.

The automated upstream update check across all discovered manifests (or for specific apps) is run by:

```sh
tools/aiextra.py check --all
tools/aiextra.py check com.openai.ChatGPT
```

`check` refuses to start when the working tree is dirty. It rolls a failed
checker back with `git reset --hard`, so this guard is what keeps that from
destroying uncommitted local work.

Or for a single manifest directly:

```sh
flatpak-external-data-checker --update --commit-to-current-branch manifests/com.openai.ChatGPT/com.openai.ChatGPT.yml
```

Review checker-generated manifest changes together with the prepended release entries in the matching metainfo file. The GitHub workflow commits directly to `main`, pushes, then explicitly dispatches `build.yml` with the updated app IDs (`-f apps=...`) so that only changed applications are rebuilt.

## Package architecture

Each directory under `manifests/<app-id>/` is one package unit containing a manifest, an `architectures` file, shell launcher, desktop entry, AppStream metainfo, and size-specific icons. The app ID is coupled across these assets: manifest and metadata filenames, `command`, installed launcher, desktop `Exec`/`Icon`/`StartupWMClass`, metainfo ID and launchable desktop ID, icon filename prefix, and Electron patch target must remain aligned.

`architectures` is the CI build/publication interface for that application. It contains exactly one or both Flatpak architecture names (`x86_64` and `aarch64`), one per line. Discovery rejects missing, empty, duplicate, or unknown values. Once a configured architecture builds successfully, CI removes any previously published refs for architectures no longer listed; failed replacement builds leave old refs intact.

Each current manifest contains two `extra-data` sources—one for `x86_64`, one for `aarch64`—with vendor URL, size, SHA256, and `x-checker-data`. `flatpak-builder` records the source matching the current architecture but intentionally does not download the large upstream payload during CI. The `architectures` file controls which native builds are published without removing the other source's update metadata.

The checker type follows what the vendor publishes. OpenAI and Anthropic serve apt repositories, so those manifests use `type: debian-repo`. Z.AI serves only a CDN plus a releases API, so `ai.z.ZCode` uses `type: json` against `https://zcode.z.ai/api/v1/releases/latest`; that API advertises only the AppImage, and the `url-query` rewrites the extension to reach the `.deb` published beside it. Keep the two per-architecture queries pointed at `.platforms["linux-x86_64"]` and `.platforms["linux-aarch64"]` respectively, and `is-main-source: true` on the `x86_64` source only.

At installation time, the manifest's inline `apply_extra` script:

1. Uses `bsdtar` to extract the application directory from the downloaded `.deb` into `/app/extra`.
2. Removes the downloaded package.
3. Runs the Electron BaseApp-provided `patch-electron-desktop-filename` tool with the exact Flatpak app ID. The `--skip-integrity-check resources/app.asar` flag is required because this modifies the packaged Electron application.

Vendors do not agree on where the payload lives inside the `.deb`, so the `--strip-components` depth and subtree path differ per app: ChatGPT and Claude install under `./usr/lib/<name>` (depth 4), ZCode under `./opt/ZCode` (depth 3).

The installed shell launcher runs the extracted vendor executable through `zypak-wrapper` and sets `TMPDIR=$XDG_CACHE_HOME`. ChatGPT also deliberately persists `.codex` through its manifest permissions, and ZCode `.zcode`.

`ai.z.ZCode`'s `finish-args` are derived from what its `app.asar` actually uses rather than copied from other apps, and the manifest carries per-line comments recording that evidence—including for permissions deliberately withheld (`org.kde.StatusNotifierWatcher`, because its tray code is Windows-only). `org.freedesktop.Flatpak` is granted so ZCode can request host-side command execution through Flatpak's D-Bus API. Do not widen the remaining permissions without re-checking the payload.

Icon installation derives the size from filenames shaped as `<app-id>-<size>.png`; preserve that naming scheme when changing icons.

## Adding a new application

Adding a new application **does not require editing any GitHub Actions workflows** (`.github/workflows/`). To add an app:

1. Create a package directory under `manifests/` named with the reverse-DNS Flatpak app ID: `manifests/<app-id>/`.
2. Add `manifests/<app-id>/architectures` with `x86_64`, `aarch64`, or both, one per line.
3. Create the Flatpak manifest `manifests/<app-id>/<app-id>.yml` (or `.yaml`) specifying matching `app-id: <app-id>` and architecture-specific `extra-data` sources with `x-checker-data`.
4. Add the desktop entry `manifests/<app-id>/<app-id>.desktop`, AppStream metadata `manifests/<app-id>/<app-id>.metainfo.xml`, shell launcher `manifests/<app-id>/<name>.sh`, and icons under `manifests/<app-id>/icons/<app-id>-<size>.png`.
5. Validate discovery and manifest build locally:
   ```sh
   tools/aiextra.py plan --all
   tools/aiextra.py build <app-id>
   ```
6. If the app is ready for users, add a row to the `Apps` table in `README.md`. The install command and the `aiextra.flatpakrepo` description are app-agnostic and must not be re-specialized to name individual apps.

## CI and publication flow

`.github/workflows/build.yml` first resolves the target applications and takes the union of their `architectures` files, then runs only the required native `x86_64` and/or `aarch64` jobs. Architecture jobs run serially. They update the same incremental OSTree repository on `gh-pages`, so preserving the existing `repo/` checkout and `max-parallel: 1` prevents one architecture from overwriting the other.

Within each architecture job, CI:

1. Seeds `repo/` from the existing `gh-pages` branch.
2. Imports the private GPG key and installs the runtime, SDK, and Electron BaseApp.
3. Builds configured applications for the job's native architecture via `tools/aiextra.py build`, skipping applications that do not list it.
4. Runs `tools/aiextra.py prune --all` as separate repository maintenance, removing `app/`, `.Debug` and `.Locale` refs for architectures an application no longer configures. It covers every application, not only the ones built in this run, and its failures are reported separately from build failures.
5. Signs updated repository metadata and publishes `repo/` back to `gh-pages` if at least one build succeeded.
6. Fails the workflow job if any application build failed, surfacing the list of failed app IDs in `::error::`.

The dynamic app build step uses `continue-on-error` and isolates individual build errors so that successful app updates can still be published while preserving previous versions of failed apps.

`aiextra.flatpakrepo` embeds the public key corresponding to CI's `GPG_PRIVATE_KEY`; keep them synchronized during key rotation.

The build workflow's path filter ignores documentation, tests, and the CI/update-check workflows (`paths-ignore`), triggering on any push to `main` that touches application manifests, assets, tools, or repo metadata.

`.github/workflows/ci.yml` runs the `tests/` suite and `tools/aiextra.py plan --all` on every push and pull request.

The runtime, SDK and BaseApp refs CI installs are derived from the manifests by `tools/aiextra.py plan` (its `runtimes` output), so bumping a manifest's `runtime-version` needs no workflow edit.
