from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import unittest

from prefer_bench.paths import REPO_ROOT


AUDIO_ROOT = REPO_ROOT / "docker" / "audio-cpp"
IMAGE_ROOT = REPO_ROOT / "docker" / "stable-diffusion-cpp"
SGLANG_ROOT = REPO_ROOT / "docker" / "sglang"
VLLM_ROOT = REPO_ROOT / "docker" / "vllm"
REVISION = "1" * 40


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def find_bash() -> str | None:
    candidates = [shutil.which("bash")]
    if os.name == "nt":
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        candidates.append(str(program_files / "Git" / "bin" / "bash.exe"))
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        completed = subprocess.run(
            [candidate, "--version"],
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            return candidate
    return None


class ArtifactDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bash = find_bash()
        if cls.bash is None:
            raise unittest.SkipTest("bash with flock is required for downloader integration tests")

    def setUp(self) -> None:
        created = subprocess.run(
            [self.bash, "-lc", 'mktemp -d ".artifact-download-test.XXXXXX"'],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        self.root = (REPO_ROOT / created.stdout.strip()).resolve()
        self.models = self.root / "models"
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir(parents=True)
        self.models.mkdir()
        self.source = self.root / "source.bin"
        self.state = self.root / "hf.state"
        self.log = self.root / "hf.log"
        self.fake_hf = self.bin_dir / "hf"
        self.fake_hf.write_text(
            r"""#!/usr/bin/env bash
set -euo pipefail
if [ "${FAKE_HF_MUST_NOT_RUN:-0}" = "1" ]; then
  exit 99
fi
[ "$1" = "download" ]
repo="$2"
shift 2
artifacts=()
local_dir=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --revision) shift 2 ;;
    --local-dir) local_dir="$2"; shift 2 ;;
    *) artifacts+=("$1"); shift ;;
  esac
done
[ -n "$local_dir" ]
[ "${#artifacts[@]}" -gt 0 ]
first_artifact="${artifacts[0]}"
partial="$local_dir/.cache/huggingface/download/${first_artifact//\//--}.incomplete"
mkdir -p "$(dirname "$partial")" "$(dirname "$local_dir/$first_artifact")"
resume_size=0
if [ -f "$partial" ]; then
  resume_size="$(stat -c '%s' "$partial")"
fi
joined="$(IFS=,; printf '%s' "${artifacts[*]}")"
printf '%s\t%s\t%s\n' "$repo" "$joined" "$resume_size" >> "$FAKE_HF_LOG"
if [ "${FAKE_HF_ALWAYS_429:-0}" = "1" ] || { [ "${FAKE_HF_429_ONCE:-0}" = "1" ] && [ ! -e "${FAKE_HF_429_STATE:-$FAKE_HF_STATE.429}" ]; }; then
  : > "${FAKE_HF_429_STATE:-$FAKE_HF_STATE.429}"
  echo "HTTP 429 Too Many Requests; Retry-After: 0" >&2
  exit 29
fi
if [ "${FAKE_HF_FAIL_ONCE:-0}" = "1" ] && [ ! -e "$FAKE_HF_STATE" ]; then
  head -c "${FAKE_HF_SPLIT_BYTES:-1}" "$FAKE_HF_SOURCE" > "$partial"
  : > "$FAKE_HF_STATE"
  exit 42
fi
for artifact in "${artifacts[@]}"; do
  partial="$local_dir/.cache/huggingface/download/${artifact//\//--}.incomplete"
  mkdir -p "$(dirname "$partial")" "$(dirname "$local_dir/$artifact")"
  current_size=0
  if [ -f "$partial" ]; then current_size="$(stat -c '%s' "$partial")"; fi
  if [ "$current_size" -gt 0 ]; then
    tail -c "+$((current_size + 1))" "$FAKE_HF_SOURCE" >> "$partial"
  else
    cp "$FAKE_HF_SOURCE" "$partial"
  fi
  mv -f "$partial" "$local_dir/$artifact"
  printf '%s\n' "$local_dir/$artifact"
done
""",
            encoding="utf-8",
            newline="\n",
        )
        self.fake_hf.chmod(0o755)
        self.fake_s5cmd = self.bin_dir / "s5cmd"
        self.fake_s5cmd.write_text(
            r"""#!/usr/bin/env bash
set -euo pipefail
[ "$1" = "cp" ]
uri="$2"
destination="$3"
printf '%s\n' "$uri" >> "$FAKE_S5CMD_LOG"
if [ "${FAKE_S5CMD_MUST_NOT_RUN:-0}" = "1" ]; then
  exit 99
fi
if [ "${FAKE_S5CMD_FAIL:-0}" = "1" ]; then
  exit 44
fi
mkdir -p "$(dirname "$destination")"
cp "$FAKE_S3_SOURCE" "$destination"
""",
            encoding="utf-8",
            newline="\n",
        )
        self.fake_s5cmd.chmod(0o755)
        if os.name == "nt":
            fake_flock = self.bin_dir / "flock"
            fake_flock.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8", newline="\n")
            fake_flock.chmod(0o755)

    def tearDown(self) -> None:
        if (
            self.root.parent == REPO_ROOT.resolve()
            and self.root.name.startswith(".artifact-download-test.")
        ):
            shutil.rmtree(self.root)

    def run_helper(
        self,
        helper: Path,
        artifact: bytes,
        *,
        expected: bytes | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.source.write_bytes(artifact)
        expected_bytes = artifact if expected is None else expected
        expected_sha = hashlib.sha256(expected_bytes).hexdigest()
        artifact_id = hashlib.sha256(b"test-artifact-identity").hexdigest()
        script = """
set -uo pipefail
set +e
export PATH="$FAKE_BIN:$PATH"
source "$1"
if [ "${FAKE_PUBLICATION_FAILURE:-0}" = "1" ] || [ "${FAKE_MARKER_FAILURE:-0}" = "1" ]; then
  mv() {
    local destination="${!#}"
    if [ "${FAKE_PUBLICATION_FAILURE:-0}" = "1" ]; then
      case "$destination" in
        */owner/repo/nested/model.bin) return 55 ;;
      esac
    fi
    if [ "${FAKE_MARKER_FAILURE:-0}" = "1" ]; then
      case "$destination" in
        */downloads-v2/verified/*.complete) return 56 ;;
      esac
    fi
    command mv "$@"
  }
fi
if [ "${FAKE_FLOCK_FAILURE:-0}" = "1" ]; then
  flock() { return 57; }
fi
prefer_download_hf_artifact \
  test-download "$2" owner/repo "$3" nested/model.bin "$4" "$5"
"""
        env = os.environ.copy()
        env.update(
            {
                "FAKE_BIN": repo_relative(self.bin_dir),
                "PREFER_MODELS_DIR": repo_relative(self.models),
                "FAKE_HF_SOURCE": repo_relative(self.source),
                "FAKE_HF_STATE": repo_relative(self.state),
                "FAKE_HF_LOG": repo_relative(self.log),
            }
        )
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [
                self.bash,
                "-c",
                script,
                "_",
                repo_relative(helper),
                artifact_id,
                REVISION,
                str(len(expected_bytes)),
                expected_sha,
            ],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_helpers_remain_identical_and_generated_maps_use_them(self) -> None:
        audio_helper = (AUDIO_ROOT / "download-artifacts.sh").read_bytes()
        image_helper = (IMAGE_ROOT / "download-artifacts.sh").read_bytes()
        sglang_helper = (SGLANG_ROOT / "download-artifacts.sh").read_bytes()
        vllm_helper = (VLLM_ROOT / "download-artifacts.sh").read_bytes()
        self.assertEqual(audio_helper, image_helper)
        self.assertEqual(audio_helper, sglang_helper)
        self.assertEqual(audio_helper, vllm_helper)
        self.assertIn(b"hf download", audio_helper)
        self.assertIn(b"prefer_download_s3_artifact", audio_helper)
        self.assertIn(b"downloads-v2/staging", audio_helper)
        self.assertIn(b"prefer_download_model_keys", audio_helper)
        self.assertIn(b"prefer_download_model_keys_hf", audio_helper)
        self.assertIn(b"repository-staging", audio_helper)
        for root in (AUDIO_ROOT, IMAGE_ROOT, SGLANG_ROOT, VLLM_ROOT):
            generated = (root / "model-downloads.generated.sh").read_text(encoding="utf-8")
            self.assertIn("prefer_download_hf_artifact", generated)
            self.assertIn("prefer_download_model_keys_hf", generated)
            self.assertNotIn("curl ", generated)
            self.assertNotIn("partial.$$", generated)
        self.assertIn("sglang_download_model_keys_s3", (SGLANG_ROOT / "model-downloads.generated.sh").read_text(encoding="utf-8"))

    def test_runtime_handoff_manifest_is_validated_before_any_transfer(self) -> None:
        content = b"runtime-handoff-artifact\n" * 32
        expected_sha = hashlib.sha256(content).hexdigest()
        self.source.write_bytes(content)
        manifest = self.root / "handoff-artifacts.tsv"
        manifest.write_text(
            "\t".join(
                [
                    "a" * 64,
                    "owner/repo",
                    REVISION,
                    "valid/model.bin",
                    str(len(content)),
                    "sha256",
                    expected_sha,
                ]
            )
            + "\n"
            + "invalid-record\n",
            encoding="utf-8",
            newline="\n",
        )
        script = """
set -uo pipefail
set +e
export PATH="$FAKE_BIN:$PATH"
source "$1"
source "$2"
prefer_download_runtime_manifest runtime-handoff 2 8 "$3"
"""
        env = os.environ.copy()
        env.update(
            {
                "FAKE_BIN": repo_relative(self.bin_dir),
                "PREFER_MODELS_DIR": repo_relative(self.models),
                "FAKE_HF_SOURCE": repo_relative(self.source),
                "FAKE_HF_STATE": repo_relative(self.state),
                "FAKE_HF_LOG": repo_relative(self.log),
                "FAKE_HF_MUST_NOT_RUN": "1",
            }
        )
        completed = subprocess.run(
            [
                self.bash,
                "-c",
                script,
                "_",
                repo_relative(AUDIO_ROOT / "download-artifacts.sh"),
                "scripts/runtime-handoff-download.sh",
                repo_relative(manifest),
            ],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
        self.assertIn("invalid runtime artifact manifest record", completed.stderr)
        self.assertFalse(self.log.exists())
        self.assertFalse((self.models / "owner" / "repo" / "valid" / "model.bin").exists())

    def test_runtime_handoff_manifest_stages_exact_artifacts(self) -> None:
        content = b"runtime-handoff-artifact\n" * 32
        expected_sha = hashlib.sha256(content).hexdigest()
        git_blob_sha = hashlib.sha1(
            f"blob {len(content)}\0".encode("ascii") + content
        ).hexdigest()
        self.source.write_bytes(content)
        manifest = self.root / "handoff-artifacts.tsv"
        manifest.write_text(
            "\n".join(
                "\t".join([artifact_id, "owner/repo", REVISION, path, str(len(content)), algorithm, digest])
                for artifact_id, path, algorithm, digest in (
                    ("a" * 64, "first/model.bin", "sha256", expected_sha),
                    ("b" * 64, "second/adapter.bin", "git-blob-sha1", git_blob_sha),
                )
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        script = """
set -euo pipefail
export PATH="$FAKE_BIN:$PATH"
source "$1"
source "$2"
prefer_download_runtime_manifest runtime-handoff 2 8 "$3"
"""
        env = os.environ.copy()
        env.update(
            {
                "FAKE_BIN": repo_relative(self.bin_dir),
                "PREFER_MODELS_DIR": repo_relative(self.models),
                "FAKE_HF_SOURCE": repo_relative(self.source),
                "FAKE_HF_STATE": repo_relative(self.state),
                "FAKE_HF_LOG": repo_relative(self.log),
            }
        )
        completed = subprocess.run(
            [
                self.bash,
                "-c",
                script,
                "_",
                repo_relative(AUDIO_ROOT / "download-artifacts.sh"),
                "scripts/runtime-handoff-download.sh",
                repo_relative(manifest),
            ],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual((self.models / "owner" / "repo" / "first" / "model.bin").read_bytes(), content)
        self.assertEqual((self.models / "owner" / "repo" / "second" / "adapter.bin").read_bytes(), content)
        log_lines = self.log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(log_lines), 1)
        self.assertIn("first/model.bin,second/adapter.bin", log_lines[0])

    def test_repository_transfer_retries_a_bounded_rate_limit(self) -> None:
        content = b"rate-limited-artifact\n" * 16
        expected_sha = hashlib.sha256(content).hexdigest()
        self.source.write_bytes(content)
        manifest = self.root / "rate-limit.tsv"
        manifest.write_text(
            "\t".join(["a" * 64, "owner/repo", REVISION, "model.bin", str(len(content)), "sha256", expected_sha]) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        script = """
set -euo pipefail
export PATH="$FAKE_BIN:$PATH"
source "$1"
prefer_download_hf_manifest rate-limit 4 8 "$2"
"""
        env = {
            **os.environ,
            "FAKE_BIN": repo_relative(self.bin_dir),
            "PREFER_MODELS_DIR": repo_relative(self.models),
            "FAKE_HF_SOURCE": repo_relative(self.source),
            "FAKE_HF_STATE": repo_relative(self.state),
            "FAKE_HF_LOG": repo_relative(self.log),
            "FAKE_HF_429_ONCE": "1",
            "PREFER_HF_RETRY_BASE_SECONDS": "0",
            "PREFER_HF_RETRY_MAX_SECONDS": "0",
        }
        completed = subprocess.run(
            [self.bash, "-c", script, "_", repo_relative(AUDIO_ROOT / "download-artifacts.sh"), repo_relative(manifest)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(len(self.log.read_text(encoding="utf-8").splitlines()), 2)
        self.assertIn("rate limited attempt 1/5", completed.stderr)
        self.assertEqual((self.models / "owner" / "repo" / "model.bin").read_bytes(), content)

    def test_model_key_download_groups_artifacts_by_repository_revision(self) -> None:
        content = b"repository-group-artifact\n" * 16
        expected_sha = hashlib.sha256(content).hexdigest()
        self.source.write_bytes(content)
        first_id = "a" * 64
        second_id = "b" * 64
        script = f"""
set -euo pipefail
export PATH="$FAKE_BIN:$PATH"
source "$1"
resolver() {{ printf '%s\\n' {first_id} {second_id}; }}
records() {{
  case "$1" in
    {first_id}) printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' "$1" owner/repo {REVISION} first.bin {len(content)} sha256 {expected_sha} ;;
    {second_id}) printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' "$1" owner/repo {REVISION} second.bin {len(content)} sha256 {expected_sha} ;;
  esac
}}
prefer_download_model_keys_hf grouped-model 4 8 resolver records model-a
"""
        env = {
            **os.environ,
            "FAKE_BIN": repo_relative(self.bin_dir),
            "PREFER_MODELS_DIR": repo_relative(self.models),
            "FAKE_HF_SOURCE": repo_relative(self.source),
            "FAKE_HF_STATE": repo_relative(self.state),
            "FAKE_HF_LOG": repo_relative(self.log),
        }
        completed = subprocess.run(
            [self.bash, "-c", script, "_", repo_relative(AUDIO_ROOT / "download-artifacts.sh")],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(self.log.read_text(encoding="utf-8").splitlines(), ["owner/repo\tfirst.bin,second.bin\t0"])
        self.assertEqual((self.models / "owner" / "repo" / "first.bin").read_bytes(), content)
        self.assertEqual((self.models / "owner" / "repo" / "second.bin").read_bytes(), content)

    def test_repository_rate_limit_stops_at_configured_attempt_count(self) -> None:
        content = b"bounded-rate-limit\n"
        expected_sha = hashlib.sha256(content).hexdigest()
        self.source.write_bytes(content)
        manifest = self.root / "persistent-rate-limit.tsv"
        manifest.write_text(
            "\t".join(["a" * 64, "owner/repo", REVISION, "model.bin", str(len(content)), "sha256", expected_sha]) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        script = """
set -uo pipefail
set +e
export PATH="$FAKE_BIN:$PATH"
source "$1"
prefer_download_hf_manifest rate-limit 1 8 "$2"
"""
        env = {
            **os.environ,
            "FAKE_BIN": repo_relative(self.bin_dir),
            "PREFER_MODELS_DIR": repo_relative(self.models),
            "FAKE_HF_SOURCE": repo_relative(self.source),
            "FAKE_HF_STATE": repo_relative(self.state),
            "FAKE_HF_LOG": repo_relative(self.log),
            "FAKE_HF_ALWAYS_429": "1",
            "PREFER_HF_MAX_ATTEMPTS": "3",
            "PREFER_HF_RETRY_BASE_SECONDS": "0",
            "PREFER_HF_RETRY_MAX_SECONDS": "0",
        }
        completed = subprocess.run(
            [self.bash, "-c", script, "_", repo_relative(AUDIO_ROOT / "download-artifacts.sh"), repo_relative(manifest)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 29, completed.stdout + completed.stderr)
        self.assertEqual(len(self.log.read_text(encoding="utf-8").splitlines()), 3)
        self.assertIn("rate limit persisted after 3 attempts", completed.stderr)
        self.assertFalse((self.models / "owner" / "repo" / "model.bin").exists())

    def test_qwen_nvfp4_stages_runtime_files_only(self) -> None:
        sglang_model = (SGLANG_ROOT / "models" / "qwen" / "qwen-3.8-27b" / "model.json").read_text(encoding="utf-8")
        sglang_generated = (SGLANG_ROOT / "model-downloads.generated.sh").read_text(encoding="utf-8")
        vllm_model = (VLLM_ROOT / "models" / "qwen" / "qwen-3.8-27b" / "model.json").read_text(encoding="utf-8")
        for excluded in (".gitattributes", ".quant_summary.txt", "README.md", "conversion-manifest.json", "qualification.json", "tensor-audit.json"):
            self.assertNotIn(excluded, sglang_model)
            self.assertNotIn(excluded, sglang_generated)
        self.assertNotIn('"path": "LICENSE"', sglang_model)
        self.assertNotIn('"path": "LICENSE"', vllm_model)
        self.assertIn("model-00001-of-00003.safetensors", sglang_generated)
        self.assertIn("nvfp4_experts_mtp.safetensors", (VLLM_ROOT / "model-downloads.generated.sh").read_text(encoding="utf-8"))

    def test_interrupted_transfer_resumes_and_marker_skips_restart_hash(self) -> None:
        content = b"pinned-artifact-content\n" * 64
        helper = IMAGE_ROOT / "download-artifacts.sh"
        first = self.run_helper(
            helper,
            content,
            extra_env={"FAKE_HF_FAIL_ONCE": "1", "FAKE_HF_SPLIT_BYTES": "37"},
        )
        self.assertEqual(first.returncode, 42, first.stdout + first.stderr)
        destination = self.models / "owner" / "repo" / "nested" / "model.bin"
        self.assertFalse(destination.exists())
        partials = list(self.models.rglob("*.incomplete"))
        self.assertEqual(len(partials), 1)
        self.assertEqual(partials[0].stat().st_size, 37)

        second = self.run_helper(
            helper,
            content,
            extra_env={"FAKE_HF_FAIL_ONCE": "1", "FAKE_HF_SPLIT_BYTES": "37"},
        )
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(destination.read_bytes(), content)
        self.assertFalse(list(self.models.rglob("*.incomplete")))
        self.assertTrue(list(self.models.rglob("*.complete")))
        log_lines = self.log.read_text(encoding="utf-8").splitlines()
        self.assertTrue(log_lines[-1].endswith("\t37"), log_lines)

        third = self.run_helper(
            helper,
            content,
            extra_env={"FAKE_HF_MUST_NOT_RUN": "1"},
        )
        self.assertEqual(third.returncode, 0, third.stdout + third.stderr)
        self.assertIn("verified marker hit", third.stdout)
        self.assertEqual(self.log.read_text(encoding="utf-8").splitlines(), log_lines)

    def test_s3_artifact_read_through_verifies_and_falls_back_to_huggingface(self) -> None:
        content = b"s3-pinned-artifact-content\n" * 64
        helper = SGLANG_ROOT / "download-artifacts.sh"
        artifact_id = "a" * 64
        expected_sha = hashlib.sha256(content).hexdigest()
        self.source.write_bytes(content)
        script = """
set -uo pipefail
set +e
export PATH="$FAKE_BIN:$PATH"
source "$1"
prefer_download_s3_artifact sglang-s3 "$2" owner/repo nested/model.bin "$3" "$4" "$5" "$6"
"""
        env = os.environ.copy()
        env.update(
            {
                "FAKE_BIN": repo_relative(self.bin_dir),
                "PREFER_MODELS_DIR": repo_relative(self.models),
                "FAKE_S3_SOURCE": repo_relative(self.source),
                "FAKE_S5CMD_LOG": repo_relative(self.root / "s5cmd.log"),
                "FAKE_HF_SOURCE": repo_relative(self.source),
                "FAKE_HF_STATE": repo_relative(self.root / "fallback-hf.state"),
                "FAKE_HF_LOG": repo_relative(self.log),
            }
        )
        completed = subprocess.run(
            [
                self.bash,
                "-c",
                script,
                "_",
                repo_relative(helper),
                artifact_id,
                str(len(content)),
                expected_sha,
                "prefer-bucket",
                "model-prefix",
            ],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        destination = self.models / "owner" / "repo" / "nested" / "model.bin"
        self.assertEqual(destination.read_bytes(), content)
        marker = self.models / ".prefer-cache" / "downloads-v2" / "verified" / f"{artifact_id}.complete"
        self.assertTrue(marker.is_file())
        self.assertEqual(
            (self.root / "s5cmd.log").read_text(encoding="utf-8").strip(),
            "s3://prefer-bucket/model-prefix/owner/repo/nested/model.bin",
        )

        marker_hit = subprocess.run(
            [
                self.bash,
                "-c",
                script,
                "_",
                repo_relative(helper),
                artifact_id,
                str(len(content)),
                expected_sha,
                "prefer-bucket",
                "model-prefix",
            ],
            cwd=REPO_ROOT,
            env={**env, "FAKE_S5CMD_MUST_NOT_RUN": "1"},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(marker_hit.returncode, 0, marker_hit.stdout + marker_hit.stderr)
        self.assertIn("verified marker hit", marker_hit.stdout)

        fallback_id = "b" * 64
        fallback_script = """
set -uo pipefail
set +e
export PATH="$FAKE_BIN:$PATH"
source "$1"
if prefer_download_s3_artifact sglang-s3 "$2" owner/repo fallback.bin "$3" "$4" "$5" "$6"; then
  exit 12
fi
prefer_download_hf_artifact sglang-hf "$2" owner/repo "$7" fallback.bin "$3" "$4"
"""
        fallback = subprocess.run(
            [
                self.bash,
                "-c",
                fallback_script,
                "_",
                repo_relative(helper),
                fallback_id,
                str(len(content)),
                expected_sha,
                "prefer-bucket",
                "model-prefix",
                REVISION,
                "fallback.bin",
            ],
            cwd=REPO_ROOT,
            env={**env, "FAKE_S5CMD_FAIL": "1"},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(fallback.returncode, 0, fallback.stdout + fallback.stderr)
        self.assertEqual((self.models / "owner" / "repo" / "fallback.bin").read_bytes(), content)
        self.assertIn("S3 object unavailable", fallback.stderr)
        self.assertTrue(self.log.is_file())

    def test_changed_file_is_reverified_and_bad_replacement_is_not_published(self) -> None:
        correct = b"correct-pinned-bytes" * 32
        helper = AUDIO_ROOT / "download-artifacts.sh"
        initial = self.run_helper(helper, correct)
        self.assertEqual(initial.returncode, 0, initial.stdout + initial.stderr)
        destination = self.models / "owner" / "repo" / "nested" / "model.bin"
        corrupted = b"x" * len(correct)
        destination.write_bytes(corrupted)

        wrong_download = b"y" * len(correct)
        failed = self.run_helper(helper, wrong_download, expected=correct)
        self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
        self.assertEqual(destination.read_bytes(), corrupted)
        self.assertFalse(
            (self.models / ".prefer-cache" / "downloads-v2" / "staging").joinpath(
                hashlib.sha256(b"test-artifact-identity").hexdigest(), "nested", "model.bin"
            ).exists()
        )

        repaired = self.run_helper(helper, correct)
        self.assertEqual(repaired.returncode, 0, repaired.stdout + repaired.stderr)
        self.assertEqual(destination.read_bytes(), correct)

    def test_publication_marker_and_lock_failures_propagate_with_errexit_off(self) -> None:
        correct = b"correct-pinned-bytes" * 32
        corrupted = b"x" * len(correct)
        helper = IMAGE_ROOT / "download-artifacts.sh"
        destination = self.models / "owner" / "repo" / "nested" / "model.bin"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(corrupted)

        publication_failed = self.run_helper(
            helper,
            correct,
            extra_env={"FAKE_PUBLICATION_FAILURE": "1"},
        )
        self.assertEqual(
            publication_failed.returncode,
            55,
            publication_failed.stdout + publication_failed.stderr,
        )
        self.assertEqual(destination.read_bytes(), corrupted)
        self.assertFalse(list(self.models.rglob("*.complete")))
        self.assertNotIn("verified and published", publication_failed.stdout)
        staged = (
            self.models
            / ".prefer-cache"
            / "downloads-v2"
            / "staging"
            / hashlib.sha256(b"test-artifact-identity").hexdigest()
            / "nested"
            / "model.bin"
        )
        self.assertEqual(staged.read_bytes(), correct)

        destination.write_bytes(correct)
        hf_log_before = self.log.read_text(encoding="utf-8")
        marker_failed = self.run_helper(
            helper,
            correct,
            extra_env={"FAKE_MARKER_FAILURE": "1", "FAKE_HF_MUST_NOT_RUN": "1"},
        )
        self.assertEqual(marker_failed.returncode, 56, marker_failed.stdout + marker_failed.stderr)
        self.assertEqual(destination.read_bytes(), correct)
        self.assertFalse(list(self.models.rglob("*.complete")))
        self.assertNotIn("existing artifact verified", marker_failed.stdout)
        self.assertEqual(self.log.read_text(encoding="utf-8"), hf_log_before)

        lock_failed = self.run_helper(
            helper,
            correct,
            extra_env={"FAKE_FLOCK_FAILURE": "1", "FAKE_HF_MUST_NOT_RUN": "1"},
        )
        self.assertEqual(lock_failed.returncode, 57, lock_failed.stdout + lock_failed.stderr)
        self.assertFalse(list(self.models.rglob("*.complete")))
        self.assertNotIn("verified marker hit", lock_failed.stdout)
        self.assertEqual(self.log.read_text(encoding="utf-8"), hf_log_before)

    def test_model_artifacts_are_deduplicated_and_fail_in_catalog_order(self) -> None:
        helper = AUDIO_ROOT / "download-artifacts.sh"
        log = self.root / "batch.log"
        a = "a" * 64
        b = "b" * 64
        c = "c" * 64
        script = f"""
set -euo pipefail
source "$1"
resolver() {{
  case "$1" in
    model-a) printf '%s\\n' {a} {b} ;;
    model-b) printf '%s\\n' {a} {c} ;;
    *) return 2 ;;
  esac
}}
downloader() {{
  printf '%s\\n' "$1" >> "$2"
}}
export -f downloader
download_one() {{ downloader "$1" "$BATCH_LOG"; }}
export -f download_one
prefer_download_model_keys test-download 2 8 resolver download_one model-a model-b
"""
        env = os.environ.copy()
        env["BATCH_LOG"] = repo_relative(log)
        completed = subprocess.run(
            [self.bash, "-c", script, "_", repo_relative(helper)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertCountEqual(log.read_text(encoding="utf-8").splitlines(), [a, b, c])

        failure_script = f"""
set -uo pipefail
source "$1"
resolver() {{ printf '%s\\n' {a} {b} {c}; }}
downloader() {{
  printf '%s\\n' "$1" >> "$FAILURE_LOG"
  [ "$1" != "{b}" ] || return 7
  [ "$1" != "{c}" ] || return 9
}}
export -f downloader
prefer_download_model_keys test-download 2 8 resolver downloader model-a
"""
        failure_log = self.root / "failure.log"
        env["FAILURE_LOG"] = repo_relative(failure_log)
        failed = subprocess.run(
            [self.bash, "-c", failure_script, "_", repo_relative(helper)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(failed.returncode, 7, failed.stdout + failed.stderr)
        self.assertCountEqual(failure_log.read_text(encoding="utf-8").splitlines(), [a, b])
        self.assertIn(f"artifact {b} failed first in catalog order", failed.stderr)

        too_many_jobs_script = f"""
set -uo pipefail
source "$1"
resolver() {{ printf '%s\\n' {a}; }}
downloader() {{ return 99; }}
prefer_download_model_keys test-download 9 8 resolver downloader model-a
"""
        too_many_jobs = subprocess.run(
            [self.bash, "-c", too_many_jobs_script, "_", repo_relative(helper)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(too_many_jobs.returncode, 2)
        self.assertIn("download jobs must be an integer from 1 through 8", too_many_jobs.stderr)


if __name__ == "__main__":
    unittest.main()
