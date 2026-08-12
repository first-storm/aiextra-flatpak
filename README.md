# aiextra-flatpak

Unofficial Flatpak packaging for **ChatGPT Desktop** (OpenAI) and **Claude
Desktop** (Anthropic, Linux beta), distributed from this repo via GitHub
Pages — no Flathub submission.

The proprietary app binaries themselves are **not** stored in this repo or
in the published Flatpak repo. Both manifests use Flatpak's [`extra-data`
source type](https://docs.flatpak.org/en/latest/module-sources.html#extra-data):
when you `flatpak install`, your own Flatpak client downloads the app
directly from OpenAI's / Anthropic's official apt repositories and verifies
it against the checksum recorded in the manifest. This repo only ships the
small Flatpak wrapper (desktop file, icons, sandbox permissions, launcher
script) around that download.

## Install

```sh
flatpak remote-add --if-not-exists aiextra https://first-storm.github.io/aiextra-flatpak/aiextra.flatpakrepo
flatpak install aiextra com.openai.ChatGPT com.anthropic.Claude
```

Then launch with `flatpak run com.openai.ChatGPT` / `flatpak run
com.anthropic.Claude`, or from your application launcher.

This repo is **unsigned** (no GPG key) — integrity relies on HTTPS transport
plus the per-source sha256 checksum baked into each manifest, the same as
the sha256 published in OpenAI's/Anthropic's own apt repo indexes.

## Updating

Regular `flatpak update` picks up new wrapper releases (permission changes,
icon/desktop-file fixes, etc). The upstream app version itself is checked
automatically — see below — so a `flatpak update` after a new upstream
release also fetches the new app build.

## How auto-updates work

- `.github/workflows/update-check.yml` runs
  [`flatpak-external-data-checker`](https://github.com/flathub/flatpak-external-data-checker)
  (the same tool Flathub uses) every 6 hours against both manifests. Each
  manifest's `extra-data` sources carry `x-checker-data` of type
  `debian-repo`, pointing at OpenAI's/Anthropic's apt repo
  (package name, repo root, dist, component) — the checker resolves the
  newest published version straight from each repo's `Packages` index and
  rewrites the `url`/`sha256`/`size` in place, committing directly to `main`.
- `.github/workflows/build.yml` runs on every push to `main` that touches a
  manifest, rebuilds both apps into a shared OSTree repo with
  `flatpak-builder`, and publishes the result to the `gh-pages` branch
  (served by GitHub Pages). Because `extra-data` is only *resolved* at
  install time by each user's own Flatpak client, this build step never
  downloads the multi-hundred-MB app binaries itself — it stays fast and the
  published repo stays small.
- A push that only touches one app's manifest still rebuilds both (the
  `paths:` filter only decides whether the workflow runs at all, not which
  steps run), but the two builds are independent: each uses
  `continue-on-error`, and the job checks out the currently-published
  `gh-pages` OSTree repo as its starting point before building, so
  `flatpak-builder` only adds/updates the ref for the app(s) that built
  successfully. If, say, Claude's manifest breaks, ChatGPT's update still
  publishes normally and Claude's ref stays pinned to its last successful
  build — a broken manifest for one app never blocks the other's release.
  The workflow run is still marked failed (and will show up as a red run /
  trigger notifications) so the break doesn't go unnoticed.

## Known limitations

- Claude Desktop's Linux beta does not yet support the Cowork /
  computer-use sandbox (per
  [Anthropic's own docs](https://code.claude.com/docs/en/desktop-linux)), so
  no `--device=kvm` or similar permission is requested for it here. If that
  feature ships later it may need a manifest update.
- Both apps run under [zypak](https://github.com/refi64/zypak) (via
  `org.electronjs.Electron2.BaseApp`) for Chromium sandbox compatibility
  inside the Flatpak sandbox.

## Repo layout

- `com.openai.ChatGPT/` — ChatGPT Desktop manifest, desktop file, metainfo, launcher.
- `com.anthropic.Claude/` — Claude Desktop manifest, desktop file, metainfo, launcher.
- `icons/` — hicolor-theme icon sets for both apps, extracted from the
  upstream `.deb` packages.
- `aiextra.flatpakrepo` — the remote definition users add with `flatpak
  remote-add`.
