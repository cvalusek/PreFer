#!/usr/bin/env bash

# Shared download behavior for PreFer's generated Audio, Image, SGLang, and
# vLLM artifact maps. This file is sourced by an entrypoint, so it intentionally
# does not change the caller's shell options.

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

prefer_artifact_digest_matches() {
  local path="$1"
  local expected_size="$2"
  local algorithm="$3"
  local expected_digest="$4"
  local actual_size=""
  local actual_digest=""

  [ -f "$path" ] || return 1
  if actual_size="$(stat -c '%s' "$path")"; then
    :
  else
    return 1
  fi
  [ "$actual_size" = "$expected_size" ] || return 1
  case "$algorithm" in
    sha256)
      if actual_digest="$(sha256sum "$path")"; then :; else return 1; fi
      ;;
    git-blob-sha1)
      if actual_digest="$({ printf 'blob %s\0' "$actual_size"; cat "$path"; } | sha1sum)"; then :; else return 1; fi
      ;;
    *) return 1 ;;
  esac
  actual_digest="${actual_digest%% *}"
  [ "$actual_digest" = "$expected_digest" ] || return 1
  return 0
}

prefer_artifact_sha_matches() {
  prefer_artifact_digest_matches "$1" "$2" sha256 "$3"
}

prefer_s3_object_uri() {
  local bucket="$1"
  local prefix="$2"
  local object="$3"
  prefix="${prefix#/}"
  prefix="${prefix%/}"
  if [ -n "$prefix" ]; then
    printf 's3://%s/%s/%s\n' "$bucket" "$prefix" "$object"
  else
    printf 's3://%s/%s\n' "$bucket" "$object"
  fi
}

prefer_download_s3_artifact_locked() {
  local log_prefix="$1"
  local artifact_id="$2"
  local repo="$3"
  local artifact_path="$4"
  local expected_size="$5"
  local expected_digest="$6"
  local bucket="$7"
  local prefix="$8"
  local expected_algorithm="${9:-sha256}"
  local models_dir="${PREFER_MODELS_DIR:-/models}"
  local destination="$models_dir/$repo/$artifact_path"
  local staging_dir="$models_dir/.prefer-cache/downloads-v2/s3-staging/$artifact_id"
  local staged_artifact="$staging_dir/$repo/$artifact_path"
  local destination_dir="${destination%/*}"
  local staged_dir="${staged_artifact%/*}"
  local remote_uri=""
  local status=0

  if mkdir -p "$destination_dir" "$staged_dir"; then
    :
  else
    status=$?
    echo "[$log_prefix] $repo/$artifact_path: could not create S3 staging or destination directory" >&2
    return "$status"
  fi
  if prefer_artifact_marker_matches "$destination" "$expected_size" "$artifact_id"; then
    echo "[$log_prefix] $repo/$artifact_path: verified marker hit"
    return 0
  fi
  if [ -f "$destination" ] && prefer_artifact_digest_matches "$destination" "$expected_size" "$expected_algorithm" "$expected_digest"; then
    if prefer_write_artifact_marker "$destination" "$artifact_id"; then
      :
    else
      status=$?
      echo "[$log_prefix] $repo/$artifact_path: existing S3 artifact verified but marker publication failed" >&2
      return "$status"
    fi
    echo "[$log_prefix] $repo/$artifact_path: existing artifact verified"
    return 0
  fi

  remote_uri="$(prefer_s3_object_uri "$bucket" "$prefix" "$repo/$artifact_path")"
  rm -f "$staged_artifact"
  echo "[$log_prefix] $repo/$artifact_path: staging exact S3 object"
  if s5cmd cp "$remote_uri" "$staged_artifact"; then
    status=0
  else
    status=$?
    echo "[$log_prefix] $repo/$artifact_path: S3 object unavailable; falling back to Hugging Face" >&2
    return "$status"
  fi
  if ! prefer_artifact_digest_matches "$staged_artifact" "$expected_size" "$expected_algorithm" "$expected_digest"; then
    echo "[$log_prefix] $repo/$artifact_path: S3 size or digest validation failed" >&2
    rm -f "$staged_artifact" || true
    return 1
  fi
  if mv -f "$staged_artifact" "$destination"; then
    :
  else
    status=$?
    echo "[$log_prefix] $repo/$artifact_path: verified S3 staging publication failed" >&2
    return "$status"
  fi
  if prefer_write_artifact_marker "$destination" "$artifact_id"; then
    :
  else
    status=$?
    echo "[$log_prefix] $repo/$artifact_path: S3 artifact published but marker publication failed" >&2
    return "$status"
  fi
  echo "[$log_prefix] $repo/$artifact_path: S3 artifact verified and published"
  return 0
}

prefer_download_s3_artifact() {
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
    prefer_download_s3_artifact_locked "$@"
  )
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

prefer_with_artifact_lock() {
  local artifact_id="$1"
  local callback="$2"
  shift 2
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
    "$callback" "$artifact_id" "$@"
  )
}

prefer_hf_artifact_ready_locked() {
  local artifact_id="$1"
  local log_prefix="$2"
  local repo="$3"
  local artifact_path="$4"
  local expected_size="$5"
  local expected_algorithm="$6"
  local expected_digest="$7"
  local models_dir="${PREFER_MODELS_DIR:-/models}"
  local destination="$models_dir/$repo/$artifact_path"
  local destination_size=""
  local status=0

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
      if prefer_artifact_digest_matches "$destination" "$expected_size" "$expected_algorithm" "$expected_digest"; then
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
      echo "[$log_prefix] $repo/$artifact_path: existing artifact failed digest verification; downloading replacement" >&2
    else
      echo "[$log_prefix] $repo/$artifact_path: existing artifact has the wrong size or type; downloading replacement" >&2
    fi
  fi
  return 10
}

prefer_hf_artifact_ready() {
  local log_prefix="$1"
  local artifact_id="$2"
  shift 2
  prefer_with_artifact_lock "$artifact_id" prefer_hf_artifact_ready_locked "$log_prefix" "$@"
}

prefer_publish_hf_artifact_locked() {
  local artifact_id="$1"
  local log_prefix="$2"
  local repo="$3"
  local artifact_path="$4"
  local expected_size="$5"
  local expected_algorithm="$6"
  local expected_digest="$7"
  local staged_artifact="$8"
  local models_dir="${PREFER_MODELS_DIR:-/models}"
  local destination="$models_dir/$repo/$artifact_path"
  local destination_dir="${destination%/*}"
  local status=0

  if mkdir -p "$destination_dir"; then
    :
  else
    status=$?
    echo "[$log_prefix] $repo/$artifact_path: could not create destination directory" >&2
    return "$status"
  fi
  if prefer_artifact_marker_matches "$destination" "$expected_size" "$artifact_id"; then
    rm -f "$staged_artifact" || true
    echo "[$log_prefix] $repo/$artifact_path: verified marker hit"
    return 0
  fi
  if [ -f "$destination" ] && prefer_artifact_digest_matches "$destination" "$expected_size" "$expected_algorithm" "$expected_digest"; then
    if prefer_write_artifact_marker "$destination" "$artifact_id"; then
      :
    else
      status=$?
      echo "[$log_prefix] $repo/$artifact_path: existing artifact verified but marker publication failed" >&2
      return "$status"
    fi
    rm -f "$staged_artifact" || true
    echo "[$log_prefix] $repo/$artifact_path: existing artifact verified"
    return 0
  fi
  if ! prefer_artifact_digest_matches "$staged_artifact" "$expected_size" "$expected_algorithm" "$expected_digest"; then
    echo "[$log_prefix] $repo/$artifact_path: size or digest validation failed" >&2
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

prefer_publish_hf_artifact() {
  local log_prefix="$1"
  local artifact_id="$2"
  shift 2
  prefer_with_artifact_lock "$artifact_id" prefer_publish_hf_artifact_locked "$log_prefix" "$@"
}

prefer_hf_retry_delay() {
  local attempt="$1"
  local error_log="$2"
  local base_seconds="${PREFER_HF_RETRY_BASE_SECONDS:-5}"
  local cap_seconds="${PREFER_HF_RETRY_MAX_SECONDS:-60}"
  local retry_after=""
  local delay=0
  local exponent=1
  local index=1

  if [[ ! "$base_seconds" =~ ^[0-9]+$ ]] || [ "$base_seconds" -gt 3600 ] \
    || [[ ! "$cap_seconds" =~ ^[0-9]+$ ]] || [ "$cap_seconds" -gt 3600 ]; then
    echo "[artifact-download] Hugging Face retry delays must be integers from 0 through 3600 seconds" >&2
    return 2
  fi
  retry_after="$(grep -Eio 'retry[- ]after[^0-9]*[0-9]+' "$error_log" 2>/dev/null | grep -Eo '[0-9]+' | head -n 1 || true)"
  if [ -n "$retry_after" ] && [ "$retry_after" -le 3600 ]; then
    delay="$retry_after"
  else
    while [ "$index" -lt "$attempt" ]; do
      exponent=$((exponent * 2))
      index=$((index + 1))
    done
    delay=$((base_seconds * exponent))
  fi
  if [ "$delay" -gt "$cap_seconds" ]; then
    delay="$cap_seconds"
  fi
  printf '%s\n' "$delay"
}

prefer_hf_download_with_retry() {
  local log_prefix="$1"
  local repo="$2"
  local revision="$3"
  local staging_dir="$4"
  shift 4
  local max_attempts="${PREFER_HF_MAX_ATTEMPTS:-5}"
  local attempt=1
  local status=0
  local error_log=""
  local delay=0
  local revision_args=()

  if [[ ! "$max_attempts" =~ ^[1-9][0-9]*$ ]] || [ "$max_attempts" -gt 8 ]; then
    echo "[$log_prefix] PREFER_HF_MAX_ATTEMPTS must be an integer from 1 through 8" >&2
    return 2
  fi
  if error_log="$(mktemp "$staging_dir/.prefer-hf-errors.XXXXXX")"; then
    :
  else
    status=$?
    echo "[$log_prefix] $repo: could not create Hugging Face retry log" >&2
    return "$status"
  fi
  if [ -n "$revision" ]; then
    revision_args=(--revision "$revision")
  fi
  while [ "$attempt" -le "$max_attempts" ]; do
    : > "$error_log" || { status=$?; rm -f "$error_log" || true; return "$status"; }
    if hf download "$repo" "$@" "${revision_args[@]}" --local-dir "$staging_dir" 2> "$error_log"; then
      if [ -s "$error_log" ]; then
        cat "$error_log" >&2 || true
      fi
      rm -f "$error_log" || true
      return 0
    else
      status=$?
    fi
    if [ -s "$error_log" ]; then
      cat "$error_log" >&2 || true
    fi
    if ! grep -Eiq '(^|[^0-9])429([^0-9]|$)|too many requests|rate.?limit' "$error_log"; then
      echo "[$log_prefix] $repo: transfer failed with status $status; resumable state retained" >&2
      rm -f "$error_log" || true
      return "$status"
    fi
    if [ "$attempt" -ge "$max_attempts" ]; then
      echo "[$log_prefix] $repo: Hugging Face rate limit persisted after $attempt attempts; resumable state retained" >&2
      rm -f "$error_log" || true
      return "$status"
    fi
    if delay="$(prefer_hf_retry_delay "$attempt" "$error_log")"; then
      :
    else
      status=$?
      rm -f "$error_log" || true
      return "$status"
    fi
    echo "[$log_prefix] $repo: Hugging Face rate limited attempt $attempt/$max_attempts; retrying in ${delay}s" >&2
    if [ "$delay" -gt 0 ]; then
      sleep "$delay"
    fi
    attempt=$((attempt + 1))
  done
  rm -f "$error_log" || true
  return "$status"
}

prefer_validate_hf_manifest() {
  local log_prefix="$1"
  local manifest="$2"
  local artifact_id=""
  local repo=""
  local revision=""
  local artifact_path=""
  local expected_size=""
  local expected_algorithm=""
  local expected_digest=""
  local extra=""
  local component=""
  local index=0
  declare -A seen_ids=()
  declare -A seen_destinations=()

  if [ ! -f "$manifest" ]; then
    echo "[$log_prefix] artifact manifest not found: $manifest" >&2
    return 2
  fi
  while IFS=$'\t' read -r artifact_id repo revision artifact_path expected_size expected_algorithm expected_digest extra; do
    [ -n "$artifact_id$repo$revision$artifact_path$expected_size$expected_algorithm$expected_digest$extra" ] || continue
    if [ -n "$extra" ] || [[ ! "$artifact_id" =~ ^[0-9a-f]{64}$ ]] || [[ ! "$repo" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] \
      || [[ ! "$revision" =~ ^[0-9a-f]{40}$ ]] || [[ ! "$expected_size" =~ ^[1-9][0-9]*$ ]] \
      || { [ "$expected_algorithm" = "sha256" ] && [[ ! "$expected_digest" =~ ^[0-9a-f]{64}$ ]]; } \
      || { [ "$expected_algorithm" = "git-blob-sha1" ] && [[ ! "$expected_digest" =~ ^[0-9a-f]{40}$ ]]; } \
      || { [ "$expected_algorithm" != "sha256" ] && [ "$expected_algorithm" != "git-blob-sha1" ]; }; then
      echo "[$log_prefix] invalid artifact manifest record at index $index" >&2
      return 2
    fi
    if [[ "$artifact_path" == /* || "$artifact_path" == -* || "$artifact_path" == *\\* || "$artifact_path" == *$'\t'* \
      || "$artifact_path" == *$'\r'* || "$artifact_path" == *$'\n'* ]]; then
      echo "[$log_prefix] unsafe artifact path: $artifact_path" >&2
      return 2
    fi
    IFS='/' read -ra components <<< "$artifact_path"
    for component in "${components[@]}"; do
      if [ -z "$component" ] || [ "$component" = "." ] || [ "$component" = ".." ]; then
        echo "[$log_prefix] unsafe artifact path: $artifact_path" >&2
        return 2
      fi
    done
    if [ -n "${seen_ids[$artifact_id]:-}" ]; then
      echo "[$log_prefix] duplicate artifact id: $artifact_id" >&2
      return 2
    fi
    if [ -n "${seen_destinations[$repo/$artifact_path]:-}" ]; then
      echo "[$log_prefix] duplicate artifact destination: $repo/$artifact_path" >&2
      return 2
    fi
    seen_ids["$artifact_id"]=1
    seen_destinations["$repo/$artifact_path"]=1
    index=$((index + 1))
  done < "$manifest"
  if [ "$index" -eq 0 ]; then
    echo "[$log_prefix] artifact manifest is empty" >&2
    return 2
  fi
  return 0
}

prefer_download_hf_repository_manifest_locked() {
  local log_prefix="$1"
  local manifest="$2"
  local group_id="$3"
  local models_dir="${PREFER_MODELS_DIR:-/models}"
  local staging_dir="$models_dir/.prefer-cache/downloads-v2/repository-staging/$group_id"
  local artifact_id=""
  local repo=""
  local revision=""
  local artifact_path=""
  local expected_size=""
  local expected_algorithm=""
  local expected_digest=""
  local extra=""
  local status=0
  local ready_status=0
  local expected_repo=""
  local expected_revision=""
  local index=0
  local missing_indices=()
  local paths=()
  local ids=()
  local repos=()
  local revisions=()
  local sizes=()
  local algorithms=()
  local digests=()

  if mkdir -p "$staging_dir"; then
    :
  else
    status=$?
    echo "[$log_prefix] could not create repository staging directory: $staging_dir" >&2
    return "$status"
  fi
  while IFS=$'\t' read -r artifact_id repo revision artifact_path expected_size expected_algorithm expected_digest extra; do
    [ -n "$artifact_id$repo$revision$artifact_path$expected_size$expected_algorithm$expected_digest$extra" ] || continue
    if [ -z "$expected_repo" ]; then
      expected_repo="$repo"
      expected_revision="$revision"
    elif [ "$repo" != "$expected_repo" ] || [ "$revision" != "$expected_revision" ]; then
      echo "[$log_prefix] repository batch mixes repository identities" >&2
      return 2
    fi
    ids+=("$artifact_id")
    repos+=("$repo")
    revisions+=("$revision")
    paths+=("$artifact_path")
    sizes+=("$expected_size")
    algorithms+=("$expected_algorithm")
    digests+=("$expected_digest")
    if prefer_hf_artifact_ready "$log_prefix" "$artifact_id" "$repo" "$artifact_path" "$expected_size" "$expected_algorithm" "$expected_digest"; then
      ready_status=0
    else
      ready_status=$?
      if [ "$ready_status" -ne 10 ]; then
        return "$ready_status"
      fi
      missing_indices+=("$index")
    fi
    index=$((index + 1))
  done < "$manifest"

  if [ "${#missing_indices[@]}" -eq 0 ]; then
    return 0
  fi
  local download_paths=()
  for index in "${missing_indices[@]}"; do
    download_paths+=("${paths[$index]}")
  done
  echo "[$log_prefix] $expected_repo: downloading ${#download_paths[@]} pinned artifact(s) in one repository transfer"
  if prefer_hf_download_with_retry "$log_prefix" "$expected_repo" "$expected_revision" "$staging_dir" "${download_paths[@]}"; then
    :
  else
    return $?
  fi
  for index in "${missing_indices[@]}"; do
    if prefer_publish_hf_artifact "$log_prefix" "${ids[$index]}" "${repos[$index]}" "${paths[$index]}" \
      "${sizes[$index]}" "${algorithms[$index]}" "${digests[$index]}" "$staging_dir/${paths[$index]}"; then
      :
    else
      return $?
    fi
  done
  return 0
}

prefer_download_hf_repository_manifest() {
  local log_prefix="$1"
  local manifest="$2"
  local repo=""
  local revision=""
  local group_id=""
  local models_dir="${PREFER_MODELS_DIR:-/models}"
  local lock_dir="$models_dir/.prefer-cache/downloads-v2/repository-locks"
  local status=0

  IFS=$'\t' read -r _ repo revision _ < "$manifest" || return 2
  group_id="$({ printf '%s\0%s' "$repo" "$revision"; } | sha256sum)" || return $?
  group_id="${group_id%% *}"
  if mkdir -p "$lock_dir"; then
    :
  else
    status=$?
    echo "[$log_prefix] could not create repository lock directory: $lock_dir" >&2
    return "$status"
  fi
  (
    if exec 9> "$lock_dir/$group_id.lock"; then
      :
    else
      status=$?
      echo "[$log_prefix] could not open repository lock: $repo@$revision" >&2
      return "$status"
    fi
    if flock 9; then
      :
    else
      status=$?
      echo "[$log_prefix] could not acquire repository lock: $repo@$revision" >&2
      return "$status"
    fi
    prefer_download_hf_repository_manifest_locked "$log_prefix" "$manifest" "$group_id"
  )
}

prefer_run_hf_group_batch() {
  local log_prefix="$1"
  shift
  local manifest=""
  local index=0
  local status=0
  local first_failure=0
  local first_failed_group=""
  local pids=()
  local manifests=()

  for manifest in "$@"; do
    prefer_download_hf_repository_manifest "$log_prefix" "$manifest" &
    pids+=("$!")
    manifests+=("$manifest")
  done
  while [ "$index" -lt "${#pids[@]}" ]; do
    if wait "${pids[$index]}"; then
      :
    else
      status=$?
      if [ "$first_failure" -eq 0 ]; then
        first_failure="$status"
        first_failed_group="${manifests[$index]}"
      fi
    fi
    index=$((index + 1))
  done
  if [ "$first_failure" -ne 0 ]; then
    echo "[$log_prefix] repository group $first_failed_group failed first in catalog order (status $first_failure)" >&2
    return "$first_failure"
  fi
  return 0
}

prefer_download_hf_manifest() {
  local log_prefix="$1"
  local requested_jobs="$2"
  local maximum_jobs="$3"
  local manifest="$4"
  local models_dir="${PREFER_MODELS_DIR:-/models}"
  local request_root="$models_dir/.prefer-cache/downloads-v2/manifests"
  local request_dir=""
  local group_id=""
  local artifact_id=""
  local repo=""
  local revision=""
  local artifact_path=""
  local expected_size=""
  local expected_algorithm=""
  local expected_digest=""
  local extra=""
  local status=0
  local group_files=()
  local batch=()
  declare -A seen_groups=()

  if [[ ! "$requested_jobs" =~ ^[1-9][0-9]*$ ]] || [ "$requested_jobs" -gt "$maximum_jobs" ]; then
    echo "[$log_prefix] download jobs must be an integer from 1 through $maximum_jobs" >&2
    return 2
  fi
  if prefer_validate_hf_manifest "$log_prefix" "$manifest"; then
    :
  else
    return $?
  fi
  if mkdir -p "$request_root"; then
    :
  else
    status=$?
    echo "[$log_prefix] could not create manifest staging directory: $request_root" >&2
    return "$status"
  fi
  if request_dir="$(mktemp -d "$request_root/request.XXXXXX")"; then
    :
  else
    status=$?
    echo "[$log_prefix] could not create request manifest directory" >&2
    return "$status"
  fi
  while IFS=$'\t' read -r artifact_id repo revision artifact_path expected_size expected_algorithm expected_digest extra; do
    [ -n "$artifact_id$repo$revision$artifact_path$expected_size$expected_algorithm$expected_digest$extra" ] || continue
    group_id="$({ printf '%s\0%s' "$repo" "$revision"; } | sha256sum)" || { status=$?; rm -rf "$request_dir" || true; return "$status"; }
    group_id="${group_id%% *}"
    if [ -z "${seen_groups[$group_id]:-}" ]; then
      seen_groups["$group_id"]=1
      group_files+=("$request_dir/$group_id.tsv")
    fi
    if printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$artifact_id" "$repo" "$revision" "$artifact_path" \
      "$expected_size" "$expected_algorithm" "$expected_digest" >> "$request_dir/$group_id.tsv"; then
      :
    else
      status=$?
      rm -rf "$request_dir" || true
      return "$status"
    fi
  done < "$manifest"
  for manifest in "${group_files[@]}"; do
    batch+=("$manifest")
    if [ "${#batch[@]}" -ge "$requested_jobs" ]; then
      if prefer_run_hf_group_batch "$log_prefix" "${batch[@]}"; then
        :
      else
        status=$?
        rm -rf "$request_dir" || true
        return "$status"
      fi
      batch=()
    fi
  done
  if [ "${#batch[@]}" -gt 0 ]; then
    if prefer_run_hf_group_batch "$log_prefix" "${batch[@]}"; then
      :
    else
      status=$?
      rm -rf "$request_dir" || true
      return "$status"
    fi
  fi
  rm -rf "$request_dir" || true
  return 0
}

prefer_download_model_keys_hf() {
  local log_prefix="$1"
  local requested_jobs="$2"
  local maximum_jobs="$3"
  local resolver="$4"
  local record_resolver="$5"
  shift 5
  local models_dir="${PREFER_MODELS_DIR:-/models}"
  local manifest_root="$models_dir/.prefer-cache/downloads-v2/manifests"
  local manifest=""
  local model_key=""
  local resolved=""
  local artifact_id=""
  local record=""
  local record_id=""
  local status=0
  local artifact_ids=()
  declare -A seen_artifacts=()

  for model_key in "$@"; do
    if resolved="$("$resolver" "$model_key")"; then
      :
    else
      return $?
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
  if [ "${#artifact_ids[@]}" -eq 0 ]; then
    return 0
  fi
  if mkdir -p "$manifest_root"; then
    :
  else
    status=$?
    echo "[$log_prefix] could not create artifact manifest directory: $manifest_root" >&2
    return "$status"
  fi
  if manifest="$(mktemp "$manifest_root/selection.XXXXXX.tsv")"; then
    :
  else
    status=$?
    echo "[$log_prefix] could not create artifact selection manifest" >&2
    return "$status"
  fi
  for artifact_id in "${artifact_ids[@]}"; do
    if record="$("$record_resolver" "$artifact_id")"; then
      :
    else
      status=$?
      rm -f "$manifest" || true
      return "$status"
    fi
    if [[ "$record" == *$'\n'* ]]; then
      echo "[$log_prefix] artifact $artifact_id resolved multiple manifest records" >&2
      rm -f "$manifest" || true
      return 2
    fi
    IFS=$'\t' read -r record_id _ <<< "$record"
    if [ "$record_id" != "$artifact_id" ]; then
      echo "[$log_prefix] artifact $artifact_id resolved a mismatched manifest identity" >&2
      rm -f "$manifest" || true
      return 2
    fi
    if printf '%s\n' "$record" >> "$manifest"; then
      :
    else
      status=$?
      rm -f "$manifest" || true
      return "$status"
    fi
  done
  if prefer_download_hf_manifest "$log_prefix" "$requested_jobs" "$maximum_jobs" "$manifest"; then
    status=0
  else
    status=$?
  fi
  rm -f "$manifest" || true
  return "$status"
}

prefer_download_hf_artifact_locked() {
  local log_prefix="$1"
  local artifact_id="$2"
  local repo="$3"
  local revision="$4"
  local artifact_path="$5"
  local expected_size="$6"
  local expected_digest="$7"
  local expected_algorithm="${8:-sha256}"
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
      if prefer_artifact_digest_matches "$destination" "$expected_size" "$expected_algorithm" "$expected_digest"; then
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
      echo "[$log_prefix] $repo/$artifact_path: existing artifact failed digest verification; downloading replacement" >&2
    else
      echo "[$log_prefix] $repo/$artifact_path: existing artifact has the wrong size or type; downloading replacement" >&2
    fi
  fi

  echo "[$log_prefix] $repo/$artifact_path: downloading pinned artifact"
  if prefer_hf_download_with_retry "$log_prefix" "$repo" "$revision" "$staging_dir" "$artifact_path"; then
    status=0
  else
    status=$?
    echo "[$log_prefix] $repo/$artifact_path: transfer failed with status $status; resumable state retained" >&2
    return "$status"
  fi

  if ! prefer_artifact_digest_matches "$staged_artifact" "$expected_size" "$expected_algorithm" "$expected_digest"; then
    echo "[$log_prefix] $repo/$artifact_path: size or digest validation failed" >&2
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
