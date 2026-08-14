import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

from prefer_bench.contract import parse_preset
from prefer_bench.paths import REPO_ROOT


PREFER_ROOT = REPO_ROOT / "docker" / "prefer"
SCENARIOS_PATH = PREFER_ROOT / "preset-scenarios" / "aws.json"


def effective_preset_settings(path: Path) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1]
            sections[current] = {}
            continue
        if current is not None and "=" in line:
            key, value = line.split("=", 1)
            sections[current][key.strip()] = value.strip()

    defaults = sections.pop("*", {})
    return {section: {**defaults, **settings} for section, settings in sections.items()}


class GeneratedPresetTests(unittest.TestCase):
    def test_generated_outputs_are_current(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(PREFER_ROOT / "generate-presets.py"), "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_aws_sidecars_exactly_match_scenario_model_keys(self) -> None:
        source = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
        for scenario in source["scenarios"]:
            expected = list(dict.fromkeys(entry["key"] for entry in scenario["models"]))
            ini_path = PREFER_ROOT / "presets" / scenario["path"]
            sidecar = ini_path.with_suffix(".prestage").read_text(encoding="utf-8").strip().split(",")
            self.assertEqual(sidecar, expected, scenario["path"])
            self.assertTrue(parse_preset(ini_path), scenario["path"])

    def test_every_aws_route_has_at_least_128k_context_per_slot_and_f16_kv(self) -> None:
        source = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
        for scenario in source["scenarios"]:
            defaults = scenario.get("defaults", {})
            for entry in scenario["models"]:
                settings = {**defaults, **entry.get("overrides", {})}
                self.assertEqual(settings["cache-type-k"], "f16", scenario["path"])
                self.assertEqual(settings["cache-type-v"], "f16", scenario["path"])
                self.assertGreaterEqual(
                    int(settings["ctx-size"]) // int(settings["parallel"]),
                    131072,
                    f"{scenario['path']}:{entry['key']}",
                )

    def test_deepseek_0731_is_quality_quant_with_dspark(self) -> None:
        preset_path = PREFER_ROOT / "presets" / "aws" / "g7e" / "12xlarge" / "deepseek-v4-flash-0731.ini"
        preset = preset_path.read_text(encoding="utf-8")
        self.assertIn("UD-Q4_K_XL", preset)
        self.assertIn("spec-type = draft-dspark", preset)
        self.assertIn("spec-draft-n-max = 5", preset)
        self.assertNotIn("IQ1", preset)
        self.assertNotIn("IQ2", preset)
        settings = next(iter(effective_preset_settings(preset_path).values()))
        self.assertEqual(settings["ctx-size"], "1572864")
        self.assertEqual(settings["parallel"], "4")

    def test_muse_presets_use_pinned_quality_lanes_with_dflash(self) -> None:
        cases = [
            ("aws/g6/xlarge/muse.ini", "muse-glimmer-30b-q4", "UD-Q4_K_XL", 131072, 1),
            ("aws/g6e/xlarge/muse.ini", "muse-glimmer-30b-q6", "UD-Q6_K_XL", 262144, 2),
            ("aws/g7e/2xlarge/muse.ini", "muse-glimmer-30b-q6", "UD-Q6_K_XL", 524288, 4),
        ]
        for preset_name, prestage_key, quant, ctx_size, parallel in cases:
            preset_path = PREFER_ROOT / "presets" / preset_name
            sections = effective_preset_settings(preset_path)
            self.assertEqual(len(sections), 1, preset_name)
            settings = next(iter(sections.values()))
            self.assertIn(quant, settings["model"], preset_name)
            self.assertTrue(settings["model-draft"].endswith("/dflash-kquant.gguf"), preset_name)
            self.assertTrue(settings["mmproj"].endswith("/mmproj-kquant.gguf"), preset_name)
            self.assertEqual(settings["spec-type"], "draft-dflash", preset_name)
            self.assertEqual(settings["spec-draft-n-max"], "15", preset_name)
            self.assertEqual(settings["cache-type-k"], "f16", preset_name)
            self.assertEqual(settings["cache-type-v"], "f16", preset_name)
            self.assertEqual(settings["ctx-size"], str(ctx_size), preset_name)
            self.assertEqual(settings["parallel"], str(parallel), preset_name)
            self.assertEqual(settings["load-on-startup"], "true", preset_name)
            self.assertEqual(preset_path.with_suffix(".prestage").read_text(encoding="utf-8").strip(), prestage_key)

        catalog = json.loads((PREFER_ROOT / "preset-catalog.json").read_text(encoding="utf-8"))
        for key in ("muse-glimmer-30b-q4", "muse-glimmer-30b-q6"):
            model = catalog["models"][key]
            self.assertEqual(model["lineage"]["revision"], "90625aaf7c8d5338df3779e3f2ef1b8c9e669252")
            self.assertEqual(model["downloads"][0]["revision"], "faa5b025c584459c13febfa5c59883516710ae39")
            self.assertEqual(model["runtime_requirement"]["llama_cpp_merge"], "62bf73d25c53b8161f8a22894d4f90c4aebbd7d0")
            self.assertEqual(model["settings"]["top-k"], 64)
            self.assertEqual(model["settings"]["min-p"], 0.0)

    def test_qwen_35_keeps_parallel_vision_without_mtp(self) -> None:
        preset_path = PREFER_ROOT / "presets" / "aws" / "g6" / "xlarge" / "general.ini"
        models = {model["canonical_id"]: model for model in parse_preset(preset_path)}
        qwen = models["unsloth/Qwen3.5-9B-GGUF:UD-Q4_K_XL"]
        self.assertIsNone(qwen["spec_type"])
        self.assertIsNone(qwen["spec_draft_n_max"])
        preset = preset_path.read_text(encoding="utf-8")
        self.assertIn("mmproj = /models/unsloth/Qwen3.5-9B-GGUF/mmproj-F16.gguf", preset)
        self.assertNotIn("unsloth/Qwen3.5-9B-MTP-GGUF", preset)

    def test_qwen_38_27b_uses_pinned_q6_with_embedded_mtp(self) -> None:
        catalog = json.loads((PREFER_ROOT / "preset-catalog.json").read_text(encoding="utf-8"))
        self.assertNotIn("qwen-3.6-27b", catalog["models"])
        qwen = catalog["models"]["qwen-3.8-27b"]
        self.assertEqual(qwen["section"], "unsloth/Qwen3.8-27B-GGUF:UD-Q6_K_XL")
        self.assertEqual(qwen["aliases"], ["qwen-3.8-27b"])
        self.assertTrue(qwen["embedded_mtp"])
        self.assertEqual(qwen["settings"]["spec-type"], "draft-mtp")
        self.assertEqual(qwen["settings"]["spec-draft-n-max"], 2)
        self.assertNotIn("mmproj", qwen["settings"])
        self.assertEqual(qwen["downloads"], [{
            "repo": "unsloth/Qwen3.8-27B-GGUF",
            "revision": "4604b899a826000505a834e623272db5b7fd62f6",
            "include": ["Qwen3.8-27B-UD-Q6_K_XL.gguf"],
        }])
        self.assertEqual(qwen["artifacts"], [{
            "role": "model",
            "repo": "unsloth/Qwen3.8-27B-GGUF",
            "path": "Qwen3.8-27B-UD-Q6_K_XL.gguf",
            "size": 25924152384,
            "sha256": "739202186fd9389bb58497c58b56c8a0d4253d99d20131e6a0427e363e678fc8",
        }])

    def test_single_model_aws_presets_match_their_bundle_routes(self) -> None:
        cases = [
            ("aws/g6/xlarge/general.ini", "aws/g6/xlarge/gemma-e2b.ini", "unsloth/gemma-4-E2B-it-qat-GGUF:UD-Q4_K_XL"),
            ("aws/g6/xlarge/general.ini", "aws/g6/xlarge/gemma-e4b.ini", "unsloth/gemma-4-E4B-it-qat-GGUF:UD-Q4_K_XL"),
            ("aws/g6/xlarge/general.ini", "aws/g6/xlarge/gemma-12b.ini", "unsloth/gemma-4-12B-it-qat-GGUF:UD-Q4_K_XL"),
            ("aws/g6/xlarge/general.ini", "aws/g6/xlarge/qwen-9b.ini", "unsloth/Qwen3.5-9B-GGUF:UD-Q4_K_XL"),
            ("aws/g6e/xlarge/gemma.ini", "aws/g6e/xlarge/gemma-26b-a4b.ini", "unsloth/gemma-4-26B-A4B-it-qat-GGUF:UD-Q4_K_XL"),
            ("aws/g6e/xlarge/gemma.ini", "aws/g6e/xlarge/gemma-31b.ini", "unsloth/gemma-4-31B-it-qat-GGUF:UD-Q4_K_XL"),
            ("aws/g6e/xlarge/qwen.ini", "aws/g6e/xlarge/qwen-35b-a3b.ini", "unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q6_K_XL"),
            ("aws/g6e/xlarge/qwen.ini", "aws/g6e/xlarge/qwen-27b.ini", "unsloth/Qwen3.8-27B-GGUF:UD-Q6_K_XL"),
            ("aws/g7e/2xlarge/qwen.ini", "aws/g7e/2xlarge/qwen-35b-a3b.ini", "unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q6_K_XL"),
            ("aws/g7e/2xlarge/qwen.ini", "aws/g7e/2xlarge/qwen-27b.ini", "unsloth/Qwen3.8-27B-GGUF:UD-Q6_K_XL"),
            ("aws/g7e/2xlarge/gemma.ini", "aws/g7e/2xlarge/gemma-26b-a4b.ini", "unsloth/gemma-4-26B-A4B-it-qat-GGUF:UD-Q4_K_XL"),
            ("aws/g7e/2xlarge/gemma.ini", "aws/g7e/2xlarge/gemma-31b.ini", "unsloth/gemma-4-31B-it-qat-GGUF:UD-Q4_K_XL"),
            ("aws/g7e/2xlarge/general.ini", "aws/g7e/2xlarge/glm-4.7-flash.ini", "unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF:UD-Q6_K_XL"),
        ]
        for bundle_name, single_name, section in cases:
            bundle = effective_preset_settings(PREFER_ROOT / "presets" / bundle_name)
            single_path = PREFER_ROOT / "presets" / single_name
            single = effective_preset_settings(single_path)
            self.assertEqual(list(single), [section], single_name)
            self.assertEqual(single[section].pop("load-on-startup"), "true", single_name)
            self.assertEqual(single[section], bundle[section], single_name)
            self.assertNotIn("[*]", single_path.read_text(encoding="utf-8"), single_name)
            self.assertNotIn(",", single_path.with_suffix(".prestage").read_text(encoding="utf-8"), single_name)

    def test_cumulative_general_presets_use_one_best_lane_per_model(self) -> None:
        expected = {
            "aws/g6/xlarge/general.ini": {
                "gemma-4-e2b": (524288, 4),
                "gemma-4-e4b": (524288, 4),
                "gemma-4-12b": (524288, 4),
                "qwen-3.5-9b": (262144, 2),
                "muse-glimmer-30b-q4": (131072, 1),
            },
            "aws/g6e/xlarge/general.ini": {
                "gemma-4-e2b": (524288, 4),
                "gemma-4-e4b": (524288, 4),
                "gemma-4-12b": (524288, 4),
                "gemma-4-26b-a4b": (524288, 2),
                "gemma-4-31b": (262144, 1),
                "qwen-3.5-9b": (262144, 2),
                "qwen-3.6-35b-a3b": (196608, 1),
                "qwen-3.8-27b": (196608, 1),
                "muse-glimmer-30b-q6": (262144, 2),
            },
            "aws/g7e/2xlarge/general.ini": {
                "gemma-4-e2b": (524288, 4),
                "gemma-4-e4b": (524288, 4),
                "gemma-4-12b": (524288, 4),
                "gemma-4-26b-a4b": (1048576, 4),
                "gemma-4-31b": (524288, 2),
                "qwen-3.5-9b": (262144, 2),
                "qwen-3.6-35b-a3b": (1048576, 4),
                "qwen-3.8-27b": (1048576, 4),
                "glm-4.7-flash": (811008, 4),
                "muse-glimmer-30b-q6": (524288, 4),
            },
        }
        source = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
        scenarios = {scenario["path"]: scenario for scenario in source["scenarios"]}
        for path, model_shapes in expected.items():
            scenario = scenarios[path]
            actual = {
                entry["key"]: (entry["overrides"]["ctx-size"], entry["overrides"]["parallel"])
                for entry in scenario["models"]
            }
            self.assertEqual(actual, model_shapes, path)
            keys = set(actual)
            self.assertFalse({"muse-glimmer-30b-q4", "muse-glimmer-30b-q6"} <= keys, path)

    def test_g6e_qwen_uses_q6_one_by_192k(self) -> None:
        for name in ("qwen.ini", "qwen-27b.ini", "qwen-35b-a3b.ini"):
            preset = PREFER_ROOT / "presets" / "aws" / "g6e" / "xlarge" / name
            for settings in effective_preset_settings(preset).values():
                self.assertIn("UD-Q6_K_XL", settings["model"], name)
                self.assertEqual(settings["ctx-size"], "196608", name)
                self.assertEqual(settings["parallel"], "1", name)

    def test_removed_qwen_yarn_route_is_absent_from_active_presets(self) -> None:
        source = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
        for scenario in source["scenarios"]:
            preset = (PREFER_ROOT / "presets" / scenario["path"]).read_text(encoding="utf-8")
            self.assertNotIn("qwen-3.6-35b-a3b-1m", preset, scenario["path"])
            self.assertNotIn("yarn-orig-ctx", preset, scenario["path"])

    def test_draft_mtp_models_declare_their_draft_source(self) -> None:
        catalog = json.loads((PREFER_ROOT / "preset-catalog.json").read_text(encoding="utf-8"))
        for key, model in catalog["models"].items():
            settings = model["settings"]
            if settings.get("spec-type") == "draft-mtp":
                self.assertTrue(settings.get("model-draft") or model.get("embedded_mtp"), key)

    def test_external_draft_models_have_exact_catalog_artifacts(self) -> None:
        catalog = json.loads((PREFER_ROOT / "preset-catalog.json").read_text(encoding="utf-8"))
        for key, model in catalog["models"].items():
            settings = model["settings"]
            if settings.get("spec-type") in {"draft-dflash", "draft-dspark", "draft-eagle3", "draft-simple"}:
                draft_path = settings.get("model-draft")
                self.assertIsNotNone(draft_path, key)
                exact_paths = {f"/models/{artifact['repo']}/{artifact['path']}" for artifact in model["artifacts"] if artifact["role"] == "draft"}
                self.assertIn(draft_path, exact_paths, key)

    def test_blank_prestage_uses_selected_preset_sidecar(self) -> None:
        downloader = (PREFER_ROOT / "download-models.sh").read_text(encoding="utf-8")
        example_env = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn('if [ -z "${PRESTAGE_MODELS:-}" ]; then', downloader)
        self.assertIn('PRESTAGE_FILE="${PRESET_PATH%.ini}.prestage"', downloader)
        self.assertIn('[ "$model_key" = "none" ]', downloader)
        self.assertIn("\nPRESTAGE_MODELS=\n", f"\n{example_env}")

    def test_generated_downloader_has_catalog_fingerprints_and_exact_artifacts(self) -> None:
        catalog = json.loads((PREFER_ROOT / "preset-catalog.json").read_text(encoding="utf-8"))
        generated = (PREFER_ROOT / "model-downloads.generated.sh").read_text(encoding="utf-8")
        for key, model in catalog["models"].items():
            payload = {
                "schema_version": 1,
                "key": key,
                "downloads": model["downloads"],
                "artifacts": model["artifacts"],
            }
            fingerprint = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            self.assertIn(fingerprint, generated, key)
            for artifact in model["artifacts"]:
                self.assertIn(f"{artifact['repo']}/{artifact['path']}", generated, key)

    def test_s3_staging_uses_ttl_markers_bounded_jobs_and_exact_artifacts(self) -> None:
        downloader = (PREFER_ROOT / "download-models.sh").read_text(encoding="utf-8")
        self.assertIn('MODEL_CACHE_RECHECK_DAYS="${MODEL_CACHE_RECHECK_DAYS:-7}"', downloader)
        self.assertIn('DEFAULT_MODEL_DOWNLOAD_JOBS=4', downloader)
        self.assertIn('MODEL_CACHE_MARKER_DIR="$MODELS_DIR/.prefer-cache/downloads-v1"', downloader)
        self.assertIn('model_key_artifacts "$MODEL_ACTIVE_KEY"', downloader)
        self.assertIn('s5cmd cp "s3://$S3_BUCKET_NAME/$artifact" "$MODELS_DIR/$artifact"', downloader)
        self.assertNotIn('s5cmd sync "${s3_filters[@]}"', downloader)
        self.assertIn('run_model_batch "${MODEL_BATCH[@]}"', downloader)


if __name__ == "__main__":
    unittest.main()
