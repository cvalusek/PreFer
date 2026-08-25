import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

from prefer_bench.contract import parse_preset
from prefer_bench.paths import REPO_ROOT


PREFER_ROOT = REPO_ROOT / "docker" / "prefer"
SCENARIOS_ROOT = PREFER_ROOT / "preset-scenarios"
INVENTORY_PATH = PREFER_ROOT / "deployment-inventory.generated.json"


def scenario_sources(provider: str | None = None) -> list[dict]:
    sources = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(SCENARIOS_ROOT.rglob("*.json"))]
    if provider is not None:
        sources = [source for source in sources if source.get("provider") == provider]
    return sources


def scenarios(provider: str | None = None) -> list[dict]:
    return [scenario for source in scenario_sources(provider) for scenario in source["scenarios"]]


def deployment_inventory() -> dict:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def catalog_models() -> dict:
    return deployment_inventory()["models"]


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

    def test_model_catalog_is_split_by_family_model_and_quant_dictionary(self) -> None:
        metadata = json.loads((PREFER_ROOT / "preset-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["schema_version"], 2)
        self.assertNotIn("models", metadata)
        seen_keys: set[str] = set()
        for path in sorted((PREFER_ROOT / "models").glob("*/*/model.json")):
            source = json.loads(path.read_text(encoding="utf-8"))
            family, model_slug, _ = path.relative_to(PREFER_ROOT / "models").parts
            self.assertEqual(source["family"], family, path)
            self.assertEqual(source["model_slug"], model_slug, path)
            self.assertTrue(source["quants"], path)
            for lane in source["quants"].values():
                self.assertNotIn(lane["key"], seen_keys, lane["key"])
                seen_keys.add(lane["key"])
        self.assertEqual(seen_keys, set(catalog_models()))
        muse = json.loads(
            (PREFER_ROOT / "models" / "muse" / "muse-glimmer-30b" / "model.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(muse["quants"]), {"ud-q4-k-xl", "ud-q6-k-xl"})
        self.assertEqual(muse["shared"]["settings"]["spec-type"], "draft-dflash")
        self.assertEqual(set(muse["quants"]["ud-q4-k-xl"]["settings"]), {"model"})
        self.assertEqual(set(muse["quants"]["ud-q6-k-xl"]["settings"]), {"model"})

    def test_deployment_inventory_resolves_every_generated_scenario(self) -> None:
        inventory = deployment_inventory()
        self.assertEqual(inventory["schema_version"], "prefer.deployment-inventory.v1")
        for key, model in inventory["models"].items():
            self.assertIn(model["request_model_id"], model["aliases"], key)
        deployments = inventory["deployments"]
        self.assertEqual(len(deployments), len(scenarios()))
        self.assertEqual(len({deployment["id"] for deployment in deployments}), len(deployments))
        for deployment in deployments:
            preset = PREFER_ROOT / "presets" / deployment["preset"].removeprefix("/presets/")
            prestage = PREFER_ROOT / "presets" / deployment["prestage_manifest"].removeprefix("/presets/")
            self.assertTrue(preset.exists(), deployment["id"])
            self.assertTrue(prestage.exists(), deployment["id"])
            self.assertEqual(deployment["environment"]["LLAMA_ARG_MODELS_PRESET"], deployment["preset"])
            self.assertEqual(deployment["environment"]["LLAMA_ARG_MODELS_MAX"], "1")
            self.assertEqual(
                deployment["environment"]["PRESTAGE_MODELS"],
                ",".join(dict.fromkeys(model["key"] for model in deployment["models"])),
            )
            for model in deployment["models"]:
                self.assertIn(model["request_model_id"], model["aliases"], deployment["id"])

        titan_general = next(
            deployment
            for deployment in deployments
            if deployment["id"] == "local/titan-x-pascal/1x/general"
        )
        gemma_e2b = next(model for model in titan_general["models"] if model["key"] == "gemma-4-e2b")
        self.assertEqual(gemma_e2b["section"], "unsloth/gemma-4-E2B-it-qat-GGUF:UD-Q4_K_XL")
        self.assertEqual(gemma_e2b["request_model_id"], "gemma-4-e2b")

        dockerfile = (PREFER_ROOT / "Dockerfile").read_text(encoding="utf-8")
        netskope = (PREFER_ROOT / "Dockerfile.netskope").read_text(encoding="utf-8")
        workflow = (REPO_ROOT / ".github" / "workflows" / "build-prefer.yml").read_text(encoding="utf-8")
        self.assertIn("COPY deployment-inventory.generated.json /deployment-inventory.json", dockerfile)
        self.assertIn(
            "COPY docker/prefer/deployment-inventory.generated.json /deployment-inventory.json", netskope
        )
        self.assertIn("prefer-deployment-inventory-${{ github.sha }}", workflow)
        self.assertIn("io.prefer.deployment-inventory.path=/deployment-inventory.json", workflow)

    def test_runpod_inventory_uses_exact_gpu_ids_and_only_one_initial_multigpu_shape(self) -> None:
        deployments = [item for item in deployment_inventory()["deployments"] if item["provider"] == "runpod"]
        expected_cards = {
            "pro-6000-mig-24gb", "l4", "rtx-3090", "rtx-4090", "rtx-a5000", "rtx-5090",
            "pro-6000-mig-48gb", "l40s", "rtx-6000-ada", "a40", "l40", "rtx-a6000",
            "h100-pcie", "h100-sxm", "a100-pcie", "a100-sxm", "h100-nvl", "rtx-pro-6000",
            "h200", "b200", "b300",
        }
        self.assertEqual({item["hardware"]["gpu_slug"] for item in deployments}, expected_cards)
        self.assertTrue(all(item["hardware"].get("provider_gpu_type_id") for item in deployments))
        multigpu = [item for item in deployments if item["hardware"]["gpu_count"] > 1]
        self.assertEqual([item["id"] for item in multigpu], ["runpod/rtx-pro-6000/2x/deepseek-v4-flash"])
        for deployment in deployments:
            for model in deployment["models"]:
                self.assertEqual(model["cache_type_k"], "f16", deployment["id"])
                self.assertEqual(model["cache_type_v"], "f16", deployment["id"])
                self.assertGreaterEqual(model["context_per_request"], 131072, deployment["id"])

        deepseek = multigpu[0]
        self.assertEqual(deepseek["hardware"]["provider_gpu_type_id"], "NVIDIA RTX PRO 6000 Blackwell Server Edition")
        self.assertEqual(deepseek["models"][0]["quant_slug"], "ud-q4-k-xl")
        self.assertEqual(deepseek["models"][0]["parallel"], 4)
        self.assertEqual(deepseek["models"][0]["context_per_request"], 393216)
        self.assertEqual(deepseek["models"][0]["settings"]["spec-type"], "draft-dspark")

    def test_local_inventory_is_generic_and_contains_only_the_owned_gpu_classes(self) -> None:
        deployments = [item for item in deployment_inventory()["deployments"] if item["provider"] == "local"]
        self.assertEqual(
            {item["hardware"]["gpu_slug"] for item in deployments},
            {"rtx-4060", "rtx-a2000-8gb", "gtx-1070-ti", "titan-x-pascal"},
        )
        for deployment in deployments:
            hardware = deployment["hardware"]
            self.assertEqual(set(hardware), {"gpu_slug", "gpu_name", "gpu_count", "vram_gb_each", "architecture"})
            self.assertEqual(hardware["gpu_count"], 1)
            for model in deployment["models"]:
                expected_cache = (
                    "f16"
                    if model["key"] in {"gemma-4-26b-a4b", "qwen-3.6-35b-a3b-q4"}
                    else "q4_0"
                )
                self.assertEqual(model["cache_type_k"], expected_cache, deployment["id"])
                self.assertEqual(model["cache_type_v"], expected_cache, deployment["id"])

        pascal_e4b = next(
            item for item in deployments if item["id"] == "local/titan-x-pascal/1x/gemma-e4b"
        )["models"][0]["settings"]
        self.assertNotIn("model-draft", pascal_e4b)
        self.assertNotIn("spec-type", pascal_e4b)

        pascal_general = next(
            item for item in deployments if item["id"] == "local/titan-x-pascal/1x/general"
        )
        large_local = {
            model["key"]: model["settings"]
            for model in pascal_general["models"]
            if model["key"] in {"gemma-4-26b-a4b", "qwen-3.6-35b-a3b-q4"}
        }
        self.assertEqual(set(large_local), {"gemma-4-26b-a4b", "qwen-3.6-35b-a3b-q4"})
        for settings in large_local.values():
            self.assertGreater(settings["n-cpu-moe"], 0)
            self.assertFalse(settings["mmap"])
            self.assertNotIn("spec-type", settings)

    def test_aws_scenarios_are_split_by_instance_family(self) -> None:
        self.assertFalse((SCENARIOS_ROOT / "aws.json").exists())
        paths = {path.relative_to(SCENARIOS_ROOT).as_posix() for path in SCENARIOS_ROOT.glob("aws/*/*.json")}
        self.assertEqual(
            paths,
            {"aws/g6/xlarge.json", "aws/g6e/xlarge.json", "aws/g7e/2xlarge.json", "aws/g7e/12xlarge.json"},
        )

    def test_aws_sidecars_exactly_match_scenario_model_keys(self) -> None:
        for scenario in scenarios("aws"):
            expected = list(dict.fromkeys(entry["key"] for entry in scenario["models"]))
            ini_path = PREFER_ROOT / "presets" / scenario["path"]
            sidecar = ini_path.with_suffix(".prestage").read_text(encoding="utf-8").strip().split(",")
            self.assertEqual(sidecar, expected, scenario["path"])
            self.assertTrue(parse_preset(ini_path), scenario["path"])

    def test_every_aws_route_has_at_least_128k_context_per_slot_and_f16_kv(self) -> None:
        for scenario in scenarios("aws"):
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

        catalog = {"models": catalog_models()}
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
        catalog = {"models": catalog_models()}
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
        scenarios_by_path = {scenario["path"]: scenario for scenario in scenarios("aws")}
        for path, model_shapes in expected.items():
            scenario = scenarios_by_path[path]
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
        for scenario in scenarios("aws"):
            preset = (PREFER_ROOT / "presets" / scenario["path"]).read_text(encoding="utf-8")
            self.assertNotIn("qwen-3.6-35b-a3b-1m", preset, scenario["path"])
            self.assertNotIn("yarn-orig-ctx", preset, scenario["path"])

    def test_draft_mtp_models_declare_their_draft_source(self) -> None:
        catalog = {"models": catalog_models()}
        for key, model in catalog["models"].items():
            settings = model["settings"]
            if settings.get("spec-type") == "draft-mtp":
                self.assertTrue(settings.get("model-draft") or model.get("embedded_mtp"), key)

    def test_external_draft_models_have_exact_catalog_artifacts(self) -> None:
        catalog = {"models": catalog_models()}
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
        catalog = {"models": catalog_models()}
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
