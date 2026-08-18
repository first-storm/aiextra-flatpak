#!/usr/bin/env bash
#
# build-apps.sh
# Dynamically discovers and builds Flatpak applications into a shared OSTree repo.
# If arguments are provided, only specified applications are built.
#
# Environment variables:
#   GPG_KEY_ID    - Optional GPG key ID for signing commits
#   GNUPGHOME     - Optional GPG home directory
#   GITHUB_OUTPUT - GitHub Actions output file path (if running in CI)
#   TARGET_ARCH   - Optional expected native architecture (CI safety check)
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

manifest_list="$(tools/discover-manifests.sh "$@")"
mapfile -t manifests <<<"${manifest_list}"
current_arch="$(flatpak --default-arch)"
if [[ -n "${TARGET_ARCH:-}" && "${TARGET_ARCH}" != "${current_arch}" ]]; then
    echo "Error: Runner architecture is ${current_arch}, expected ${TARGET_ARCH}" >&2
    exit 1
fi

successful_apps=()
skipped_apps=()
failed_apps=()

remove_unsupported_refs() {
    local app_id="$1"
    local arch_file="$2"
    local arch
    local prefix
    local refs

    for arch in x86_64 aarch64; do
        grep -Fxq "${arch}" "${arch_file}" && continue

        prefix="app/${app_id}/${arch}"
        refs="$(ostree refs --repo=repo --list "${prefix}")"
        [[ -n "${refs}" ]] || continue

        echo "Removing unsupported published refs:"
        printf '  %s\n' "${refs}"
        ostree refs --repo=repo --delete "${prefix}"
    done
}

for manifest in "${manifests[@]}"; do
    app_id="${manifest%/*}"
    app_id="${app_id##*/}"
    arch_file="${manifest%/*}/architectures"

    # Groups the output on GitHub Actions, plain header everywhere else.
    echo "::group::Building ${app_id} for ${current_arch} (${manifest})"

    if ! grep -Fxq "${current_arch}" "${arch_file}"; then
        echo "Skipping ${app_id}: ${current_arch} is not configured in ${arch_file}"
        skipped_apps+=("${app_id}")
        echo "::endgroup::"
        echo ""
        continue
    fi

    cmd=(flatpak-builder --force-clean --disable-rofiles-fuse --repo=repo)
    if [[ -n "${GPG_KEY_ID:-}" && -n "${GNUPGHOME:-}" ]]; then
        cmd+=(--gpg-sign="${GPG_KEY_ID}" --gpg-homedir="${GNUPGHOME}")
    fi
    cmd+=("build-${app_id}" "${manifest}")

    if "${cmd[@]}" && remove_unsupported_refs "${app_id}" "${arch_file}"; then
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
echo "  Targeted:   ${#manifests[@]}"
echo "  Successful: ${#successful_apps[@]} (${successful_apps[*]:-none})"
echo "  Skipped:    ${#skipped_apps[@]} (${skipped_apps[*]:-none})"
echo "  Failed:     ${#failed_apps[@]} (${failed_apps[*]:-none})"
echo "=================================================="

if [[ -f "${GITHUB_OUTPUT:-}" ]]; then
    {
        echo "success_count=${#successful_apps[@]}"
        echo "failure_count=${#failed_apps[@]}"
        echo "failed_apps=${failed_apps[*]:-}"
    } >>"${GITHUB_OUTPUT}"
fi

# Exit with error if any application failed to build
if [[ "${#failed_apps[@]}" -gt 0 ]]; then
    exit 1
fi
