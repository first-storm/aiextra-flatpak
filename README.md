# aiextra-flatpak

> [!NOTE]
> **Relationship to Flathub & Proof of Concept**
>
> This repository provides independently maintained Flatpak wrappers and serves as a reference proof of concept (PoC). In accordance with [Flathub's Generative AI policy](https://docs.flathub.org/docs/for-app-authors/requirements), manifests from this repository are not submitted to Flathub as-is. You are welcome to reference or adapt anything here for your own Flathub submissions under the MIT License.

Unofficial Flatpak packaging for AI desktop apps, served from this repo's
GitHub Pages.

The app binaries aren't here. The manifests use Flatpak's [`extra-data` source
type](https://docs.flatpak.org/en/latest/module-sources.html#extra-data), so
`flatpak install` downloads each app on your machine, from its own upstream
servers (an apt repo or a releases API, depending on what the app publishes),
and verifies it against the sha256 in the manifest.
This repo is only the wrapper: desktop file, icons, sandbox permissions,
launcher.

## Apps

| App | ID |
| --- | --- |
| ChatGPT Desktop | `com.openai.ChatGPT` |
| Claude Desktop | `com.anthropic.Claude` |
| [ZCode](docs/zcode-host-command-hooks.md) | `ai.z.ZCode` |

## Install

```sh
flatpak remote-add --if-not-exists aiextra https://first-storm.github.io/aiextra-flatpak/aiextra.flatpakrepo
flatpak install aiextra <app-id>
```

Pick an ID from the table above; `flatpak install` also takes several at once.
Published builds cover both x86_64 and aarch64, and it picks the ref matching
your machine automatically.

## Signing

CI signs every OSTree commit and the repo summary, and `aiextra.flatpakrepo`
embeds the public key, so `remote-add` turns verification on by itself.
Fingerprint `01C7 6F3F 9B96 23D7 5ECA F346 F735 39F5 C33B 8E12`, armored copy
in [`keys/`](https://github.com/first-storm/aiextra-flatpak/blob/main/keys/aiextra-flatpak.asc).

If you added the remote before signing existed, your local config has
`gpg-verify=false` cached and re-fetching the `.flatpakrepo` won't change it.
Re-add the remote:

```sh
flatpak remote-delete aiextra
flatpak remote-add aiextra https://first-storm.github.io/aiextra-flatpak/aiextra.flatpakrepo
```

## Updates

A job checks all application manifests' upstream sources every 6 hours with
[flatpak-external-data-checker](https://github.com/flathub/flatpak-external-data-checker).
New upstream builds and wrapper changes both reach you through
`flatpak update`.

All packaged apps run under [zypak](https://github.com/refi64/zypak), from
`org.electronjs.Electron2.BaseApp`, so Chromium's sandbox works inside the
Flatpak sandbox. The files under `.github/workflows/` and `tools/` are
commented if you want the rest.
