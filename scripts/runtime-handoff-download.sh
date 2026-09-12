#!/usr/bin/env bash

# Stage the exact artifacts emitted by `prefer runtime materialize`. The caller
# must source prefer-download-artifacts.sh first. This helper deliberately
# validates the complete manifest before starting any transfer.

prefer_download_runtime_artifact() {
  local log_prefix="$1"
  local artifact_id="$2"
  local repo="$3"
  local revision="$4"
  local artifact_path="$5"
  local expected_size="$6"
  local expected_algorithm="$7"
  local expected_digest="$8"
  local bucket="$9"
  shift 9
  local prefix="${1:-}"
  local status=0

  if [ -n "$bucket" ]; then
    if prefer_download_s3_artifact "$log_prefix" "$artifact_id" "$repo" "$artifact_path" "$expected_size" "$expected_digest" "$bucket" "$prefix" "$expected_algorithm"; then
      return 0
    else
      status=$?
      echo "[$log_prefix] $repo/$artifact_path: exact S3 staging failed with status $status; trying Hugging Face" >&2
    fi
  fi
  prefer_download_hf_artifact "$log_prefix" "$artifact_id" "$repo" "$revision" "$artifact_path" "$expected_size" "$expected_digest" "$expected_algorithm"
}

prefer_download_runtime_manifest() {
  local log_prefix="$1"
  local requested_jobs="$2"
  local maximum_jobs="$3"
  local manifest="$4"
  local bucket="${5:-}"
  local prefix="${6:-}"
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
  local cursor=0
  local end=0
  local status=0
  local first_failure=0
  local first_failed_artifact=""
  local ids=()
  local repos=()
  local revisions=()
  local paths=()
  local sizes=()
  local algorithms=()
  local digests=()
  local pids=()
  local batch_ids=()
  declare -A seen_ids=()
  declare -A seen_destinations=()

  if [[ ! "$requested_jobs" =~ ^[1-9][0-9]*$ ]] || [ "$requested_jobs" -gt "$maximum_jobs" ]; then
    echo "[$log_prefix] download jobs must be an integer from 1 through $maximum_jobs" >&2
    return 2
  fi
  if [ ! -f "$manifest" ]; then
    echo "[$log_prefix] runtime artifact manifest not found: $manifest" >&2
    return 2
  fi
  if [ -n "$bucket" ]; then
    if [[ "$bucket" == s3://* || "$bucket" == */* || "$bucket" == *\\* ]]; then
      echo "[$log_prefix] S3 bucket must be a bucket name, not a URI or path" >&2
      return 2
    fi
    if [[ "$prefix" == s3://* || "$prefix" == /* || "$prefix" == *\\* ]]; then
      echo "[$log_prefix] S3 model prefix must be relative" >&2
      return 2
    fi
    IFS='/' read -ra components <<< "$prefix"
    for component in "${components[@]}"; do
      if [ "$component" = ".." ]; then
        echo "[$log_prefix] S3 model prefix must not contain '..' path components" >&2
        return 2
      fi
    done
    prefix="${prefix#/}"
    prefix="${prefix%/}"
  fi

  while IFS=$'\t' read -r artifact_id repo revision artifact_path expected_size expected_algorithm expected_digest extra; do
    [ -n "$artifact_id$repo$revision$artifact_path$expected_size$expected_algorithm$expected_digest$extra" ] || continue
    if [ -n "$extra" ] || [[ ! "$artifact_id" =~ ^[0-9a-f]{64}$ ]] || [[ ! "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] \
      || [[ ! "$revision" =~ ^[0-9a-f]{40}$ ]] || [[ ! "$expected_size" =~ ^[1-9][0-9]*$ ]] \
      || { [ "$expected_algorithm" = "sha256" ] && [[ ! "$expected_digest" =~ ^[0-9a-f]{64}$ ]]; } \
      || { [ "$expected_algorithm" = "git-blob-sha1" ] && [[ ! "$expected_digest" =~ ^[0-9a-f]{40}$ ]]; } \
      || { [ "$expected_algorithm" != "sha256" ] && [ "$expected_algorithm" != "git-blob-sha1" ]; }; then
      echo "[$log_prefix] invalid runtime artifact manifest record at index $index" >&2
      return 2
    fi
    if [[ "$artifact_path" == /* || "$artifact_path" == *\\* || "$artifact_path" == *$'\r'* || "$artifact_path" == *$'\n'* ]]; then
      echo "[$log_prefix] unsafe runtime artifact path: $artifact_path" >&2
      return 2
    fi
    IFS='/' read -ra components <<< "$artifact_path"
    for component in "${components[@]}"; do
      if [ -z "$component" ] || [ "$component" = "." ] || [ "$component" = ".." ]; then
        echo "[$log_prefix] unsafe runtime artifact path: $artifact_path" >&2
        return 2
      fi
    done
    if [ -n "${seen_ids[$artifact_id]:-}" ]; then
      echo "[$log_prefix] duplicate runtime artifact id: $artifact_id" >&2
      return 2
    fi
    if [ -n "${seen_destinations[$repo/$artifact_path]:-}" ]; then
      echo "[$log_prefix] duplicate runtime artifact destination: $repo/$artifact_path" >&2
      return 2
    fi
    seen_ids["$artifact_id"]=1
    seen_destinations["$repo/$artifact_path"]=1
    ids+=("$artifact_id")
    repos+=("$repo")
    revisions+=("$revision")
    paths+=("$artifact_path")
    sizes+=("$expected_size")
    algorithms+=("$expected_algorithm")
    digests+=("$expected_digest")
    index=$((index + 1))
  done < "$manifest"

  if [ "${#ids[@]}" -eq 0 ]; then
    echo "[$log_prefix] runtime artifact manifest is empty" >&2
    return 2
  fi

  if [ -z "$bucket" ]; then
    prefer_download_hf_manifest "$log_prefix" "$requested_jobs" "$maximum_jobs" "$manifest"
    return $?
  fi

  while [ "$cursor" -lt "${#ids[@]}" ]; do
    end=$((cursor + requested_jobs))
    if [ "$end" -gt "${#ids[@]}" ]; then
      end="${#ids[@]}"
    fi
    pids=()
    batch_ids=()
    index="$cursor"
    while [ "$index" -lt "$end" ]; do
      prefer_download_runtime_artifact \
        "$log_prefix" "${ids[$index]}" "${repos[$index]}" "${revisions[$index]}" \
        "${paths[$index]}" "${sizes[$index]}" "${algorithms[$index]}" "${digests[$index]}" "$bucket" "$prefix" &
      pids+=("$!")
      batch_ids+=("${ids[$index]}")
      index=$((index + 1))
    done
    index=0
    first_failure=0
    first_failed_artifact=""
    while [ "$index" -lt "${#pids[@]}" ]; do
      if wait "${pids[$index]}"; then
        status=0
      else
        status=$?
        if [ "$first_failure" -eq 0 ]; then
          first_failure="$status"
          first_failed_artifact="${batch_ids[$index]}"
        fi
      fi
      index=$((index + 1))
    done
    if [ "$first_failure" -ne 0 ]; then
      echo "[$log_prefix] runtime artifact $first_failed_artifact failed first in handoff order (status $first_failure)" >&2
      return "$first_failure"
    fi
    cursor="$end"
  done
  return 0
}
