import json
from pathlib import Path
import subprocess
import sys
import unittest


from prefer_bench.paths import REPO_ROOT


SGLANG_ROOT = REPO_ROOT / "docker" / "sglang"


class SGLangTests(unittest.TestCase):
    def test_generated_outputs_are_current(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SGLANG_ROOT / "generate.py"), "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_catalog_pins_the_complete_multimodal_nvfp4_checkpoint(self) -> None:
        catalog_path = SGLANG_ROOT / "models" / "qwen" / "qwen3.8-27b" / "model.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertEqual(catalog["shared"]["license"], "Apache-2.0")
        self.assertEqual(catalog["shared"]["native_context_length"], 262144)
        self.assertEqual(catalog["shared"]["max_context_length"], 1048576)
        self.assertEqual(catalog["shared"]["modalities"]["native"], ["text", "image", "video"])
        self.assertEqual(
            catalog["shared"]["reasoning_controls"]["reasoning_effort"],
            {"supported": ["low", "medium", "xhigh"], "default": "xhigh"},
        )
        lane = catalog["quants"]["nvfp4"]
        self.assertTrue(lane["primary"])
        self.assertEqual(lane["key"], "qwen3.8-27b-nvfp4")
        self.assertEqual(lane["artifacts"][0]["revision"], "319f741cce68d7914884900c138a1fbb70a42f30")
        self.assertEqual(len(lane["artifacts"]), 22)
        self.assertEqual(catalog["shared"]["kv_cache_scaling"]["quantization"], "FP8")
        self.assertFalse(catalog["shared"]["kv_cache_scaling"]["explicit_scale_metadata"])
        self.assertEqual(catalog["shared"]["kv_cache_scaling"]["parameter_file"], None)
        self.assertEqual(catalog["shared"]["artifact_variant"]["total_bytes"], 21945295265)
        self.assertEqual(
            sum(artifact["size"] for artifact in lane["artifacts"]),
            21945295265,
        )
        shards = {
            artifact["path"]: artifact
            for artifact in lane["artifacts"]
            if artifact["path"].endswith(".safetensors")
        }
        self.assertEqual(
            shards["model-00001-of-00003.safetensors"]["sha256"],
            "fbcdb5ba1cdda462b5f38592d071e772c4d398afea61a0aa9188b32d1a239a79",
        )
        self.assertEqual(
            shards["model-00002-of-00003.safetensors"]["size"],
            9985757064,
        )
        roles = {artifact["role"] for artifact in lane["artifacts"]}
        self.assertIn("image-preprocessor", roles)
        self.assertIn("video-preprocessor", roles)
        self.assertIn("chat-template", roles)
        self.assertIn("license", roles)

    def test_inventory_exposes_model_profiles_api_and_hardware_gates(self) -> None:
        runtime = json.loads((SGLANG_ROOT / "runtime.json").read_text(encoding="utf-8"))
        inventory = json.loads(
            (SGLANG_ROOT / "deployment-inventory.generated.json").read_text(encoding="utf-8")
        )
        self.assertEqual(inventory["schema_version"], "prefer.sglang-deployment-inventory.v1")
        self.assertEqual(inventory["runtime"]["source_revision"], runtime["runtime"]["source_revision"])
        self.assertEqual(inventory["base_image"]["index_digest"], runtime["base_image"]["index_digest"])
        self.assertEqual(
            inventory["base_image"]["build_revision"],
            "5f55db35e926d50676f75b812640ea2410b0fe0e",
        )
        self.assertEqual(inventory["requirements"]["minimum_compute_capability"], "sm_100")
        self.assertEqual(inventory["requirements"]["cuda_major"], 13)
        self.assertEqual(
            inventory["staging"]["aws_s3"]["read_policy"],
            ["s3:GetObject", "s3:ListBucket"],
        )
        self.assertEqual(inventory["staging"]["aws_s3"]["write_policy"], [])
        self.assertEqual(
            inventory["experimental_routes"]["dflash2"]["status"],
            "upstream-verify-blocked",
        )
        dflash = inventory["experimental_routes"]["dflash2"]
        self.assertEqual(dflash["target_repo"], "RadixArk/Qwen3.8-27B-NVFP4")
        self.assertFalse(dflash["custom_campaign"]["applies_to_catalog_lane"])
        self.assertEqual(dflash["custom_campaign"]["target_repo"], "orcarouter/Qwen3.8-27B-Uncensored-FP8")
        self.assertEqual(
            inventory["experimental_routes"]["flash_next"]["status"],
            "deferred-experimental",
        )
        audit = inventory["provenance_audit"]
        self.assertEqual(audit["status"], "owner-review-required")
        self.assertFalse(audit["pinned_image_lineage"]["custom_fork_code_included"])
        features = {row["feature"]: row for row in audit["feature_matrix"]}
        self.assertIn("Native NEXTN/MTP on the pinned RadixArk NVFP4 checkpoint", features)
        self.assertIn("DFlash2 speculation", features)
        self.assertIn("HiCache/NIXL and complete hybrid-state persistence", features)
        self.assertEqual(
            features["DFlash2 speculation"]["official_pinned_image"]["status"],
            "upstream-present-but-prefill-graph-blocked",
        )
        self.assertEqual(
            features["DFlash2 speculation"]["jpezzulli_custom_fork"]["status"],
            "custom-fork-different-target-format",
        )
        upstream_changes = {
            change["id"]: change for change in audit["upstream_changes_outside_pinned_image"]
        }
        self.assertEqual(upstream_changes["sglang/#36806"]["status"], "merged-upstream-after-image-build")
        self.assertEqual(upstream_changes["sglang/#35821"]["status"], "merged-upstream-after-image-build")
        self.assertTrue(audit["lineage_recommendation"]["owner_decision_required"])
        self.assertEqual(
            inventory["api"],
            {
                "health": "GET /health",
                "models": "GET /v1/models",
                "chat_completions": "POST /v1/chat/completions",
                "completions": "POST /v1/completions",
                "anthropic_messages": "POST /v1/messages",
            },
        )
        profile = inventory["model_profiles"]["qwen3.8-27b"]
        self.assertEqual(profile["native_modalities"], ["text", "image", "video"])
        self.assertEqual(inventory["models"]["qwen3.8-27b-nvfp4"]["profile_id"], "qwen3.8-27b")
        self.assertEqual(
            inventory["models"]["qwen3.8-27b-nvfp4"]["artifact_bytes"],
            21945295265,
        )
        self.assertFalse(
            inventory["models"]["qwen3.8-27b-nvfp4"]["kv_cache_scaling"]["explicit_scale_metadata"]
        )
        deployments = {deployment["id"]: deployment for deployment in inventory["deployments"]}
        self.assertEqual(deployments["sglang/cuda13"]["kind"], "runtime-default")
        self.assertEqual(deployments["sglang/cuda13"]["provider"], "unspecified")
        self.assertNotIn("hardware", deployments["sglang/cuda13"])
        self.assertIn("aws/g7e/2xlarge/balanced", deployments)
        self.assertIn("aws/g7e/2xlarge/fidelity", deployments)
        self.assertIn("runpod/rtx-5090/1x/target-only", deployments)
        self.assertIn("runpod/rtx-5090/1x/performance", deployments)
        self.assertIn("local/gb10/1x/balanced", deployments)
        self.assertEqual(deployments["aws/g7e/2xlarge/balanced"]["hardware"]["compute_capability"], "sm_120")
        self.assertEqual(deployments["aws/g7e/2xlarge/balanced"]["staging"]["source"], "s3-then-huggingface")
        self.assertEqual(deployments["local/gb10/1x/balanced"]["staging"]["source"], "huggingface-only")
        self.assertEqual(deployments["aws/g7e/2xlarge/balanced"]["server"]["context_length"], 524288)
        self.assertEqual(
            deployments["aws/g7e/2xlarge/balanced"]["residency"]["capacity"]["effective_admitted_concurrency"],
            "unknown-until-smoke",
        )
        self.assertEqual(
            deployments["aws/g7e/2xlarge/balanced"]["residency"]["capacity"]["token_pool"],
            "dynamically shared",
        )
        self.assertTrue(
            deployments["aws/g7e/2xlarge/balanced"]["server"]["speculative"]["enabled"]
        )
        self.assertEqual(
            deployments["aws/g7e/2xlarge/fidelity"]["server"]["kv_cache_dtype"],
            "bfloat16",
        )
        self.assertFalse(
            deployments["runpod/rtx-5090/1x/target-only"]["server"]["speculative"]["enabled"]
        )
        self.assertTrue(
            deployments["runpod/rtx-5090/1x/performance"]["server"]["speculative"]["enabled"]
        )
        self.assertEqual(
            deployments["local/gb10/1x/balanced"]["server"]["mem_fraction_static"],
            0.8,
        )
        self.assertTrue(any("Qwen3.8-Flash" in risk for risk in inventory["known_limitations"]))

    def test_generated_configs_are_single_model_and_use_declared_kv_paths(self) -> None:
        config_paths = sorted((SGLANG_ROOT / "server-configs").rglob("*.json"))
        self.assertGreaterEqual(len(config_paths), 5)
        for config_path in config_paths:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["runtime"], "sglang")
            self.assertEqual(config["port"], 30000)
            self.assertEqual(len(config["models"]), 1)
            self.assertIn(config["server"]["kv_cache_dtype"], {"fp8_e4m3", "bfloat16"})
            self.assertIn("--kv-cache-dtype", config["command"])
            self.assertIn(config["server"]["kv_cache_dtype"], config["command"])
            self.assertIn("--mamba-ssm-dtype", config["command"])
            self.assertIn("bfloat16", config["command"])
            prestage_path = config_path.with_suffix(".prestage")
            self.assertTrue(prestage_path.is_file())
            self.assertEqual(prestage_path.read_text(encoding="utf-8").strip(), "qwen3.8-27b-nvfp4")
        balanced = json.loads(
            (SGLANG_ROOT / "server-configs" / "aws" / "g7e" / "2xlarge" / "balanced.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn("--speculative-algorithm", balanced["command"])
        self.assertIn("--context-length", balanced["command"])
        self.assertIn("524288", balanced["command"])
        target_only = json.loads(
            (SGLANG_ROOT / "server-configs" / "runpod" / "rtx-5090" / "1x" / "target-only.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn("--speculative-algorithm", target_only["command"])
        fidelity = json.loads(
            (SGLANG_ROOT / "server-configs" / "aws" / "g7e" / "2xlarge" / "fidelity.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(fidelity["server"]["kv_cache_dtype"], "bfloat16")
        self.assertNotIn("--quantization-param-path", fidelity["command"])

    def test_download_contract_matches_llama_layout_and_shared_helper(self) -> None:
        helper = (SGLANG_ROOT / "download-artifacts.sh").read_bytes()
        llama_helper = (REPO_ROOT / "docker" / "audio-cpp" / "download-artifacts.sh").read_bytes()
        self.assertEqual(helper, llama_helper)
        generated = (SGLANG_ROOT / "model-downloads.generated.sh").read_text(encoding="utf-8")
        entrypoint = (SGLANG_ROOT / "entrypoint.sh").read_text(encoding="utf-8")
        llama_downloader = (REPO_ROOT / "docker" / "llama-cpp" / "download-models.sh").read_text(
            encoding="utf-8"
        )
        dockerfile = (SGLANG_ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("model_key_fingerprint", generated)
        self.assertIn("model_key_artifacts", generated)
        self.assertIn("download_model_key", generated)
        self.assertIn("prefer_download_hf_artifact", generated)
        self.assertIn("prefer_download_s3_artifact", generated)
        self.assertIn("sglang_download_model_keys_s3", generated)
        self.assertNotIn("curl ", generated)
        self.assertIn("PRESTAGE_MODELS", entrypoint)
        self.assertIn("MODEL_DOWNLOAD_JOBS", entrypoint)
        self.assertIn("S3_BUCKET_NAME", entrypoint)
        self.assertIn("SGLANG_S3_MODEL_PREFIX", entrypoint)
        self.assertIn("sglang_download_model_keys_s3", entrypoint)
        self.assertIn("downloads-v1", entrypoint)
        self.assertIn('MARKER_BUCKET_NAME="${S3_BUCKET_NAME:--}"', llama_downloader)
        self.assertIn("printf 'v1\\t-\\t%s\\t%s\\n'", entrypoint)
        self.assertIn("HF_HOME=/models", dockerfile)
        self.assertIn("S5CMD_VERSION=2.2.2", dockerfile)
        self.assertIn("TARGETARCH", dockerfile)
        self.assertIn('io.prefer.sglang.image-build-revision="5f55db35e926d50676f75b812640ea2410b0fe0e"', dockerfile)
        self.assertIn('io.prefer.sglang.lineage="official-upstream"', dockerfile)
        self.assertIn("COPY download-artifacts.sh /prefer-download-artifacts.sh", dockerfile)

    def test_compose_and_grouped_workflow_keep_sglang_separate_and_immutable(self) -> None:
        compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        env = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        workflow = (REPO_ROOT / ".github" / "workflows" / "build-prefer.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("profiles: [sglang]", compose)
        self.assertIn('container_name: prefer-sglang', compose)
        self.assertIn('"${SGLANG_PORT:-8083}:30000"', compose)
        self.assertIn("prefer-sglang-model-cache", compose)
        self.assertIn("name: ${PREFER_SGLANG_MODEL_VOLUME:-prefer-model-cache}", compose)
        self.assertIn("SGLANG_SERVER_CONFIG=${SGLANG_SERVER_CONFIG:-}", compose)
        self.assertIn("SGLANG_PRESTAGE_MODELS=${SGLANG_PRESTAGE_MODELS:-}", compose)
        self.assertIn("SGLANG_DOWNLOAD_JOBS=${SGLANG_DOWNLOAD_JOBS:-4}", compose)
        self.assertIn("S3_BUCKET_NAME=${S3_BUCKET_NAME:-}", compose)
        self.assertIn("S3_MODEL_PREFIX=${S3_MODEL_PREFIX:-}", compose)
        self.assertIn("SGLANG_S3_BUCKET_NAME=${SGLANG_S3_BUCKET_NAME:-}", compose)
        self.assertIn("SGLANG_S3_MODEL_PREFIX=${SGLANG_S3_MODEL_PREFIX:-}", compose)
        self.assertIn("SGLANG_PORT=8083", env)
        self.assertIn("PREFER_SGLANG_MODEL_VOLUME=prefer-model-cache", env)
        self.assertIn("SGLANG_S3_BUCKET_NAME=", env)
        self.assertIn("SGLANG_S3_MODEL_PREFIX=", env)
        self.assertIn("S3_BUCKET_NAME=", env)
        self.assertIn("S3_MODEL_PREFIX=", env)
        self.assertIn("docker/sglang/**", workflow)
        self.assertIn('image_repository=ghcr.io/${GITHUB_REPOSITORY,,}', workflow)
        self.assertEqual(workflow.count("name=${{ steps.image.outputs.image_repository }}"), 2)
        self.assertIn("IMAGE_REPOSITORY: ${{ steps.image.outputs.image_repository }}", workflow)
        self.assertIn("push-by-digest=true", workflow)
        self.assertIn("name-canonical=true", workflow)
        self.assertIn("sglang_amd64:", workflow)
        self.assertIn("sglang_arm64:", workflow)
        self.assertIn("needs: [sglang_amd64, sglang_arm64]", workflow)
        self.assertIn("Free runner disk space", workflow)
        self.assertIn("sudo docker system prune --all --force --volumes", workflow)
        self.assertIn("docker buildx imagetools create", workflow)
        self.assertIn("--metadata-file", workflow)
        self.assertIn("docker buildx imagetools inspect", workflow)
        self.assertIn("grep -q 'linux/amd64'", workflow)
        self.assertIn("grep -q 'linux/arm64'", workflow)
        self.assertIn('."containerimage.descriptor".digest', workflow)
        self.assertNotIn("type=raw,value=sglang-cuda13", workflow)
        self.assertIn("$image_repository:sglang-cuda", workflow)
        self.assertIn("$image_repository:sglang-cuda-preview", workflow)
        self.assertIn("--sglang-digest", workflow)
        self.assertIn("--sglang-inventory", workflow)
        self.assertIn("needs: [llama, audio_cuda, audio_cpu, image, sglang]", workflow)


if __name__ == "__main__":
    unittest.main()
