import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_SCRIPT = REPO_ROOT / "release" / "build-release.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build-prefer.yml"


class GroupedReleaseTests(unittest.TestCase):
    def build_release(
        self,
        output_dir: Path,
        image_digest: str | None = None,
        package_version: str = "0.0.0-gabcdef0",
    ) -> subprocess.CompletedProcess[str]:
        tooling_dir = output_dir / "tooling-input"
        tooling_dir.mkdir(parents=True)
        tooling_assets = {
            "package": ("prefer-inference-core.tgz", b"package"),
            "cli": ("prefer.mjs", b"cli"),
            "model_catalog": ("prefer-model-catalog.json", b"catalog"),
            "model_catalog_schema": ("prefer-model-catalog.schema.json", b"schema"),
            "model_catalog_extension_schema": (
                "prefer-model-catalog-extension.schema.json",
                b"extension-schema",
            ),
            "resource_profile_schema": (
                "prefer-resource-profile.schema.json",
                b"resource-schema",
            ),
            "model_plan_schema": (
                "prefer-model-plan.schema.json",
                b"plan-schema",
            ),
        }
        manifest_assets: dict[str, dict[str, object]] = {}
        for key, (name, payload) in tooling_assets.items():
            (tooling_dir / name).write_bytes(payload)
            manifest_assets[key] = {
                "asset": name,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        tooling_manifest = {
            "schema_version": "prefer.tooling-build.v1",
            "source_revision": "abcdef0123456789abcdef0123456789abcdef01",
            "package_version": package_version,
            "huggingface_refresh": "live",
            "catalog_fingerprint": "7" * 64,
            "source_fingerprint": "8" * 64,
            "distribution": {"model_weights_embedded": False, "metadata_only": True},
            "assets": manifest_assets,
        }
        tooling_manifest_path = tooling_dir / "prefer-tooling-build.json"
        tooling_manifest_path.write_text(json.dumps(tooling_manifest), encoding="utf-8")
        digests = {
            "llama": "sha256:" + "1" * 64,
            "audio_cuda": "sha256:" + "2" * 64,
            "audio_cpu": "sha256:" + "3" * 64,
            "image": image_digest or "sha256:" + "4" * 64,
            "sglang": "sha256:" + "5" * 64,
            "vllm": "sha256:" + "6" * 64,
        }
        return subprocess.run(
            [
                sys.executable,
                str(RELEASE_SCRIPT),
                "--commit",
                "abcdef0123456789abcdef0123456789abcdef01",
                "--source-repository",
                "https://github.com/cvalusek/PreFer",
                "--image-repository",
                "ghcr.io/CValusek/PreFer",
                "--llama-digest",
                digests["llama"],
                "--audio-cuda-digest",
                digests["audio_cuda"],
                "--audio-cpu-digest",
                digests["audio_cpu"],
                "--image-digest",
                digests["image"],
                "--sglang-digest",
                digests["sglang"],
                "--vllm-digest",
                digests["vllm"],
                "--llama-inventory",
                str(REPO_ROOT / "docker" / "llama-cpp" / "deployment-inventory.generated.json"),
                "--audio-inventory",
                str(REPO_ROOT / "docker" / "audio-cpp" / "deployment-inventory.generated.json"),
                "--image-inventory",
                str(
                    REPO_ROOT
                    / "docker"
                    / "stable-diffusion-cpp"
                    / "deployment-inventory.generated.json"
                ),
                "--sglang-inventory",
                str(
                    REPO_ROOT
                    / "docker"
                    / "sglang"
                    / "deployment-inventory.generated.json"
                ),
                "--vllm-inventory",
                str(
                    REPO_ROOT
                    / "docker"
                    / "vllm"
                    / "deployment-inventory.generated.json"
                ),
                "--tooling-manifest",
                str(tooling_manifest_path),
                "--tooling-dir",
                str(tooling_dir),
                "--output-dir",
                str(output_dir),
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_bundle_binds_every_engine_to_one_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            result = self.build_release(output_dir)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((output_dir / "prefer-release.json").read_text(encoding="utf-8"))

            self.assertEqual(manifest["schema_version"], "prefer.release.v1")
            self.assertEqual(manifest["release"]["id"], "sha-abcdef0")
            self.assertEqual(
                manifest["release"]["source_revision"],
                "abcdef0123456789abcdef0123456789abcdef01",
            )
            self.assertFalse(manifest["distribution"]["model_weights_embedded"])
            self.assertTrue(manifest["distribution"]["models_stage_at_runtime"])
            self.assertEqual(
                set(manifest["engines"]),
                {"llama", "audio", "image", "sglang", "vllm"},
            )
            self.assertEqual(manifest["tooling"]["package_version"], "0.0.0-gabcdef0")
            self.assertEqual(manifest["tooling"]["huggingface_refresh"], "live")
            for key in (
                "package",
                "cli",
                "model_catalog",
                "model_catalog_schema",
                "model_catalog_extension_schema",
                "resource_profile_schema",
                "model_plan_schema",
            ):
                binding = manifest["tooling"][key]
                copied = output_dir / binding["asset"]
                self.assertEqual(binding["sha256"], hashlib.sha256(copied.read_bytes()).hexdigest())

            expected_images = {
                ("llama", "cuda"): (
                    "llama-cuda-sha-abcdef0",
                    ["linux/amd64"],
                ),
                ("audio", "cuda12"): (
                    "audio-cuda12-sha-abcdef0",
                    ["linux/amd64", "linux/arm64"],
                ),
                ("audio", "cpu"): (
                    "audio-cpu-sha-abcdef0",
                    ["linux/amd64", "linux/arm64"],
                ),
                ("image", "cuda12"): (
                    "image-cuda12-sha-abcdef0",
                    ["linux/amd64"],
                ),
                ("sglang", "cuda13"): (
                    "sglang-cuda13-sha-abcdef0",
                    ["linux/amd64", "linux/arm64"],
                ),
                ("vllm", "cuda13"): (
                    "vllm-cuda13-sha-abcdef0",
                    ["linux/amd64", "linux/arm64"],
                ),
            }
            for (engine, variant), (tag, platforms) in expected_images.items():
                image = manifest["engines"][engine]["images"][variant]
                self.assertEqual(image["tag"], tag)
                self.assertEqual(image["platforms"], platforms)
                self.assertTrue(image["reference"].startswith(f"ghcr.io/cvalusek/prefer:{tag}@sha256:"))

            sources = {
                "llama": REPO_ROOT / "docker" / "llama-cpp" / "deployment-inventory.generated.json",
                "audio": REPO_ROOT / "docker" / "audio-cpp" / "deployment-inventory.generated.json",
                "image": REPO_ROOT
                / "docker"
                / "stable-diffusion-cpp"
                / "deployment-inventory.generated.json",
                "sglang": REPO_ROOT
                / "docker"
                / "sglang"
                / "deployment-inventory.generated.json",
                "vllm": REPO_ROOT
                / "docker"
                / "vllm"
                / "deployment-inventory.generated.json",
            }
            for engine, source in sources.items():
                inventory = manifest["engines"][engine]["inventory"]
                copied = output_dir / inventory["asset"]
                self.assertEqual(copied.read_bytes(), source.read_bytes())
                self.assertEqual(inventory["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())

    def test_bundle_rejects_an_unresolved_image_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.build_release(Path(directory), image_digest="sha256:pending")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid digest for image-cuda12-sha-abcdef0", result.stderr)

    def test_bundle_rejects_tooling_that_is_not_release_matched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.build_release(
                Path(directory), package_version="0.0.0-gfffffff"
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("tooling package version does not match the release", result.stderr)

    def test_one_workflow_builds_and_publishes_all_engines(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertFalse((WORKFLOW.parent / "build-audio.yml").exists())
        self.assertFalse((WORKFLOW.parent / "build-image.yml").exists())
        for watched_path in (
            "docker/llama-cpp/**",
            "docker/audio-cpp/**",
            "docker/stable-diffusion-cpp/**",
            "docker/sglang/**",
            "docker/vllm/**",
            "release/**",
            "catalog/**",
            "packages/prefer/**",
            "scripts/**",
        ):
            self.assertIn(watched_path, workflow)
        for immutable_tag in (
            "llama-cuda-sha-",
            "audio-cuda12-sha-",
            "audio-cpu-sha-",
            "image-cuda12-sha-",
            "sglang-cuda13-sha-",
            "vllm-cuda13-sha-",
        ):
            self.assertIn(immutable_tag, workflow)
        self.assertIn("needs: [tooling, llama, audio_cuda, audio_cpu, image, sglang, vllm]", workflow)
        self.assertIn("name: prefer-release-${{ github.sha }}", workflow)
        self.assertIn("gh release create", workflow)
        self.assertIn("prefer-release.json", workflow)
        self.assertIn("prefer-inference-core.tgz", workflow)
        self.assertIn("https://registry.npmjs.org", workflow)
        self.assertIn("secrets.NPM_TOKEN", workflow)
        self.assertIn("NPM_CONFIG_USERCONFIG", workflow)
        self.assertIn("//registry.npmjs.org/:_authToken=${NODE_AUTH_TOKEN}", workflow)
        self.assertIn("prefer-inference-core@$package_version", workflow)
        self.assertIn("npm publish ./prefer-release/prefer-inference-core.tgz", workflow)
        self.assertNotIn("always-auth", workflow)
        self.assertNotIn("https://npm.pkg.github.com", workflow)
        self.assertNotIn("@cvalusek/prefer", workflow)
        self.assertIn("prefer-model-catalog.json", workflow)
        self.assertIn("sha256sum prefer-release/* > prefer-release/SHA256SUMS", workflow)
        self.assertIn('package_dist_tag="latest"', workflow)
        self.assertIn('package_dist_tag="preview"', workflow)
        self.assertIn('--tag "$package_dist_tag"', workflow)

    def test_release_channels_are_branch_scoped(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("branches: [main, develop]", workflow)
        self.assertIn("prefer-release-${{ github.ref_name }}", workflow)
        for preview_tag in (
            "llama-cuda-preview",
            "audio-cuda12-preview",
            "audio-cpu-preview",
            "image-cuda12-preview",
            "vllm-cuda-preview",
        ):
            self.assertIn(preview_tag, workflow)
        for stable_tag in (
            '"$image_repository:latest"',
            '"$image_repository:llama-cuda"',
            '"$image_repository:audio-cuda12"',
            '"$image_repository:audio-cpu"',
            '"$image_repository:image-cuda12"',
            '"$image_repository:vllm-cuda"',
        ):
            self.assertIn(stable_tag, workflow)
        self.assertIn('release_channel="stable"', workflow)
        self.assertIn('release_channel="preview"', workflow)
        self.assertIn("--prerelease --latest=false", workflow)
        self.assertIn("--prerelease=false --latest", workflow)

    def test_release_schema_is_checked_in_and_parseable(self) -> None:
        schema = json.loads(
            (REPO_ROOT / "release" / "prefer-release.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(schema["properties"]["schema_version"]["const"], "prefer.release.v1")
        self.assertEqual(
            set(schema["properties"]["engines"]["required"]),
            {"llama", "audio", "image", "sglang", "vllm"},
        )
        self.assertIn("tooling", schema["required"])


if __name__ == "__main__":
    unittest.main()
