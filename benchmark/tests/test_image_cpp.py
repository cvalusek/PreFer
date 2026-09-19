import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
IMAGE_ROOT = ROOT / "docker" / "stable-diffusion-cpp"


class ImageCppTests(unittest.TestCase):
    def test_generated_outputs_are_current(self):
        completed = subprocess.run([sys.executable, str(IMAGE_ROOT / "generate.py"), "--check"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_catalog_is_split_by_model_and_uses_immutable_artifacts(self):
        files = sorted((IMAGE_ROOT / "models").glob("*/*/model.json"))
        self.assertGreaterEqual(len(files), 5)
        for path in files:
            model = json.loads(path.read_text(encoding="utf-8"))
            for lane in model["quants"].values():
                for artifact in lane["artifacts"]:
                    self.assertRegex(artifact["revision"], r"^[0-9a-f]{40}$")
                    self.assertGreater(artifact["size"], 0)
                    self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")

    def test_inventory_preserves_api_and_models_without_hardware_deployments(self):
        inventory = json.loads((IMAGE_ROOT / "deployment-inventory.generated.json").read_text(encoding="utf-8"))
        self.assertEqual(inventory["deployments"], [])
        self.assertTrue(inventory["models"])
        self.assertIn("fast", inventory["bundles"])
        self.assertNotIn("PREFER_DEPLOYMENT", inventory["composition"]["environment"])
        self.assertFalse((IMAGE_ROOT / "deployment-scenarios").exists())
        self.assertFalse((IMAGE_ROOT / "server-configs").exists())

    def test_base_template_is_discovery_only(self):
        config = json.loads((IMAGE_ROOT / "server.generated.json").read_text(encoding="utf-8"))
        self.assertEqual(config["models"], [])

    def test_compose_uses_runtime_selection_not_generated_configs(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("IMAGE_MODELS=${IMAGE_MODELS:-}", compose)
        self.assertIn("IMAGE_BUNDLE=${IMAGE_BUNDLE:-}", compose)
        self.assertIn("IMAGE_RUNTIME_HANDOFF=${IMAGE_RUNTIME_HANDOFF:-}", compose)
        self.assertNotIn("IMAGE_SERVER_CONFIG=", compose)
        self.assertNotIn("IMAGE_DEPLOYMENT=", compose)


if __name__ == "__main__":
    unittest.main()
