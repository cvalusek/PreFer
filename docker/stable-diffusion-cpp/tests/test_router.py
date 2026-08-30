from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
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

    def test_config_rejects_multiple_resident_models(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.json"
            path.write_text(
                json.dumps({"max_loaded_models": 2, "models": [{"id": "example"}]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "max_loaded_models=1"):
                router.load_config(path)


if __name__ == "__main__":
    unittest.main()
