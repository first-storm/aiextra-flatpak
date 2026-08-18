#!/usr/bin/env bash
#
# determine-target-apps.sh
# Determines which Flatpak applications should be built based on workflow inputs
# or git changes.
#
# Environment variables:
#   INPUT_APPS    - Optional space- or comma-separated target app IDs from workflow inputs
#   EVENT_NAME    - GitHub event name (e.g. "push", "workflow_dispatch")
#   BEFORE_SHA    - Git commit SHA before the push event
#   GITHUB_OUTPUT - GitHub Actions output file path (if running in CI)
#
# Output: space-separated app IDs to build (or empty for all apps), printed to stdout.
# In CI, writes both `apps` and a native-runner `matrix` to GITHUB_OUTPUT.
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

emit_plan() {
    local target_apps="${1:-}"
    local manifest_list
    local manifest
    local app_id
    local arch
    local has_x86_64=false
    local has_aarch64=false
    local matrix
    local output_apps=""
    local -a resolved_apps=()

    if [[ -n "${target_apps}" ]]; then
        manifest_list="$(tools/discover-manifests.sh "${target_apps}")"
    else
        manifest_list="$(tools/discover-manifests.sh)"
    fi

    while IFS= read -r manifest; do
        app_id="${manifest%/*}"
        resolved_apps+=("${app_id##*/}")
        while IFS= read -r arch; do
            case "${arch}" in
                x86_64) has_x86_64=true ;;
                aarch64) has_aarch64=true ;;
            esac
        done <"${manifest%/*}/architectures"
    done <<<"${manifest_list}"

    if [[ -n "${target_apps}" ]]; then
        output_apps="${resolved_apps[*]}"
    fi

    if [[ "${has_x86_64}" = true && "${has_aarch64}" = true ]]; then
        matrix='{"include":[{"arch":"x86_64","runner":"ubuntu-latest"},{"arch":"aarch64","runner":"ubuntu-24.04-arm"}]}'
    elif [[ "${has_x86_64}" = true ]]; then
        matrix='{"include":[{"arch":"x86_64","runner":"ubuntu-latest"}]}'
    elif [[ "${has_aarch64}" = true ]]; then
        matrix='{"include":[{"arch":"aarch64","runner":"ubuntu-24.04-arm"}]}'
    else
        echo "Error: No configured architectures found for target applications" >&2
        exit 1
    fi

    if [[ -f "${GITHUB_OUTPUT:-}" ]]; then
        {
            echo "apps=${output_apps}"
            echo "matrix=${matrix}"
        } >>"${GITHUB_OUTPUT}"
    fi
    echo "${output_apps}"
}

# If explicit targets are passed as CLI args or INPUT_APPS, use them
target_input="${*:-${INPUT_APPS:-}}"

if [[ -n "${target_input}" && "${target_input}" != "all" ]]; then
    echo "Target apps explicitly specified: ${target_input}" >&2
    emit_plan "${target_input}"
    exit 0
fi

event_name="${EVENT_NAME:-}"

if [[ "${event_name}" = "push" || -z "${event_name}" ]]; then
    before_sha="${BEFORE_SHA:-}"
    range=""

    if [[ -n "${before_sha}" && "${before_sha}" != "0000000000000000000000000000000000000000" ]] && git rev-parse --verify "${before_sha}^{commit}" >/dev/null 2>&1; then
        range="${before_sha}..HEAD"
    elif git rev-parse --verify HEAD~1 >/dev/null 2>&1; then
        range="HEAD~1..HEAD"
    fi

    if [[ -n "${range}" ]]; then
        changed_files="$(git diff --name-only "${range}")"
        echo "Changed files in ${range}:" >&2
        echo "${changed_files}" >&2

        build_all=false
        app_ids=()

        while IFS= read -r file; do
            [[ -z "${file}" ]] && continue
            if [[ "${file}" =~ ^manifests/([^/]+)/ ]]; then
                app_ids+=("${BASH_REMATCH[1]}")
            else
                echo "Change outside manifests detected (${file}); will build all apps." >&2
                build_all=true
                break
            fi
        done <<<"${changed_files}"

        if [[ "${build_all}" = false && ${#app_ids[@]} -gt 0 ]]; then
            mapfile -t unique_apps < <(printf '%s\n' "${app_ids[@]}" | sort -u)
            echo "Target apps from git diff: ${unique_apps[*]}" >&2
            emit_plan "${unique_apps[*]}"
            exit 0
        fi
    fi
fi

echo "Building all applications." >&2
emit_plan ""
