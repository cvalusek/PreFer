import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from prefer_bench.paths import REPO_ROOT


SGLANG_ROOT = REPO_ROOT / "docker" / "sglang"
GATEWAY_PATH = SGLANG_ROOT / "video_gateway.py"


def load_gateway_module():
    spec = importlib.util.spec_from_file_location("prefer_sglang_video_gateway", GATEWAY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the SGLang video gateway module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compose_video_config(directory: Path) -> dict:
    output = directory / "server.json"
    completed = subprocess.run(
        [sys.executable, str(SGLANG_ROOT / "generate.py"), "--compose", "--models", "minimax-h3-fl2va-int8-convrot",
         "--output", str(output), "--prestage-output", str(directory / "prestage"),
         "--plan-output", str(directory / "plan")],
        cwd=REPO_ROOT, text=True, capture_output=True,
    )
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    return json.loads(output.read_text(encoding="utf-8"))


class SGLangVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gateway_module = load_gateway_module()

    def test_catalog_and_inventory_keep_video_modes_explicit(self):
        inventory = json.loads((SGLANG_ROOT / "deployment-inventory.generated.json").read_text(encoding="utf-8"))
        self.assertEqual(inventory["runtime_modes"], ["diffusion", "text"])
        fl2va = inventory["models"]["minimax-h3-fl2va-int8-convrot"]
        ref2va = inventory["models"]["minimax-h3-ref2va-int8-convrot"]
        self.assertEqual(fl2va["runtime_mode"], "diffusion")
        self.assertEqual(fl2va["tasks"], ["t2va", "fl2va"])
        self.assertEqual(ref2va["tasks"], ["ref2va"])
        self.assertEqual(fl2va["output_contract"]["container"], "mp4")
        self.assertEqual(inventory["deployments"], [])

    def test_diffusion_command_uses_sglang_serve_without_text_model_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            config = compose_video_config(Path(directory))
        self.assertEqual(config["mode"], "diffusion")
        self.assertEqual(config["command"][:2], ["sglang", "serve"])
        self.assertIn("--model-type", config["command"])
        self.assertIn("--component-weights-paths.transformer", config["command"])
        self.assertNotIn("--served-model-name", config["command"])
        self.assertEqual(config["gateway"]["upstream_port"], 30001)

    def test_gateway_distinguishes_worker_failure_from_warmup(self):
        with tempfile.TemporaryDirectory() as directory:
            config = compose_video_config(Path(directory))
        gateway = self.gateway_module.VideoGateway(config, [])
        with self.assertRaises(self.gateway_module.GatewayError) as warming:
            gateway.require_ready()
        self.assertEqual(warming.exception.code, "upstream_not_ready")

        class ExitedProcess:
            def poll(self):
                return 2

        gateway.process = ExitedProcess()
        with self.assertRaises(self.gateway_module.GatewayError) as failed:
            gateway.require_ready()
        self.assertEqual(failed.exception.code, "upstream_failed")

    def test_gateway_multipart_parser_preserves_uploaded_payload(self):
        content_type = 'multipart/form-data; boundary="prefer-test"'
        body = (
            b"--prefer-test\r\nContent-Disposition: form-data; name=\"request\"\r\n\r\n"
            b'{"model":"t2v","task":"t2v","conditions":[{"upload":"frame"}]}\r\n'
            b"--prefer-test\r\nContent-Disposition: form-data; name=\"frame\"; filename=\"frame.bin\"\r\n"
            b"Content-Type: application/octet-stream\r\n\r\npayload-ending-in-newline\n\r\n--prefer-test--\r\n"
        )
        fields, files = self.gateway_module.parse_multipart(content_type, body)
        self.assertEqual(json.loads(fields["request"])["task"], "t2v")
        self.assertEqual(files["frame"][1], b"payload-ending-in-newline\n")


if __name__ == "__main__":
    unittest.main()
