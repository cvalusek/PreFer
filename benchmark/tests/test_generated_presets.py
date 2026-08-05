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
        preset = (PREFER_ROOT / "presets" / "aws" / "g7e" / "12xlarge" / "deepseek-v4-flash-0731.ini").read_text(encoding="utf-8")
        self.assertIn("UD-Q4_K_XL", preset)
        self.assertIn("spec-type = draft-dspark", preset)
        self.assertIn("spec-draft-n-max = 5", preset)
        self.assertNotIn("IQ1", preset)
        self.assertNotIn("IQ2", preset)

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

    def test_s3_staging_uses_ttl_markers_bounded_jobs_and_cache_filters(self) -> None:
        downloader = (PREFER_ROOT / "download-models.sh").read_text(encoding="utf-8")
        self.assertIn('MODEL_CACHE_RECHECK_DAYS="${MODEL_CACHE_RECHECK_DAYS:-7}"', downloader)
        self.assertIn('DEFAULT_MODEL_DOWNLOAD_JOBS=4', downloader)
        self.assertIn('MODEL_CACHE_MARKER_DIR="$MODELS_DIR/.prefer-cache/downloads-v1"', downloader)
        self.assertIn('s3_filters=(--exclude ".cache/*")', downloader)
        self.assertIn('run_model_batch "${MODEL_BATCH[@]}"', downloader)


if __name__ == "__main__":
    unittest.main()
