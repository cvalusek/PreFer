import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
VLLM_ROOT = ROOT / "docker" / "vllm"


class VLLMTests(unittest.TestCase):
    def test_generated_outputs_are_current(self):
        completed = subprocess.run([sys.executable, str(VLLM_ROOT / "generate.py"), "--check"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_catalog_pins_inferact_nvfp4_bundle(self):
        model = json.loads((VLLM_ROOT / "models" / "qwen" / "qwen-3.8-27b" / "model.json").read_text(encoding="utf-8"))
        lane = next(iter(model["quants"].values()))
        self.assertTrue(any(a["path"] == "nvfp4_experts_mtp.safetensors" for a in lane["artifacts"]))
        for artifact in lane["artifacts"]:
            self.assertRegex(artifact["revision"], r"^[0-9a-f]{40}$")
            self.assertGreater(artifact["size"], 0)
            self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")

    def test_inventory_is_base_free_and_retains_runtime_contract(self):
        inventory = json.loads((VLLM_ROOT / "deployment-inventory.generated.json").read_text(encoding="utf-8"))
        self.assertEqual(inventory["deployments"], [])
        self.assertTrue(inventory["models"])
        self.assertNotIn("PREFER_DEPLOYMENT", inventory["composition"]["environment"])
        self.assertFalse((VLLM_ROOT / "deployment-scenarios").exists())
        self.assertFalse((VLLM_ROOT / "server-configs").exists())
        self.assertEqual(set(inventory["base_images"]), {"cuda12", "cuda13"})

    def test_model_composes_with_mtp_control(self):
        inventory = json.loads((VLLM_ROOT / "deployment-inventory.generated.json").read_text(encoding="utf-8"))
        key = next(iter(inventory["models"]))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "server.json"
            completed = subprocess.run(
                [sys.executable, str(VLLM_ROOT / "generate.py"), "--compose", "--models", key,
                 "--output", str(output), "--prestage-output", str(Path(directory) / "prestage"),
                 "--plan-output", str(Path(directory) / "plan")],
                cwd=ROOT, text=True, capture_output=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            config = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(len(config["models"]), 1)
        self.assertIn("--speculative-config", config["command"])
        self.assertEqual(config["command"][config["command"].index("--port") + 1], "8000")
        self.assertEqual(config["command"][config["command"].index("--host") + 1], "0.0.0.0")
        self.assertNotIn("backend_port", config)

    def test_download_contract_uses_shared_helper_and_no_weights_in_image(self):
        self.assertEqual(
            (VLLM_ROOT / "download-artifacts.sh").read_bytes(),
            (ROOT / "docker" / "audio-cpp" / "download-artifacts.sh").read_bytes(),
        )
        dockerfile = (VLLM_ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertNotRegex(dockerfile, r"COPY .*\.(?:gguf|safetensors|bin)(?:\s|$)")
        self.assertFalse((VLLM_ROOT / "router.py").exists())
        self.assertNotIn("prefer-vllm-router", dockerfile)
        self.assertNotIn("prefer-vllm-router", (VLLM_ROOT / "entrypoint.sh").read_text(encoding="utf-8"))

    def test_compose_keeps_vllm_opt_in_and_base_free(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("profiles: [vllm]", compose)
        self.assertIn("VLLM_MODELS=${VLLM_MODELS:-}", compose)
        self.assertIn("VLLM_RUNTIME_HANDOFF=${VLLM_RUNTIME_HANDOFF:-}", compose)
        self.assertNotIn("VLLM_SERVER_CONFIG=", compose)
        self.assertNotIn("VLLM_DEPLOYMENT=", compose)
        self.assertIn("VLLM_CUDA_VARIANT", compose)
        self.assertIn("VLLM_BASE_IMAGE", compose)


if __name__ == "__main__":
    unittest.main()
