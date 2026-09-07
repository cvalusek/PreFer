import importlib.util
import json
from pathlib import Path
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


class SGLangVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gateway_module = load_gateway_module()

    def test_catalog_and_inventory_keep_video_modes_explicit(self) -> None:
        inventory = json.loads(
            (SGLANG_ROOT / "deployment-inventory.generated.json").read_text(encoding="utf-8")
        )
        self.assertEqual(inventory["schema_version"], "prefer.sglang-deployment-inventory.v2")
        self.assertEqual(inventory["runtime_modes"], ["diffusion", "text"])
        self.assertIn("minimax-h3", inventory["model_profiles"])
        fl2va = inventory["models"]["minimax-h3-fl2va-int8-convrot"]
        ref2va = inventory["models"]["minimax-h3-ref2va-int8-convrot"]
        self.assertEqual(fl2va["runtime_mode"], "diffusion")
        self.assertEqual(fl2va["tasks"], ["t2va", "fl2va"])
        self.assertEqual(ref2va["tasks"], ["ref2va"])
        self.assertEqual(fl2va["output_contract"]["container"], "mp4")
        self.assertEqual(fl2va["output_contract"]["fps"], 24)
        self.assertEqual(fl2va["artifact_bytes"], 42470585471)
        self.assertEqual(ref2va["artifact_bytes"], 42470585471)
        self.assertEqual(
            inventory["model_profiles"]["minimax-h3"]["runtime_modes"],
            ["diffusion"],
        )
        deployments = {deployment["id"]: deployment for deployment in inventory["deployments"]}
        self.assertIn("local/rtx-4090/1x/h3-fl2va", deployments)
        self.assertIn("aws/g6e/xlarge/h3-fl2va", deployments)
        self.assertIn("aws/g7e/2xlarge/h3-ref2va", deployments)
        self.assertEqual(
            deployments["aws/g7e/2xlarge/h3-fl2va"]["runtime_modes"],
            ["diffusion"],
        )

    def test_diffusion_command_uses_sglang_serve_without_text_model_flag(self) -> None:
        config = json.loads(
            (
                SGLANG_ROOT
                / "server-configs"
                / "aws"
                / "g7e"
                / "2xlarge"
                / "h3-fl2va.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(config["mode"], "diffusion")
        self.assertEqual(config["command"][:2], ["sglang", "serve"])
        self.assertIn("--model-type", config["command"])
        self.assertIn("diffusion", config["command"])
        self.assertIn("--revision", config["command"])
        self.assertIn("--pin-cpu-memory", config["command"])
        self.assertIn("false", config["command"])
        self.assertNotIn("--served-model-name", config["command"])
        self.assertEqual(config["gateway"]["upstream_port"], 30001)

    def test_gateway_normalizes_aliases_and_rejects_remote_inputs(self) -> None:
        gateway_module = self.gateway_module
        source_config = json.loads(
            (
                SGLANG_ROOT
                / "server-configs"
                / "local"
                / "rtx-4090"
                / "1x"
                / "h3-fl2va.json"
            ).read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_root = root / "inputs"
            input_root.mkdir()
            media = input_root / "frame.png"
            media.write_bytes(b"PNG")
            source_config["gateway"]["input_mount"] = str(input_root)
            source_config["gateway"]["output_mount"] = str(root / "outputs")
            gateway = gateway_module.VideoGateway(source_config, [])
            normalized = gateway.normalize_request(
                {
                    "model": "i2v",
                    "task": "i2v",
                    "prompt": "A small paper boat crosses a moonlit lake.",
                    "seconds": 4,
                    "conditions": [{"uri": media.as_uri()}],
                }
            )
            self.assertEqual(normalized["model"], "MiniMaxAI/MiniMax-H3")
            self.assertEqual(normalized["task"], "fl2va")
            self.assertEqual(normalized["conditions"][0]["uri"], media.resolve().as_uri())
            with self.assertRaises(gateway_module.GatewayError) as context:
                gateway.normalize_request(
                    {
                        "model": "t2v",
                        "task": "t2v",
                        "prompt": "remote input",
                        "conditions": [{"uri": "https://example.com/frame.png"}],
                    }
                )
            self.assertEqual(context.exception.code, "remote_input_uri")

    def test_gateway_multipart_parser_preserves_uploaded_payload(self) -> None:
        gateway_module = self.gateway_module
        content_type = 'multipart/form-data; boundary="prefer-test"'
        body = (
            b"--prefer-test\r\n"
            b'Content-Disposition: form-data; name="request"\r\n'
            b"\r\n"
            b'{"model":"t2v","task":"t2v","conditions":[{"upload":"frame"}]}\r\n'
            b"--prefer-test\r\n"
            b'Content-Disposition: form-data; name="frame"; filename="frame.bin"\r\n'
            b"Content-Type: application/octet-stream\r\n"
            b"\r\n"
            b"payload-ending-in-newline\n"
            b"\r\n--prefer-test--\r\n"
        )
        fields, files = gateway_module.parse_multipart(content_type, body)
        self.assertEqual(json.loads(fields["request"])["task"], "t2v")
        self.assertEqual(files["frame"][0], "frame.bin")
        self.assertEqual(files["frame"][1], b"payload-ending-in-newline\n")


if __name__ == "__main__":
    unittest.main()
