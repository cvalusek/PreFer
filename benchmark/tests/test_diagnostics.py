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
        self.assertIn("server-cuda-b11058", dockerfile)
        self.assertIn("sha256:480f67114291c698d2b13097e0e3efdd57e81aa3a9de6720564c307663868a59", dockerfile)

    def test_historical_lane_is_published_immutable_b9982(self) -> None:
        candidate = LANES["b9982"]
        self.assertEqual(candidate["source_commit"], "99f3dc32296f825fec94f202da1e9fede1e78cf9")
        self.assertEqual(candidate["manifest_digest"], "sha256:3a8429364531aa324a477f5fd3f9a9472ca16164c9c5fbc5b202629068263e76")
        self.assertEqual(
            candidate["base_image"],
            "ghcr.io/ggml-org/llama.cpp@sha256:3a8429364531aa324a477f5fd3f9a9472ca16164c9c5fbc5b202629068263e76",
        )
        self.assertNotIn("b9990", LANES)

    def test_current_lane_is_published_immutable_b11058(self) -> None:
        current = LANES["current"]
        self.assertEqual(current["revision"], "b11058")
        self.assertEqual(current["source_commit"], "f072b103714dfa1eee531f80b24512faf38e3dd2")
        self.assertEqual(current["manifest_digest"], "sha256:480f67114291c698d2b13097e0e3efdd57e81aa3a9de6720564c307663868a59")
        self.assertEqual(LANES["b10362"]["revision"], "b10362")

        catalog = json.loads((REPO_ROOT / "docker" / "llama-cpp" / "preset-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(
            catalog["runtime"]["platform_manifests"],
            {
                "linux/amd64": "sha256:fb70beb2887ac5127d3982ec6d80feb3d2cc36058e0410d90696febe533a83ae",
                "linux/arm64": "sha256:ff1005faa7bd7432f9a8c7fb94380c94450f7e85b5cd8be2b68f6c86992a5044",
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
