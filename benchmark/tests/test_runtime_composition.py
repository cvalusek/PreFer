import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
ENGINES = ("llama-cpp", "audio-cpp", "stable-diffusion-cpp", "sglang", "vllm")


class RuntimeCompositionTests(unittest.TestCase):
    def compose(self, engine: str, *, bundles: str = "", models: str = "", server=None, model=None):
        generator = "generate-presets.py" if engine == "llama-cpp" else "generate.py"
        suffix = ".ini" if engine == "llama-cpp" else ".json"
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output_root = Path(temporary.name)
        config_path = output_root / f"config{suffix}"
        prestage_path = output_root / "config.prestage"
        plan_path = output_root / "plan.json"
        command = [
            sys.executable,
            str(ROOT / "docker" / engine / generator),
            "--compose",
            "--bundles",
            bundles,
            "--models",
            models,
            "--server-overrides",
            json.dumps(server or {}),
            "--model-overrides",
            json.dumps(model or {}),
            "--output",
            str(config_path),
            "--prestage-output",
            str(prestage_path),
            "--plan-output",
            str(plan_path),
        ]
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        if completed.returncode:
            self.fail(f"composition failed ({completed.returncode}): {completed.stderr}\n{completed.stdout}")
        config = config_path.read_text(encoding="utf-8")
        prestage = [item for item in prestage_path.read_text(encoding="utf-8").strip().split(",") if item]
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        return config, prestage, plan

    def compose_handoff(self, engine: str, handoff: dict):
        generator = "generate-presets.py" if engine == "llama-cpp" else "generate.py"
        suffix = ".ini" if engine == "llama-cpp" else ".json"
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output_root = Path(temporary.name)
        handoff_path = output_root / "handoff.json"
        config_path = output_root / f"config{suffix}"
        prestage_path = output_root / "config.prestage"
        plan_path = output_root / "plan.json"
        handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
        command = [
            sys.executable,
            str(ROOT / "docker" / engine / generator),
            "--compose-handoff",
            "--handoff-input",
            str(handoff_path),
            "--output",
            str(config_path),
            "--prestage-output",
            str(prestage_path),
            "--plan-output",
            str(plan_path),
        ]
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        if completed.returncode:
            self.fail(f"handoff composition failed ({completed.returncode}): {completed.stderr}\n{completed.stdout}")
        config = config_path.read_text(encoding="utf-8")
        prestage = [item for item in prestage_path.read_text(encoding="utf-8").strip().split(",") if item]
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        return config, prestage, plan

    @staticmethod
    def handoff(engine: str, *, settings=None, artifacts=None, capabilities=None):
        artifact_records = artifacts or [
            {
                "id": "1" * 64,
                "repository": "owner/runtime-model",
                "revision": "a" * 40,
                "path": "model.gguf",
                "size": 123,
                "sha256": "b" * 64,
                "model_id": "controller-model",
                "role": "model",
                "local_path": "/models/owner/runtime-model/model.gguf",
            }
        ]
        return {
            "schema_version": "prefer.runtime-handoff.v1",
            "catalog_fingerprint": "c" * 64,
            "handoff_fingerprint": "d" * 64,
            "engine": engine,
            "server_settings": {},
            "model_root": "/models",
            "models": [
                {
                    "model_id": "controller-model",
                    "request_model_id": "controller-model",
                    "source": "extension",
                    "family": "controller",
                    "display_name": "Controller Model",
                    "repository": "owner/runtime-model",
                    "repository_path": "/models/owner/runtime-model",
                    "revision": "a" * 40,
                    "quant": "q6-k-xl",
                    "artifact_ids": [artifact["id"] for artifact in artifact_records],
                    "capabilities": capabilities or ["text-generation"],
                    "settings": settings or {},
                }
            ],
            "artifacts": artifact_records,
        }

    def test_llama_requires_explicit_models_and_composes_base_free(self):
        config, prestage, plan = self.compose(
            "llama-cpp",
            models="qwen-3.8-27b,gemma-4-e2b",
            server={"threads": 6},
            model={"qwen-3.8-27b": {"parallel": 2}},
        )
        self.assertEqual(prestage, ["qwen-3.8-27b", "gemma-4-e2b"])
        self.assertIn("threads = 6", config)
        qwen = config.split("[unsloth/Qwen3.8-27B-GGUF:UD-Q6_K_XL]", 1)[1]
        self.assertIn("parallel = 2", qwen)
        self.assertNotIn("base_deployment", plan)

    def test_audio_composes_semantic_bundle_plus_model(self):
        config_text, prestage, _ = self.compose(
            "audio-cpp",
            bundles="speech",
            models="personaplex-7b",
            server={"max_loaded_models": 2},
            model={"personaplex-7b": {"session_options": {"personaplex.graph_arena_mb": 768}}},
        )
        config = json.loads(config_text)
        self.assertEqual(config["max_loaded_models"], 2)
        self.assertEqual(prestage[-1], "personaplex-7b-q4")
        personaplex = next(model for model in config["models"] if model["id"] == "personaplex-7b")
        self.assertEqual(personaplex["session_options"]["personaplex.graph_arena_mb"], 768)

    def test_image_composes_semantic_bundle_and_exact_quant(self):
        config_text, prestage, _ = self.compose(
            "stable-diffusion-cpp",
            bundles="fast",
            models="qwen-image-q6",
            server={"busy_timeout_ms": 7_200_000},
        )
        config = json.loads(config_text)
        self.assertEqual(prestage, ["flux-2-klein-4b-bf16-q8", "z-image-turbo-q8", "qwen-image-q6"])
        qwen = next(model for model in config["models"] if model["id"] == "qwen-image")
        self.assertEqual(qwen["catalog_key"], "qwen-image-q6")
        self.assertEqual(config["busy_timeout_ms"], 7_200_000)

    def test_sglang_composes_one_model_without_hardware_defaults(self):
        config_text, prestage, _ = self.compose(
            "sglang",
            models="minimax-h3-fl2va",
            server={"max_running_requests": 2},
        )
        config = json.loads(config_text)
        self.assertEqual(prestage, ["minimax-h3-fl2va-int8-convrot"])
        self.assertEqual(config["mode"], "diffusion")
        self.assertEqual(config["server"]["max_running_requests"], 2)

    def test_vllm_applies_server_then_model_override(self):
        config_text, prestage, _ = self.compose(
            "vllm",
            models="qwen-3.8-27b",
            model={"qwen-3.8-27b": {"gpu_memory_utilization": 0.91, "max_num_seqs": 6}},
            server={"max_num_seqs": 8},
        )
        config = json.loads(config_text)
        self.assertEqual(prestage, ["qwen-3.8-27b-nvfp4"])
        self.assertEqual(config["server"]["gpu_memory_utilization"], 0.91)
        self.assertEqual(config["server"]["max_num_seqs"], 6)

    def test_runtime_handoff_maps_exact_gguf_and_lora_paths_into_llama(self):
        artifacts = [
            {
                "id": "1" * 64,
                "repository": "owner/runtime-model",
                "revision": "a" * 40,
                "path": "model.gguf",
                "size": 123,
                "sha256": "b" * 64,
                "model_id": "controller-model",
                "role": "model",
                "local_path": "/models/owner/runtime-model/model.gguf",
            },
            {
                "id": "2" * 64,
                "repository": "owner/runtime-lora",
                "revision": "e" * 40,
                "path": "adapter.gguf",
                "size": 45,
                "sha256": "f" * 64,
                "model_id": "controller-model",
                "role": "lora",
                "local_path": "/models/owner/runtime-lora/adapter.gguf",
            },
        ]
        handoff = self.handoff(
            "llama.cpp", settings={"launcher": {"ctx-size": 131072, "parallel": 2}}, artifacts=artifacts
        )
        config, prestage, plan = self.compose_handoff("llama-cpp", handoff)
        self.assertEqual(prestage, ["1" * 64, "2" * 64])
        self.assertIn("model = /models/owner/runtime-model/model.gguf", config)
        self.assertIn("lora = /models/owner/runtime-lora/adapter.gguf", config)
        self.assertIn("ctx-size = 131072", config)
        self.assertIn("parallel = 2", config)
        self.assertEqual(plan["resolved_artifact_ids"], prestage)

    def test_runtime_handoff_exposes_cross_engine_gguf_load_format(self):
        for engine in ("sglang", "vllm"):
            with self.subTest(engine=engine):
                handoff = self.handoff(
                    engine,
                    settings={
                        "model": {"task": "chat", "tasks": ["chat", "completion"]},
                        "launcher": {"load_format": "gguf"},
                    },
                )
                config_text, prestage, plan = self.compose_handoff(engine, handoff)
                config = json.loads(config_text)
                self.assertEqual(prestage, ["1" * 64])
                self.assertIn("--load-format", config["command"])
                self.assertIn("gguf", config["command"])
                self.assertIn("/models/owner/runtime-model/model.gguf", config["command"])
                self.assertEqual(plan["resolved_artifact_ids"], prestage)

    def test_runtime_handoff_maps_audio_and_image_artifacts(self):
        audio = self.handoff(
            "audio.cpp",
            settings={"model": {"task": "tts", "mode": "offline"}, "launcher": {"session_options": {"temperature": 0.7}}},
            capabilities=["speech-generation"],
        )
        audio_text, audio_prestage, _ = self.compose_handoff("audio-cpp", audio)
        audio_config = json.loads(audio_text)
        self.assertEqual(audio_prestage, ["1" * 64])
        self.assertEqual(audio_config["models"][0]["path"], "/models/owner/runtime-model/model.gguf")
        self.assertEqual(audio_config["models"][0]["temperature"], 0.7)

        artifact = {
            "id": "1" * 64,
            "repository": "owner/runtime-model",
            "revision": "a" * 40,
            "path": "model.gguf",
            "size": 123,
            "git_blob_sha1": "b" * 40,
            "model_id": "controller-model",
            "role": "target",
            "local_path": "/models/owner/runtime-model/model.gguf",
        }
        image = self.handoff(
            "stable-diffusion.cpp",
            settings={"launcher": {"args": ["--vae-tiling"]}},
            artifacts=[artifact],
            capabilities=["image-generation"],
        )
        image_text, image_prestage, _ = self.compose_handoff("stable-diffusion-cpp", image)
        image_config = json.loads(image_text)
        self.assertEqual(image_prestage, ["1" * 64])
        self.assertIn("--diffusion-model", image_config["models"][0]["args"])
        self.assertIn("--vae-tiling", image_config["models"][0]["args"])

    def test_every_published_model_lane_can_be_composed_exactly(self):
        for engine in ENGINES:
            inventory = json.loads(
                (ROOT / "docker" / engine / "deployment-inventory.generated.json").read_text(encoding="utf-8")
            )
            for key in inventory["models"]:
                with self.subTest(engine=engine, key=key):
                    _, prestage, plan = self.compose(engine, models=key)
                    self.assertEqual(prestage, [key])
                    self.assertEqual(plan["resolved_model_keys"], [key])

    def test_inventories_are_base_free_and_publish_no_hardware_deployments(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                inventory = json.loads(
                    (ROOT / "docker" / engine / "deployment-inventory.generated.json").read_text(encoding="utf-8")
                )
                self.assertEqual(inventory["deployments"], [])
                composition = inventory["composition"]
                self.assertEqual(composition["schema_version"], "prefer.runtime-composition.v1")
                self.assertNotIn("PREFER_DEPLOYMENT", composition["environment"])
                self.assertIn("PREFER_MODELS", composition["environment"])
                self.assertNotIn("hardware deployment defaults", composition["precedence"])
                self.assertEqual(composition["runtime_handoff_transports"], ["path", "base64"])

    def test_hardware_catalog_is_provider_only_and_contains_no_model_choices(self):
        catalog = json.loads((ROOT / "catalog" / "hardware-profiles.json").read_text(encoding="utf-8"))
        self.assertTrue(catalog["profiles"])
        for profile_id, profile in catalog["profiles"].items():
            with self.subTest(profile=profile_id):
                self.assertIn(profile["provider"], {"aws", "runpod"})
                self.assertFalse(profile_id.startswith("local/"))
                serialized = json.dumps(profile)
                for forbidden in ("model_keys", "models", "quant", "context", "parallel", "cache", "speculative"):
                    self.assertNotIn(f'"{forbidden}"', serialized)

    def test_generators_reject_removed_hardware_base_selector(self):
        for engine in ENGINES:
            generator = "generate-presets.py" if engine == "llama-cpp" else "generate.py"
            with tempfile.TemporaryDirectory() as temporary:
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "docker" / engine / generator),
                        "--compose",
                        "--base",
                        "removed/hardware/profile",
                        "--models",
                        next(iter(json.loads((ROOT / "docker" / engine / "deployment-inventory.generated.json").read_text())["models"])),
                        "--output",
                        str(Path(temporary) / "config"),
                        "--prestage-output",
                        str(Path(temporary) / "prestage"),
                        "--plan-output",
                        str(Path(temporary) / "plan"),
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                )
                with self.subTest(engine=engine):
                    self.assertNotEqual(completed.returncode, 0)

    def test_every_entrypoint_accepts_environment_safe_runtime_handoffs(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                entrypoint = (ROOT / "docker" / engine / "entrypoint.sh").read_text(encoding="utf-8")
                self.assertIn("PREFER_RUNTIME_HANDOFF_BASE64", entrypoint)
                self.assertIn("--handoff-base64-env PREFER_RUNTIME_HANDOFF_BASE64", entrypoint)
                self.assertIn("path and base64 runtime handoff inputs are mutually exclusive", entrypoint)

        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        for prefix in ("LLAMA", "AUDIO", "IMAGE", "SGLANG", "VLLM"):
            self.assertIn(f"{prefix}_RUNTIME_HANDOFF_BASE64=${{{prefix}_RUNTIME_HANDOFF_BASE64:-}}", compose)

    def test_cpu_downloader_is_handoff_only_and_gpu_free(self):
        dockerfile = (ROOT / "docker" / "downloader" / "Dockerfile").read_text(encoding="utf-8").lower()
        entrypoint = (ROOT / "docker" / "downloader" / "entrypoint.sh").read_text(encoding="utf-8")
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("from debian:bookworm-slim", dockerfile)
        self.assertNotIn("cuda", dockerfile)
        self.assertNotIn("nvidia", dockerfile)
        self.assertIn("PREFER_RUNTIME_HANDOFF", entrypoint)
        self.assertIn("prefer_download_runtime_manifest", entrypoint)
        self.assertIn("profiles: [downloader]", compose)
        self.assertNotIn("capabilities: [gpu]", compose.split("  downloader:", 1)[1].split("  image:", 1)[0])

    def test_images_embed_catalog_sources_but_not_weights(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                dockerfile = (ROOT / "docker" / engine / "Dockerfile").read_text(encoding="utf-8")
                self.assertIn("/prefer-catalog/", dockerfile)
                self.assertNotRegex(dockerfile, r"COPY .*\.(?:gguf|safetensors|bin)(?:\s|$)")


if __name__ == "__main__":
    unittest.main()
