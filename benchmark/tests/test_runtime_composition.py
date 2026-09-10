import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class RuntimeCompositionTests(unittest.TestCase):
    def compose(self, engine: str, *, base: str, bundles: str = "", models: str = "", server=None, model=None):
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
            "--base",
            base,
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

    def compose_handoff(self, engine: str, handoff: dict, *, base: str):
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
            "--base",
            base,
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

    def test_llama_bundle_and_direct_model_are_additive(self):
        config, prestage, plan = self.compose(
            "llama-cpp",
            base="aws/g7e/2xlarge/general",
            bundles="gemma",
            models="qwen-3.8-27b",
            server={"threads": 6},
            model={"qwen-3.8-27b": {"parallel": 2}},
        )
        self.assertEqual(prestage, ["gemma-4-26b-a4b", "gemma-4-31b", "qwen-3.8-27b"])
        self.assertIn("threads = 6", config)
        qwen = config.split("[unsloth/Qwen3.8-27B-GGUF:UD-Q6_K_XL]", 1)[1]
        self.assertIn("parallel = 2", qwen)
        self.assertEqual(plan["schema_version"], "prefer.runtime-plan.v1")

    def test_llama_exact_lane_replaces_bundle_lane(self):
        _, prestage, _ = self.compose(
            "llama-cpp",
            base="aws/g7e/2xlarge/general",
            bundles="ornith",
            models="ornith-1.5-9b-q4",
        )
        self.assertIn("ornith-1.5-9b-q4", prestage)
        self.assertNotIn("ornith-1.5-9b-q8", prestage)
        self.assertIn("ornith-1.5-35b-a3b-q8", prestage)

    def test_audio_composes_bundle_plus_model(self):
        config_text, prestage, _ = self.compose(
            "audio-cpp",
            base="audio/cuda12",
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

    def test_audio_nested_model_override_preserves_session_defaults(self):
        config_text, _, _ = self.compose(
            "audio-cpp",
            base="audio/cuda12",
            models="minimax-music-3",
            model={"minimax-music-3": {"session_options": {"mem_saver": False}}},
        )
        config = json.loads(config_text)
        minimax = next(model for model in config["models"] if model["id"] == "minimax-music-3")
        self.assertFalse(minimax["session_options"]["mem_saver"])
        self.assertEqual(minimax["session_options"]["language_model_gguf"], "language_model_q4_0.gguf")

    def test_image_uses_exact_quant_and_preserves_hardware_args(self):
        config_text, prestage, _ = self.compose(
            "stable-diffusion-cpp",
            base="image/cuda12",
            bundles="fast",
            models="qwen-image-q6",
            server={"busy_timeout_ms": 7_200_000},
        )
        config = json.loads(config_text)
        self.assertEqual(prestage, ["flux-2-klein-4b-bf16-q8", "z-image-turbo-q8", "qwen-image-q6"])
        qwen = next(model for model in config["models"] if model["id"] == "qwen-image")
        self.assertEqual(qwen["catalog_key"], "qwen-image-q6")
        self.assertIn("--offload-to-cpu", qwen["args"])

    def test_sglang_switches_to_same_hardware_video_defaults(self):
        config_text, prestage, _ = self.compose(
            "sglang",
            base="aws/g7e/2xlarge/balanced",
            models="minimax-h3-fl2va",
            server={"max_running_requests": 2},
        )
        config = json.loads(config_text)
        self.assertEqual(prestage, ["minimax-h3-fl2va-int8-convrot"])
        self.assertEqual(config["mode"], "diffusion")
        self.assertEqual(config["server"]["performance_mode"], "speed")
        self.assertEqual(config["server"]["max_running_requests"], 2)

    def test_vllm_applies_server_then_model_override(self):
        config_text, prestage, _ = self.compose(
            "vllm",
            base="aws/g7e/2xlarge/performance",
            models="qwen-3.8-27b",
            model={
                "qwen-3.8-27b": {
                    "gpu_memory_utilization": 0.91,
                    "max_num_seqs": 6,
                    "speculative": {"num_speculative_tokens": 2},
                }
            },
            server={"max_num_seqs": 8},
        )
        config = json.loads(config_text)
        self.assertEqual(prestage, ["qwen-3.8-27b-nvfp4"])
        self.assertEqual(config["server"]["gpu_memory_utilization"], 0.91)
        self.assertEqual(config["server"]["max_num_seqs"], 6)
        self.assertTrue(config["server"]["speculative"]["enabled"])
        self.assertEqual(config["server"]["speculative"]["method"], "mtp")
        self.assertEqual(config["server"]["speculative"]["num_speculative_tokens"], 2)

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
            "llama.cpp",
            settings={"launcher": {"ctx-size": 131072, "parallel": 2}},
            artifacts=artifacts,
        )
        config, prestage, plan = self.compose_handoff(
            "llama-cpp", handoff, base="aws/g7e/2xlarge/general"
        )
        self.assertEqual(prestage, ["1" * 64, "2" * 64])
        self.assertIn("[controller-model]", config)
        self.assertIn("model = /models/owner/runtime-model/model.gguf", config)
        self.assertIn("lora = /models/owner/runtime-lora/adapter.gguf", config)
        self.assertIn("ctx-size = 524288", config)
        self.assertIn("parallel = 4", config)
        self.assertEqual(plan["resolved_artifact_ids"], prestage)

    def test_runtime_handoff_exposes_cross_engine_gguf_load_format(self):
        for engine, base in (
            ("sglang", "aws/g7e/2xlarge/balanced"),
            ("vllm", "aws/g7e/2xlarge/performance"),
        ):
            with self.subTest(engine=engine):
                handoff = self.handoff(
                    engine,
                    settings={
                        "model": {"task": "chat", "tasks": ["chat", "completion"]},
                        "launcher": {"load_format": "gguf"},
                    },
                )
                config_text, prestage, plan = self.compose_handoff(engine, handoff, base=base)
                config = json.loads(config_text)
                self.assertEqual(prestage, ["1" * 64])
                self.assertIn("--load-format", config["command"])
                self.assertIn("gguf", config["command"])
                self.assertIn("/models/owner/runtime-model/model.gguf", config["command"])
                self.assertEqual(plan["resolved_artifact_ids"], prestage)

    def test_runtime_handoff_maps_text_lora_directories(self):
        artifacts = [
            {
                "id": "1" * 64,
                "repository": "owner/runtime-model",
                "revision": "a" * 40,
                "path": "config.json",
                "size": 123,
                "git_blob_sha1": "b" * 40,
                "model_id": "controller-model",
                "role": "model",
                "local_path": "/models/owner/runtime-model/config.json",
            },
            {
                "id": "2" * 64,
                "repository": "owner/runtime-lora",
                "revision": "e" * 40,
                "path": "adapter_config.json",
                "size": 45,
                "git_blob_sha1": "f" * 40,
                "model_id": "controller-model",
                "role": "lora",
                "settings": {"adapter_name": "custom"},
                "local_path": "/models/owner/runtime-lora/adapter_config.json",
            },
            {
                "id": "3" * 64,
                "repository": "owner/runtime-lora",
                "revision": "e" * 40,
                "path": "adapter_model.safetensors",
                "size": 456,
                "sha256": "9" * 64,
                "model_id": "controller-model",
                "role": "lora",
                "settings": {"adapter_name": "custom"},
                "local_path": "/models/owner/runtime-lora/adapter_model.safetensors",
            },
        ]
        for engine, base, flag in (
            ("sglang", "aws/g7e/2xlarge/balanced", "--lora-paths"),
            ("vllm", "aws/g7e/2xlarge/performance", "--lora-modules"),
        ):
            with self.subTest(engine=engine):
                handoff = self.handoff(engine, artifacts=artifacts)
                config_text, prestage, _ = self.compose_handoff(engine, handoff, base=base)
                config = json.loads(config_text)
                self.assertEqual(prestage, ["1" * 64, "2" * 64, "3" * 64])
                self.assertIn(flag, config["command"])
                self.assertIn("custom=/models/owner/runtime-lora", config["command"])
                if engine == "vllm":
                    self.assertIn("--enable-lora", config["command"])

    def test_runtime_handoff_maps_audio_and_image_artifacts(self):
        audio = self.handoff(
            "audio.cpp",
            settings={
                "model": {"task": "tts", "mode": "offline"},
                "launcher": {"session_options": {"temperature": 0.7}},
            },
            capabilities=["speech-generation"],
        )
        audio_config_text, audio_prestage, _ = self.compose_handoff(
            "audio-cpp", audio, base="audio/cuda12"
        )
        audio_config = json.loads(audio_config_text)
        self.assertEqual(audio_prestage, ["1" * 64])
        self.assertEqual(audio_config["models"][0]["path"], "/models/owner/runtime-model/model.gguf")
        self.assertEqual(audio_config["models"][0]["temperature"], 0.7)

        image_artifact = {
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
            artifacts=[image_artifact],
            capabilities=["image-generation"],
        )
        image_config_text, image_prestage, _ = self.compose_handoff(
            "stable-diffusion-cpp", image, base="image/cuda12"
        )
        image_config = json.loads(image_config_text)
        self.assertEqual(image_prestage, ["1" * 64])
        self.assertIn("--diffusion-model", image_config["models"][0]["args"])
        self.assertIn("/models/owner/runtime-model/model.gguf", image_config["models"][0]["args"])
        self.assertIn("--vae-tiling", image_config["models"][0]["args"])
        self.assertEqual(image_config["models"][0]["required_files"][0]["download_id"], "1" * 64)
        self.assertEqual(image_config["models"][0]["required_files"][0]["git_blob_sha1"], "b" * 40)

    def test_sglang_nested_override_preserves_speculative_defaults(self):
        config_text, _, _ = self.compose(
            "sglang",
            base="aws/g7e/2xlarge/balanced",
            server={"speculative": {"num_steps": 2}},
        )
        config = json.loads(config_text)
        self.assertTrue(config["server"]["speculative"]["enabled"])
        self.assertEqual(config["server"]["speculative"]["algorithm"], "NEXTN")
        self.assertEqual(config["server"]["speculative"]["num_steps"], 2)

    def test_llama_legacy_detected_preset_remains_composable(self):
        config, prestage, plan = self.compose(
            "llama-cpp",
            base="/presets/12gb.ini",
            server={"threads": 6},
        )
        self.assertEqual(
            prestage,
            [
                "gemma-4-26b-a4b",
                "gemma-4-e2b",
                "gemma-4-e4b",
                "qwen-3.6-35b-a3b",
                "qwen-3.8-27b",
                "glm-4.7-flash",
            ],
        )
        self.assertIn("threads = 6", config)
        self.assertEqual(plan["base_deployment"], "12gb")

    def test_every_published_model_lane_can_be_composed_exactly(self):
        default_bases = {
            "llama-cpp": "aws/g7e/2xlarge/general",
            "audio-cpp": "audio/cuda12",
            "stable-diffusion-cpp": "image/cuda12",
            "sglang": "sglang/cuda13",
            "vllm": "vllm/cuda13",
        }
        for engine, fallback_base in default_bases.items():
            inventory = json.loads(
                (ROOT / "docker" / engine / "deployment-inventory.generated.json").read_text(encoding="utf-8")
            )
            for key in inventory["models"]:
                exact_deployment = next(
                    (
                        deployment["id"]
                        for deployment in inventory["deployments"]
                        if key in {model["key"] for model in deployment.get("models", [])}
                    ),
                    None,
                )
                with self.subTest(engine=engine, key=key):
                    _, prestage, plan = self.compose(
                        engine,
                        base=exact_deployment or fallback_base,
                        models=key,
                    )
                    self.assertEqual(prestage, [key])
                    self.assertEqual(plan["resolved_model_keys"], [key])

    def test_every_inventory_advertises_the_shared_contract(self):
        for engine in ("llama-cpp", "audio-cpp", "stable-diffusion-cpp", "sglang", "vllm"):
            with self.subTest(engine=engine):
                inventory = json.loads(
                    (ROOT / "docker" / engine / "deployment-inventory.generated.json").read_text(encoding="utf-8")
                )
                composition = inventory["composition"]
                self.assertEqual(composition["schema_version"], "prefer.runtime-composition.v1")
                self.assertEqual(composition["effective_plan_path"], "/run/prefer/plan.json")
                self.assertIn("PREFER_DEPLOYMENT", composition["environment"])
                self.assertIn("PREFER_MODELS", composition["environment"])
                self.assertEqual(
                    composition["override_merge"],
                    "objects merge recursively; scalar and array values replace",
                )
                self.assertEqual(composition["precedence"][-1], "raw engine arguments")

    def test_every_deployment_model_preserves_exact_model_and_quant_identity(self):
        for engine in ("llama-cpp", "audio-cpp", "stable-diffusion-cpp", "sglang", "vllm"):
            inventory = json.loads(
                (ROOT / "docker" / engine / "deployment-inventory.generated.json").read_text(encoding="utf-8")
            )
            for deployment in inventory["deployments"]:
                for model in deployment.get("models", []):
                    with self.subTest(engine=engine, deployment=deployment["id"], model=model.get("key")):
                        self.assertTrue(model.get("model_slug"))
                        self.assertTrue(model.get("quant_slug"))

        image_inventory = json.loads(
            (ROOT / "docker" / "stable-diffusion-cpp" / "deployment-inventory.generated.json").read_text(encoding="utf-8")
        )
        local_image = next(
            deployment for deployment in image_inventory["deployments"]
            if deployment["id"] == "local/rtx-4060/1x/general"
        )
        self.assertEqual(local_image["residency"]["offload"]["components"], ["model", "text_encoder", "vae"])

    def test_images_embed_catalog_sources_but_not_weights(self):
        for engine in ("llama-cpp", "audio-cpp", "stable-diffusion-cpp", "sglang", "vllm"):
            with self.subTest(engine=engine):
                dockerfile = (ROOT / "docker" / engine / "Dockerfile").read_text(encoding="utf-8")
                self.assertIn("/prefer-catalog/", dockerfile)
                self.assertNotRegex(dockerfile, r"COPY .*\.(?:gguf|safetensors|bin)(?:\s|$)")


if __name__ == "__main__":
    unittest.main()
