import unittest

from prefer_bench.contract import parse_preset
from prefer_bench.diagnostics import classify_runtime_failure, manifest_failure_code, reason_category
from prefer_bench.local import LANES
from prefer_bench.paths import PRESETS_ROOT, REPO_ROOT


class DiagnosticAndCompatibilityTests(unittest.TestCase):
    def test_pascal_preset_only_removes_e4b_mtp(self) -> None:
        standard_path = PRESETS_ROOT / "12gb.ini"
        pascal_path = PRESETS_ROOT / "12gb-pascal.ini"
        standard = standard_path.read_text(encoding="utf-8").splitlines()
        pascal = pascal_path.read_text(encoding="utf-8").splitlines()
        removed = {
            "model-draft = /models/unsloth/gemma-4-E4B-it-qat-GGUF/mtp-gemma-4-E4B-it.gguf",
            "spec-type = draft-mtp",
            "spec-draft-n-max = 4",
        }
        e4b_start = standard.index("[unsloth/gemma-4-E4B-it-qat-GGUF:UD-Q4_K_XL]")
        next_section = standard.index("[unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q6_K_XL]")
        expected = standard[:e4b_start] + [line for line in standard[e4b_start:next_section] if line not in removed] + standard[next_section:]
        self.assertEqual(pascal, expected)

        standard_models = {model["canonical_id"]: model for model in parse_preset(standard_path)}
        pascal_models = {model["canonical_id"]: model for model in parse_preset(pascal_path)}
        self.assertEqual(set(standard_models), set(pascal_models))
        e4b = "unsloth/gemma-4-E4B-it-qat-GGUF:UD-Q4_K_XL"
        e2b = "unsloth/gemma-4-E2B-it-qat-GGUF:UD-Q4_K_XL"
        self.assertIsNotNone(standard_models[e4b]["model_draft_path"])
        self.assertIsNone(pascal_models[e4b]["model_draft_path"])
        self.assertEqual(standard_models[e2b]["model_draft_path"], pascal_models[e2b]["model_draft_path"])

    def test_pascal_preset_is_explicit_and_does_not_change_detected_tiers(self) -> None:
        detected_tier_names = {path.name for path in PRESETS_ROOT.glob("*gb.ini")}
        self.assertNotIn("12gb-pascal.ini", detected_tier_names)
        self.assertIn("12gb.ini", detected_tier_names)
        dockerfile = (REPO_ROOT / "docker" / "prefer" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("server-cuda-b9843", dockerfile)

    def test_candidate_lane_is_published_immutable_b9982(self) -> None:
        candidate = LANES["b9982"]
        self.assertEqual(candidate["source_commit"], "99f3dc32296f825fec94f202da1e9fede1e78cf9")
        self.assertEqual(candidate["manifest_digest"], "sha256:3a8429364531aa324a477f5fd3f9a9472ca16164c9c5fbc5b202629068263e76")
        self.assertIn("server-cuda-b9982@sha256:", candidate["base_image"])
        self.assertNotIn("b9990", LANES)

    def test_manifest_failures_are_not_collapsed_into_build_failures(self) -> None:
        self.assertEqual(manifest_failure_code("manifest unknown"), "image_manifest_unavailable")
        self.assertEqual(manifest_failure_code("dial tcp: timeout"), "image_manifest_check_failed")
        self.assertEqual(reason_category("image_manifest_unavailable"), "image_manifest_unavailable")

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
