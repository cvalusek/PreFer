import json
import unittest

from prefer_bench.diagnostics import (
    classify_runtime_failure,
    linux_amd64_manifest_digests,
    manifest_failure_code,
    reason_category,
)
from prefer_bench.local import LANES
from prefer_bench.paths import REPO_ROOT


class DiagnosticAndCompatibilityTests(unittest.TestCase):
    def test_legacy_hardware_presets_and_detection_are_removed(self) -> None:
        llama_root = REPO_ROOT / "docker" / "llama-cpp"
        self.assertFalse((llama_root / "presets").exists())
        self.assertFalse((llama_root / "detect-preset.sh").exists())
        dockerfile = (llama_root / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("server-cuda-b10362", dockerfile)
        self.assertIn("sha256:182a26fbd68d1774860bd2a0fb5581ba3047974307eaeee64930d8bf889e0c0c", dockerfile)

    def test_historical_lane_is_published_immutable_b9982(self) -> None:
        candidate = LANES["b9982"]
        self.assertEqual(candidate["source_commit"], "99f3dc32296f825fec94f202da1e9fede1e78cf9")
        self.assertEqual(candidate["manifest_digest"], "sha256:3a8429364531aa324a477f5fd3f9a9472ca16164c9c5fbc5b202629068263e76")
        self.assertEqual(
            candidate["base_image"],
            "ghcr.io/ggml-org/llama.cpp@sha256:3a8429364531aa324a477f5fd3f9a9472ca16164c9c5fbc5b202629068263e76",
        )
        self.assertNotIn("b9990", LANES)

    def test_current_lane_is_published_immutable_b10362(self) -> None:
        current = LANES["current"]
        self.assertEqual(current["revision"], "b10362")
        self.assertEqual(current["source_commit"], "4801e3c567d5131dd41b387df5f2d4b1370d92be")
        self.assertEqual(current["manifest_digest"], "sha256:182a26fbd68d1774860bd2a0fb5581ba3047974307eaeee64930d8bf889e0c0c")

        catalog = json.loads((REPO_ROOT / "docker" / "llama-cpp" / "preset-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(
            catalog["runtime"]["platform_manifests"],
            {
                "linux/amd64": "sha256:1caad187e691f18327d9050464f6884ae193fd7151b71f3a192f21213a59208f",
                "linux/arm64": "sha256:ea625a2c5910867fbaff88f8f7cf87b0dbd9948743c13ec6db42036b32d50073",
            },
        )

    def test_manifest_failures_are_not_collapsed_into_build_failures(self) -> None:
        self.assertEqual(manifest_failure_code("manifest unknown"), "image_manifest_unavailable")
        self.assertEqual(manifest_failure_code("dial tcp: timeout"), "image_manifest_check_failed")
        self.assertEqual(reason_category("image_manifest_unavailable"), "image_manifest_unavailable")
        payload = [
            {
                "Descriptor": {
                    "digest": "sha256:" + "a" * 64,
                    "platform": {"os": "linux", "architecture": "amd64"},
                }
            },
            {
                "Descriptor": {
                    "digest": "sha256:" + "b" * 64,
                    "platform": {"os": "linux", "architecture": "arm64"},
                }
            },
        ]
        self.assertEqual(linux_amd64_manifest_digests(payload), {"sha256:" + "a" * 64})

    def test_pascal_tile_cache_and_generic_load_diagnostics_are_distinct(self) -> None:
        tile = classify_runtime_failure(
            "/app/fattn-tile.cuh:1321 fatal Li512ELi512",
            error_detail="model failed to load",
            preset="12gb.ini",
            backend_revision="version: 9843 (86b94708f)",
        )
        self.assertEqual(tile["category"], "unsupported_combination")
        self.assertEqual(tile["code"], "llama_cpp_e4b_mtp_pascal_fattn_tile")

        cache = classify_runtime_failure("V cache quantization requires flash_attn")
        self.assertEqual(cache["code"], "unsupported_quantized_v_cache_without_flash_attention")

        memory = classify_runtime_failure("CUDA error: out of memory")
        self.assertEqual(memory["category"], "resource_limit")

        generic = classify_runtime_failure("", error_detail="selected model failed to load")
        self.assertEqual(generic["category"], "model_load_failure")


if __name__ == "__main__":
    unittest.main()
