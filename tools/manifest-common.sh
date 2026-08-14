#!/usr/bin/env bash

load_application_manifests() {
  local repo_root="$1"
  local purpose="$2"
  local manifests_name="$3"
  local total_count_name="$4"
  local manifest_output
  local -n loaded_manifests="${manifests_name}"
  local -n loaded_total_count="${total_count_name}"

  loaded_manifests=()
  loaded_total_count=0

  if ! manifest_output="$("${repo_root}/tools/discover-manifests.sh" "${repo_root}")"; then
    return 1
  fi

  if [[ -z "${manifest_output}" ]]; then
    echo "Error: No application manifests found ${purpose}." >&2
    return 1
  fi

  mapfile -t loaded_manifests <<< "${manifest_output}"
  loaded_total_count="${#loaded_manifests[@]}"

  printf 'Discovered %s application manifest(s) %s:\n' "${loaded_total_count}" "${purpose}"
  printf '  - %s\n' "${loaded_manifests[@]}"
  printf '\n'
}

manifest_app_id() {
  local manifest_dir="${1%/*}"
  printf '%s\n' "${manifest_dir##*/}"
}
