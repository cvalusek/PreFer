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
    def build_release(self, output_dir: Path, image_digest: str | None = None) -> subprocess.CompletedProcess[str]:
        digests = {
            "llama": "sha256:" + "1" * 64,
            "audio_cuda": "sha256:" + "2" * 64,
            "audio_cpu": "sha256:" + "3" * 64,
            "image": image_digest or "sha256:" + "4" * 64,
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
            self.assertEqual(set(manifest["engines"]), {"llama", "audio", "image"})

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

    def test_one_workflow_builds_and_publishes_all_engines(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertFalse((WORKFLOW.parent / "build-audio.yml").exists())
        self.assertFalse((WORKFLOW.parent / "build-image.yml").exists())
        for watched_path in (
            "docker/llama-cpp/**",
            "docker/audio-cpp/**",
            "docker/stable-diffusion-cpp/**",
            "release/**",
        ):
            self.assertIn(watched_path, workflow)
        for immutable_tag in (
            "llama-cuda-sha-",
            "audio-cuda12-sha-",
            "audio-cpu-sha-",
            "image-cuda12-sha-",
        ):
            self.assertIn(immutable_tag, workflow)
        self.assertIn("needs: [llama, audio_cuda, audio_cpu, image]", workflow)
        self.assertIn("name: prefer-release-${{ github.sha }}", workflow)
        self.assertIn("gh release create", workflow)
        self.assertIn("prefer-release.json", workflow)

    def test_release_channels_are_branch_scoped(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("branches: [main, develop]", workflow)
        self.assertIn("prefer-release-${{ github.ref_name }}", workflow)
        for preview_tag in (
            "llama-cuda-preview",
            "audio-cuda12-preview",
            "audio-cpu-preview",
            "image-cuda12-preview",
        ):
            self.assertIn(preview_tag, workflow)
        for stable_tag in (
            '"$image_repository:latest"',
            '"$image_repository:llama-cuda"',
            '"$image_repository:audio-cuda12"',
            '"$image_repository:audio-cpu"',
            '"$image_repository:image-cuda12"',
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
        self.assertEqual(set(schema["properties"]["engines"]["required"]), {"llama", "audio", "image"})


if __name__ == "__main__":
    unittest.main()
