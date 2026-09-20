import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from prefer_bench.paths import REPO_ROOT


SGLANG_ROOT = REPO_ROOT / "docker" / "sglang"


def compose_video_config(directory: Path) -> dict:
    output = directory / "server.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SGLANG_ROOT / "generate.py"),
            "--compose",
            "--models",
            "minimax-h3-fl2va-int8-convrot",
            "--output",
            str(output),
            "--prestage-output",
            str(directory / "prestage"),
            "--plan-output",
            str(directory / "plan"),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    return json.loads(output.read_text(encoding="utf-8"))


class SGLangVideoTests(unittest.TestCase):
    def test_catalog_and_inventory_keep_video_modes_explicit(self):
        inventory = json.loads(
            (SGLANG_ROOT / "deployment-inventory.generated.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(inventory["runtime_modes"], ["diffusion", "text"])
        fl2va = inventory["models"]["minimax-h3-fl2va-int8-convrot"]
        ref2va = inventory["models"]["minimax-h3-ref2va-int8-convrot"]
        self.assertEqual(fl2va["runtime_mode"], "diffusion")
        self.assertEqual(fl2va["tasks"], ["t2va", "fl2va"])
        self.assertEqual(ref2va["tasks"], ["ref2va"])
        self.assertEqual(fl2va["output_contract"]["container"], "mp4")
        self.assertEqual(inventory["deployments"], [])

    def test_diffusion_command_exposes_native_sglang_api(self):
        with tempfile.TemporaryDirectory() as directory:
            config = compose_video_config(Path(directory))
        command = config["command"]
        self.assertEqual(config["mode"], "diffusion")
        self.assertEqual(config["port"], 30000)
        self.assertEqual(command[:2], ["sglang", "serve"])
        self.assertIn("--model-type", command)
        self.assertIn("--component-weights-paths.transformer", command)
        self.assertIn("--model-id", command)
        self.assertIn("--input-save-path", command)
        self.assertEqual(command[command.index("--port") + 1], "30000")
        self.assertNotIn("--served-model-name", command)
        self.assertNotIn("gateway", config)

    def test_native_material_contract_keeps_remote_inputs(self):
        runtime = json.loads((SGLANG_ROOT / "runtime.json").read_text(encoding="utf-8"))
        diffusion = runtime["features"]["diffusion_server"]
        self.assertEqual(diffusion["transport"], "native SGLang /v1/videos API; no PreFer inference proxy")
        self.assertTrue({"http", "https", "data", "base64"}.issubset(diffusion["input_uri_schemes"]))
        self.assertFalse((SGLANG_ROOT / "video_gateway.py").exists())
        dockerfile = (SGLANG_ROOT / "Dockerfile").read_text(encoding="utf-8")
        entrypoint = (SGLANG_ROOT / "entrypoint.sh").read_text(encoding="utf-8")
        self.assertNotIn("video_gateway", dockerfile)
        self.assertNotIn("video_gateway", entrypoint)


if __name__ == "__main__":
    unittest.main()
