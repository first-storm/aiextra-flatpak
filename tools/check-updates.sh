#!/usr/bin/env bash
#
# check-updates.sh
# Dynamically discovers all Flatpak application manifests and runs
# flatpak-external-data-checker on each of them.
#
# Environment variables:
#   CHECKER_IMAGE - Docker image for the checker (default: ghcr.io/flathub/flatpak-external-data-checker:latest)
#   CHECKER_CMD   - Custom command override (e.g. for testing)
#   GITHUB_OUTPUT - GitHub Actions output file path (if running in CI)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

source "${SCRIPT_DIR}/manifest-common.sh"

CHECKER_IMAGE="${CHECKER_IMAGE:-ghcr.io/flathub/flatpak-external-data-checker:latest}"

manifests=()
total_count=0
load_application_manifests "${REPO_ROOT}" "for update checking" manifests total_count

failed_apps=()
updated_apps=()
initial_head="$(git rev-parse HEAD)"

for manifest in "${manifests[@]}"; do
  app_id="$(manifest_app_id "${manifest}")"
  head_before="$(git rev-parse HEAD)"

  echo "=================================================="
  echo "Checking updates for: ${app_id} (${manifest})"
  echo "=================================================="

  echo "::group::Checking ${app_id}"

  check_success=true
  if [[ -n "${CHECKER_CMD:-}" ]]; then
    if ! eval "${CHECKER_CMD} --update --commit-to-current-branch \"${manifest}\""; then
      check_success=false
    fi
  elif command -v flatpak-external-data-checker >/dev/null 2>&1; then
    if ! flatpak-external-data-checker --update --commit-to-current-branch "${manifest}"; then
      check_success=false
    fi
  else
    # Fallback to docker container
    docker_cmd=(
      docker run --rm
      -v "${REPO_ROOT}:/repo"
      -w /repo
      -e GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-flatpak-external-data-checker}"
      -e GIT_COMMITTER_NAME="${GIT_COMMITTER_NAME:-flatpak-external-data-checker}"
      -e GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"
      -e GIT_COMMITTER_EMAIL="${GIT_COMMITTER_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"
      "${CHECKER_IMAGE}"
      --update --commit-to-current-branch "${manifest}"
    )
    if ! "${docker_cmd[@]}"; then
      check_success=false
    fi
  fi

  if ${check_success}; then
    echo "Check finished for ${app_id}"
    head_after="$(git rev-parse HEAD)"
    if [[ "${head_before}" != "${head_after}" ]]; then
      echo "Update commit created for ${app_id}"
      updated_apps+=("${app_id}")
    fi
  else
    echo "Check failed for ${app_id}" >&2
    failed_apps+=("${app_id}")
    # Clean up any uncommitted dirty working tree changes from the failed run without losing prior commits
    git reset --hard "${head_before}" >/dev/null 2>&1 || true
  fi

  echo "::endgroup::"
  echo ""
done

# Summary output
current_head="$(git rev-parse HEAD)"
has_updates=false
if [[ "${initial_head}" != "${current_head}" ]]; then
  has_updates=true
fi

echo "=================================================="
echo "Update Check Summary:"
echo "  Total checked: ${total_count}"
echo "  Updated apps:  ${#updated_apps[@]} (${updated_apps[*]:-none})"
echo "  Failed checks: ${#failed_apps[@]} (${failed_apps[*]:-none})"
echo "  Has updates:   ${has_updates}"
echo "=================================================="

# Set step outputs for GitHub Actions if GITHUB_OUTPUT is set
if [[ -n "${GITHUB_OUTPUT:-}" && -f "${GITHUB_OUTPUT}" ]]; then
  echo "failed_apps=${failed_apps[*]:-}" >> "${GITHUB_OUTPUT}"
  echo "failure_count=${#failed_apps[@]}" >> "${GITHUB_OUTPUT}"
  echo "updated_apps=${updated_apps[*]:-}" >> "${GITHUB_OUTPUT}"
  echo "has_updates=${has_updates}" >> "${GITHUB_OUTPUT}"
  echo "total_count=${total_count}" >> "${GITHUB_OUTPUT}"
fi

# Exit with error if any checker failed
if [[ "${#failed_apps[@]}" -gt 0 ]]; then
  exit 1
fi
