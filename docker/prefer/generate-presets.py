#!/usr/bin/env python3
"""Generate deployment presets and downloader definitions from one catalog."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import shlex
import sys
from collections import OrderedDict
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "preset-catalog.json"
SCENARIO_PATHS = (ROOT / "preset-scenarios" / "aws.json",)
DOWNLOADS_PATH = ROOT / "model-downloads.generated.sh"


class CatalogError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=OrderedDict)


def ini_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def artifact_local_path(artifact: dict[str, Any]) -> str:
    return f"/models/{artifact['repo']}/{artifact['path']}"


def include_matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern)


def validate_catalog(catalog: dict[str, Any]) -> None:
    if catalog.get("schema_version") != 1:
        raise CatalogError("preset-catalog.json must use schema_version 1")
    models = catalog.get("models")
    if not isinstance(models, dict) or not models:
        raise CatalogError("catalog models must be a non-empty object")

    for key, model in models.items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", key):
            raise CatalogError(f"unsafe model key: {key!r}")
        if not model.get("section"):
            raise CatalogError(f"{key}: section is required")
        settings = model.get("settings", {})
        if not settings.get("model"):
            raise CatalogError(f"{key}: settings.model is required")
        downloads = model.get("downloads", [])
        artifacts = model.get("artifacts", [])
        if not downloads or not artifacts:
            raise CatalogError(f"{key}: downloads and artifacts are required")

        for download in downloads:
            if not download.get("repo") or not download.get("include"):
                raise CatalogError(f"{key}: each download needs repo and include")
            revision = download.get("revision")
            if revision and not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
                raise CatalogError(f"{key}: immutable download revision must be a 40-character commit SHA")

        roles = {artifact["role"] for artifact in artifacts}
        if "model" not in roles:
            raise CatalogError(f"{key}: a model artifact is required")

        for setting, role in (("model", "model"), ("model-draft", "draft"), ("mmproj", "projector")):
            configured = settings.get(setting)
            if not configured:
                continue
            matches = [artifact for artifact in artifacts if artifact["role"] == role and artifact_local_path(artifact) == configured]
            if not matches:
                raise CatalogError(f"{key}: {setting} has no exact {role} artifact record: {configured}")

        for artifact in artifacts:
            if not artifact.get("repo") or not artifact.get("path") or not artifact.get("role"):
                raise CatalogError(f"{key}: artifact repo, path, and role are required")
            relative_path = PurePosixPath(artifact["repo"]) / PurePosixPath(artifact["path"])
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise CatalogError(f"{key}: unsafe artifact path: {relative_path}")
            matching_downloads = [
                download
                for download in downloads
                if download["repo"] == artifact["repo"]
                and any(include_matches(artifact["path"], pattern) for pattern in download["include"])
            ]
            if not matching_downloads:
                raise CatalogError(
                    f"{key}: required {artifact['role']} artifact is omitted by downloads: "
                    f"{artifact['repo']}/{artifact['path']}"
                )
            if any(download.get("revision") for download in matching_downloads):
                if not isinstance(artifact.get("size"), int) or artifact["size"] <= 0:
                    raise CatalogError(f"{key}: pinned artifact needs a positive byte size: {artifact['path']}")
                if not re.fullmatch(r"[0-9a-fA-F]{64}", str(artifact.get("sha256", ""))):
                    raise CatalogError(f"{key}: pinned artifact needs a SHA-256 digest: {artifact['path']}")

        artifact_paths = {(artifact["repo"], artifact["path"]) for artifact in artifacts}
        for artifact in artifacts:
            shard = re.fullmatch(r"(?P<prefix>.+)-00001-of-(?P<count>[0-9]{5})\.gguf", artifact["path"])
            if not shard:
                continue
            shard_count = int(shard.group("count"))
            expected = {
                (
                    artifact["repo"],
                    f"{shard.group('prefix')}-{index:05d}-of-{shard_count:05d}.gguf",
                )
                for index in range(1, shard_count + 1)
            }
            missing = sorted(path for path in expected if path not in artifact_paths)
            if missing:
                raise CatalogError(f"{key}: sharded model artifact list is incomplete: {missing[0][1]}")

    legacy = catalog.get("legacy_default_prestage", [])
    unknown = sorted(set(legacy) - set(models))
    if unknown:
        raise CatalogError(f"legacy_default_prestage contains unknown keys: {', '.join(unknown)}")


def render_ini(catalog: dict[str, Any], scenario: dict[str, Any]) -> tuple[str, list[str]]:
    models = catalog["models"]
    lines = ["version = 1", ""]
    defaults = scenario.get("defaults", {})
    if defaults:
        lines.append("[*]")
        lines.extend(f"{name} = {ini_value(value)}" for name, value in defaults.items())
        lines.append("")

    prestage: list[str] = []
    sections: set[str] = set()
    for entry in scenario.get("models", []):
        key = entry.get("key")
        if key not in models:
            raise CatalogError(f"{scenario['path']}: unknown model key {key!r}")
        model = models[key]
        section = entry.get("section", model["section"])
        if section in sections:
            raise CatalogError(f"{scenario['path']}: duplicate section {section}")
        sections.add(section)
        if key not in prestage:
            prestage.append(key)

        settings = OrderedDict(model["settings"])
        aliases = entry.get("aliases", model.get("aliases", []))
        if aliases:
            settings["alias"] = ", ".join(aliases)
        for name, value in entry.get("overrides", {}).items():
            if value is None:
                settings.pop(name, None)
            else:
                settings[name] = value

        lines.append(f"[{section}]")
        lines.extend(f"{name} = {ini_value(value)}" for name, value in settings.items())
        lines.append("")

    if not prestage:
        raise CatalogError(f"{scenario['path']}: scenario must contain at least one model")
    return "\n".join(lines), prestage


def validate_output_path(value: str) -> Path:
    posix = PurePosixPath(value)
    if posix.is_absolute() or ".." in posix.parts or posix.suffix != ".ini":
        raise CatalogError(f"unsafe or non-INI scenario path: {value}")
    return ROOT / "presets" / Path(*posix.parts)


def model_download_fingerprint(key: str, model: dict[str, Any]) -> str:
    payload = {
        "schema_version": 1,
        "key": key,
        "downloads": model["downloads"],
        "artifacts": model["artifacts"],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def render_downloads(catalog: dict[str, Any]) -> str:
    lines = [
        "#!/bin/bash",
        "# Generated by generate-presets.py. Do not edit by hand.",
        f"GENERATED_MODEL_KEYS={shlex.quote(','.join(catalog['models']))}",
        f"LEGACY_SMALL_MODELS={shlex.quote(','.join(catalog['legacy_default_prestage']))}",
        "",
        "model_key_fingerprint() {",
        "  case \"$1\" in",
    ]
    for key, model in catalog["models"].items():
        fingerprint = model_download_fingerprint(key, model)
        lines.extend(
            [
                f"    {shlex.quote(key)})",
                f"      printf '%s\\n' {shlex.quote(fingerprint)}",
                "      ;;",
            ]
        )
    lines.extend(
        [
            "    *)",
            "      echo \"[download-models] unknown model key: $1\" >&2",
            "      return 2",
            "      ;;",
            "  esac",
            "}",
            "",
            "model_key_artifacts() {",
            "  case \"$1\" in",
        ]
    )
    for key, model in catalog["models"].items():
        lines.append(f"    {shlex.quote(key)})")
        for artifact in model["artifacts"]:
            relative_path = f"{artifact['repo']}/{artifact['path']}"
            lines.append(f"      printf '%s\\n' {shlex.quote(relative_path)}")
        lines.append("      ;;")
    lines.extend(
        [
            "    *)",
            "      echo \"[download-models] unknown model key: $1\" >&2",
            "      return 2",
            "      ;;",
            "  esac",
            "}",
            "",
            "download_model_key() {",
            "  case \"$1\" in",
        ]
    )
    for key, model in catalog["models"].items():
        lines.append(f"    {shlex.quote(key)})")
        for download in model["downloads"]:
            args = [download["repo"], download.get("revision") or ""]
            for pattern in download["include"]:
                args.extend(("--include", pattern))
            lines.append("      download " + " ".join(shlex.quote(str(arg)) for arg in args))
        lines.append("      ;;")
    lines.extend(
        [
            "    *)",
            "      echo \"[download-models] unknown model key: $1\" >&2",
            "      return 2",
            "      ;;",
            "  esac",
            "}",
            "",
        ]
    )
    return "\n".join(lines)


def expected_outputs() -> dict[Path, str]:
    catalog = load_json(CATALOG_PATH)
    validate_catalog(catalog)
    outputs: dict[Path, str] = {DOWNLOADS_PATH: render_downloads(catalog)}
    seen_paths: set[Path] = set()

    for source_path in SCENARIO_PATHS:
        source = load_json(source_path)
        if source.get("schema_version") != 1:
            raise CatalogError(f"{source_path}: schema_version must be 1")
        for scenario in source.get("scenarios", []):
            output_path = validate_output_path(scenario["path"])
            if output_path in seen_paths:
                raise CatalogError(f"duplicate generated preset path: {scenario['path']}")
            seen_paths.add(output_path)
            ini, prestage = render_ini(catalog, scenario)
            outputs[output_path] = ini
            outputs[output_path.with_suffix(".prestage")] = ",".join(prestage) + "\n"

    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated files are stale")
    args = parser.parse_args()

    try:
        outputs = expected_outputs()
    except (CatalogError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"generate-presets: {exc}", file=sys.stderr)
        return 2

    stale: list[Path] = []
    for path, content in outputs.items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")

    if stale:
        for path in stale:
            print(f"stale generated file: {path.relative_to(ROOT)}", file=sys.stderr)
        return 1
    if not args.check:
        print(f"generated {len(outputs)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
