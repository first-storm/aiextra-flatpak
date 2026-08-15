#!/usr/bin/env bash
#
# discover-manifests.sh
# Discovers valid Flatpak application manifests in the repository.
#
# Searches in manifests/<app-id>/<app-id>.{yml,yaml}.
# If arguments are provided (app IDs, manifest paths, or directories),
# only matching manifests are resolved and validated.
#
# Output: relative manifest paths (e.g. "manifests/com.openai.ChatGPT/com.openai.ChatGPT.yml"),
# sorted alphabetically, one per line.
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Normalize arguments: split on whitespace and commas, deduplicate while preserving order
targets=()
declare -A seen_targets=()

if [[ $# -gt 0 && "$1" != "all" ]]; then
    for arg in "$@"; do
        # Split arg by whitespace or commas
        IFS=', ' read -r -a tokens <<<"${arg}"
        for token in "${tokens[@]}"; do
            [[ -n "${token}" ]] || continue

            # Normalize token to app ID
            clean="${token#"${REPO_ROOT}/"}"
            clean="${clean#./}"
            clean="${clean#manifests/}"
            clean="${clean%/}"
            app_id="${clean%%/*}"
            if [[ "${app_id}" == *.yml ]]; then
                app_id="${app_id%.yml}"
            elif [[ "${app_id}" == *.yaml ]]; then
                app_id="${app_id%.yaml}"
            fi

            [[ -n "${app_id}" ]] || continue

            if [[ -z "${seen_targets[${app_id}]:-}" ]]; then
                seen_targets["${app_id}"]=1
                targets+=("${app_id}")
            fi
        done
    done
fi

manifests=()

if [[ ${#targets[@]} -gt 0 ]]; then
    for app_id in "${targets[@]}"; do
        entry="${REPO_ROOT}/manifests/${app_id}/"
        if [[ ! -d "${entry}" ]]; then
            echo "Error: Manifest directory not found for app '${app_id}' (${entry})" >&2
            exit 1
        fi

        found_manifest=""
        for manifest in "${entry}${app_id}.yml" "${entry}${app_id}.yaml"; do
            [[ -f "${manifest}" ]] || continue

            declared="$(awk '$1 == "app-id:" { print $2; exit }' "${manifest}" | tr -d "\"'")"
            if [[ -n "${declared}" && "${declared}" != "${app_id}" ]]; then
                echo "Error: ${manifest} declares app-id '${declared}', expected '${app_id}'" >&2
                exit 1
            fi

            found_manifest="${manifest#"${REPO_ROOT}/"}"
            break # .yml wins if both extensions somehow exist
        done

        if [[ -z "${found_manifest}" ]]; then
            echo "Error: No application manifest found for '${app_id}' in ${entry}" >&2
            exit 1
        fi

        manifests+=("${found_manifest}")
    done
else
    for entry in "${REPO_ROOT}"/manifests/*/; do
        app_id="$(basename "${entry}")"

        for manifest in "${entry}${app_id}.yml" "${entry}${app_id}.yaml"; do
            [[ -f "${manifest}" ]] || continue

            # Catch the classic copy-paste mistake when adding an app: the manifest
            # still declares the app ID it was copied from.
            declared="$(awk '$1 == "app-id:" { print $2; exit }' "${manifest}" | tr -d "\"'")"
            if [[ -n "${declared}" && "${declared}" != "${app_id}" ]]; then
                echo "Error: ${manifest} declares app-id '${declared}', expected '${app_id}'" >&2
                exit 1
            fi

            manifests+=("${manifest#"${REPO_ROOT}/"}")
            break # .yml wins if both extensions somehow exist
        done
    done
fi

# Also covers a missing manifests/ directory: the glob then matches nothing.
if [[ ${#manifests[@]} -eq 0 ]]; then
    echo "Error: No application manifests found under ${REPO_ROOT}/manifests" >&2
    exit 1
fi

# Output manifest paths sorted alphabetically
printf '%s\n' "${manifests[@]}" | sort -u
