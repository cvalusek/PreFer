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
        profile = source.get("profile")
        if not isinstance(profile, dict):
            raise CatalogError(f"{relative.as_posix()}: profile must be an object")

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
            model["profile"] = copy.deepcopy(profile)
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

PROFILE_MODALITIES = {"text", "image", "audio", "video"}
PROFILE_REASONING_CONTROL = {"none", "prompted", "request-selectable", "always-on", "unknown"}
PROFILE_ARCHITECTURES = {"dense", "moe", "hybrid-moe"}
PROFILE_CONFIDENCE = {"high", "medium", "low", "mixed"}
PROFILE_EVIDENCE_BASIS = {"official", "operator", "maintainer", "inference"}


def validate_string_list(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise CatalogError(f"{label} must be a {'possibly empty ' if allow_empty else 'non-empty '}list of strings")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise CatalogError(f"{label} must contain only non-empty strings")
    if len(value) != len(set(value)):
        raise CatalogError(f"{label} must not contain duplicates")
    return value


def validate_model_profile(key: str, profile: Any) -> None:
    if not isinstance(profile, dict):
        raise CatalogError(f"{key}: profile must be an object")
    for name in ("display_name", "prompt_summary"):
        if not isinstance(profile.get(name), str) or not profile[name].strip():
            raise CatalogError(f"{key}: profile.{name} must be a non-empty string")

    architecture = profile.get("architecture")
    if not isinstance(architecture, dict) or architecture.get("kind") not in PROFILE_ARCHITECTURES:
        raise CatalogError(f"{key}: profile.architecture.kind must name a supported architecture")
    for name in ("total_parameters_b", "active_parameters_b"):
        value = architecture.get(name)
        if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0):
            raise CatalogError(f"{key}: profile.architecture.{name} must be a positive number when present")
    if (
        architecture.get("active_parameters_b") is not None
        and architecture.get("total_parameters_b") is not None
        and architecture["active_parameters_b"] > architecture["total_parameters_b"]
    ):
        raise CatalogError(f"{key}: active parameters cannot exceed total parameters")

    capabilities = profile.get("capabilities")
    if not isinstance(capabilities, dict):
        raise CatalogError(f"{key}: profile.capabilities must be an object")
    native_inputs = validate_string_list(
        capabilities.get("native_input_modalities"), f"{key}: profile.capabilities.native_input_modalities"
    )
    configured_inputs = validate_string_list(
        capabilities.get("configured_input_modalities"), f"{key}: profile.capabilities.configured_input_modalities"
    )
    outputs = validate_string_list(
        capabilities.get("output_modalities"), f"{key}: profile.capabilities.output_modalities"
    )
    for name, modalities in (
        ("native_input_modalities", native_inputs),
        ("configured_input_modalities", configured_inputs),
        ("output_modalities", outputs),
    ):
        unknown = sorted(set(modalities) - PROFILE_MODALITIES)
        if unknown:
            raise CatalogError(f"{key}: profile.capabilities.{name} has unsupported modality {unknown[0]!r}")
    if not set(configured_inputs).issubset(native_inputs):
        raise CatalogError(f"{key}: configured input modalities must be a subset of native input modalities")
    context = capabilities.get("native_context_tokens")
    if not isinstance(context, int) or isinstance(context, bool) or context <= 0:
        raise CatalogError(f"{key}: profile.capabilities.native_context_tokens must be a positive integer")
    if capabilities.get("reasoning_control") not in PROFILE_REASONING_CONTROL:
        raise CatalogError(f"{key}: profile.capabilities.reasoning_control is unsupported")

    roles = profile.get("roles")
    if not isinstance(roles, dict):
        raise CatalogError(f"{key}: profile.roles must be an object")
    role_sets: dict[str, set[str]] = {}
    for name in ("preferred", "capable", "avoid"):
        values = validate_string_list(roles.get(name), f"{key}: profile.roles.{name}", allow_empty=name != "preferred")
        if any(not re.fullmatch(r"[a-z0-9][a-z0-9-]*", value) for value in values):
            raise CatalogError(f"{key}: profile.roles.{name} must use lowercase slug values")
        role_sets[name] = set(values)
    if any(role_sets[left] & role_sets[right] for left, right in (("preferred", "capable"), ("preferred", "avoid"), ("capable", "avoid"))):
        raise CatalogError(f"{key}: profile role lists must not overlap")

    for name in ("strengths", "limitations", "prompting"):
        validate_string_list(profile.get(name), f"{key}: profile.{name}")

    evidence = profile.get("evidence")
    if not isinstance(evidence, dict) or evidence.get("confidence") not in PROFILE_CONFIDENCE:
        raise CatalogError(f"{key}: profile.evidence.confidence is unsupported")
    basis = validate_string_list(evidence.get("basis"), f"{key}: profile.evidence.basis")
    unknown_basis = sorted(set(basis) - PROFILE_EVIDENCE_BASIS)
    if unknown_basis:
        raise CatalogError(f"{key}: profile.evidence.basis has unsupported value {unknown_basis[0]!r}")
    if not isinstance(evidence.get("notes"), str) or not evidence["notes"].strip():
        raise CatalogError(f"{key}: profile.evidence.notes must be a non-empty string")


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
        validate_model_profile(key, model.get("profile"))
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
    model_profiles: OrderedDict[str, dict[str, Any]] = OrderedDict()
    inventory_models: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for key, model in catalog["models"].items():
        identity = model["_catalog"]
        profile_id = identity["model_slug"]
        if profile_id not in model_profiles:
            profile = OrderedDict(
                family=identity["family"],
                model_slug=profile_id,
                aliases=copy.deepcopy(model["aliases"]),
                request_model_id=model["request_model_id"],
                quant_keys=[],
            )
            profile.update(copy.deepcopy(model["profile"]))
            model_profiles[profile_id] = profile
        else:
            profile = model_profiles[profile_id]
            if (
                profile["family"] != identity["family"]
                or profile["aliases"] != model["aliases"]
                or profile["request_model_id"] != model["request_model_id"]
                or any(profile[name] != model["profile"][name] for name in model["profile"])
            ):
                raise CatalogError(f"{key}: logical model profile differs across quant lanes")
        model_profiles[profile_id]["quant_keys"].append(key)

        item = OrderedDict(
            key=key,
            family=identity["family"],
            model_slug=identity["model_slug"],
            quant_slug=identity["quant_slug"],
            source=identity["source"],
            profile_id=profile_id,
        )
        for name, value in model.items():
            if name not in {"_catalog", "profile"}:
                item[name] = value
        item["download_fingerprint"] = model_download_fingerprint(key, model)
        sizes = [artifact.get("size") for artifact in model["artifacts"]]
        item["artifact_bytes"] = sum(sizes) if all(isinstance(size, int) for size in sizes) else None
        inventory_models[key] = item

    catalog_payload = OrderedDict(
        runtime=catalog["runtime"],
        legacy_default_prestage=catalog["legacy_default_prestage"],
        model_profiles=model_profiles,
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
                    profile_id=identity["model_slug"],
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
        product="PreFer",
        distribution=OrderedDict(
            embedded_image_path="/deployment-inventory.json",
            workflow_artifact_name_pattern="prefer-release-<commit-sha>",
            github_release_tag_pattern="sha-<short-commit>",
            release_inventory_asset="prefer-llama-deployment-inventory.json",
            oci_labels=OrderedDict(
                path="io.prefer.deployment-inventory.path",
                schema="io.prefer.deployment-inventory.schema",
            ),
        ),
        runtime=catalog["runtime"],
        composition=OrderedDict(
            schema_version="prefer.runtime-composition.v1",
            activation="opt-in; existing preset variables remain compatible when no composition variable is set",
            multi_model=True,
            effective_config_path="/run/prefer/llama.ini",
            effective_plan_path="/run/prefer/plan.json",
            effective_handoff_path="/run/prefer/handoff.json",
            runtime_handoff_schema="prefer.runtime-handoff.v1",
            compose_environment_prefix="LLAMA",
            override_merge="objects merge recursively; scalar and array values replace",
            environment=OrderedDict(
                PREFER_DEPLOYMENT=OrderedDict(type="string", source="deployments[].id"),
                PREFER_BUNDLE=OrderedDict(type="string-list", source="same-hardware preset name"),
                PREFER_MODELS=OrderedDict(type="string-list", source="models key, model_slug, request_model_id, or alias"),
                PREFER_SERVER_OVERRIDES=OrderedDict(type="json-object", applies_to="shared INI settings"),
                PREFER_MODEL_OVERRIDES=OrderedDict(type="json-object-map", applies_to="selected model INI settings"),
                PREFER_RUNTIME_HANDOFF=OrderedDict(type="path", source="immutable release-matched runtime handoff"),
            ),
            selection_rules=[
                "bundle and model selections are additive",
                "an exact quant key replaces another lane for the same logical model",
                "a friendly model selection inherits the selected hardware deployment's lane",
                "ambiguous friendly selections require an exact quant key",
                "a runtime handoff replaces bundle/model selection and may include controller-extension artifacts",
            ],
            precedence=[
                "catalog model and lane defaults",
                "hardware deployment defaults",
                "PREFER_SERVER_OVERRIDES",
                "PREFER_MODEL_OVERRIDES",
                "raw engine arguments",
            ],
            setting_sources=OrderedDict(
                server="deployments[].models[].settings plus deployment-shared preset defaults",
                model="models[].settings and deployments[].models[].settings",
            ),
        ),
        model_profiles=model_profiles,
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


def parse_composition_list(value: str) -> list[str]:
    """Parse the shared comma/newline selection syntax without losing order."""
    result: list[str] = []
    for item in re.split(r"[,\r\n]+", value or ""):
        item = item.strip()
        if item and item not in result:
            result.append(item)
    return result


def parse_composition_object(value: str, label: str) -> OrderedDict[str, Any]:
    if not value:
        return OrderedDict()
    parsed = json.loads(value, object_pairs_hook=OrderedDict)
    if not isinstance(parsed, dict):
        raise CatalogError(f"{label} must be a JSON object")
    return parsed


def normalize_runtime_preset(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    if normalized.startswith("/presets/"):
        normalized = normalized[len("/presets/") :]
    elif normalized.startswith("presets/"):
        normalized = normalized[len("presets/") :]
    if not normalized.endswith(".ini"):
        normalized += ".ini"
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise CatalogError(f"unsafe runtime deployment: {value!r}")
    return path.as_posix()


def parse_runtime_ini(path: Path, catalog: dict[str, Any], normalized_path: str) -> dict[str, Any]:
    """Turn a legacy checked-in INI into a scenario-shaped composition base."""
    if not path.is_file():
        raise CatalogError(f"runtime base preset not found: {path}")
    sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()
    current: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")) or line == "version = 1":
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1]
            sections[current] = OrderedDict()
            continue
        if current is None or "=" not in line:
            raise CatalogError(f"cannot compose malformed preset line in {path}: {raw_line!r}")
        name, value = line.split("=", 1)
        sections[current][name.strip()] = value.strip()

    by_section = {model["section"]: key for key, model in catalog["models"].items()}
    entries: list[dict[str, Any]] = []
    for section, settings in sections.items():
        if section == "*":
            continue
        key = by_section.get(section)
        if key is None:
            raise CatalogError(
                f"runtime composition cannot map section {section!r} in {path} to a catalog model"
            )
        entries.append(OrderedDict(key=key, section=section, overrides=settings))
    if not entries:
        raise CatalogError(f"runtime base preset contains no catalog models: {path}")
    return OrderedDict(
        path=normalized_path,
        defaults=sections.get("*", OrderedDict()),
        models=entries,
    )


def resolve_runtime_scenario(
    reference: str,
    catalog: dict[str, Any],
    scenario_records: list[tuple[dict[str, Any], dict[str, Any], Path]],
) -> tuple[dict[str, Any], str]:
    normalized = normalize_runtime_preset(reference)
    for scenario, _, _ in scenario_records:
        if scenario["path"] == normalized:
            return copy.deepcopy(scenario), normalized

    candidates = [
        Path(reference),
        ROOT / "presets" / Path(*PurePosixPath(normalized).parts),
        Path("/presets") / Path(*PurePosixPath(normalized).parts),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return parse_runtime_ini(candidate, catalog, normalized), normalized
    raise CatalogError(f"unknown runtime deployment or preset: {reference!r}")


def llama_selection_names(key: str, model: dict[str, Any]) -> set[str]:
    identity = model["_catalog"]
    return {
        key,
        identity["model_slug"],
        model["request_model_id"],
        *model.get("aliases", []),
    }


def compose_runtime_preset(
    *,
    base: str,
    bundle_value: str,
    model_value: str,
    server_overrides_value: str,
    model_overrides_value: str,
) -> tuple[str, list[str], dict[str, Any]]:
    catalog = load_catalog()
    validate_catalog(catalog)
    scenario_records = load_scenarios()
    base_scenario, base_path = resolve_runtime_scenario(base, catalog, scenario_records)
    base_parent = PurePosixPath(base_path).parent
    scenarios = {scenario["path"]: scenario for scenario, _, _ in scenario_records}

    bundles = parse_composition_list(bundle_value)
    requested_models = parse_composition_list(model_value)
    server_overrides = parse_composition_object(server_overrides_value, "PREFER_SERVER_OVERRIDES")
    model_overrides = parse_composition_object(model_overrides_value, "PREFER_MODEL_OVERRIDES")
    if any(not isinstance(value, dict) for value in model_overrides.values()):
        raise CatalogError("PREFER_MODEL_OVERRIDES values must be JSON objects")

    cohort = [
        scenario
        for scenario, _, _ in scenario_records
        if PurePosixPath(scenario["path"]).parent == base_parent
    ]
    if base_scenario not in cohort:
        cohort.insert(0, base_scenario)

    selected: list[dict[str, Any]] = []

    def model_slug_for_entry(entry: dict[str, Any]) -> str:
        return catalog["models"][entry["key"]]["_catalog"]["model_slug"]

    def add_entry(entry: dict[str, Any]) -> None:
        slug = model_slug_for_entry(entry)
        selected[:] = [existing for existing in selected if model_slug_for_entry(existing) != slug]
        selected.append(copy.deepcopy(entry))

    for bundle in bundles:
        if bundle in {"base", "current"}:
            bundle_scenario = base_scenario
        else:
            bundle_path = (base_parent / f"{bundle}.ini").as_posix()
            bundle_scenario = scenarios.get(bundle_path)
            if bundle_scenario is None:
                raise CatalogError(
                    f"unknown llama.cpp bundle {bundle!r} for {base_parent.as_posix() or 'root'}"
                )
        for entry in bundle_scenario.get("models", []):
            add_entry(entry)

    def matching_keys(selection: str) -> list[str]:
        return [
            key
            for key, model in catalog["models"].items()
            if selection in llama_selection_names(key, model)
        ]

    def template_entry(key: str) -> dict[str, Any]:
        model = catalog["models"][key]
        slug = model["_catalog"]["model_slug"]
        exact: list[dict[str, Any]] = []
        same_model: list[dict[str, Any]] = []
        for scenario in cohort:
            for entry in scenario.get("models", []):
                entry_model = catalog["models"][entry["key"]]
                if entry["key"] == key:
                    exact.append(entry)
                elif entry_model["_catalog"]["model_slug"] == slug:
                    same_model.append(entry)
        source = exact[0] if exact else (same_model[0] if same_model else OrderedDict())
        result = copy.deepcopy(source)
        result["key"] = key
        result.pop("section", None)
        result.pop("aliases", None)
        result.pop("request_model_id", None)
        return result

    for selection in requested_models:
        matches = matching_keys(selection)
        if not matches:
            raise CatalogError(f"unknown llama.cpp model selection: {selection!r}")
        if selection in catalog["models"]:
            key = selection
        else:
            cohort_keys = {
                entry["key"]
                for scenario in cohort
                for entry in scenario.get("models", [])
                if entry.get("key") in matches
            }
            if len(cohort_keys) == 1:
                key = next(iter(cohort_keys))
            elif len(matches) == 1:
                key = matches[0]
            else:
                raise CatalogError(
                    f"ambiguous llama.cpp model {selection!r}; choose an exact lane: {', '.join(matches)}"
                )
        add_entry(template_entry(key))

    if not bundles and not requested_models:
        selected = copy.deepcopy(base_scenario.get("models", []))
    if not selected:
        raise CatalogError("runtime composition selected no llama.cpp models")

    composed = OrderedDict(
        path="runtime/effective.ini",
        defaults=OrderedDict(base_scenario.get("defaults", {})),
        models=selected,
    )
    for name, value in server_overrides.items():
        if value is None:
            composed["defaults"].pop(name, None)
        else:
            composed["defaults"][name] = value

    applied_model_overrides: OrderedDict[str, Any] = OrderedDict()
    for entry in composed["models"]:
        key = entry["key"]
        model = catalog["models"][key]
        names = llama_selection_names(key, model)
        matching = [value for name, value in model_overrides.items() if name in names]
        if len(matching) > 1:
            raise CatalogError(f"multiple PREFER_MODEL_OVERRIDES entries target {key}")
        if matching:
            entry.setdefault("overrides", OrderedDict())
            for name, value in matching[0].items():
                entry["overrides"][name] = value
            applied_model_overrides[key] = matching[0]

    unknown_override_targets = [
        name
        for name in model_overrides
        if not any(name in llama_selection_names(entry["key"], catalog["models"][entry["key"]]) for entry in composed["models"])
    ]
    if unknown_override_targets:
        raise CatalogError(
            "PREFER_MODEL_OVERRIDES targets are not selected: " + ", ".join(unknown_override_targets)
        )

    ini, prestage = render_ini(catalog, composed)
    plan = OrderedDict(
        schema_version="prefer.runtime-plan.v1",
        runtime="llama.cpp",
        base_deployment=PurePosixPath(base_path).with_suffix("").as_posix(),
        bundles=bundles,
        requested_models=requested_models,
        resolved_model_keys=prestage,
        server_overrides=server_overrides,
        model_overrides=applied_model_overrides,
        precedence=[
            "catalog model and lane defaults",
            "hardware deployment defaults",
            "PREFER_SERVER_OVERRIDES",
            "PREFER_MODEL_OVERRIDES",
            "llama-server command arguments",
        ],
    )
    return ini, prestage, plan


def runtime_handoff_model_settings(
    handoff: dict[str, Any],
    model: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    template: OrderedDict[str, Any],
) -> OrderedDict[str, Any]:
    settings: OrderedDict[str, Any] = OrderedDict()
    raw_settings = model.get("settings", {})
    if not isinstance(raw_settings, dict):
        raise CatalogError(f"runtime handoff model {model.get('model_id')!r} settings must be an object")
    launcher = raw_settings.get("launcher", {})
    if not isinstance(launcher, dict):
        raise CatalogError(f"runtime handoff model {model.get('model_id')!r} launcher settings must be an object")
    protected = {"model", "model-draft", "mmproj", "alias"} & launcher.keys()
    if protected:
        raise CatalogError(
            f"runtime handoff launcher cannot replace artifact identity setting {sorted(protected)[0]!r}"
        )
    for name, value in launcher.items():
        if isinstance(value, (dict, list)):
            raise CatalogError(f"llama.cpp launcher setting {name!r} must be a scalar")
        if value is None:
            settings.pop(name, None)
        else:
            settings[name] = value
    for name, value in template.items():
        if name in {"model", "model-draft", "mmproj", "alias", "load-on-startup"}:
            continue
        if value is None:
            settings.pop(name, None)
        else:
            settings[name] = value

    primary: list[str] = []
    projectors: list[str] = []
    drafts: list[str] = []
    loras: list[str] = []
    for artifact_id in model.get("artifact_ids", []):
        artifact = artifacts.get(artifact_id)
        if artifact is None:
            raise CatalogError(f"runtime handoff model references unknown artifact {artifact_id!r}")
        role = str(artifact.get("role", "")).lower()
        path = artifact.get("local_path")
        if not isinstance(path, str) or not path.startswith("/"):
            raise CatalogError(f"runtime handoff artifact {artifact_id!r} has no materialized path")
        argument = artifact.get("settings", {}).get("argument") if isinstance(artifact.get("settings"), dict) else None
        if argument is not None:
            if not isinstance(argument, str) or not re.fullmatch(r"--?[a-z0-9][a-z0-9-]*", argument):
                raise CatalogError(f"runtime handoff artifact {artifact_id!r} has an unsafe launcher argument")
            name = argument.lstrip("-")
            if name in {"model", "model-draft", "mmproj", "lora"}:
                {"model": primary, "model-draft": drafts, "mmproj": projectors, "lora": loras}[name].append(path)
                continue
        if role in {"model", "model-shard", "target", "checkpoint"} or (not role and path.lower().endswith(".gguf")):
            primary.append(path)
        elif role in {"projector", "mmproj"}:
            projectors.append(path)
        elif role in {"draft", "drafter", "mtp", "dspark", "dflash"}:
            drafts.append(path)
        elif role in {"lora", "adapter"}:
            loras.append(path)

    if not primary:
        raise CatalogError(f"runtime handoff model {model.get('model_id')!r} has no llama.cpp model GGUF")
    settings["model"] = primary[0]
    if projectors:
        settings["mmproj"] = projectors[0]
    if drafts:
        settings["model-draft"] = drafts[0]
    if loras:
        settings["lora"] = loras[0]
    settings["alias"] = model["request_model_id"]
    return settings


def compose_runtime_handoff_preset(
    *,
    handoff_path: str,
    base: str,
    default_base: str,
    server_overrides_value: str,
    model_overrides_value: str,
) -> tuple[str, list[str], dict[str, Any]]:
    handoff = load_json(Path(handoff_path))
    if handoff.get("schema_version") != "prefer.runtime-handoff.v1" or handoff.get("engine") != "llama.cpp":
        raise CatalogError("materialized runtime handoff is not for llama.cpp")
    models = handoff.get("models")
    raw_artifacts = handoff.get("artifacts")
    if not isinstance(models, list) or not models or not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise CatalogError("materialized runtime handoff requires models and artifacts")
    artifacts = {artifact.get("id"): artifact for artifact in raw_artifacts if isinstance(artifact, dict)}
    if len(artifacts) != len(raw_artifacts):
        raise CatalogError("materialized runtime handoff has duplicate or invalid artifacts")

    catalog = load_catalog()
    validate_catalog(catalog)
    scenario_records = load_scenarios()
    base_reference = base or str(handoff.get("base_deployment") or default_base)
    if not base_reference:
        raise CatalogError("runtime handoff needs a base deployment")
    base_scenario, base_path = resolve_runtime_scenario(base_reference, catalog, scenario_records)
    defaults = OrderedDict(base_scenario.get("defaults", {}))
    server_overrides = parse_composition_object(server_overrides_value, "PREFER_SERVER_OVERRIDES")
    handoff_server = handoff.get("server_settings", {})
    if not isinstance(handoff_server, dict):
        raise CatalogError("runtime handoff server_settings must be an object")
    protected_defaults = {"model", "model-draft", "mmproj", "alias", "lora"}
    if protected_defaults & (handoff_server.keys() | server_overrides.keys()):
        raise CatalogError("runtime server settings cannot replace model artifact identity")
    for source in (handoff_server, server_overrides):
        for name, value in source.items():
            if isinstance(value, (dict, list)):
                raise CatalogError(f"llama.cpp server setting {name!r} must be a scalar")
            if value is None:
                defaults.pop(name, None)
            else:
                defaults[name] = value

    model_overrides = parse_composition_object(model_overrides_value, "PREFER_MODEL_OVERRIDES")
    if any(not isinstance(value, dict) for value in model_overrides.values()):
        raise CatalogError("PREFER_MODEL_OVERRIDES values must be JSON objects")
    sections: list[tuple[str, OrderedDict[str, Any]]] = []
    applied_model_overrides: OrderedDict[str, Any] = OrderedDict()
    used_sections: set[str] = set()
    selected_names: set[str] = set()

    for model in models:
        if not isinstance(model, dict):
            raise CatalogError("runtime handoff model must be an object")
        model_id = model.get("model_id")
        request_model_id = model.get("request_model_id")
        if not isinstance(model_id, str) or not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", model_id):
            raise CatalogError("runtime handoff model id is unsafe")
        if not isinstance(request_model_id, str) or not request_model_id or re.search(r"[\[\]=,\r\n]", request_model_id):
            raise CatalogError(f"runtime handoff request model id for {model_id} is unsafe for llama.cpp")
        if model_id in used_sections:
            raise CatalogError(f"duplicate runtime handoff model {model_id}")
        used_sections.add(model_id)
        names = {model_id, request_model_id}
        selected_names.update(names)

        candidates = [
            entry for entry in base_scenario.get("models", [])
            if catalog["models"][entry["key"]]["_catalog"]["model_slug"] == model_id
        ]
        template_entry = candidates[0] if candidates else next(iter(base_scenario.get("models", [])), None)
        template = OrderedDict()
        if template_entry is not None:
            template = OrderedDict(template_entry.get("overrides", {}))
            if not candidates:
                for name in [name for name in template if name.startswith("spec-")]:
                    template.pop(name, None)
        settings = runtime_handoff_model_settings(handoff, model, artifacts, template)
        for source in (handoff_server, server_overrides):
            for name, value in source.items():
                if value is None:
                    settings.pop(name, None)
                else:
                    settings[name] = value

        matching = [value for name, value in model_overrides.items() if name in names]
        if len(matching) > 1:
            raise CatalogError(f"multiple PREFER_MODEL_OVERRIDES entries target {model_id}")
        if matching:
            protected = protected_defaults & matching[0].keys()
            if protected:
                raise CatalogError(f"runtime model overrides cannot replace {sorted(protected)[0]!r}")
            for name, value in matching[0].items():
                if isinstance(value, (dict, list)):
                    raise CatalogError(f"llama.cpp model setting {name!r} must be a scalar")
                if value is None:
                    settings.pop(name, None)
                else:
                    settings[name] = value
            applied_model_overrides[model_id] = matching[0]
        sections.append((model_id, settings))

    unknown_targets = [name for name in model_overrides if name not in selected_names]
    if unknown_targets:
        raise CatalogError("PREFER_MODEL_OVERRIDES targets are not selected: " + ", ".join(unknown_targets))

    lines = ["version = 1", ""]
    if defaults:
        lines.append("[*]")
        lines.extend(f"{name} = {ini_value(value, name)}" for name, value in defaults.items())
        lines.append("")
    for section, settings in sections:
        lines.append(f"[{section}]")
        lines.extend(f"{name} = {ini_value(value, name)}" for name, value in settings.items())
        lines.append("")

    artifact_ids = [artifact["id"] for artifact in raw_artifacts]
    plan = OrderedDict(
        schema_version="prefer.runtime-plan.v1",
        runtime="llama.cpp",
        base_deployment=PurePosixPath(base_path).with_suffix("").as_posix(),
        handoff_fingerprint=handoff.get("handoff_fingerprint"),
        bundles=[],
        requested_models=[model["model_id"] for model in models],
        resolved_model_keys=[],
        resolved_artifact_ids=artifact_ids,
        server_overrides=server_overrides,
        model_overrides=applied_model_overrides,
        precedence=[
            "runtime handoff model and artifact settings",
            "hardware deployment defaults",
            "runtime handoff server settings",
            "PREFER_SERVER_OVERRIDES",
            "PREFER_MODEL_OVERRIDES",
            "llama-server command arguments",
        ],
    )
    return "\n".join(lines), artifact_ids, plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated files are stale")
    parser.add_argument("--compose", action="store_true", help="write an ephemeral runtime-composed preset")
    parser.add_argument("--compose-handoff", action="store_true", help="write a preset from a materialized runtime handoff")
    parser.add_argument("--handoff-input", default="")
    parser.add_argument("--default-base", default="")
    parser.add_argument("--base", default="")
    parser.add_argument("--bundles", default="")
    parser.add_argument("--models", default="")
    parser.add_argument("--server-overrides", default="")
    parser.add_argument("--model-overrides", default="")
    parser.add_argument("--output")
    parser.add_argument("--prestage-output")
    parser.add_argument("--plan-output")
    args = parser.parse_args()

    if args.compose_handoff:
        if args.check or args.compose or not args.handoff_input or not args.output or not args.prestage_output or not args.plan_output:
            parser.error("--compose-handoff requires --handoff-input, --output, --prestage-output, and --plan-output")
        try:
            ini, artifact_ids, plan = compose_runtime_handoff_preset(
                handoff_path=args.handoff_input,
                base=args.base,
                default_base=args.default_base,
                server_overrides_value=args.server_overrides,
                model_overrides_value=args.model_overrides,
            )
            output = Path(args.output)
            prestage_output = Path(args.prestage_output)
            plan_output = Path(args.plan_output)
            for path in (output, prestage_output, plan_output):
                path.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(ini, encoding="utf-8", newline="\n")
            prestage_output.write_text(",".join(artifact_ids) + "\n", encoding="utf-8", newline="\n")
            plan_output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8", newline="\n")
            print(f"composed llama.cpp runtime preset from immutable handoff {plan['handoff_fingerprint']}")
            return 0
        except (CatalogError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
            print(f"generate-presets: {exc}", file=sys.stderr)
            return 2

    if args.compose:
        if args.check or not args.base or not args.output or not args.prestage_output or not args.plan_output:
            parser.error("--compose requires --base, --output, --prestage-output, and --plan-output")
        try:
            ini, prestage, plan = compose_runtime_preset(
                base=args.base,
                bundle_value=args.bundles,
                model_value=args.models,
                server_overrides_value=args.server_overrides,
                model_overrides_value=args.model_overrides,
            )
            output = Path(args.output)
            prestage_output = Path(args.prestage_output)
            plan_output = Path(args.plan_output)
            for path in (output, prestage_output, plan_output):
                path.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(ini, encoding="utf-8", newline="\n")
            prestage_output.write_text(",".join(prestage) + "\n", encoding="utf-8", newline="\n")
            plan_output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8", newline="\n")
            print(
                f"composed llama.cpp runtime preset from {plan['base_deployment']}: "
                + ", ".join(prestage)
            )
            return 0
        except (CatalogError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
            print(f"generate-presets: {exc}", file=sys.stderr)
            return 2

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
