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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${1:-"${SCRIPT_DIR}/.."}" && pwd)"

MANIFESTS_DIR="${REPO_ROOT}/manifests"
if [[ ! -d "${MANIFESTS_DIR}" ]]; then
  echo "Error: Missing manifests directory in ${REPO_ROOT}" >&2
  exit 1
fi

manifests=()

for entry in "${MANIFESTS_DIR}"/*; do
  [[ -d "${entry}" ]] || continue

  dirname="$(basename "${entry}")"
  yml_file="${entry}/${dirname}.yml"
  yaml_file="${entry}/${dirname}.yaml"

  has_yml=false
  has_yaml=false
  [[ -f "${yml_file}" ]] && has_yml=true
  [[ -f "${yaml_file}" ]] && has_yaml=true

  if ${has_yml} && ${has_yaml}; then
    echo "Error: Duplicate manifests found for ${dirname} (${dirname}.yml and ${dirname}.yaml)" >&2
    exit 1
  fi

  manifest=""
  if ${has_yml}; then
    manifest="${yml_file}"
  elif ${has_yaml}; then
    manifest="${yaml_file}"
  else
    continue
  fi

  # Validate that app-id matches directory name if app-id is present in manifest
  app_id="$(awk '$1 == "app-id:" { print $2; exit }' "${manifest}" | tr -d '"' | tr -d "'")"
  if [[ -n "${app_id}" && "${app_id}" != "${dirname}" ]]; then
    echo "Error: Manifest ${manifest} specifies app-id '${app_id}', expected '${dirname}'" >&2
    exit 1
  fi

  # Store relative path to REPO_ROOT
  manifest_rel="${manifest#"${REPO_ROOT}/"}"
  manifests+=("${manifest_rel}")
done

if [[ ${#manifests[@]} -eq 0 ]]; then
  echo "Error: No valid Flatpak manifests found in ${REPO_ROOT}" >&2
  exit 1
fi

# Output sorted manifest paths
printf '%s\n' "${manifests[@]}" | sort
