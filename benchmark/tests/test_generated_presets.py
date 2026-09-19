import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
LLAMA_ROOT = ROOT / "docker" / "llama-cpp"


class GeneratedPresetTests(unittest.TestCase):
    def test_generated_outputs_are_current(self):
        completed = subprocess.run(
            [sys.executable, str(LLAMA_ROOT / "generate-presets.py"), "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_hardware_presets_and_local_profiles_are_removed(self):
        self.assertFalse((LLAMA_ROOT / "preset-scenarios").exists())
        self.assertFalse((LLAMA_ROOT / "presets").exists())
        self.assertFalse((LLAMA_ROOT / "detect-preset.sh").exists())
        inventory = json.loads((LLAMA_ROOT / "deployment-inventory.generated.json").read_text(encoding="utf-8"))
        self.assertEqual(inventory["deployments"], [])

    def test_model_catalog_is_split_and_every_artifact_is_immutable(self):
        files = sorted((LLAMA_ROOT / "models").glob("*/*/model.json"))
        self.assertGreater(len(files), 10)
        keys = set()
        destinations = {}
        for path in files:
            model = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("profile", model)
            self.assertIn("quants", model)
            for lane in model["quants"].values():
                key = lane["key"]
                self.assertNotIn(key, keys)
                keys.add(key)
                revisions = {download["repo"]: download["revision"] for download in lane["downloads"]}
                for revision in revisions.values():
                    self.assertRegex(revision, r"^[0-9a-f]{40}$")
                for artifact in lane["artifacts"]:
                    self.assertIn(artifact["repo"], revisions)
                    self.assertGreater(artifact["size"], 0)
                    self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")
                    destination = (artifact["repo"], artifact["path"])
                    identity = (artifact["size"], artifact["sha256"], revisions[artifact["repo"]])
                    if destination in destinations:
                        self.assertEqual(destinations[destination], identity)
                    destinations[destination] = identity

    def test_model_profiles_remain_prompt_ready(self):
        inventory = json.loads((LLAMA_ROOT / "deployment-inventory.generated.json").read_text(encoding="utf-8"))
        self.assertTrue(inventory["model_profiles"])
        for profile in inventory["model_profiles"].values():
            self.assertTrue(profile["prompt_summary"])
            self.assertTrue(profile["architecture"])
            self.assertTrue(profile["capabilities"])
            self.assertTrue(profile["roles"])
            self.assertTrue(profile["evidence"])

    def test_generated_downloader_uses_exact_shared_downloads_v2_contract(self):
        generated = (LLAMA_ROOT / "model-downloads.generated.sh").read_text(encoding="utf-8")
        downloader = (LLAMA_ROOT / "download-models.sh").read_text(encoding="utf-8")
        self.assertIn("llama_model_artifact_ids", generated)
        self.assertIn("llama_artifact_record", generated)
        self.assertIn("prefer_download_runtime_manifest", downloader)
        self.assertIn("/prefer-download-artifacts.sh", downloader)
        self.assertIn("/prefer-runtime-handoff-download.sh", downloader)
        self.assertIn("downloads-v2 verification markers", downloader)
        self.assertNotIn("downloads-v1", downloader)
        self.assertNotIn("LEGACY_SMALL_MODELS", generated)

    def test_runtime_composition_has_no_hardware_precedence(self):
        inventory = json.loads((LLAMA_ROOT / "deployment-inventory.generated.json").read_text(encoding="utf-8"))
        composition = inventory["composition"]
        self.assertNotIn("PREFER_DEPLOYMENT", composition["environment"])
        self.assertNotIn("PREFER_BUNDLE", composition["environment"])
        self.assertEqual(composition["activation"], "required; select models or supply an immutable runtime handoff")
        self.assertNotIn("hardware deployment defaults", composition["precedence"])


if __name__ == "__main__":
    unittest.main()
