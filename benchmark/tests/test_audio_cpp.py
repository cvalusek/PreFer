import json
from pathlib import Path
import subprocess
import sys
import unittest

from prefer_bench.paths import REPO_ROOT


AUDIO_ROOT = REPO_ROOT / "docker" / "audio-cpp"


class AudioCppTests(unittest.TestCase):
    def test_generated_outputs_are_current(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(AUDIO_ROOT / "generate.py"), "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_catalog_is_split_by_model_and_uses_immutable_artifacts(self) -> None:
        seen_keys = set()
        for path in sorted((AUDIO_ROOT / "models").glob("*/*/model.json")):
            source = json.loads(path.read_text(encoding="utf-8"))
            family, model_slug, _ = path.relative_to(AUDIO_ROOT / "models").parts
            self.assertEqual(source["family"], family, path)
            self.assertEqual(source["model_slug"], model_slug, path)
            self.assertEqual(sum(bool(lane.get("primary")) for lane in source["quants"].values()), 1)
            for lane in source["quants"].values():
                self.assertNotIn(lane["key"], seen_keys)
                seen_keys.add(lane["key"])
                artifacts = lane.get("artifacts", [lane.get("artifact")])
                self.assertTrue(all(artifacts))
                for artifact in artifacts:
                    self.assertEqual(len(artifact["revision"]), 40)
                    self.assertEqual(len(artifact["sha256"]), 64)
                    self.assertGreater(artifact["size"], 0)
        self.assertEqual(
            seen_keys,
            {
                "qwen3-tts-0.6b-bf16",
                "qwen3-tts-1.7b-customvoice-bf16",
                "qwen3-tts-1.7b-voicedesign-bf16",
                "qwen3-asr-0.6b-q8",
                "ace-step-1.5-turbo-q8",
                "minimax-music-3-q4",
                "personaplex-7b-q4",
            },
        )

    def test_server_configs_are_lazy_single_residency_with_tts_and_streaming_asr(self) -> None:
        for backend, filename in (("cuda", "server.cuda.generated.json"), ("cpu", "server.cpu.generated.json")):
            config = json.loads((AUDIO_ROOT / filename).read_text(encoding="utf-8"))
            self.assertEqual(config["backend"], backend)
            self.assertTrue(config["lazy_load"])
            self.assertEqual(config["max_loaded_models"], 1)
            self.assertEqual(config["idle_unload_ms"], 1800000)
            self.assertEqual(config["min_free_memory_mb"], 0)
            models = {model["id"]: model for model in config["models"]}
            self.assertEqual(
                set(models),
                {
                    "qwen3-tts-0.6b",
                    "qwen3-tts-1.7b-customvoice",
                    "qwen3-tts-1.7b-voicedesign",
                    "qwen3-asr-0.6b",
                    "ace-step-1.5",
                    "minimax-music-3",
                    "personaplex-7b",
                },
            )
            self.assertEqual(models["qwen3-tts-0.6b"]["task"], "tts")
            self.assertEqual(models["qwen3-tts-0.6b"]["mode"], "offline")
            self.assertEqual(models["qwen3-tts-1.7b-customvoice"]["task"], "tts")
            self.assertEqual(models["qwen3-tts-1.7b-customvoice"]["mode"], "offline")
            self.assertEqual(models["qwen3-tts-1.7b-voicedesign"]["task"], "vdes")
            self.assertEqual(models["qwen3-tts-1.7b-voicedesign"]["mode"], "offline")
            self.assertEqual(models["qwen3-asr-0.6b"]["task"], "asr")
            self.assertEqual(models["qwen3-asr-0.6b"]["mode"], "streaming")
            self.assertEqual(models["ace-step-1.5"]["task"], "gen")
            self.assertEqual(models["ace-step-1.5"]["mode"], "offline")
            self.assertTrue(models["ace-step-1.5"]["session_options"]["mem_saver"])
            self.assertEqual(models["minimax-music-3"]["task"], "gen")
            self.assertEqual(models["minimax-music-3"]["mode"], "offline")
            self.assertEqual(
                models["minimax-music-3"]["path"],
                "/models/audio-cpp/MiniMax-Music3-GGUF",
            )
            self.assertEqual(
                models["minimax-music-3"]["session_options"],
                {
                    "language_model_gguf": "language_model_q4_0.gguf",
                    "rvq_depth_decoder_gguf": "rvq_depth_decoder_q8_0.gguf",
                    "flow_transformer_gguf": "transformer_q4_0.gguf",
                    "mem_saver": True,
                },
            )
            self.assertEqual(models["personaplex-7b"]["task"], "s2s")
            self.assertEqual(models["personaplex-7b"]["mode"], "streaming")
            self.assertEqual(
                models["personaplex-7b"]["session_options"]["personaplex.graph_arena_mb"],
                512,
            )

    def test_inventory_and_images_have_exact_runtime_identity(self) -> None:
        runtime = json.loads((AUDIO_ROOT / "runtime.json").read_text(encoding="utf-8"))
        inventory = json.loads((AUDIO_ROOT / "deployment-inventory.generated.json").read_text(encoding="utf-8"))
        self.assertEqual(inventory["schema_version"], "prefer.audio-deployment-inventory.v1")
        self.assertEqual(len(inventory["catalog_fingerprint"]), 64)
        self.assertEqual(inventory["runtime"]["source_revision"], runtime["runtime"]["source_revision"])
        self.assertEqual(inventory["api"]["live_speech"], "POST /v1/audio/speech/live")
        self.assertEqual(inventory["api"]["tasks"], "POST /v1/tasks/run")
        self.assertEqual(
            inventory["distribution"]["embedded_image_path"],
            "/deployment-inventory.json",
        )
        self.assertEqual(
            inventory["distribution"]["workflow_artifact_name_pattern"],
            "prefer-audio-deployment-inventory-<commit-sha>",
        )
        self.assertEqual(len(inventory["models"]["minimax-music-3-q4"]["artifacts"]), 13)
        self.assertEqual(
            inventory["models"]["minimax-music-3-q4"]["artifact_bytes"],
            sum(
                artifact["size"]
                for artifact in inventory["models"]["minimax-music-3-q4"]["artifacts"]
            ),
        )
        self.assertEqual(
            len(inventory["models"]["minimax-music-3-q4"]["download_fingerprint"]),
            64,
        )
        self.assertEqual(
            inventory["models"]["minimax-music-3-q4"]["server"]["session_options"]["rvq_depth_decoder_gguf"],
            "rvq_depth_decoder_q8_0.gguf",
        )
        self.assertEqual(
            {deployment["image_tag"] for deployment in inventory["deployments"]},
            {"audio-cuda12", "audio-cpu"},
        )
        for deployment in inventory["deployments"]:
            self.assertEqual(deployment["container"]["name"], "prefer-audio")
            self.assertEqual(deployment["container"]["internal_port"], 8080)
            self.assertEqual(deployment["container"]["model_mount"], "/models")
            self.assertEqual(deployment["container"]["voice_mount"], "/voices")
            if deployment["id"] in {"audio/cuda12", "audio/cpu"}:
                self.assertEqual(
                    deployment["environment"]["AUDIO_PRESTAGE_MODELS"],
                    ",".join(deployment["prestage_models"]),
                )
            else:
                self.assertEqual(deployment["environment"]["AUDIO_PRESTAGE_MODELS"], "")
                self.assertEqual(
                    deployment["environment"]["AUDIO_SERVER_CONFIG"],
                    deployment["server_config"],
                )
                self.assertEqual(
                    deployment["prestage_manifest"],
                    deployment["container"]["prestage_manifest"],
                )
                self.assertEqual(
                    deployment["verification"],
                    deployment["verification_status"],
                )
        for variant, dockerfile in (("cuda12", "Dockerfile"), ("cpu", "Dockerfile.cpu")):
            reference = runtime["base_images"][variant]["reference"]
            dockerfile_text = (AUDIO_ROOT / dockerfile).read_text(encoding="utf-8")
            self.assertIn(reference, dockerfile_text)
            self.assertIn("--start-period=4h", dockerfile_text)
            self.assertNotIn("ENV AUDIO_PRESTAGE_MODELS", dockerfile_text)
            self.assertEqual(set(runtime["base_images"][variant]["platform_manifests"]), {"linux/amd64", "linux/arm64"})

    def test_generated_deployment_bundles_and_scenarios_are_controller_ready(self) -> None:
        inventory = json.loads(
            (AUDIO_ROOT / "deployment-inventory.generated.json").read_text(
                encoding="utf-8"
            )
        )
        bundles = inventory["bundles"]
        self.assertEqual(
            set(bundles),
            {"general", "speech", "assistant", "voice-lab", "conversation", "music"},
        )
        self.assertEqual(len(bundles["general"]["models"]), 7)
        self.assertEqual(
            bundles["assistant"]["models"],
            [
                "qwen3-asr-0.6b-q8",
                "qwen3-tts-0.6b-bf16",
                "qwen3-tts-1.7b-customvoice-bf16",
            ],
        )
        self.assertEqual(
            bundles["music"]["models"],
            ["ace-step-1.5-turbo-q8", "minimax-music-3-q4"],
        )

        deployments = {item["id"]: item for item in inventory["deployments"]}
        aws_general = deployments["aws/g6/xlarge/general"]
        self.assertEqual(aws_general["hardware"]["provider_sku"], "g6.xlarge")
        self.assertEqual(aws_general["hardware"]["gpu_name"], "NVIDIA L4")
        self.assertEqual(len(aws_general["models"]), 7)
        self.assertEqual(aws_general["residency"]["max_loaded_models"], 1)
        self.assertGreater(aws_general["staged_artifact_bytes"], 30_000_000_000)

        self.assertIn("local/titan-x-pascal/1x/general", deployments)
        self.assertIn("local/rtx-4060/1x/speech", deployments)
        self.assertNotIn("local/rtx-4060/1x/general", deployments)
        self.assertNotIn("local/gtx-1070-ti/1x/personaplex-7b", deployments)

        runpod_gpu_ids = {
            item["hardware"]["provider_gpu_type_id"]
            for item in deployments.values()
            if item.get("provider") == "runpod"
        }
        self.assertEqual(
            runpod_gpu_ids,
            {
                "NVIDIA L4",
                "NVIDIA RTX PRO 6000 Blackwell Server Edition MIG 1g.24gb",
                "NVIDIA GeForce RTX 3090",
                "NVIDIA GeForce RTX 4090",
                "NVIDIA GeForce RTX 5090",
                "NVIDIA RTX A5000",
                "NVIDIA A40",
                "NVIDIA L40",
                "NVIDIA L40S",
                "NVIDIA RTX PRO 6000 Blackwell Server Edition MIG 2g.48gb",
                "NVIDIA RTX 6000 Ada Generation",
                "NVIDIA RTX A6000",
            },
        )

        for deployment in deployments.values():
            if deployment.get("kind") not in {"bundle", "single-model"}:
                continue
            self.assertEqual(deployment["image_tag"], "audio-cuda12")
            self.assertTrue(deployment["residency"]["lazy_load"])
            self.assertEqual(deployment["residency"]["max_loaded_models"], 1)
            relative_config = deployment["server_config"].removeprefix(
                "/server-configs/"
            )
            config_path = AUDIO_ROOT / "server-configs" / relative_config
            prestage_path = config_path.with_suffix(".prestage")
            self.assertTrue(config_path.is_file(), deployment["id"])
            self.assertTrue(prestage_path.is_file(), deployment["id"])
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["backend"], "cuda")
            self.assertEqual(config["max_loaded_models"], 1)
            self.assertEqual(
                prestage_path.read_text(encoding="utf-8").strip().split(","),
                deployment["prestage_models"],
            )

    def test_compose_and_workflow_keep_product_compatibility_and_distinct_variants(self) -> None:
        compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        workflow = (REPO_ROOT / ".github" / "workflows" / "build-audio.yml").read_text(encoding="utf-8")
        llama_workflow = (REPO_ROOT / ".github" / "workflows" / "build-prefer.yml").read_text(encoding="utf-8")
        self.assertIn("container_name: prefer-llama", compose)
        self.assertIn("container_name: prefer-audio", compose)
        self.assertNotIn("profiles: [audio]", compose)
        self.assertIn("${AUDIO_PORT:-8081}:8080", compose)
        self.assertIn("AUDIO_SERVER_CONFIG=${AUDIO_SERVER_CONFIG:-}", compose)
        self.assertIn("AUDIO_PRESTAGE_MODELS=${AUDIO_PRESTAGE_MODELS:-}", compose)
        self.assertIn("type=raw,value=audio-${{ matrix.variant }}", workflow)
        self.assertIn("type=sha,prefix=audio-${{ matrix.variant }}-sha-", workflow)
        self.assertIn("prefer-audio-deployment-inventory-${{ github.sha }}", workflow)
        self.assertIn("type=raw,value=latest", llama_workflow)
        self.assertIn("type=raw,value=llama-cuda", llama_workflow)


if __name__ == "__main__":
    unittest.main()
