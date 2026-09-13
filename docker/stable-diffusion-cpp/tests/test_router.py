from __future__ import annotations

import importlib.util
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prefer_image_router", ROOT / "router.py")
router = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(router)


class RouterTests(unittest.TestCase):
    def test_json_model_selection(self) -> None:
        body = json.dumps({"model": "z-image-turbo", "prompt": "cat"}).encode()
        self.assertEqual(router.extract_model_id("application/json", body), "z-image-turbo")

    def test_multipart_model_selection(self) -> None:
        boundary = "prefer-boundary"
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n"
            "qwen-image-edit-2511\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        self.assertEqual(
            router.extract_model_id(f"multipart/form-data; boundary={boundary}", body),
            "qwen-image-edit-2511",
        )

    def test_header_model_wins(self) -> None:
        body = json.dumps({"model": "z-image-turbo"}).encode()
        self.assertEqual(
            router.extract_model_id("application/json", body, "flux-2-klein-4b"),
            "flux-2-klein-4b",
        )

    def test_sdapi_model_selection_supports_override_settings(self) -> None:
        body = json.dumps(
            {
                "prompt": "cat",
                "override_settings": {"sd_model_checkpoint": "qwen-image"},
            }
        ).encode()
        self.assertEqual(
            router.extract_sdapi_model_id("application/json", body),
            "qwen-image",
        )

    def test_discovery_does_not_load(self) -> None:
        config = {
            "max_loaded_models": 1,
            "idle_unload_ms": 1800000,
            "models": [
                {
                    "id": "example",
                    "capabilities": ["generation"],
                    "required_files": [],
                }
            ],
        }
        manager = router.ModelManager(config)
        try:
            catalog = manager.catalog()
            self.assertEqual(catalog["data"][0]["id"], "example")
            self.assertIsNone(manager.process)
            self.assertIsNone(manager.active_model)
        finally:
            manager.close()

    def test_staged_requires_a_marker_bound_to_the_exact_file_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact_path = root / "owner" / "repo" / "model.bin"
            artifact_path.parent.mkdir(parents=True)
            artifact_path.write_bytes(b"verified bytes")
            artifact = {
                "repo": "owner/repo",
                "revision": "1" * 40,
                "path": "model.bin",
                "size": artifact_path.stat().st_size,
                "sha256": "2" * 64,
                "container_path": str(artifact_path),
            }
            model = {"required_files": [artifact]}
            with mock.patch.object(router, "MODELS_ROOT", root):
                self.assertFalse(router.model_files_present(model))
                artifact_id = router.artifact_download_id(artifact)
                marker = (
                    root
                    / ".prefer-cache"
                    / "downloads-v2"
                    / "verified"
                    / f"{artifact_id}.complete"
                )
                marker.parent.mkdir(parents=True)
                marker.write_text(
                    f"v1\t{artifact_id}\t"
                    f"{router.artifact_stat_signature(artifact_path.stat())}\n",
                    encoding="utf-8",
                )
                self.assertTrue(router.model_files_present(model))
                artifact_path.write_bytes(b"changed! bytes")
                self.assertFalse(router.model_files_present(model))

    def test_completed_none_prestage_keeps_legacy_exact_size_files_usable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact_path = root / "owner" / "repo" / "model.bin"
            artifact_path.parent.mkdir(parents=True)
            artifact_path.write_bytes(b"legacy verified bytes")
            artifact = {
                "repo": "owner/repo",
                "revision": "1" * 40,
                "path": "model.bin",
                "size": artifact_path.stat().st_size,
                "sha256": "2" * 64,
                "container_path": str(artifact_path),
            }
            status = root / "prestage.status"
            status.write_text("0\n", encoding="utf-8")
            with (
                mock.patch.object(router, "MODELS_ROOT", root),
                mock.patch.object(router, "PRESTAGE_STATUS_PATH", status),
            ):
                self.assertTrue(router.model_files_present({"required_files": [artifact]}))

    def test_runtime_handoff_marker_uses_its_release_bound_download_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact_path = root / "owner" / "repo" / "config.json"
            artifact_path.parent.mkdir(parents=True)
            artifact_path.write_bytes(b"{}")
            artifact = {
                "download_id": "3" * 64,
                "repo": "owner/repo",
                "revision": "1" * 40,
                "path": "config.json",
                "size": artifact_path.stat().st_size,
                "git_blob_sha1": "2" * 40,
                "container_path": str(artifact_path),
            }
            marker = (
                root
                / ".prefer-cache"
                / "downloads-v2"
                / "verified"
                / f"{'3' * 64}.complete"
            )
            marker.parent.mkdir(parents=True)
            marker.write_text(
                f"v1\t{'3' * 64}\t{router.artifact_stat_signature(artifact_path.stat())}\n",
                encoding="utf-8",
            )
            with mock.patch.object(router, "MODELS_ROOT", root):
                self.assertEqual(router.artifact_download_id(artifact), "3" * 64)
                self.assertTrue(router.model_files_present({"required_files": [artifact]}))

    def test_config_rejects_multiple_resident_models(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.json"
            path.write_text(
                json.dumps({"max_loaded_models": 2, "models": [{"id": "example"}]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "max_loaded_models=1"):
                router.load_config(path)

    def test_sdapi_routes_select_and_proxy_one_worker(self) -> None:
        config = {
            "default_model": "generator",
            "max_loaded_models": 1,
            "idle_unload_ms": 1800000,
            "busy_timeout_ms": 1000,
            "max_request_body_bytes": 4096,
            "models": [
                {
                    "id": "generator",
                    "capabilities": ["generation"],
                    "required_files": [
                        {
                            "role": "target",
                            "container_path": "/models/generator.gguf",
                            "sha256": "1" * 64,
                        }
                    ],
                },
                {
                    "id": "editor",
                    "capabilities": ["edit"],
                    "required_files": [
                        {
                            "role": "target",
                            "container_path": "/models/editor.gguf",
                            "sha256": "2" * 64,
                        }
                    ],
                },
            ],
        }
        manager = router.ModelManager(config)
        loaded = []
        proxied = []

        def ensure_model(model_id: str) -> None:
            manager.validate_model(model_id)
            manager.active_model = model_id
            manager.selected_model = model_id
            loaded.append(model_id)

        def proxy(method: str, path: str, headers: dict, body: bytes):
            proxied.append((method, path, body))
            return 200, [("Content-Type", "application/json")], b'{"ok":true}'

        class TestHandler(router.ImageRequestHandler):
            def log_message(self, _format: str, *_args: object) -> None:
                pass

        TestHandler.manager = manager
        server = router.ThreadingHTTPServer(("127.0.0.1", 0), TestHandler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        try:
            with (
                mock.patch.object(manager, "ensure_model", side_effect=ensure_model),
                mock.patch.object(manager, "proxy", side_effect=proxy),
            ):
                connection.request("GET", "/sdapi/v1/sd-models")
                response = connection.getresponse()
                models = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual([model["title"] for model in models], ["generator", "editor"])
                self.assertEqual(loaded, [])

                options_body = json.dumps({"sd_model_checkpoint": "editor"}).encode()
                connection.request(
                    "POST",
                    "/sdapi/v1/options",
                    body=options_body,
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                options = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(options["sd_model_checkpoint"], "editor")
                self.assertEqual(loaded, ["editor"])

                connection.request(
                    "POST",
                    "/sdapi/v1/img2img",
                    body=b"{}",
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read()), {"ok": True})
                self.assertEqual(proxied[-1][:2], ("POST", "/sdapi/v1/img2img"))
                self.assertEqual(loaded[-1], "editor")

                connection.request(
                    "GET", "/sdapi/v1/samplers?model=generator&refresh=1"
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                response.read()
                self.assertEqual(
                    proxied[-1][:2],
                    ("GET", "/sdapi/v1/samplers?refresh=1"),
                )
                self.assertEqual(loaded[-1], "generator")

                connection.request(
                    "OPTIONS",
                    "/sdapi/v1/txt2img",
                    headers={"Origin": "http://localhost:3000"},
                )
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 204)
                self.assertEqual(
                    response.getheader("Access-Control-Allow-Origin"),
                    "*",
                )

                connection.request("GET", "/sdcpp/v1/capabilities")
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 404)
                self.assertEqual(loaded[-1], "generator")
        finally:
            connection.close()
            server.shutdown()
            server.server_close()
            manager.close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
