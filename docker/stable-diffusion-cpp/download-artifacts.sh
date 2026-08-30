#!/usr/bin/env bash

# Shared download behavior for PreFer's generated Audio and Image artifact
# maps. This file is sourced by an entrypoint, so it intentionally does not
# change the caller's shell options.

prefer_artifact_stat_signature() {
  stat -c '%d:%i:%s' "$1"
}

prefer_artifact_marker_path() {
  local artifact_id="$1"
  local models_dir="${PREFER_MODELS_DIR:-/models}"
  printf '%s\n' "$models_dir/.prefer-cache/downloads-v2/verified/$artifact_id.complete"
}

prefer_artifact_marker_matches() {
  local destination="$1"
  local expected_size="$2"
  local artifact_id="$3"
  local marker=""
  local schema=""
  local recorded_id=""
  local recorded_signature=""
  local extra=""
  local actual_signature=""
  local actual_size=""

  [ -f "$destination" ] || return 1
  if actual_size="$(stat -c '%s' "$destination")"; then
    :
  else
    return 1
  fi
  [ "$actual_size" = "$expected_size" ] || return 1
  marker="$(prefer_artifact_marker_path "$artifact_id")"
  [ -s "$marker" ] || return 1
  IFS=$'\t' read -r schema recorded_id recorded_signature extra < "$marker" || return 1
  [ "$schema" = "v1" ] || return 1
  [ "$recorded_id" = "$artifact_id" ] || return 1
  [ -z "$extra" ] || return 1
  if actual_signature="$(prefer_artifact_stat_signature "$destination")"; then
    :
  else
    return 1
  fi
  [ "$recorded_signature" = "$actual_signature" ] || return 1
  [ ! "$destination" -nt "$marker" ] || return 1
  return 0
}

prefer_artifact_sha_matches() {
  local path="$1"
  local expected_size="$2"
  local expected_sha256="$3"
  local actual_size=""
  local actual_sha256=""

  [ -f "$path" ] || return 1
  if actual_size="$(stat -c '%s' "$path")"; then
    :
  else
    return 1
  fi
  [ "$actual_size" = "$expected_size" ] || return 1
  if actual_sha256="$(sha256sum "$path")"; then
    :
  else
    return 1
  fi
  actual_sha256="${actual_sha256%% *}"
  [ "$actual_sha256" = "$expected_sha256" ] || return 1
  return 0
}

prefer_write_artifact_marker() {
  local destination="$1"
  local artifact_id="$2"
  local marker=""
  local marker_dir=""
  local temp_marker=""
  local signature=""
  local status=0

  marker="$(prefer_artifact_marker_path "$artifact_id")"
  marker_dir="${marker%/*}"
  if mkdir -p "$marker_dir"; then
    :
  else
    status=$?
    echo "[artifact-download] could not create marker directory: $marker_dir" >&2
    return "$status"
  fi
  if temp_marker="$(mktemp "$marker_dir/.$artifact_id.XXXXXX")"; then
    :
  else
    status=$?
    echo "[artifact-download] could not create temporary marker for $artifact_id" >&2
    return "$status"
  fi
  if signature="$(prefer_artifact_stat_signature "$destination")"; then
    :
  else
    status=$?
    rm -f "$temp_marker" || true
    echo "[artifact-download] could not stat published artifact for $artifact_id" >&2
    return "$status"
  fi
  if printf 'v1\t%s\t%s\n' "$artifact_id" "$signature" > "$temp_marker"; then
    :
  else
    status=$?
    rm -f "$temp_marker" || true
    echo "[artifact-download] could not write temporary marker for $artifact_id" >&2
    return "$status"
  fi
  if mv -f "$temp_marker" "$marker"; then
    return 0
  else
    status=$?
    rm -f "$temp_marker" || true
    echo "[artifact-download] could not publish marker for $artifact_id" >&2
    return "$status"
  fi
}

prefer_download_hf_artifact_locked() {
  local log_prefix="$1"
  local artifact_id="$2"
  local repo="$3"
  local revision="$4"
  local artifact_path="$5"
  local expected_size="$6"
  local expected_sha256="$7"
  local models_dir="${PREFER_MODELS_DIR:-/models}"
  local destination="$models_dir/$repo/$artifact_path"
  local staging_dir="$models_dir/.prefer-cache/downloads-v2/staging/$artifact_id"
  local staged_artifact="$staging_dir/$artifact_path"
  local destination_dir="${destination%/*}"
  local destination_size=""
  local status=0

  if mkdir -p "$destination_dir" "$staging_dir"; then
    :
  else
    status=$?
    echo "[$log_prefix] $repo/$artifact_path: could not create staging or destination directory" >&2
    return "$status"
  fi
  if prefer_artifact_marker_matches "$destination" "$expected_size" "$artifact_id"; then
    echo "[$log_prefix] $repo/$artifact_path: verified marker hit"
    return 0
  fi

  if [ -e "$destination" ]; then
    if destination_size="$(stat -c '%s' "$destination")"; then
      :
    else
      status=$?
      echo "[$log_prefix] $repo/$artifact_path: could not stat existing artifact" >&2
      return "$status"
    fi
    if [ -f "$destination" ] && [ "$destination_size" = "$expected_size" ]; then
      echo "[$log_prefix] $repo/$artifact_path: verifying existing artifact"
      if prefer_artifact_sha_matches "$destination" "$expected_size" "$expected_sha256"; then
        if prefer_write_artifact_marker "$destination" "$artifact_id"; then
          :
        else
          status=$?
          echo "[$log_prefix] $repo/$artifact_path: existing artifact verified but marker publication failed" >&2
          return "$status"
        fi
        echo "[$log_prefix] $repo/$artifact_path: existing artifact verified"
        return 0
      fi
      echo "[$log_prefix] $repo/$artifact_path: existing artifact failed SHA-256; downloading replacement" >&2
    else
      echo "[$log_prefix] $repo/$artifact_path: existing artifact has the wrong size or type; downloading replacement" >&2
    fi
  fi

  echo "[$log_prefix] $repo/$artifact_path: downloading pinned artifact"
  if hf download "$repo" "$artifact_path" --revision "$revision" --local-dir "$staging_dir"; then
    status=0
  else
    status=$?
    echo "[$log_prefix] $repo/$artifact_path: transfer failed with status $status; resumable state retained" >&2
    return "$status"
  fi

  if ! prefer_artifact_sha_matches "$staged_artifact" "$expected_size" "$expected_sha256"; then
    echo "[$log_prefix] $repo/$artifact_path: size or SHA-256 validation failed" >&2
    # hf completed this file, so it is not an interrupted transfer worth
    # retaining. Leave any separate *.incomplete state untouched.
    if rm -f "$staged_artifact"; then
      :
    else
      echo "[$log_prefix] $repo/$artifact_path: invalid completed staging file could not be removed" >&2
    fi
    return 1
  fi

  if mv -f "$staged_artifact" "$destination"; then
    :
  else
    status=$?
    echo "[$log_prefix] $repo/$artifact_path: atomic artifact publication failed; verified staging file retained" >&2
    return "$status"
  fi
  if prefer_write_artifact_marker "$destination" "$artifact_id"; then
    :
  else
    status=$?
    echo "[$log_prefix] $repo/$artifact_path: artifact published but marker publication failed" >&2
    return "$status"
  fi
  echo "[$log_prefix] $repo/$artifact_path: verified and published"
  return 0
}

prefer_download_hf_artifact() {
  local artifact_id="$2"
  local models_dir="${PREFER_MODELS_DIR:-/models}"
  local lock_dir="$models_dir/.prefer-cache/downloads-v2/locks"
  local status=0

  if mkdir -p "$lock_dir"; then
    :
  else
    status=$?
    echo "[artifact-download] could not create lock directory: $lock_dir" >&2
    return "$status"
  fi
  (
    if exec 9> "$lock_dir/$artifact_id.lock"; then
      :
    else
      status=$?
      echo "[artifact-download] could not open artifact lock: $artifact_id" >&2
      return "$status"
    fi
    if flock 9; then
      :
    else
      status=$?
      echo "[artifact-download] could not acquire artifact lock: $artifact_id" >&2
      return "$status"
    fi
    prefer_download_hf_artifact_locked "$@"
  )
}

prefer_run_artifact_batch() {
  local log_prefix="$1"
  local downloader="$2"
  shift 2
  local artifact_id=""
  local index=0
  local status=0
  local first_failure=0
  local first_failed_artifact=""
  local pids=()
  local artifact_ids=()

  for artifact_id in "$@"; do
    ("$downloader" "$artifact_id") &
    pids+=("$!")
    artifact_ids+=("$artifact_id")
  done

  while [ "$index" -lt "${#pids[@]}" ]; do
    if wait "${pids[$index]}"; then
      status=0
    else
      status=$?
      if [ "$first_failure" -eq 0 ]; then
        first_failure="$status"
        first_failed_artifact="${artifact_ids[$index]}"
      fi
    fi
    index=$((index + 1))
  done

  if [ "$first_failure" -ne 0 ]; then
    echo "[$log_prefix] artifact $first_failed_artifact failed first in catalog order (status $first_failure)" >&2
    return "$first_failure"
  fi
  return 0
}

prefer_download_model_keys() {
  local log_prefix="$1"
  local requested_jobs="$2"
  local maximum_jobs="$3"
  local resolver="$4"
  local downloader="$5"
  shift 5
  local model_key=""
  local resolved=""
  local artifact_id=""
  local status=0
  local artifact_ids=()
  local batch=()
  declare -A seen_artifacts=()

  if [[ ! "$requested_jobs" =~ ^[1-9][0-9]*$ ]] || [ "$requested_jobs" -gt "$maximum_jobs" ]; then
    echo "[$log_prefix] download jobs must be an integer from 1 through $maximum_jobs" >&2
    return 2
  fi

  for model_key in "$@"; do
    if resolved="$("$resolver" "$model_key")"; then
      status=0
    else
      status=$?
      return "$status"
    fi
    while IFS= read -r artifact_id; do
      [ -n "$artifact_id" ] || continue
      if [[ ! "$artifact_id" =~ ^[0-9a-f]{64}$ ]]; then
        echo "[$log_prefix] $model_key resolved an invalid artifact id: $artifact_id" >&2
        return 2
      fi
      if [ -z "${seen_artifacts[$artifact_id]:-}" ]; then
        seen_artifacts["$artifact_id"]=1
        artifact_ids+=("$artifact_id")
      fi
    done <<< "$resolved"
  done

  for artifact_id in "${artifact_ids[@]}"; do
    batch+=("$artifact_id")
    if [ "${#batch[@]}" -ge "$requested_jobs" ]; then
      if prefer_run_artifact_batch "$log_prefix" "$downloader" "${batch[@]}"; then
        status=0
      else
        status=$?
        return "$status"
      fi
      batch=()
    fi
  done
  if [ "${#batch[@]}" -gt 0 ]; then
    if prefer_run_artifact_batch "$log_prefix" "$downloader" "${batch[@]}"; then
      return 0
    else
      status=$?
      return "$status"
    fi
  fi
  return 0
}
