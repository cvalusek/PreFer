import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SGLANG_ROOT = ROOT / "docker" / "sglang"


class SGLangTests(unittest.TestCase):
    def test_generated_outputs_are_current(self):
        completed = subprocess.run([sys.executable, str(SGLANG_ROOT / "generate.py"), "--check"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_catalog_pins_exact_runtime_artifacts(self):
        for path in sorted((SGLANG_ROOT / "models").glob("*/*/model.json")):
            model = json.loads(path.read_text(encoding="utf-8"))
            for lane in model["quants"].values():
                for artifact in lane["artifacts"]:
                    self.assertRegex(artifact["revision"], r"^[0-9a-f]{40}$")
                    self.assertGreater(artifact["size"], 0)
                    self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")

    def test_inventory_exposes_text_and_video_without_hardware_deployments(self):
        inventory = json.loads((SGLANG_ROOT / "deployment-inventory.generated.json").read_text(encoding="utf-8"))
        self.assertEqual(inventory["deployments"], [])
        self.assertTrue(any(model["runtime_mode"] == "text" for model in inventory["models"].values()))
        self.assertTrue(any(model["runtime_mode"] == "diffusion" for model in inventory["models"].values()))
        self.assertNotIn("PREFER_DEPLOYMENT", inventory["composition"]["environment"])
        self.assertFalse((SGLANG_ROOT / "deployment-scenarios").exists())
        self.assertFalse((SGLANG_ROOT / "server-configs").exists())
        self.assertEqual(set(inventory["base_images"]), {"cuda12", "cuda13"})

    def test_every_lane_composes_to_one_model(self):
        inventory = json.loads((SGLANG_ROOT / "deployment-inventory.generated.json").read_text(encoding="utf-8"))
        for key in inventory["models"]:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "server.json"
                completed = subprocess.run(
                    [sys.executable, str(SGLANG_ROOT / "generate.py"), "--compose", "--models", key,
                     "--output", str(output), "--prestage-output", str(Path(directory) / "prestage"),
                     "--plan-output", str(Path(directory) / "plan")],
                    cwd=ROOT, text=True, capture_output=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                config = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(len(config["models"]), 1)
                self.assertTrue(config["command"])

    def test_download_contract_uses_shared_exact_marker_helper(self):
        helper = (SGLANG_ROOT / "download-artifacts.sh").read_bytes()
        self.assertEqual(helper, (ROOT / "docker" / "audio-cpp" / "download-artifacts.sh").read_bytes())
        dockerfile = (SGLANG_ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("/prefer-download-artifacts.sh", dockerfile)
        self.assertNotRegex(dockerfile, r"COPY .*\.(?:gguf|safetensors|bin)(?:\s|$)")

    def test_compose_keeps_sglang_opt_in_and_base_free(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("profiles: [sglang]", compose)
        self.assertIn("SGLANG_MODELS=${SGLANG_MODELS:-}", compose)
        self.assertIn("SGLANG_RUNTIME_HANDOFF=${SGLANG_RUNTIME_HANDOFF:-}", compose)
        self.assertNotIn("SGLANG_SERVER_CONFIG=", compose)
        self.assertNotIn("SGLANG_DEPLOYMENT=", compose)
        self.assertIn("SGLANG_CUDA_VARIANT", compose)
        self.assertIn("SGLANG_BASE_IMAGE", compose)


if __name__ == "__main__":
    unittest.main()
