from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from .paths import (
    CONTRACT_PATH,
    CONTRACT_SCHEMA_PATH,
    CORPUS_PATH,
    CORPUS_SCHEMA_PATH,
    PRESETS_ROOT,
)
from .schema import assert_valid


class ContractError(ValueError):
    pass


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_contract() -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    assert_valid(contract, load_json(CONTRACT_SCHEMA_PATH), "client contract")
    return contract


def load_corpus() -> dict[str, Any]:
    corpus = load_json(CORPUS_PATH)
    assert_valid(corpus, load_json(CORPUS_SCHEMA_PATH), "evaluation corpus")
    return corpus


def known_model_names(contract: dict[str, Any] | None = None) -> set[str]:
    contract = contract or load_contract()
    names: set[str] = set()
    for model in contract["models"]:
        names.add(model["discovery_id"])
        names.update(model["aliases"])
    return names


def model_record(requested_id: str, contract: dict[str, Any] | None = None) -> dict[str, Any] | None:
    contract = contract or load_contract()
    for model in contract["models"]:
        if requested_id in {model["canonical_id"], model["discovery_id"]} or requested_id in model["aliases"]:
            return model
    return None


def validate_models_response(payload: Any) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(payload, dict):
        return [{"path": "$", "message": "response must be an object"}]
    data = payload.get("data")
    if not isinstance(data, list):
        return [{"path": "$.data", "message": "data must be an array"}]
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            errors.append({"path": f"$.data[{index}]", "message": "model must be an object"})
        elif not isinstance(item.get("id"), str) or not item["id"].strip():
            errors.append({"path": f"$.data[{index}].id", "message": "id must be a non-empty string"})
    return errors


def validate_error_response(payload: Any) -> list[dict[str, str]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("error"), dict):
        return [{"path": "$.error", "message": "error must be an object"}]
    errors: list[dict[str, str]] = []
    for field in ("message", "type"):
        if not isinstance(payload["error"].get(field), str) or not payload["error"][field]:
            errors.append({"path": f"$.error.{field}", "message": "must be a non-empty string"})
    return errors


def validate_tool_calls(tool_calls: Any) -> list[dict[str, str]]:
    if not isinstance(tool_calls, list) or not tool_calls:
        return [{"path": "$.tool_calls", "message": "tool_calls must be a non-empty array"}]
    errors: list[dict[str, str]] = []
    for index, call in enumerate(tool_calls):
        path = f"$.tool_calls[{index}]"
        if not isinstance(call, dict):
            errors.append({"path": path, "message": "tool call must be an object"})
            continue
        if not isinstance(call.get("id"), str) or not call["id"]:
            errors.append({"path": f"{path}.id", "message": "id must be a non-empty string"})
        if call.get("type") != "function":
            errors.append({"path": f"{path}.type", "message": "type must be function"})
        function = call.get("function")
        if not isinstance(function, dict):
            errors.append({"path": f"{path}.function", "message": "function must be an object"})
            continue
        if not isinstance(function.get("name"), str) or not function["name"]:
            errors.append({"path": f"{path}.function.name", "message": "name must be a non-empty string"})
        arguments = function.get("arguments")
        if not isinstance(arguments, str):
            errors.append({"path": f"{path}.function.arguments", "message": "arguments must be a JSON string"})
        else:
            try:
                parsed = json.loads(arguments)
                if not isinstance(parsed, dict):
                    raise ValueError("not an object")
            except (json.JSONDecodeError, ValueError):
                errors.append({"path": f"{path}.function.arguments", "message": "arguments must encode a JSON object"})
    return errors


def validate_chat_response(payload: Any) -> list[dict[str, str]]:
    if not isinstance(payload, dict):
        return [{"path": "$", "message": "response must be an object"}]
    errors: list[dict[str, str]] = []
    required = ("id", "object", "created", "model", "choices")
    for field in required:
        if field not in payload:
            errors.append({"path": "$", "message": f"missing required property {field!r}"})
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        errors.append({"path": "$.choices", "message": "choices must be a non-empty array"})
        return errors
    for index, choice in enumerate(choices):
        path = f"$.choices[{index}]"
        if not isinstance(choice, dict):
            errors.append({"path": path, "message": "choice must be an object"})
            continue
        for field in ("index", "message", "finish_reason"):
            if field not in choice:
                errors.append({"path": path, "message": f"missing required property {field!r}"})
        message = choice.get("message")
        if not isinstance(message, dict):
            errors.append({"path": f"{path}.message", "message": "message must be an object"})
            continue
        if message.get("role") != "assistant":
            errors.append({"path": f"{path}.message.role", "message": "role must be assistant"})
        content = message.get("content")
        tool_calls = message.get("tool_calls")
        if not isinstance(content, str) and tool_calls is None:
            errors.append({"path": f"{path}.message.content", "message": "content must be a string unless tool_calls are present"})
        if tool_calls is not None:
            errors.extend(validate_tool_calls(tool_calls))
    return errors


def validate_chat_request(payload: Any, enforce_known_model: bool = True) -> None:
    if not isinstance(payload, dict):
        raise ContractError("request must be a JSON object")
    model = payload.get("model")
    if not isinstance(model, str) or not model:
        raise ContractError("model is required")
    if enforce_known_model and model not in known_model_names():
        raise ContractError("unknown model id or alias")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ContractError("messages must be a non-empty array")
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in {"system", "user", "assistant", "tool"}:
            raise ContractError("each message needs a supported role")
        if message.get("role") == "tool" and (
            not isinstance(message.get("tool_call_id"), str) or not message["tool_call_id"]
        ):
            raise ContractError("tool messages require tool_call_id")
    if payload.get("stream") and payload.get("n", 1) != 1:
        raise ContractError("streaming n != 1 is outside the PreFer contract")
    if payload.get("parallel_tool_calls"):
        raise ContractError("parallel_tool_calls is outside the PreFer contract")
    if "response_format" in payload:
        response_format = payload["response_format"]
        if not isinstance(response_format, dict) or response_format.get("type") != "json_schema":
            raise ContractError("response_format must use type=json_schema")
        wrapper = response_format.get("json_schema")
        if not isinstance(wrapper, dict) or wrapper.get("strict") is not True:
            raise ContractError("json_schema.strict must be true")
        if not isinstance(wrapper.get("name"), str) or not wrapper["name"]:
            raise ContractError("json_schema.name is required")
        if not isinstance(wrapper.get("schema"), dict):
            raise ContractError("json_schema.schema must be an object")
    if "tools" in payload:
        tools = payload["tools"]
        if not isinstance(tools, list) or not tools:
            raise ContractError("tools must be a non-empty array")
        for tool in tools:
            if not isinstance(tool, dict):
                raise ContractError("only OpenAI function tools are in contract")
            function = tool.get("function")
            if tool.get("type") != "function" or not isinstance(function, dict):
                raise ContractError("only OpenAI function tools are in contract")
            if not isinstance(function.get("name"), str) or not function["name"] or not isinstance(function.get("parameters"), dict):
                raise ContractError("function tools require name and parameters")


def parse_preset(path: Path) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    section: str | None = None
    values: dict[str, str] = {}

    def append_section() -> None:
        if section is None or section == "*":
            return
        aliases = [alias.strip() for alias in values.get("alias", "").split(",") if alias.strip()]
        models.append({
            "canonical_id": section,
            "aliases": aliases,
            "model_path": values.get("model"),
            "model_draft_path": values.get("model-draft"),
            "spec_type": values.get("spec-type"),
            "spec_draft_n_max": values.get("spec-draft-n-max"),
            "load_on_startup": values.get("load-on-startup", "false").strip().lower() == "true",
        })

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            append_section()
            section = line[1:-1]
            values = {}
        elif section is not None and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    append_section()
    return models


def preset_contract_diff(contract: dict[str, Any] | None = None) -> list[str]:
    contract = contract or load_contract()
    expected: dict[str, dict[str, Any]] = {model["canonical_id"]: model for model in contract["models"]}
    actual: dict[str, dict[str, Any]] = {}
    for preset_path in sorted(PRESETS_ROOT.glob("*.ini")):
        for model in parse_preset(preset_path):
            record = actual.setdefault(model["canonical_id"], {"aliases": model["aliases"], "presets": []})
            if record["aliases"] != model["aliases"]:
                record.setdefault("alias_conflicts", []).append({preset_path.name: model["aliases"]})
            record["presets"].append(preset_path.name)

    differences: list[str] = []
    for canonical_id in sorted(set(expected) | set(actual)):
        if canonical_id not in expected:
            differences.append(f"uncontracted preset model: {canonical_id}")
            continue
        if canonical_id not in actual:
            differences.append(f"contract model absent from presets: {canonical_id}")
            continue
        if actual[canonical_id].get("alias_conflicts"):
            differences.append(f"alias conflict for {canonical_id}: {actual[canonical_id]['alias_conflicts']}")
        if actual[canonical_id]["aliases"] != expected[canonical_id]["aliases"]:
            differences.append(
                f"aliases differ for {canonical_id}: contract={expected[canonical_id]['aliases']} preset={actual[canonical_id]['aliases']}"
            )
        if sorted(actual[canonical_id]["presets"]) != sorted(expected[canonical_id]["presets"]):
            differences.append(
                f"presets differ for {canonical_id}: contract={expected[canonical_id]['presets']} actual={actual[canonical_id]['presets']}"
            )
        quant = canonical_id.rsplit(":", 1)[-1]
        if quant != expected[canonical_id]["quantization"]:
            differences.append(f"quantization differs for {canonical_id}: {expected[canonical_id]['quantization']} vs {quant}")
    return differences


def inspect_models_max(repo_root: Path) -> dict[str, Any]:
    compose = (repo_root / "docker-compose.yml").read_text(encoding="utf-8")
    env_example = (repo_root / ".env.example").read_text(encoding="utf-8")
    detect = (repo_root / "docker" / "prefer" / "detect-preset.sh").read_text(encoding="utf-8")
    compose_match = re.search(r"LLAMA_ARG_MODELS_MAX=\$\{LLAMA_ARG_MODELS_MAX:-([0-9]+)\}", compose)
    example_match = re.search(r"^LLAMA_ARG_MODELS_MAX=([0-9]+)$", env_example, re.MULTILINE)
    preset_load = {
        path.name: any(model["load_on_startup"] for model in parse_preset(path))
        for path in sorted(PRESETS_ROOT.glob("*.ini"))
    }
    return {
        "compose_default": int(compose_match.group(1)) if compose_match else None,
        "env_example_default": int(example_match.group(1)) if example_match else None,
        "auto_detection_default": 1 if 'LLAMA_ARG_MODELS_MAX:-1' in detect else None,
        "upstream_fallback_default": 4,
        "presets_with_load_on_startup": sorted(name for name, enabled in preset_load.items() if enabled),
        "tier_presets_with_load_on_startup": sorted(
            name for name, enabled in preset_load.items() if enabled and re.fullmatch(r"[0-9]+gb\.ini", name)
        ),
        "precedence": [
            "llama-server --models-max command-line argument",
            "LLAMA_ARG_MODELS_MAX environment value",
            "auto-detection fallback 1 when no selected tier entry uses load-on-startup",
            "llama.cpp router fallback 4 when PreFer leaves the setting unset"
        ]
    }
