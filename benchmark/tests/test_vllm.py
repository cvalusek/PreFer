import http.client
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest


from prefer_bench.paths import REPO_ROOT


VLLM_ROOT = REPO_ROOT / "docker" / "vllm"


def load_router_module():
    spec = importlib.util.spec_from_file_location("prefer_vllm_router", VLLM_ROOT / "router.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load vLLM router module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VLLMTests(unittest.TestCase):
    def test_generated_outputs_are_current(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(VLLM_ROOT / "generate.py"), "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_catalog_pins_the_inferact_nvfp4_bundle(self) -> None:
        catalog = json.loads(
            (VLLM_ROOT / "models" / "qwen" / "qwen3.8-27b" / "model.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(catalog["shared"]["license"], "Apache-2.0")
        self.assertEqual(catalog["shared"]["native_context_length"], 262144)
        self.assertEqual(catalog["shared"]["modalities"]["native"], ["text", "image", "video"])
        self.assertEqual(
            catalog["shared"]["lineage"]["derivative_revision"],
            "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462",
        )
        lane = catalog["quants"]["nvfp4"]
        self.assertTrue(lane["primary"])
        self.assertEqual(lane["key"], "qwen3.8-27b-nvfp4")
        self.assertEqual(len(lane["artifacts"]), 19)
        self.assertEqual(lane["artifacts"][0]["revision"], "6128240ebaf4eaa7bad2b3d1c72c37d677c5f462")
        self.assertEqual(sum(artifact["size"] for artifact in lane["artifacts"]), 26404413873)
        roles = {artifact["role"] for artifact in lane["artifacts"]}
        self.assertIn("speculative-mtp", roles)
        self.assertIn("image-preprocessor", roles)
        self.assertIn("video-preprocessor", roles)

    def test_inventory_exposes_blackwell_contract_and_deferred_flash_route(self) -> None:
        runtime = json.loads((VLLM_ROOT / "runtime.json").read_text(encoding="utf-8"))
        inventory = json.loads(
            (VLLM_ROOT / "deployment-inventory.generated.json").read_text(encoding="utf-8")
        )
        self.assertEqual(inventory["schema_version"], "prefer.vllm-deployment-inventory.v1")
        self.assertEqual(inventory["base_image"]["index_digest"], runtime["base_image"]["index_digest"])
        self.assertEqual(inventory["base_image"]["platform_manifests"]["linux/amd64"], "sha256:ffaf945675c81fa7ed3e6a66c7c2d7189dd012614e2c961fac1c2702a7ba04be")
        self.assertEqual(inventory["requirements"]["minimum_compute_capability"], "sm_100")
        self.assertEqual(inventory["requirements"]["cuda_major"], 13)
        self.assertEqual(inventory["experimental_routes"]["qwen3.8-flash"]["status"], "deferred-experimental")
        self.assertEqual(inventory["models"]["qwen3.8-27b-nvfp4"]["artifact_bytes"], 26404413873)
        self.assertEqual(inventory["api"]["ready"], "GET /readyz")
        deployments = {deployment["id"]: deployment for deployment in inventory["deployments"]}
        self.assertEqual(deployments["vllm/cuda13"]["kind"], "runtime-default")
        self.assertIn("aws/g7e/2xlarge/performance", deployments)
        self.assertEqual(deployments["aws/g7e/2xlarge/performance"]["server"]["max_model_len"], 524288)
        self.assertFalse(deployments["runpod/rtx-5090/1x/target-only"]["server"]["speculative"]["enabled"])
        self.assertTrue(deployments["runpod/rtx-5090/1x/performance"]["server"]["speculative"]["enabled"])

    def test_generated_configs_are_single_model_and_have_mtp_control(self) -> None:
        config_paths = sorted((VLLM_ROOT / "server-configs").rglob("*.json"))
        self.assertEqual(len(config_paths), 7)
        for config_path in config_paths:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["runtime"], "vllm")
            self.assertEqual(config["port"], 8000)
            self.assertEqual(len(config["models"]), 1)
            self.assertTrue(config_path.with_suffix(".prestage").is_file())
            self.assertIn("vllm", config["command"])
            self.assertIn("serve", config["command"])
        performance = json.loads(
            (VLLM_ROOT / "server-configs" / "aws" / "g7e" / "2xlarge" / "performance.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn("--speculative-config", performance["command"])
        self.assertIn('{"method":"mtp","num_speculative_tokens":3}', performance["command"])
        target_only = json.loads(
            (VLLM_ROOT / "server-configs" / "runpod" / "rtx-5090" / "1x" / "target-only.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn("--speculative-config", target_only["command"])
        self.assertIn("--enforce-eager", target_only["command"])

    def test_download_contract_uses_the_shared_helper_and_no_weights_in_image(self) -> None:
        helper = (VLLM_ROOT / "download-artifacts.sh").read_bytes()
        shared_helper = (REPO_ROOT / "docker" / "audio-cpp" / "download-artifacts.sh").read_bytes()
        self.assertEqual(helper, shared_helper)
        generated = (VLLM_ROOT / "model-downloads.generated.sh").read_text(encoding="utf-8")
        dockerfile = (VLLM_ROOT / "Dockerfile").read_text(encoding="utf-8")
        entrypoint = (VLLM_ROOT / "entrypoint.sh").read_text(encoding="utf-8")
        dockerignore = (VLLM_ROOT / ".dockerignore").read_text(encoding="utf-8")
        self.assertIn("vllm_download_model_keys_s3", generated)
        self.assertIn("prefer_download_hf_artifact", generated)
        self.assertNotIn("curl ", generated)
        self.assertIn("VLLM_PRESTAGE_MODELS", entrypoint)
        self.assertIn("VLLM_S3_BUCKET_NAME", entrypoint)
        self.assertIn("downloads-v2", helper.decode("utf-8"))
        self.assertNotIn(".safetensors", dockerfile)
        self.assertNotIn("hf_hub_download", dockerfile)
        self.assertIn("**/*.safetensors", dockerignore)
        self.assertIn('io.prefer.vllm.lineage="official-upstream"', dockerfile)
        self.assertIn("COPY download-artifacts.sh /prefer-download-artifacts.sh", dockerfile)

    def test_gateway_reports_models_during_staging_and_readiness_afterward(self) -> None:
        router = load_router_module()
        config = json.loads((VLLM_ROOT / "server.generated.json").read_text(encoding="utf-8"))
        state = router.GatewayState(config, 0, [])
        server = router.ThreadingHTTPServer(("127.0.0.1", 0), router.GatewayHandler)
        server.gateway_state = state
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            connection.request("GET", "/v1/models")
            models_response = connection.getresponse()
            models = json.loads(models_response.read())
            connection.close()
            self.assertEqual(models_response.status, 200)
            self.assertEqual(models["data"][0]["id"], "qwen3.8-27b")
            self.assertIn("qwen-3.8-27b", models["data"][0]["aliases"])

            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            connection.request("GET", "/readyz")
            self.assertEqual(connection.getresponse().status, 503)
            connection.close()
            state.set_phase("ready", "test backend is ready")
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            connection.request("GET", "/readyz")
            self.assertEqual(connection.getresponse().status, 200)
            connection.close()
        finally:
            server.shutdown()
            server.server_close()

    def test_compose_and_workflow_keep_vllm_opt_in_and_grouped(self) -> None:
        compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        env = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        workflow = (REPO_ROOT / ".github" / "workflows" / "build-prefer.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("profiles: [vllm]", compose)
        self.assertIn("container_name: prefer-vllm", compose)
        self.assertIn('"${VLLM_PORT:-8084}:8000"', compose)
        self.assertIn("prefer-vllm-model-cache", compose)
        self.assertIn("VLLM_SERVER_CONFIG=${VLLM_SERVER_CONFIG:-}", compose)
        self.assertIn("VLLM_S3_BUCKET_NAME=${VLLM_S3_BUCKET_NAME:-}", compose)
        self.assertIn("VLLM_PORT=8084", env)
        self.assertIn("PREFER_VLLM_MODEL_VOLUME=prefer-model-cache", env)
        self.assertIn("docker/vllm/**", workflow)
        self.assertIn("vllm-cuda13-sha-", workflow)
        self.assertIn("vllm-cuda-preview", workflow)
        self.assertIn("--vllm-digest", workflow)
        self.assertIn("--vllm-inventory", workflow)


if __name__ == "__main__":
    unittest.main()
