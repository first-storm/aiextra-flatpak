#!/usr/bin/env bash
#
# check-updates.sh
# Dynamically discovers all Flatpak application manifests and runs
# flatpak-external-data-checker on each of them.
#
# Environment variables:
#   GITHUB_OUTPUT - GitHub Actions output file path (if running in CI)
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

manifest_list="$(tools/discover-manifests.sh)"
mapfile -t manifests <<<"${manifest_list}"

# Prefer a locally installed checker; otherwise run the Flathub image, which is
# what CI does. The checker commits, so the container needs a git identity.
if command -v flatpak-external-data-checker >/dev/null 2>&1; then
    checker=(flatpak-external-data-checker)
else
    checker=(
        docker run --rm
        -v "${REPO_ROOT}:/repo"
        -w /repo
        -e GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-flatpak-external-data-checker}"
        -e GIT_COMMITTER_NAME="${GIT_COMMITTER_NAME:-flatpak-external-data-checker}"
        -e GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"
        -e GIT_COMMITTER_EMAIL="${GIT_COMMITTER_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"
        ghcr.io/flathub/flatpak-external-data-checker:latest
    )
fi

failed_apps=()
updated_apps=()

for manifest in "${manifests[@]}"; do
    app_id="${manifest%/*}"
    app_id="${app_id##*/}"
    head_before="$(git rev-parse HEAD)"

    echo "::group::Checking ${app_id} (${manifest})"

    if "${checker[@]}" --update --commit-to-current-branch "${manifest}"; then
        echo "Check finished for ${app_id}"
        if [[ "${head_before}" != "$(git rev-parse HEAD)" ]]; then
            echo "Update commit created for ${app_id}"
            updated_apps+=("${app_id}")
        fi
    else
        echo "Check failed for ${app_id}" >&2
        failed_apps+=("${app_id}")
        # Drop the failed run's dirty working tree so the next checker's commit
        # doesn't sweep up its partial edits. Prior commits are kept.
        git reset --hard "${head_before}" >/dev/null 2>&1 || true
    fi

    echo "::endgroup::"
    echo ""
done

echo "=================================================="
echo "Update Check Summary:"
echo "  Total checked: ${#manifests[@]}"
echo "  Updated apps:  ${#updated_apps[@]} (${updated_apps[*]:-none})"
echo "  Failed checks: ${#failed_apps[@]} (${failed_apps[*]:-none})"
echo "=================================================="

if [[ -f "${GITHUB_OUTPUT:-}" ]]; then
    {
        echo "failure_count=${#failed_apps[@]}"
        echo "failed_apps=${failed_apps[*]:-}"
    } >>"${GITHUB_OUTPUT}"
fi

# Exit with error if any checker failed
if [[ "${#failed_apps[@]}" -gt 0 ]]; then
    exit 1
fi
