import json
from pathlib import Path
import subprocess
import sys
import unittest

from prefer_bench.paths import REPO_ROOT


IMAGE_ROOT = REPO_ROOT / "docker" / "stable-diffusion-cpp"


class ImageCppTests(unittest.TestCase):
    def test_generated_outputs_are_current(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(IMAGE_ROOT / "generate.py"), "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_catalog_is_split_by_model_and_uses_immutable_artifacts(self) -> None:
        seen_keys = set()
        model_ids = set()
        for path in sorted((IMAGE_ROOT / "models").glob("*/*/model.json")):
            source = json.loads(path.read_text(encoding="utf-8"))
            family, model_slug, _ = path.relative_to(IMAGE_ROOT / "models").parts
            self.assertEqual(source["family"], family, path)
            self.assertEqual(source["model_slug"], model_slug, path)
            self.assertEqual(sum(bool(lane.get("primary")) for lane in source["quants"].values()), 1)
            model_ids.add(source["shared"]["id"])
            for lane in source["quants"].values():
                self.assertNotIn(lane["key"], seen_keys)
                seen_keys.add(lane["key"])
                for artifact in lane["artifacts"]:
                    self.assertRegex(artifact["repo"], r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
                    self.assertRegex(artifact["revision"], r"^[0-9a-f]{40}$")
                    self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")
                    self.assertGreater(artifact["size"], 0)
        self.assertEqual(
            model_ids,
            {
                "flux-2-klein-4b",
                "z-image-turbo",
                "qwen-image",
                "qwen-image-edit-2511",
                "sdxl-1.0",
            },
        )
        self.assertEqual(len(seen_keys), 14)

    def test_inventory_preserves_api_residency_and_model_boundaries(self) -> None:
        inventory = json.loads(
            (IMAGE_ROOT / "deployment-inventory.generated.json").read_text(encoding="utf-8")
        )
        self.assertEqual(inventory["schema_version"], "prefer.image-deployment-inventory.v1")
        self.assertEqual(len(inventory["catalog_fingerprint"]), 64)
        self.assertEqual(inventory["platforms"], ["linux/amd64"])
        self.assertEqual(
            inventory["distribution"]["workflow_artifact_name_pattern"],
            "prefer-release-<commit-sha>",
        )
        self.assertEqual(
            inventory["distribution"]["release_inventory_asset"],
            "prefer-image-deployment-inventory.json",
        )
        self.assertEqual(
            inventory["api"],
            {
                "health": "GET /health",
                "models": "GET /v1/models",
                "generations": "POST /v1/images/generations",
                "edits": "POST /v1/images/edits",
            },
        )
        self.assertFalse(inventory["residency"]["discovery_loads_models"])
        self.assertEqual(inventory["residency"]["max_loaded_models"], 1)
        self.assertEqual(inventory["residency"]["idle_unload_ms"], 1_800_000)

        edit_lane = inventory["models"]["qwen-image-edit-2511-q6"]
        self.assertEqual(
            [artifact["role"] for artifact in edit_lane["artifacts"]],
            ["target", "vae", "text_encoder"],
        )
        self.assertEqual(edit_lane["precision"], "Q6_K target / BF16 text encoder")
        self.assertFalse(any(artifact["role"] == "projector" for artifact in edit_lane["artifacts"]))
        self.assertIn("qwen_image_zero_cond_t=true", edit_lane["server_args"])

        sdxl = inventory["models"]["sdxl-1.0-fp16"]
        self.assertEqual(sdxl["capabilities"], ["generation", "edit"])
        self.assertIn("maskless image-to-image", sdxl["description"])
        self.assertNotIn("inpainting", sdxl["description"])

    def test_generated_hardware_matrix_is_controller_ready(self) -> None:
        inventory = json.loads(
            (IMAGE_ROOT / "deployment-inventory.generated.json").read_text(encoding="utf-8")
        )
        deployments = {item["id"]: item for item in inventory["deployments"]}

        self.assertEqual(
            [model["key"] for model in deployments["aws/g6/xlarge/general"]["models"]],
            [
                "flux-2-klein-4b-bf16-q8",
                "z-image-turbo-q8",
                "qwen-image-q4",
                "sdxl-1.0-fp16",
            ],
        )
        self.assertNotIn("aws/g6/xlarge/qwen-image-edit-2511", deployments)
        self.assertEqual(
            next(
                model["key"]
                for model in deployments["aws/g6e/xlarge/general"]["models"]
                if model["request_model_id"] == "qwen-image-edit-2511"
            ),
            "qwen-image-edit-2511-q6",
        )
        self.assertEqual(
            next(
                model["key"]
                for model in deployments["aws/g7e/2xlarge/general"]["models"]
                if model["request_model_id"] == "qwen-image-edit-2511"
            ),
            "qwen-image-edit-2511-q8",
        )
        self.assertIn("local/rtx-4060/1x/general", deployments)
        self.assertIn("local/rtx-a2000-8gb/1x/general", deployments)
        self.assertIn("local/gtx-1070-ti/1x/general", deployments)
        self.assertIn("local/titan-x-pascal/1x/general", deployments)

        runpod_gpu_ids = {
            item["hardware"]["provider_gpu_type_id"]
            for item in deployments.values()
            if item.get("provider") == "runpod"
        }
        self.assertEqual(len(runpod_gpu_ids), 21)
        self.assertIn("NVIDIA RTX A5000", runpod_gpu_ids)
        self.assertIn("NVIDIA RTX A6000", runpod_gpu_ids)
        self.assertIn("NVIDIA RTX PRO 6000 Blackwell Server Edition", runpod_gpu_ids)
        self.assertIn("NVIDIA B300 SXM6 AC", runpod_gpu_ids)

        for deployment in deployments.values():
            if deployment.get("kind") not in {"bundle", "single-model"}:
                continue
            self.assertEqual(deployment["image_tag"], "image-cuda12")
            self.assertEqual(deployment["verification_status"], "configuration-only")
            self.assertEqual(deployment["residency"]["max_loaded_models"], 1)
            relative_config = deployment["container"]["server_config"].removeprefix(
                "/server-configs/"
            )
            config_path = IMAGE_ROOT / "server-configs" / relative_config
            prestage_path = config_path.with_suffix(".prestage")
            self.assertTrue(config_path.is_file(), deployment["id"])
            self.assertTrue(prestage_path.is_file(), deployment["id"])
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertTrue(config["lazy_load"])
            self.assertEqual(config["max_loaded_models"], 1)
            self.assertEqual(
                prestage_path.read_text(encoding="utf-8").strip().split(","),
                deployment["prestage_models"],
            )

    def test_image_release_and_downloader_are_isolated(self) -> None:
        runtime = json.loads((IMAGE_ROOT / "runtime.json").read_text(encoding="utf-8"))
        dockerfile = (IMAGE_ROOT / "Dockerfile").read_text(encoding="utf-8")
        downloader = (IMAGE_ROOT / "model-downloads.generated.sh").read_text(encoding="utf-8")
        compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        workflow = (REPO_ROOT / ".github" / "workflows" / "build-prefer.yml").read_text(
            encoding="utf-8"
        )
        image_job = workflow.split("\n  image:\n", 1)[1].split("\n  release:\n", 1)[0]

        self.assertIn(runtime["base_image"]["reference"], dockerfile)
        self.assertIn('"huggingface_hub[cli]"', dockerfile)
        self.assertIn("COPY download-artifacts.sh /prefer-download-artifacts.sh", dockerfile)
        self.assertIn("container_name: prefer-image", compose)
        self.assertIn("${IMAGE_PORT:-8082}:8080", compose)
        self.assertIn("IMAGE_SERVER_CONFIG=${IMAGE_SERVER_CONFIG:-}", compose)
        self.assertIn("IMAGE_PRESTAGE_MODELS=${IMAGE_PRESTAGE_MODELS:-}", compose)
        self.assertIn("IMAGE_DOWNLOAD_JOBS=${IMAGE_DOWNLOAD_JOBS:-4}", compose)
        self.assertIn("type=sha,prefix=image-cuda12-sha-", image_job)
        self.assertIn('"$image_repository:image-cuda12"', workflow)
        self.assertIn('"$image_repository:image-cuda12-preview"', workflow)
        self.assertIn("platforms: linux/amd64", image_job)
        self.assertNotIn("linux/arm64", image_job)
        self.assertIn("name: prefer-release-${{ github.sha }}", workflow)
        self.assertIn("--image-inventory", workflow)
        self.assertIn("benchmark.tests.test_artifact_downloads", workflow)
        self.assertIn("prefer_download_hf_artifact", downloader)
        self.assertIn("image_download_model_keys", downloader)
        self.assertNotIn("curl ", downloader)


if __name__ == "__main__":
    unittest.main()
