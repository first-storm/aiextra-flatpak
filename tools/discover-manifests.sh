#!/usr/bin/env bash
#
# discover-manifests.sh
# Discovers valid Flatpak application manifests in the repository.
#
# Searches in manifests/<app-id>/<app-id>.{yml,yaml}.
# If arguments are provided (app IDs, manifest paths, or directories),
# only matching manifests are resolved and validated.
# Each application directory must also contain an `architectures` file with
# one or both supported Flatpak architectures, one per line.
#
# Output: relative manifest paths (e.g. "manifests/com.openai.ChatGPT/com.openai.ChatGPT.yml"),
# sorted alphabetically, one per line.
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

validate_architectures() {
    local app_id="$1"
    local entry="$2"
    local arch_file="${entry}architectures"
    local arch
    local -a arches=()
    local -A seen_arches=()

    if [[ ! -f "${arch_file}" ]]; then
        echo "Error: Missing architecture config for '${app_id}' (${arch_file})" >&2
        exit 1
    fi

    mapfile -t arches <"${arch_file}"
    if [[ ${#arches[@]} -eq 0 ]]; then
        echo "Error: Architecture config for '${app_id}' is empty (${arch_file})" >&2
        exit 1
    fi

    for arch in "${arches[@]}"; do
        case "${arch}" in
            x86_64 | aarch64) ;;
            *)
                echo "Error: Unsupported architecture '${arch}' for '${app_id}' (${arch_file})" >&2
                exit 1
                ;;
        esac

        if [[ -n "${seen_arches[${arch}]:-}" ]]; then
            echo "Error: Duplicate architecture '${arch}' for '${app_id}' (${arch_file})" >&2
            exit 1
        fi
        seen_arches["${arch}"]=1
    done
}

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

        validate_architectures "${app_id}" "${entry}"
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

            validate_architectures "${app_id}" "${entry}"
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
