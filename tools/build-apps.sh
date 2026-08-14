#!/usr/bin/env bash
#
# build-apps.sh
# Dynamically discovers and builds all Flatpak applications into a shared OSTree repo.
#
# Environment variables:
#   REPO_DIR        - OSTree repository directory (default: repo)
#   GPG_KEY_ID      - Optional GPG key ID for signing commits
#   GNUPGHOME       - Optional GPG home directory
#   FLATPAK_BUILDER - flatpak-builder binary override (default: flatpak-builder)
#   GITHUB_OUTPUT   - GitHub Actions output file path (if running in CI)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

source "${SCRIPT_DIR}/manifest-common.sh"

REPO_DIR="${REPO_DIR:-repo}"
BUILDER="${FLATPAK_BUILDER:-flatpak-builder}"

manifests=()
total_count=0
load_application_manifests "${REPO_ROOT}" "to build" manifests total_count

successful_apps=()
failed_apps=()

for manifest in "${manifests[@]}"; do
  app_id="$(manifest_app_id "${manifest}")"
  build_dir="build-${app_id}"

  echo "=================================================="
  echo "Building application: ${app_id} (${manifest})"
  echo "=================================================="

  cmd=( "${BUILDER}" --force-clean --disable-rofiles-fuse --repo="${REPO_DIR}" )
  if [[ -n "${GPG_KEY_ID:-}" && -n "${GNUPGHOME:-}" ]]; then
    cmd+=( --gpg-sign="${GPG_KEY_ID}" --gpg-homedir="${GNUPGHOME}" )
  fi
  cmd+=( "${build_dir}" "${manifest}" )

  # Group output on GitHub Actions
  echo "::group::Building ${app_id}"

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

# Summary output
echo "=================================================="
echo "Build Summary:"
echo "  Total:      ${total_count}"
echo "  Successful: ${#successful_apps[@]} (${successful_apps[*]:-none})"
echo "  Failed:     ${#failed_apps[@]} (${failed_apps[*]:-none})"
echo "=================================================="

# Set step outputs for GitHub Actions if GITHUB_OUTPUT is set
if [[ -n "${GITHUB_OUTPUT:-}" && -f "${GITHUB_OUTPUT}" ]]; then
  echo "successful_apps=${successful_apps[*]:-}" >> "${GITHUB_OUTPUT}"
  echo "failed_apps=${failed_apps[*]:-}" >> "${GITHUB_OUTPUT}"
  echo "success_count=${#successful_apps[@]}" >> "${GITHUB_OUTPUT}"
  echo "failure_count=${#failed_apps[@]}" >> "${GITHUB_OUTPUT}"
  echo "total_count=${total_count}" >> "${GITHUB_OUTPUT}"
fi

# Exit with error if any application failed to build
if [[ "${#failed_apps[@]}" -gt 0 ]]; then
  exit 1
fi
