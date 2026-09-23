import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
AUDIO_ROOT = ROOT / "docker" / "audio-cpp"


class AudioCppTests(unittest.TestCase):
    def test_generated_outputs_are_current(self):
        completed = subprocess.run([sys.executable, str(AUDIO_ROOT / "generate.py"), "--check"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_catalog_is_split_by_model_and_uses_immutable_artifacts(self):
        files = sorted((AUDIO_ROOT / "models").glob("*/*/model.json"))
        self.assertGreaterEqual(len(files), 7)
        for path in files:
            model = json.loads(path.read_text(encoding="utf-8"))
            for lane in model["quants"].values():
                artifacts = lane.get("artifacts") or [lane["artifact"]]
                for artifact in artifacts:
                    self.assertRegex(artifact["revision"], r"^[0-9a-f]{40}$")
                    self.assertGreater(artifact["size"], 0)
                    self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")

    def test_inventory_has_models_and_bundles_but_no_hardware_deployments(self):
        inventory = json.loads((AUDIO_ROOT / "deployment-inventory.generated.json").read_text(encoding="utf-8"))
        self.assertEqual(inventory["deployments"], [])
        self.assertTrue(inventory["models"])
        self.assertIn("speech", inventory["bundles"])
        self.assertNotIn("PREFER_DEPLOYMENT", inventory["composition"]["environment"])
        self.assertFalse((AUDIO_ROOT / "deployment-scenarios").exists())
        self.assertFalse((AUDIO_ROOT / "server-configs").exists())

    def test_checked_in_server_configs_are_empty_base_free_templates(self):
        for name, backend in (("server.cuda.generated.json", "cuda"), ("server.cpu.generated.json", "cpu"), ("server.vulkan.generated.json", "vulkan")):
            config = json.loads((AUDIO_ROOT / name).read_text(encoding="utf-8"))
            self.assertEqual(config["models"], [])
            self.assertEqual(config["backend"], backend)

    def test_images_stage_external_model_volumes_as_root(self):
        for name in ("Dockerfile", "Dockerfile.cpu"):
            dockerfile = (AUDIO_ROOT / name).read_text(encoding="utf-8")
            self.assertNotRegex(dockerfile, r"(?m)^USER (?!root$)")
            self.assertIn("/models", dockerfile)

    def test_compose_exposes_only_base_free_audio_inputs(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("AUDIO_MODELS=${AUDIO_MODELS:-}", compose)
        self.assertIn("AUDIO_BUNDLE=${AUDIO_BUNDLE:-}", compose)
        self.assertIn("AUDIO_RUNTIME_HANDOFF=${AUDIO_RUNTIME_HANDOFF:-}", compose)
        self.assertNotIn("AUDIO_SERVER_CONFIG=", compose)
        self.assertNotIn("AUDIO_DEPLOYMENT=", compose)


if __name__ == "__main__":
    unittest.main()
