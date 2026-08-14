#!/usr/bin/env bash
#
# discover-manifests.sh
# Discovers valid Flatpak application manifests in the repository.
#
# Searches in manifests/<app-id>/<app-id>.{yml,yaml}.
#
# Output: relative manifest paths (e.g. "manifests/com.openai.ChatGPT/com.openai.ChatGPT.yml"),
# sorted alphabetically, one per line.
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

manifests=()

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

# Also covers a missing manifests/ directory: the glob then matches nothing.
if [[ ${#manifests[@]} -eq 0 ]]; then
    echo "Error: No application manifests found under ${REPO_ROOT}/manifests" >&2
    exit 1
fi

# Glob expansion is already sorted.
printf '%s\n' "${manifests[@]}"
