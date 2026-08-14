#!/usr/bin/env bash
#
# build-apps.sh
# Dynamically discovers and builds all Flatpak applications into a shared OSTree repo.
#
# Environment variables:
#   GPG_KEY_ID    - Optional GPG key ID for signing commits
#   GNUPGHOME     - Optional GPG home directory
#   GITHUB_OUTPUT - GitHub Actions output file path (if running in CI)
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

manifest_list="$(tools/discover-manifests.sh)"
mapfile -t manifests <<< "${manifest_list}"

successful_apps=()
failed_apps=()

for manifest in "${manifests[@]}"; do
  app_id="${manifest%/*}"
  app_id="${app_id##*/}"

  # Groups the output on GitHub Actions, plain header everywhere else.
  echo "::group::Building ${app_id} (${manifest})"

  cmd=( flatpak-builder --force-clean --disable-rofiles-fuse --repo=repo )
  if [[ -n "${GPG_KEY_ID:-}" && -n "${GNUPGHOME:-}" ]]; then
    cmd+=( --gpg-sign="${GPG_KEY_ID}" --gpg-homedir="${GNUPGHOME}" )
  fi
  cmd+=( "build-${app_id}" "${manifest}" )

  if "${cmd[@]}"; then
    echo "Build succeeded: ${app_id}"
    successful_apps+=("${app_id}")
  else
    echo "Build failed: ${app_id}" >&2
    failed_apps+=("${app_id}")
  fi

  echo "::endgroup::"
  echo ""
done

echo "=================================================="
echo "Build Summary:"
echo "  Total:      ${#manifests[@]}"
echo "  Successful: ${#successful_apps[@]} (${successful_apps[*]:-none})"
echo "  Failed:     ${#failed_apps[@]} (${failed_apps[*]:-none})"
echo "=================================================="

if [[ -f "${GITHUB_OUTPUT:-}" ]]; then
  {
    echo "success_count=${#successful_apps[@]}"
    echo "failure_count=${#failed_apps[@]}"
    echo "failed_apps=${failed_apps[*]:-}"
  } >> "${GITHUB_OUTPUT}"
fi

# Exit with error if any application failed to build
if [[ "${#failed_apps[@]}" -gt 0 ]]; then
  exit 1
fi
