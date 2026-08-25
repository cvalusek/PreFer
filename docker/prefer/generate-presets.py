#!/usr/bin/env python3
"""Generate deployment presets, downloads, and deployment inventory."""

from __future__ import annotations

import argparse
import copy
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
MODELS_ROOT = ROOT / "models"
SCENARIOS_ROOT = ROOT / "preset-scenarios"
DOWNLOADS_PATH = ROOT / "model-downloads.generated.sh"
INVENTORY_PATH = ROOT / "deployment-inventory.generated.json"


class CatalogError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=OrderedDict)


def load_catalog() -> dict[str, Any]:
    catalog = load_json(CATALOG_PATH)
    if catalog.get("schema_version") != 2:
        raise CatalogError("preset-catalog.json must use schema_version 2")

    models: OrderedDict[str, dict[str, Any]] = OrderedDict()
    model_paths = sorted(MODELS_ROOT.glob("*/*/model.json"))
    if not model_paths:
        raise CatalogError("models/<family>/<model>/model.json files are required")

    for path in model_paths:
        source = load_json(path)
        relative = path.relative_to(MODELS_ROOT)
        family, model_slug, filename = relative.parts
        if filename != "model.json":
            raise CatalogError(f"unexpected model catalog path: {relative.as_posix()}")
        if source.get("schema_version") != 1:
            raise CatalogError(f"{relative.as_posix()}: schema_version must be 1")
        if source.get("family") != family or source.get("model_slug") != model_slug:
            raise CatalogError(f"{relative.as_posix()}: family/model_slug must match its folder path")
        quants = source.get("quants")
        if not isinstance(quants, dict) or not quants:
            raise CatalogError(f"{relative.as_posix()}: quants must be a non-empty object")
        shared = source.get("shared", OrderedDict())
        if not isinstance(shared, dict):
            raise CatalogError(f"{relative.as_posix()}: shared must be an object")
        if "settings" in shared and not isinstance(shared["settings"], dict):
            raise CatalogError(f"{relative.as_posix()}: shared.settings must be an object")

        for quant_slug, lane in quants.items():
            if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", quant_slug):
                raise CatalogError(f"{relative.as_posix()}: unsafe quant key {quant_slug!r}")
            key = lane.get("key")
            if not key:
                raise CatalogError(f"{relative.as_posix()}:{quant_slug}: key is required")
            if key in models:
                raise CatalogError(f"duplicate model key {key!r}")
            model = copy.deepcopy(OrderedDict(shared))
            for name, value in lane.items():
                if name == "key":
                    continue
                if name == "settings" and name in model:
                    if not isinstance(value, dict):
                        raise CatalogError(f"{relative.as_posix()}:{quant_slug}: settings must be an object")
                    model[name] = OrderedDict((*model[name].items(), *value.items()))
                else:
                    model[name] = copy.deepcopy(value)
            if isinstance(model.get("settings"), dict):
                settings = model["settings"]
                model["settings"] = OrderedDict(
                    (name, settings[name])
                    for name in ("model", "model-draft", "mmproj")
                    if name in settings
                )
                model["settings"].update(
                    (name, value)
                    for name, value in settings.items()
                    if name not in {"model", "model-draft", "mmproj"}
                )
            model["_catalog"] = OrderedDict(
                family=family,
                model_slug=model_slug,
                quant_slug=quant_slug,
                source=f"models/{relative.as_posix()}",
            )
            models[key] = model

    model_order = catalog.get("model_order")
    if not isinstance(model_order, list) or set(model_order) != set(models) or len(model_order) != len(models):
        raise CatalogError("preset-catalog.json model_order must list every model key exactly once")
    catalog["models"] = OrderedDict((key, models[key]) for key in model_order)
    return catalog


DECIMAL_SETTINGS = {
    "temp",
    "top-p",
    "min-p",
    "dry-multiplier",
    "dry-base",
    "repeat-penalty",
    "presence-penalty",
}


def ini_value(value: Any, name: str | None = None) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if name in DECIMAL_SETTINGS and isinstance(value, int):
        return f"{value:.1f}"
    return str(value)


def artifact_local_path(artifact: dict[str, Any]) -> str:
    return f"/models/{artifact['repo']}/{artifact['path']}"


def include_matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern)


def validate_catalog(catalog: dict[str, Any]) -> None:
    if catalog.get("schema_version") != 2:
        raise CatalogError("preset-catalog.json must use schema_version 2")
    runtime = catalog.get("runtime", {})
    runtime_tag = str(runtime.get("llama_cpp_tag", ""))
    if not re.fullmatch(r"b[0-9]+", runtime_tag):
        raise CatalogError("catalog runtime needs a versioned llama_cpp_tag")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", str(runtime.get("source_revision", ""))):
        raise CatalogError("catalog runtime needs an immutable source_revision")
    if runtime.get("image") != f"ghcr.io/ggml-org/llama.cpp:server-cuda-{runtime_tag}":
        raise CatalogError("catalog runtime image must match its versioned llama_cpp_tag")
    if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", str(runtime.get("manifest_digest", ""))):
        raise CatalogError("catalog runtime needs an immutable OCI manifest digest")
    platform_manifests = runtime.get("platform_manifests", {})
    if set(platform_manifests) != {"linux/amd64", "linux/arm64"}:
        raise CatalogError("catalog runtime must record linux/amd64 and linux/arm64 manifests")
    if any(not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", str(digest)) for digest in platform_manifests.values()):
        raise CatalogError("catalog runtime platform manifests must be immutable SHA-256 digests")
    models = catalog.get("models")
    if not isinstance(models, dict) or not models:
        raise CatalogError("catalog models must be a non-empty object")

    for key, model in models.items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", key):
            raise CatalogError(f"unsafe model key: {key!r}")
        if not model.get("section"):
            raise CatalogError(f"{key}: section is required")
        aliases = model.get("aliases")
        if not isinstance(aliases, list) or not aliases or any(not isinstance(alias, str) or not alias for alias in aliases):
            raise CatalogError(f"{key}: aliases must be a non-empty list of strings")
        request_model_id = model.get("request_model_id")
        if request_model_id not in aliases:
            raise CatalogError(f"{key}: request_model_id must name one of the configured aliases")
        identity = model.get("_catalog", {})
        if set(identity) != {"family", "model_slug", "quant_slug", "source"}:
            raise CatalogError(f"{key}: generated catalog identity is incomplete")
        lineage = model.get("lineage")
        if lineage:
            if not lineage.get("repo") or not re.fullmatch(r"[0-9a-fA-F]{40}", str(lineage.get("revision", ""))):
                raise CatalogError(f"{key}: lineage requires a repo and immutable 40-character revision")
        runtime_requirement = model.get("runtime_requirement")
        if runtime_requirement:
            if not re.fullmatch(r"[0-9a-fA-F]{40}", str(runtime_requirement.get("llama_cpp_merge", ""))):
                raise CatalogError(f"{key}: runtime_requirement needs an immutable llama_cpp_merge revision")
            if not runtime_requirement.get("feature"):
                raise CatalogError(f"{key}: runtime_requirement feature is required")
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

        spec_type = settings.get("spec-type")
        embedded_mtp = model.get("embedded_mtp", False)
        if embedded_mtp and spec_type != "draft-mtp":
            raise CatalogError(f"{key}: embedded_mtp requires spec-type draft-mtp")
        if spec_type == "draft-mtp" and not settings.get("model-draft") and not embedded_mtp:
            raise CatalogError(f"{key}: draft-mtp requires model-draft or embedded_mtp")
        if spec_type in {"draft-dflash", "draft-dspark", "draft-eagle3", "draft-simple"} and not settings.get("model-draft"):
            raise CatalogError(f"{key}: {spec_type} requires model-draft")
        if embedded_mtp and settings.get("model-draft"):
            raise CatalogError(f"{key}: embedded_mtp cannot also use model-draft")

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


def load_scenarios() -> list[tuple[dict[str, Any], dict[str, Any], Path]]:
    records: OrderedDict[str, tuple[dict[str, Any], dict[str, Any], Path]] = OrderedDict()
    source_paths = sorted(SCENARIOS_ROOT.rglob("*.json"))
    if not source_paths:
        raise CatalogError("preset-scenarios/**/*.json files are required")

    for source_path in source_paths:
        source = load_json(source_path)
        if source.get("schema_version") != 1:
            raise CatalogError(f"{source_path}: schema_version must be 1")
        source_metadata = OrderedDict(
            provider=source.get("provider"),
            hardware=source.get("hardware", OrderedDict()),
            compatibility=source.get("compatibility", OrderedDict()),
            verification=source.get("verification", "configuration-only"),
        )
        for scenario in source.get("scenarios", []):
            path = scenario.get("path")
            if not path:
                raise CatalogError(f"{source_path}: every scenario needs a path")
            if path in records:
                raise CatalogError(f"duplicate generated preset path: {path}")
            records[path] = (scenario, source_metadata, source_path)

    resolved: dict[str, dict[str, Any]] = {}

    def resolve(path: str, stack: tuple[str, ...] = ()) -> dict[str, Any]:
        if path in resolved:
            return copy.deepcopy(resolved[path])
        if path not in records:
            raise CatalogError(f"unknown extended scenario: {path}")
        if path in stack:
            raise CatalogError(f"scenario inheritance cycle: {' -> '.join((*stack, path))}")
        raw, _, _ = records[path]
        base_path = raw.get("extends")
        scenario = resolve(base_path, (*stack, path)) if base_path else OrderedDict()
        for name, value in raw.items():
            if name == "extends":
                continue
            if name == "defaults" and name in scenario:
                scenario[name] = OrderedDict((*scenario[name].items(), *value.items()))
            else:
                scenario[name] = copy.deepcopy(value)
        resolved[path] = scenario
        return copy.deepcopy(scenario)

    return [(resolve(path), metadata, source_path) for path, (_, metadata, source_path) in records.items()]


def effective_request_model_id(model: dict[str, Any], entry: dict[str, Any]) -> str:
    aliases = entry.get("aliases", model.get("aliases", []))
    request_model_id = entry.get("request_model_id", model.get("request_model_id"))
    if request_model_id not in aliases:
        raise CatalogError("effective request_model_id must name one of the effective aliases")
    return request_model_id


def effective_model_settings(
    catalog: dict[str, Any], scenario: dict[str, Any], entry: dict[str, Any]
) -> tuple[str, OrderedDict[str, Any]]:
    key = entry.get("key")
    if key not in catalog["models"]:
        raise CatalogError(f"{scenario['path']}: unknown model key {key!r}")
    model = catalog["models"][key]
    settings = OrderedDict(model["settings"])
    aliases = entry.get("aliases", model.get("aliases", []))
    effective_request_model_id(model, entry)
    if aliases:
        settings["alias"] = ", ".join(aliases)
    for name, value in entry.get("overrides", {}).items():
        if value is None:
            settings.pop(name, None)
        else:
            settings[name] = value
    return entry.get("section", model["section"]), settings


def render_ini(catalog: dict[str, Any], scenario: dict[str, Any]) -> tuple[str, list[str]]:
    lines = ["version = 1", ""]
    defaults = scenario.get("defaults", {})
    if defaults:
        lines.append("[*]")
        lines.extend(f"{name} = {ini_value(value, name)}" for name, value in defaults.items())
        lines.append("")

    prestage: list[str] = []
    sections: set[str] = set()
    for entry in scenario.get("models", []):
        key = entry.get("key")
        section, settings = effective_model_settings(catalog, scenario, entry)
        if section in sections:
            raise CatalogError(f"{scenario['path']}: duplicate section {section}")
        sections.add(section)
        if key not in prestage:
            prestage.append(key)

        lines.append(f"[{section}]")
        lines.extend(f"{name} = {ini_value(value, name)}" for name, value in settings.items())
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


def render_inventory(
    catalog: dict[str, Any], scenario_records: list[tuple[dict[str, Any], dict[str, Any], Path]]
) -> str:
    inventory_models: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for key, model in catalog["models"].items():
        identity = model["_catalog"]
        item = OrderedDict(
            key=key,
            family=identity["family"],
            model_slug=identity["model_slug"],
            quant_slug=identity["quant_slug"],
            source=identity["source"],
        )
        for name, value in model.items():
            if name != "_catalog":
                item[name] = value
        item["download_fingerprint"] = model_download_fingerprint(key, model)
        sizes = [artifact.get("size") for artifact in model["artifacts"]]
        item["artifact_bytes"] = sum(sizes) if all(isinstance(size, int) for size in sizes) else None
        inventory_models[key] = item

    catalog_payload = OrderedDict(
        runtime=catalog["runtime"],
        legacy_default_prestage=catalog["legacy_default_prestage"],
        models=inventory_models,
    )
    catalog_fingerprint = hashlib.sha256(
        json.dumps(catalog_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    deployments: list[dict[str, Any]] = []
    for scenario, source_metadata, source_path in scenario_records:
        output_path = validate_output_path(scenario["path"])
        provider = source_metadata.get("provider") or PurePosixPath(scenario["path"]).parts[0]
        hardware = OrderedDict(source_metadata.get("hardware", {}))
        if provider == "aws" and scenario.get("instance_type"):
            hardware.setdefault("provider_sku", scenario["instance_type"])
        if provider == "aws" and scenario.get("gpu"):
            hardware.setdefault("display_name", scenario["gpu"])

        model_entries: list[dict[str, Any]] = []
        prestage: list[str] = []
        for entry in scenario.get("models", []):
            key = entry["key"]
            model = catalog["models"][key]
            identity = model["_catalog"]
            section, section_settings = effective_model_settings(catalog, scenario, entry)
            effective_settings = OrderedDict(scenario.get("defaults", {}))
            effective_settings.update(section_settings)
            parallel = int(effective_settings.get("parallel", 1))
            context_size = int(effective_settings.get("ctx-size", 0))
            context_per_request = context_size // parallel if context_size > 0 else None
            if key not in prestage:
                prestage.append(key)
            model_entries.append(
                OrderedDict(
                    key=key,
                    family=identity["family"],
                    model_slug=identity["model_slug"],
                    quant_slug=identity["quant_slug"],
                    section=section,
                    request_model_id=effective_request_model_id(model, entry),
                    aliases=entry.get("aliases", model.get("aliases", [])),
                    context_size=context_size,
                    parallel=parallel,
                    context_per_request=context_per_request,
                    cache_type_k=effective_settings.get("cache-type-k"),
                    cache_type_v=effective_settings.get("cache-type-v"),
                    settings=effective_settings,
                )
            )

        preset_container_path = f"/presets/{scenario['path']}"
        deployments.append(
            OrderedDict(
                id=PurePosixPath(scenario["path"]).with_suffix("").as_posix(),
                provider=provider,
                source=source_path.relative_to(ROOT).as_posix(),
                preset=preset_container_path,
                prestage_manifest=str(PurePosixPath(preset_container_path).with_suffix(".prestage")),
                environment=OrderedDict(
                    LLAMA_ARG_MODELS_PRESET=preset_container_path,
                    LLAMA_ARG_MODELS_MAX="1",
                    PRESTAGE_MODELS=",".join(prestage),
                ),
                hardware=hardware,
                compatibility=source_metadata.get("compatibility", OrderedDict()),
                verification=source_metadata.get("verification", "configuration-only"),
                models=model_entries,
            )
        )

    inventory = OrderedDict(
        schema_version="prefer.deployment-inventory.v1",
        catalog_fingerprint=catalog_fingerprint,
        runtime=catalog["runtime"],
        models=inventory_models,
        deployments=deployments,
    )
    return json.dumps(inventory, indent=2, ensure_ascii=False) + "\n"


def expected_outputs() -> dict[Path, str]:
    catalog = load_catalog()
    validate_catalog(catalog)
    scenario_records = load_scenarios()
    outputs: dict[Path, str] = {
        DOWNLOADS_PATH: render_downloads(catalog),
        INVENTORY_PATH: render_inventory(catalog, scenario_records),
    }
    seen_paths: set[Path] = set()

    for scenario, _, _ in scenario_records:
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
