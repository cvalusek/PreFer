#!/usr/bin/env python3
"""Assemble one immutable PreFer release from all runtime inventories."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    parser.add_argument("--source-repository", required=True)
    parser.add_argument("--image-repository", required=True)
    parser.add_argument("--llama-digest", required=True)
    parser.add_argument("--audio-cuda-digest", required=True)
    parser.add_argument("--audio-cpu-digest", required=True)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--sglang-digest", required=True)
    parser.add_argument("--llama-inventory", type=Path, required=True)
    parser.add_argument("--audio-inventory", type=Path, required=True)
    parser.add_argument("--image-inventory", type=Path, required=True)
    parser.add_argument("--sglang-inventory", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def require_match(value: str, pattern: re.Pattern[str], label: str) -> str:
    if not pattern.fullmatch(value):
        raise ValueError(f"invalid {label}: {value}")
    return value


def inventory_asset(
    source: Path,
    output_dir: Path,
    asset_name: str,
    expected_schema: str,
) -> dict[str, str]:
    payload = source.read_bytes()
    inventory = json.loads(payload)
    actual_schema = inventory.get("schema_version")
    if actual_schema != expected_schema:
        raise ValueError(
            f"{source} has schema {actual_schema!r}; expected {expected_schema!r}"
        )
    fingerprint = inventory.get("catalog_fingerprint")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ValueError(f"{source} has no valid catalog_fingerprint")
    destination = output_dir / asset_name
    shutil.copyfile(source, destination)
    return {
        "asset": asset_name,
        "schema_version": actual_schema,
        "catalog_fingerprint": fingerprint,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def image_entry(
    repository: str,
    tag: str,
    digest: str,
    platforms: list[str],
) -> dict[str, object]:
    require_match(digest, DIGEST_PATTERN, f"digest for {tag}")
    return {
        "tag": tag,
        "digest": digest,
        "reference": f"{repository}:{tag}@{digest}",
        "platforms": platforms,
    }


def build_manifest(args: argparse.Namespace) -> dict[str, object]:
    commit = require_match(args.commit.lower(), COMMIT_PATTERN, "commit")
    short_commit = commit[:7]
    release_id = f"sha-{short_commit}"
    image_repository = args.image_repository.rstrip("/").lower()
    source_repository = args.source_repository.rstrip("/")
    if not image_repository or not source_repository:
        raise ValueError("repository values must not be empty")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    llama_inventory = inventory_asset(
        args.llama_inventory,
        args.output_dir,
        "prefer-llama-deployment-inventory.json",
        "prefer.deployment-inventory.v1",
    )
    audio_inventory = inventory_asset(
        args.audio_inventory,
        args.output_dir,
        "prefer-audio-deployment-inventory.json",
        "prefer.audio-deployment-inventory.v1",
    )
    image_inventory = inventory_asset(
        args.image_inventory,
        args.output_dir,
        "prefer-image-deployment-inventory.json",
        "prefer.image-deployment-inventory.v1",
    )
    sglang_inventory = inventory_asset(
        args.sglang_inventory,
        args.output_dir,
        "prefer-sglang-deployment-inventory.json",
        "prefer.sglang-deployment-inventory.v1",
    )

    return {
        "schema_version": "prefer.release.v1",
        "product": "PreFer",
        "release": {
            "id": release_id,
            "source_revision": commit,
            "source_repository": source_repository,
            "source_url": f"{source_repository}/commit/{commit}",
            "artifact_name": f"prefer-release-{commit}",
        },
        "distribution": {
            "model_weights_embedded": False,
            "models_stage_at_runtime": True,
            "all_engine_images_share_release_revision": True,
        },
        "engines": {
            "llama": {
                "runtime": "llama.cpp",
                "inventory": llama_inventory,
                "images": {
                    "cuda": image_entry(
                        image_repository,
                        f"llama-cuda-{release_id}",
                        args.llama_digest,
                        ["linux/amd64"],
                    )
                },
            },
            "audio": {
                "runtime": "audio.cpp",
                "inventory": audio_inventory,
                "images": {
                    "cuda12": image_entry(
                        image_repository,
                        f"audio-cuda12-{release_id}",
                        args.audio_cuda_digest,
                        ["linux/amd64", "linux/arm64"],
                    ),
                    "cpu": image_entry(
                        image_repository,
                        f"audio-cpu-{release_id}",
                        args.audio_cpu_digest,
                        ["linux/amd64", "linux/arm64"],
                    ),
                },
            },
            "image": {
                "runtime": "stable-diffusion.cpp",
                "inventory": image_inventory,
                "images": {
                    "cuda12": image_entry(
                        image_repository,
                        f"image-cuda12-{release_id}",
                        args.image_digest,
                        ["linux/amd64"],
                    )
                },
            },
            "sglang": {
                "runtime": "sglang",
                "inventory": sglang_inventory,
                "images": {
                    "cuda13": image_entry(
                        image_repository,
                        f"sglang-cuda13-{release_id}",
                        args.sglang_digest,
                        ["linux/amd64", "linux/arm64"],
                    )
                },
            },
        },
    }


def main() -> None:
    args = parse_args()
    manifest = build_manifest(args)
    output = args.output_dir / "prefer-release.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
