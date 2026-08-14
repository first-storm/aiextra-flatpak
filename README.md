# aiextra-flatpak

Unofficial Flatpak packaging for ChatGPT Desktop, Claude Desktop, and ZCode,
served from this repo's GitHub Pages. Not on Flathub.

The app binaries aren't here. The manifests use Flatpak's [`extra-data` source
type](https://docs.flatpak.org/en/latest/module-sources.html#extra-data), so
`flatpak install` downloads each app on your machine, from the vendors' own
servers (OpenAI and Anthropic via apt repos, Z.AI via its releases API), and
verifies it against the sha256 in the manifest.
This repo is only the wrapper: desktop file, icons, sandbox permissions,
launcher.

## Install

```sh
flatpak remote-add --if-not-exists aiextra https://first-storm.github.io/aiextra-flatpak/aiextra.flatpakrepo
flatpak install aiextra com.openai.ChatGPT com.anthropic.Claude ai.z.ZCode
```

Published builds cover both x86_64 and aarch64; `flatpak install` picks the
ref matching your machine automatically.

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

A job checks all three apps' upstream sources every 6 hours with
[flatpak-external-data-checker](https://github.com/flathub/flatpak-external-data-checker).
New upstream builds and wrapper changes both reach you through
`flatpak update`.

All three apps run under [zypak](https://github.com/refi64/zypak), from
`org.electronjs.Electron2.BaseApp`, so Chromium's sandbox works inside the
Flatpak sandbox. Claude Desktop for Linux is still a beta. The files under
`.github/workflows/` are commented if you want the rest.
