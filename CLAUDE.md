# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

This repository packages unofficial Flatpak wrappers for the proprietary Linux releases of ChatGPT (`com.openai.ChatGPT`), Claude (`com.anthropic.Claude`), and ZCode (`ai.z.ZCode`). It does not build any of those applications from source and must not vendor their `.deb` packages. The manifests declare those packages as architecture-specific `extra-data`; Flatpak downloads them from the vendors and verifies their size and SHA256 during end-user installation.

Run commands below from the repository root.

## Build and validation commands

Install the build dependencies and the runtime used by every manifest:

```sh
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install -y flathub \
  org.freedesktop.Platform//25.08 \
  org.freedesktop.Sdk//25.08 \
  org.electronjs.Electron2.BaseApp//25.08
```

CI builds each application separately into the shared Flatpak repository. These exact commands require `GPG_KEY_ID` and `GNUPGHOME` to identify an imported signing key:

```sh
flatpak-builder --force-clean --disable-rofiles-fuse --repo=repo \
  --gpg-sign="$GPG_KEY_ID" --gpg-homedir="$GNUPGHOME" \
  build-chatgpt com.openai.ChatGPT/com.openai.ChatGPT.yml

flatpak-builder --force-clean --disable-rofiles-fuse --repo=repo \
  --gpg-sign="$GPG_KEY_ID" --gpg-homedir="$GNUPGHOME" \
  build-claude com.anthropic.Claude/com.anthropic.Claude.yml

flatpak-builder --force-clean --disable-rofiles-fuse --repo=repo \
  --gpg-sign="$GPG_KEY_ID" --gpg-homedir="$GNUPGHOME" \
  build-zcode ai.z.ZCode/ai.z.ZCode.yml

flatpak build-update-repo \
  --gpg-sign="$GPG_KEY_ID" --gpg-homedir="$GNUPGHOME" repo
```

For a local manifest-only build where publication/signing is not needed, omit `--repo`, `--gpg-sign`, and `--gpg-homedir` from the corresponding `flatpak-builder` command.

There is no test suite, linter, formatter, or static-check configuration. Building one app is the targeted validation equivalent; there is no single-test command. Generated state is ignored under `.flatpak-builder/`, `build-*`, `repo/`, and `*.flatpak`.

The automated upstream update command, normally run by `.github/workflows/update-check.yml`, is:

```sh
flatpak-external-data-checker --update --commit-to-current-branch \
  com.openai.ChatGPT/com.openai.ChatGPT.yml
flatpak-external-data-checker --update --commit-to-current-branch \
  com.anthropic.Claude/com.anthropic.Claude.yml
flatpak-external-data-checker --update --commit-to-current-branch \
  ai.z.ZCode/ai.z.ZCode.yml
```

Review checker-generated manifest changes together with the prepended release entries in the matching metainfo file. The GitHub workflow commits directly to `main`, pushes, then explicitly dispatches `build.yml` because a `GITHUB_TOKEN` push does not trigger another workflow.

## Package architecture

Each app-ID directory is one package unit containing a manifest, shell launcher, desktop entry, AppStream metainfo, and size-specific icons. The app ID is coupled across these assets: manifest and metadata filenames, `command`, installed launcher, desktop `Exec`/`Icon`/`StartupWMClass`, metainfo ID and launchable desktop ID, icon filename prefix, and Electron patch target must remain aligned.

Each manifest contains two `extra-data` sources—one for `x86_64`, one for `aarch64`—with vendor URL, size, SHA256, and `x-checker-data`. `flatpak-builder` records these sources but intentionally does not download the large proprietary payload during CI.

The checker type follows what the vendor publishes. OpenAI and Anthropic serve apt repositories, so those manifests use `type: debian-repo`. Z.AI serves only a CDN plus a releases API, so `ai.z.ZCode` uses `type: json` against `https://zcode.z.ai/api/v1/releases/latest`; that API advertises only the AppImage, and the `url-query` rewrites the extension to reach the `.deb` published beside it. Keep the two per-architecture queries pointed at `.platforms["linux-x86_64"]` and `.platforms["linux-aarch64"]` respectively, and `is-main-source: true` on the `x86_64` source only.

At installation time, the manifest's inline `apply_extra` script:

1. Uses `bsdtar` to extract the application directory from the downloaded `.deb` into `/app/extra`.
2. Removes the downloaded package.
3. Runs the Electron BaseApp-provided `patch-electron-desktop-filename` tool with the exact Flatpak app ID. The `--skip-integrity-check resources/app.asar` flag is required because this modifies the packaged Electron application.

Vendors do not agree on where the payload lives inside the `.deb`, so the `--strip-components` depth and subtree path differ per app: ChatGPT and Claude install under `./usr/lib/<name>` (depth 4), ZCode under `./opt/ZCode` (depth 3).

The installed shell launcher runs the extracted vendor executable through `zypak-wrapper` and sets `TMPDIR=$XDG_CACHE_HOME`. ChatGPT also deliberately persists `.codex` through its manifest permissions, and ZCode `.zcode`.

`ai.z.ZCode`'s `finish-args` are derived from what its `app.asar` actually uses rather than copied from the other two apps, and the manifest carries per-line comments recording that evidence—including for the two permissions deliberately withheld (`org.kde.StatusNotifierWatcher`, because its tray code is Windows-only; `org.freedesktop.Flatpak`, because the app has no `flatpak-spawn` support). Do not widen them without re-checking the payload.

Icon installation derives the size from filenames shaped as `<app-id>-<size>.png`; preserve that naming scheme when changing icons.

## CI and publication flow

`.github/workflows/build.yml` builds native `x86_64` and `aarch64` jobs serially. Both jobs update the same incremental OSTree repository on `gh-pages`, so preserving the existing `repo/` checkout and `max-parallel: 1` prevents one architecture from overwriting the other.

Within each architecture job, CI:

1. Seeds `repo/` from the existing `gh-pages` branch.
2. Imports the private GPG key and installs the runtime, SDK, and Electron BaseApp.
3. Builds ChatGPT, Claude, and ZCode independently into `repo/`.
4. Signs updated repository metadata and publishes `repo/` back to `gh-pages`.

The app build steps intentionally use `continue-on-error` so successful apps can still be published if another fails. A final step then fails the job if any build failed. Preserve both halves of this partial-success behavior. Adding an app means extending five places in `build.yml`: the `paths` filter, a new build step with a unique `id`, the shared `if:` condition on the three publish steps, and both the `if:` and the `::error::` message of the final failure gate.

`aiextra.flatpakrepo` embeds the public key corresponding to CI's `GPG_PRIVATE_KEY`; keep them synchronized during key rotation.

The build workflow's path filter covers the app directories, `aiextra.flatpakrepo`, and `build.yml`. README-only or update-workflow-only changes do not trigger a build automatically.
