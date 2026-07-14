from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
import time
from typing import Any

from .contract import (
    load_contract,
    load_corpus,
    model_record,
    validate_chat_response,
    validate_error_response,
    validate_models_response,
    validate_tool_calls,
)
from .diagnostics import reason_category
from .evaluate import evaluate_content
from .http_client import ClientTimeout, TransportError, request_json, stream_chat
from .memory import NvidiaMemorySampler
from .paths import PRESETS_ROOT
from .results import empty_cell, error_cell, skip_cell


@dataclass
class LiveConfig:
    base_url: str
    preset: str
    models_max: int
    model_a: str
    model_b: str | None
    timeout_seconds: float = 180.0
    concurrency: int = 2
    contexts_to_run: tuple[int, ...] = (8192,)
    include_tools: bool = True
    idle_wait_seconds: int = 0
    max_generated_request_bytes: int = 2_000_000


def _model(requested_id: str) -> dict[str, Any]:
    record = model_record(requested_id)
    if record is None:
        return {"requested_id": requested_id, "canonical_id": None, "discovery_id": None, "alias": None, "quantization": None}
    return {
        "requested_id": requested_id,
        "canonical_id": record["canonical_id"],
        "discovery_id": record["discovery_id"],
        "alias": requested_id if requested_id in record["aliases"] else None,
        "quantization": record["quantization"],
    }


def _chat_payload(model: str, prompt: str, max_tokens: int = 64, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    payload.update(extra)
    return payload


def _timings(payload: dict[str, Any], total_ms: float, memory: dict[str, Any]) -> dict[str, Any]:
    timings = payload.get("timings") if isinstance(payload.get("timings"), dict) else {}
    measurements: dict[str, Any] = {"total_ms": round(total_ms, 3), "memory": memory}
    mapping = {
        "prompt_ms": "prefill_ms",
        "predicted_ms": "decode_ms",
        "prompt_n": "prompt_tokens",
        "predicted_n": "decode_tokens",
        "prompt_per_second": "prefill_tokens_per_second",
        "predicted_per_second": "decode_tokens_per_second",
    }
    for source, target in mapping.items():
        value = timings.get(source)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            measurements[target] = value
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    measurements.setdefault("prompt_tokens", usage.get("prompt_tokens"))
    measurements.setdefault("decode_tokens", usage.get("completion_tokens"))
    measurements = {key: value for key, value in measurements.items() if value is not None}
    return measurements


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 3)


def _nonstream_cell(cell_id: str, kind: str, base_url: str, model: str, prompt: str, timeout: float) -> dict[str, Any]:
    cell = empty_cell(cell_id, kind, model=_model(model))
    try:
        with NvidiaMemorySampler() as sampler:
            response = request_json(base_url, "POST", "/v1/chat/completions", _chat_payload(model, prompt), timeout=timeout)
        payload = response.json()
        if response.status >= 400:
            error_errors = validate_error_response(payload)
            error_payload = payload.get("error", {}) if isinstance(payload.get("error"), dict) else {}
            message = str(error_payload.get("message", "request rejected"))[:500]
            cell["status"] = "failed"
            cell["contract"] = {"pass": False, "checks": [{"name": "http_success", "pass": False}, {"name": "error_envelope", "pass": not error_errors}]}
            category_code = "model_load_failure" if "failed to load" in message.casefold() else "http_rejection"
            cell["error"] = {
                "category": reason_category(category_code),
                "code": "http_rejection",
                "detail": f"HTTP {response.status}: {message}",
            }
            cell["measurements"] = {"total_ms": response.duration_ms, "memory": sampler.evidence()}
            cell["evidence"] = {
                "http_status": response.status,
                "error_type": error_payload.get("type"),
                "error_code": error_payload.get("code"),
                "error_message": message,
            }
            return cell
        errors = validate_chat_response(payload)
        cell["contract"] = {"pass": not errors, "checks": [{"name": "chat_envelope", "pass": not errors, "errors": errors}]}
        cell["status"] = "passed" if not errors else "failed"
        cell["measurements"] = _timings(payload, response.duration_ms, sampler.evidence())
        cell["evidence"] = {"http_status": response.status, "finish_reason": payload.get("choices", [{}])[0].get("finish_reason")}
        return cell
    except ClientTimeout as exc:
        return error_cell(cell_id, kind, "client_timeout", str(exc), _model(model))
    except (TransportError, json.JSONDecodeError, OSError) as exc:
        return error_cell(cell_id, kind, "transport_error", f"{type(exc).__name__}: {exc}", _model(model))


def _models_snapshot(base_url: str, timeout: float) -> tuple[int, dict[str, Any], list[dict[str, str]]]:
    response = request_json(base_url, "GET", "/v1/models", timeout=timeout)
    payload = response.json()
    return response.status, payload, validate_models_response(payload)


def _configured_identity_probe(base_url: str, timeout: float, record: dict[str, Any]) -> dict[str, Any]:
    cell = empty_cell("configured-identity-route-a", "models_discovery", model=_model(record["canonical_id"]))
    if record["canonical_id"] == record["discovery_id"]:
        return skip_cell(
            "configured-identity-route-a",
            "models_discovery",
            "identity_not_normalized",
            "Configured and discovery IDs are identical for this model.",
            _model(record["canonical_id"]),
        )
    try:
        response = request_json(
            base_url,
            "POST",
            "/v1/chat/completions",
            _chat_payload(record["canonical_id"], "Reply with synthetic identity probe.", max_tokens=16),
            timeout=timeout,
        )
        payload = response.json()
        if response.status < 400:
            errors = validate_chat_response(payload)
            behavior = "accepted_extension"
        else:
            errors = validate_error_response(payload)
            behavior = "rejected_not_promised_route"
        passed = not errors
        cell["status"] = "passed" if passed else "failed"
        cell["contract"] = {
            "pass": passed,
            "checks": [{"name": "bounded_success_or_error_envelope", "pass": passed, "errors": errors}],
        }
        cell["measurements"] = {"total_ms": round(response.duration_ms, 3)}
        cell["evidence"] = {"http_status": response.status, "behavior": behavior}
        return cell
    except ClientTimeout as exc:
        return error_cell("configured-identity-route-a", "models_discovery", "client_timeout", str(exc), _model(record["canonical_id"]))
    except (TransportError, json.JSONDecodeError, OSError) as exc:
        return error_cell("configured-identity-route-a", "models_discovery", "transport_error", f"{type(exc).__name__}: {exc}", _model(record["canonical_id"]))


def _status_map(payload: dict[str, Any]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for item in payload.get("data", []):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        status = item.get("status")
        result[item["id"]] = status.get("value") if isinstance(status, dict) else status if isinstance(status, str) else None
    return result


def _stream_cell(config: LiveConfig) -> dict[str, Any]:
    cell = empty_cell("stream-a", "streaming", model=_model(config.model_a))
    try:
        with NvidiaMemorySampler() as sampler:
            response = stream_chat(
                config.base_url,
                _chat_payload(config.model_a, "Return one short sentence containing the words synthetic stream check.", max_tokens=48, stream=True),
                timeout=config.timeout_seconds,
            )
        content_type = response.headers.get("content-type", "")
        checks = [
            {"name": "content_type", "pass": content_type.startswith("text/event-stream"), "actual": content_type},
            {"name": "chunk_count", "pass": len(response.events) > 0, "actual": len(response.events)},
            {"name": "done_termination", "pass": response.done},
        ]
        passed = all(check["pass"] for check in checks)
        cell["status"] = "passed" if passed else "failed"
        cell["contract"] = {"pass": passed, "checks": checks}
        cell["measurements"] = {
            "total_ms": round(response.duration_ms, 3),
            "ttft_ms": round(response.ttft_ms, 3) if response.ttft_ms is not None else None,
            "stream_events": len(response.events),
            "memory": sampler.evidence(),
        }
        cell["evidence"] = {"content_characters": len(response.content), "done": response.done}
        return cell
    except ClientTimeout as exc:
        return error_cell("stream-a", "streaming", "client_timeout", str(exc), _model(config.model_a))
    except (TransportError, ValueError, OSError) as exc:
        return error_cell("stream-a", "streaming", "stream_error", f"{type(exc).__name__}: {exc}", _model(config.model_a))


def _cancellation_cell(config: LiveConfig) -> dict[str, Any]:
    cell = empty_cell("stream-cancel-a", "cancellation", model=_model(config.model_a))
    try:
        response = stream_chat(
            config.base_url,
            _chat_payload(config.model_a, "Write a synthetic list of thirty short numbered items.", max_tokens=256, stream=True),
            timeout=config.timeout_seconds,
            cancel_after_events=1,
        )
        passed = response.cancelled and response.duration_ms < config.timeout_seconds * 1000
        cell["status"] = "passed" if passed else "failed"
        cell["contract"] = {
            "pass": passed,
            "checks": [
                {"name": "client_closed_after_event", "pass": response.cancelled},
                {"name": "bounded_return", "pass": response.duration_ms < config.timeout_seconds * 1000},
            ],
        }
        cell["measurements"] = {"total_ms": round(response.duration_ms, 3), "events_before_close": len(response.events)}
        cell["evidence"] = {"backend_work_cancelled": "not_observed_and_not_promised"}
        return cell
    except ClientTimeout as exc:
        return error_cell("stream-cancel-a", "cancellation", "client_timeout", str(exc), _model(config.model_a))
    except (TransportError, ValueError, OSError) as exc:
        return error_cell("stream-cancel-a", "cancellation", "stream_error", f"{type(exc).__name__}: {exc}", _model(config.model_a))


def _concurrency_cell(config: LiveConfig) -> dict[str, Any]:
    cell = empty_cell(f"concurrency-{config.concurrency}-a", "concurrency", model=_model(config.model_a))

    def call(index: int) -> dict[str, Any]:
        response = request_json(
            config.base_url,
            "POST",
            "/v1/chat/completions",
            _chat_payload(config.model_a, f"Reply with the synthetic marker concurrent-{index}.", max_tokens=32),
            timeout=config.timeout_seconds,
        )
        payload = response.json()
        return {"status": response.status, "duration_ms": response.duration_ms, "errors": validate_chat_response(payload) if response.status < 400 else validate_error_response(payload)}

    started = time.perf_counter()
    responses: list[dict[str, Any]] = []
    try:
        with NvidiaMemorySampler() as sampler:
            with ThreadPoolExecutor(max_workers=config.concurrency) as pool:
                futures = [pool.submit(call, index) for index in range(config.concurrency)]
                for future in as_completed(futures):
                    responses.append(future.result())
        wall_ms = (time.perf_counter() - started) * 1000
        passed = len(responses) == config.concurrency and all(item["status"] == 200 and not item["errors"] for item in responses)
        individual = sorted(item["duration_ms"] for item in responses)
        cell["status"] = "passed" if passed else "failed"
        cell["contract"] = {"pass": passed, "checks": [{"name": "all_responses", "pass": passed, "responses": responses}]}
        cell["measurements"] = {
            "total_ms": round(wall_ms, 3),
            "request_count": config.concurrency,
            "individual_ms": [round(value, 3) for value in individual],
            "p50_ms": _percentile(individual, 0.50),
            "p95_ms": _percentile(individual, 0.95),
            "memory": sampler.evidence(),
        }
        return cell
    except (ClientTimeout, TransportError, OSError) as exc:
        return error_cell(cell["id"], "concurrency", "concurrency_error", f"{type(exc).__name__}: {exc}", _model(config.model_a))


def _structured_cells(config: LiveConfig) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for case in load_corpus()["cases"]:
        cell_id = f"structured-{case['id']}"
        cell = empty_cell(cell_id, "structured_output", model=_model(config.model_a))
        request_body = _chat_payload(
            config.model_a,
            f"{case['instruction']}\n\nSOURCE:\n{case['source']}",
            max_tokens=512,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": case["id"].replace("-", "_"), "strict": True, "schema": case["output_schema"]},
            },
        )
        try:
            with NvidiaMemorySampler() as sampler:
                response = request_json(config.base_url, "POST", "/v1/chat/completions", request_body, timeout=config.timeout_seconds)
            payload = response.json()
            if response.status >= 400:
                error_errors = validate_error_response(payload)
                error_payload = payload.get("error", {}) if isinstance(payload.get("error"), dict) else {}
                message = str(error_payload.get("message", "request rejected"))[:500]
                cell["status"] = "failed"
                cell["contract"] = {
                    "pass": False,
                    "checks": [
                        {"name": "http_success", "pass": False},
                        {"name": "error_envelope", "pass": not error_errors, "errors": error_errors},
                    ],
                }
                cell["quality"] = {"schema_valid": False, "semantic_evaluated": False, "semantic_anomalies": []}
                cell["measurements"] = {"total_ms": response.duration_ms, "memory": sampler.evidence()}
                cell["error"] = {
                    "category": reason_category("http_rejection"),
                    "code": "http_rejection",
                    "detail": f"HTTP {response.status}: {message}",
                }
                cell["evidence"] = {
                    "case_id": case["id"],
                    "http_status": response.status,
                    "error_type": error_payload.get("type"),
                    "error_message": message,
                }
                cells.append(cell)
                continue
            envelope_errors = validate_chat_response(payload)
            content = payload.get("choices", [{}])[0].get("message", {}).get("content")
            evaluation = evaluate_content(content, case["output_schema"], case["semantic_rules"])
            envelope_pass = response.status == 200 and not envelope_errors
            cell["contract"] = {
                "pass": envelope_pass and evaluation["schema_valid"],
                "checks": [
                    {"name": "chat_envelope", "pass": envelope_pass, "errors": envelope_errors},
                    {"name": "strict_json_schema", "pass": evaluation["schema_valid"], "errors": evaluation["schema_errors"]},
                ],
            }
            cell["quality"] = {
                "schema_valid": evaluation["schema_valid"],
                "semantic_evaluated": True,
                "semantic_anomalies": evaluation["semantic_anomalies"],
            }
            cell["status"] = "passed" if cell["contract"]["pass"] else "failed"
            cell["measurements"] = _timings(payload, response.duration_ms, sampler.evidence())
            cell["evidence"] = {
                "case_id": case["id"],
                "json_valid": evaluation["json_valid"],
                "http_status": response.status,
                "synthetic_response_document": evaluation["document"],
            }
        except ClientTimeout as exc:
            cell = error_cell(cell_id, "structured_output", "client_timeout", str(exc), _model(config.model_a))
            cell["quality"] = {"schema_valid": False, "semantic_evaluated": False, "semantic_anomalies": []}
        except (TransportError, json.JSONDecodeError, OSError) as exc:
            cell = error_cell(cell_id, "structured_output", "transport_error", f"{type(exc).__name__}: {exc}", _model(config.model_a))
            cell["quality"] = {"schema_valid": False, "semantic_evaluated": False, "semantic_anomalies": []}
        cells.append(cell)
    return cells


def _tools_cell(config: LiveConfig) -> dict[str, Any]:
    if not config.include_tools:
        return skip_cell("tools-a", "tools", "operator_disabled", "Tool envelope replay was disabled for this run.", _model(config.model_a))
    cell = empty_cell("tools-a", "tools", model=_model(config.model_a))
    tool = {
        "type": "function",
        "function": {
            "name": "lookup_fixture",
            "description": "Read one synthetic fixture record",
            "parameters": {
                "type": "object",
                "required": ["record_id"],
                "properties": {"record_id": {"type": "string"}},
                "additionalProperties": False,
            },
        },
    }
    body = _chat_payload(
        config.model_a,
        "Call lookup_fixture exactly once with record_id SYN-42. Do not answer from memory.",
        max_tokens=128,
        tools=[tool],
        tool_choice={"type": "function", "function": {"name": "lookup_fixture"}},
    )
    try:
        response = request_json(config.base_url, "POST", "/v1/chat/completions", body, timeout=config.timeout_seconds)
        payload = response.json()
        if response.status >= 400:
            errors = validate_error_response(payload)
            cell["status"] = "failed"
            cell["contract"] = {"pass": False, "checks": [{"name": "tool_request_accepted", "pass": False}, {"name": "error_envelope", "pass": not errors}]}
            cell["measurements"] = {"total_ms": response.duration_ms}
            cell["error"] = {
                "category": reason_category("tool_request_rejected"),
                "code": "tool_request_rejected",
                "detail": f"HTTP {response.status}",
            }
            return cell
        envelope_errors = validate_chat_response(payload)
        message = payload.get("choices", [{}])[0].get("message", {})
        calls = message.get("tool_calls")
        if calls is None:
            cell["status"] = "unsupported"
            cell["contract"] = {"pass": None, "checks": [{"name": "conditional_tool_call", "pass": None}]}
            cell["skip"] = {
                "category": reason_category("model_did_not_emit_tool_call"),
                "code": "model_did_not_emit_tool_call",
                "detail": "Tool selection quality is outside the stable contract.",
            }
            cell["measurements"] = _timings(payload, response.duration_ms, {"source": "not_sampled", "samples": 0})
            return cell
        tool_errors = validate_tool_calls(calls)
        first_call = calls[0] if not tool_errors else None
        checks = [
            {"name": "chat_envelope", "pass": not envelope_errors, "errors": envelope_errors},
            {"name": "tool_call_envelope", "pass": not tool_errors, "errors": tool_errors},
        ]
        followup_duration_ms: float | None = None
        if first_call is not None:
            followup = dict(body)
            followup.pop("tool_choice", None)
            followup["messages"] = [
                body["messages"][0],
                message,
                {"role": "tool", "tool_call_id": first_call["id"], "content": "{\"record_id\":\"SYN-42\",\"state\":\"ready\"}"},
            ]
            followup_response = request_json(config.base_url, "POST", "/v1/chat/completions", followup, timeout=config.timeout_seconds)
            followup_duration_ms = followup_response.duration_ms
            followup_payload = followup_response.json()
            followup_errors = validate_chat_response(followup_payload) if followup_response.status < 400 else validate_error_response(followup_payload)
            checks.append({"name": "tool_result_message_accepted", "pass": followup_response.status == 200 and not followup_errors, "errors": followup_errors})
        passed = all(check["pass"] for check in checks)
        cell["status"] = "passed" if passed else "failed"
        cell["contract"] = {"pass": passed, "checks": checks}
        cell["measurements"] = _timings(payload, response.duration_ms, {"source": "not_sampled", "samples": 0})
        cell["measurements"]["tool_call_ms"] = round(response.duration_ms, 3)
        if followup_duration_ms is not None:
            cell["measurements"]["tool_result_ms"] = round(followup_duration_ms, 3)
            cell["measurements"]["total_ms"] = round(response.duration_ms + followup_duration_ms, 3)
        return cell
    except ClientTimeout as exc:
        return error_cell("tools-a", "tools", "client_timeout", str(exc), _model(config.model_a))
    except (TransportError, json.JSONDecodeError, OSError) as exc:
        return error_cell("tools-a", "tools", "transport_error", f"{type(exc).__name__}: {exc}", _model(config.model_a))


def _long_prompt(target_tokens: int, needles: list[dict[str, str]]) -> str:
    unit = "neutral synthetic filler. "
    # Measured Gemma 4 tokenization is approximately four prompt tokens per
    # unit, including spacing/punctuation. Leave room for chat/schema framing.
    repetitions = max(1, (target_tokens - 256) // 4)
    first_count = repetitions // 2
    second_count = repetitions - first_count
    return (
        f"START NEEDLE: {needles[0]['code']}\n"
        + unit * first_count
        + f"\nMIDDLE NEEDLE: {needles[1]['code']}\n"
        + unit * second_count
        + f"\nEND NEEDLE: {needles[2]['code']}\n"
        + "Return the three needle codes in start, middle, end order as strict JSON."
    )


def _long_context_cells(config: LiveConfig) -> list[dict[str, Any]]:
    specification = load_corpus()["long_context"]
    cells: list[dict[str, Any]] = []
    for target in specification["targets"]:
        cell_id = f"long-context-{target // 1024}k"
        if target not in config.contexts_to_run:
            cell = skip_cell(cell_id, "long_context", "not_selected", f"Use --contexts to opt into the {target}-token cell.", _model(config.model_a))
            cell["context"] = {"target_tokens": target, "observed_prompt_tokens": None}
            cells.append(cell)
            continue
        prompt = _long_prompt(target, specification["needles"])
        body = _chat_payload(
            config.model_a,
            prompt,
            max_tokens=64,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": f"long_context_{target}", "strict": True, "schema": specification["output_schema"]},
            },
        )
        encoded_size = len(json.dumps(body, separators=(",", ":")).encode("utf-8"))
        if encoded_size > config.max_generated_request_bytes:
            cell = skip_cell(cell_id, "long_context", "harness_size_cap", f"Generated {encoded_size} bytes exceeds safety cap {config.max_generated_request_bytes}.", _model(config.model_a))
            cell["context"] = {"target_tokens": target, "observed_prompt_tokens": None, "request_bytes": encoded_size}
            cells.append(cell)
            continue
        cell = empty_cell(cell_id, "long_context", model=_model(config.model_a))
        cell["context"] = {"target_tokens": target, "observed_prompt_tokens": None, "request_bytes": encoded_size}
        semantic_rules = [{"kind": "exact", "path": "/codes", "value": [needle["code"] for needle in specification["needles"]]}]
        try:
            with NvidiaMemorySampler() as sampler:
                response = request_json(config.base_url, "POST", "/v1/chat/completions", body, timeout=config.timeout_seconds)
            payload = response.json()
            if response.status >= 400:
                error_errors = validate_error_response(payload)
                cell["status"] = "unsupported"
                cell["contract"] = {"pass": None, "checks": [{"name": "error_envelope", "pass": not error_errors, "errors": error_errors}]}
                cell["skip"] = {
                    "category": "unsupported_combination",
                    "code": "backend_rejected_context",
                    "detail": f"HTTP {response.status}; no context success inferred.",
                }
                cell["measurements"] = {"total_ms": response.duration_ms, "memory": sampler.evidence()}
                cells.append(cell)
                continue
            envelope_errors = validate_chat_response(payload)
            content = payload.get("choices", [{}])[0].get("message", {}).get("content")
            evaluation = evaluate_content(content, specification["output_schema"], semantic_rules)
            preliminary = _timings(payload, response.duration_ms, sampler.evidence())
            observed_prompt_tokens = preliminary.get("prompt_tokens")
            target_tolerance = max(512, int(target * 0.1))
            target_window_pass = (
                isinstance(observed_prompt_tokens, (int, float))
                and abs(observed_prompt_tokens - target) <= target_tolerance
            )
            passed = not envelope_errors and evaluation["schema_valid"] and target_window_pass
            cell["status"] = "passed" if passed else "failed"
            cell["contract"] = {
                "pass": passed,
                "checks": [
                    {"name": "chat_envelope", "pass": not envelope_errors, "errors": envelope_errors},
                    {"name": "strict_json_schema", "pass": evaluation["schema_valid"], "errors": evaluation["schema_errors"]},
                    {
                        "name": "observed_prompt_within_target_window",
                        "pass": target_window_pass,
                        "target": target,
                        "observed": observed_prompt_tokens,
                        "tolerance": target_tolerance,
                    },
                ],
            }
            cell["quality"] = {
                "schema_valid": evaluation["schema_valid"],
                "semantic_evaluated": True,
                "semantic_anomalies": evaluation["semantic_anomalies"],
            }
            cell["measurements"] = preliminary
            cell["context"]["observed_prompt_tokens"] = cell["measurements"].get("prompt_tokens")
            cell["evidence"] = {
                "generator": "neutral-synthetic-filler-v2",
                "http_status": response.status,
                "synthetic_response_document": evaluation["document"],
            }
        except ClientTimeout as exc:
            cell = error_cell(cell_id, "long_context", "client_timeout", str(exc), _model(config.model_a))
            cell["context"] = {"target_tokens": target, "observed_prompt_tokens": None, "request_bytes": encoded_size}
        except (TransportError, json.JSONDecodeError, OSError) as exc:
            cell = error_cell(cell_id, "long_context", "transport_error", f"{type(exc).__name__}: {exc}", _model(config.model_a))
            cell["context"] = {"target_tokens": target, "observed_prompt_tokens": None, "request_bytes": encoded_size}
        cells.append(cell)
    return cells


def _idle_cell(config: LiveConfig) -> dict[str, Any]:
    preset_path = PRESETS_ROOT / config.preset
    sleep_seconds: int | None = None
    if preset_path.exists():
        text = preset_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.strip().startswith("sleep-idle-seconds"):
                sleep_seconds = int(line.split("=", 1)[1].strip())
                break
    if sleep_seconds is None:
        cell = skip_cell("idle-unload", "idle_unload", "preset_has_no_idle_sleep", f"{config.preset} does not configure sleep-idle-seconds.", _model(config.model_a))
        cell["status"] = "unsupported"
        return cell
    if config.idle_wait_seconds <= 0:
        return skip_cell("idle-unload", "idle_unload", "wait_not_selected", f"Preset idle sleep is {sleep_seconds}s; use --idle-wait-seconds {sleep_seconds + 5} to measure it.", _model(config.model_a))
    if config.idle_wait_seconds < sleep_seconds:
        return skip_cell("idle-unload", "idle_unload", "wait_below_configured_threshold", f"Requested wait {config.idle_wait_seconds}s is below configured {sleep_seconds}s.", _model(config.model_a))
    started = time.perf_counter()
    time.sleep(config.idle_wait_seconds)
    try:
        status, payload, errors = _models_snapshot(config.base_url, config.timeout_seconds)
        status_value = _status_map(payload).get(_model(config.model_a)["discovery_id"])
        wake = _nonstream_cell("idle-wake-probe", "warm_request", config.base_url, config.model_a, "Reply with synthetic idle wake check.", config.timeout_seconds)
        cell = empty_cell("idle-unload", "idle_unload", model=_model(config.model_a))
        observed = status_value in {"sleeping", "unloaded"}
        cell["status"] = "passed" if status == 200 and not errors and observed else "failed"
        cell["contract"] = {"pass": status == 200 and not errors, "checks": [{"name": "models_envelope", "pass": not errors, "errors": errors}]}
        cell["measurements"] = {"idle_wait_ms": round((time.perf_counter() - started) * 1000, 3), "wake_total_ms": wake["measurements"].get("total_ms")}
        cell["evidence"] = {"configured_sleep_seconds": sleep_seconds, "observed_status": status_value}
        return cell
    except (ClientTimeout, TransportError, json.JSONDecodeError, OSError) as exc:
        return error_cell("idle-unload", "idle_unload", "idle_probe_error", f"{type(exc).__name__}: {exc}", _model(config.model_a))


def _models_max_cell(config: LiveConfig) -> dict[str, Any]:
    try:
        status, models_payload, errors = _models_snapshot(config.base_url, config.timeout_seconds)
        statuses = _status_map(models_payload)
        contract_models = load_contract()["models"]
        discovery_to_canonical = {model["discovery_id"]: model["canonical_id"] for model in contract_models}
        loaded_discovery = sorted(identifier for identifier, value in statuses.items() if identifier in discovery_to_canonical and value == "loaded")
        loaded = [discovery_to_canonical[identifier] for identifier in loaded_discovery]
        within_limit = config.models_max == 0 or len(loaded) <= config.models_max
        cell = empty_cell(f"models-max-{config.models_max}", "models_max")
        passed = status == 200 and not errors and within_limit
        cell["status"] = "passed" if passed else "failed"
        cell["contract"] = {
            "pass": passed,
            "checks": [
                {"name": "models_envelope", "pass": not errors, "errors": errors},
                {"name": "loaded_count_within_limit", "pass": within_limit, "loaded_count": len(loaded), "configured_limit": config.models_max},
            ],
        }
        cell["measurements"] = {"loaded_models": len(loaded)}
        cell["evidence"] = {"loaded_canonical_ids": loaded, "statuses": statuses}
        return cell
    except (ClientTimeout, TransportError, json.JSONDecodeError, OSError) as exc:
        return error_cell(f"models-max-{config.models_max}", "models_max", "models_request_error", f"{type(exc).__name__}: {exc}")


def _attach_models_snapshot(cell: dict[str, Any], config: LiveConfig) -> None:
    try:
        status, payload, errors = _models_snapshot(config.base_url, config.timeout_seconds)
        cell.setdefault("evidence", {})["models_after_request"] = {
            "http_status": status,
            "validation_errors": errors,
            "statuses": _status_map(payload),
        }
    except (ClientTimeout, TransportError, json.JSONDecodeError, OSError) as exc:
        cell.setdefault("evidence", {})["models_after_request_error"] = f"{type(exc).__name__}: {exc}"


def run_live_suite(config: LiveConfig) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    model_a_record = _model(config.model_a)
    model_b_record = _model(config.model_b) if config.model_b else None
    try:
        status, models_payload, models_errors = _models_snapshot(config.base_url, config.timeout_seconds)
        ids = {item.get("id") for item in models_payload.get("data", []) if isinstance(item, dict)}
        required = {model_a_record["discovery_id"]}
        if model_b_record:
            required.add(model_b_record["discovery_id"])
        missing = sorted(identifier for identifier in required if identifier and identifier not in ids)
        cell = empty_cell("models-discovery", "models_discovery")
        passed = status == 200 and not models_errors and not missing
        cell["status"] = "passed" if passed else "failed"
        cell["contract"] = {
            "pass": passed,
            "checks": [
                {"name": "minimal_envelope", "pass": not models_errors, "errors": models_errors},
                {"name": "selected_discovery_ids", "pass": not missing, "missing": missing},
            ],
        }
        cell["measurements"] = {"model_count": len(ids)}
        cell["evidence"] = {"statuses": _status_map(models_payload)}
        cells.append(cell)
    except (ClientTimeout, TransportError, json.JSONDecodeError, OSError) as exc:
        cells.append(error_cell("models-discovery", "models_discovery", "models_request_error", f"{type(exc).__name__}: {exc}"))

    cells.append(_configured_identity_probe(config.base_url, config.timeout_seconds, model_a_record))
    first_load = _nonstream_cell("first-load-a-router-id", "first_model_load", config.base_url, model_a_record["discovery_id"], "Reply with exactly: synthetic first load ok", config.timeout_seconds)
    cells.append(first_load)
    if first_load["status"] != "passed":
        reason = "The selected model failed its first load; dependent request results would not measure model behavior."
        dependent = [
            ("warm-a", "warm_request"),
            ("stream-a", "streaming"),
            ("stream-cancel-a", "cancellation"),
            (f"concurrency-{config.concurrency}-a", "concurrency"),
            ("structured-aurora-facts-v1", "structured_output"),
            ("structured-cedar-plan-v1", "structured_output"),
            ("tools-a", "tools"),
            ("swap-a-to-b", "model_swap"),
            ("swap-b-to-a", "model_swap"),
            ("idle-unload", "idle_unload"),
            ("long-context-8k", "long_context"),
            ("long-context-32k", "long_context"),
            ("long-context-128k", "long_context"),
        ]
        cells.extend(skip_cell(cell_id, kind, "model_load_failed", reason, _model(config.model_a)) for cell_id, kind in dependent)
        cells.append(_models_max_cell(config))
        return cells
    cells.append(_nonstream_cell("warm-a", "warm_request", config.base_url, config.model_a, "Reply with exactly: synthetic warm ok", config.timeout_seconds))
    cells.append(_stream_cell(config))
    cells.append(_cancellation_cell(config))
    cells.append(_concurrency_cell(config))
    cells.extend(_structured_cells(config))
    cells.append(_tools_cell(config))

    if config.model_b:
        swap_to_b = _nonstream_cell("swap-a-to-b", "model_swap", config.base_url, model_b_record["discovery_id"], "Reply with exactly: synthetic model b ok", config.timeout_seconds)
        _attach_models_snapshot(swap_to_b, config)
        cells.append(swap_to_b)
        swap_to_a = _nonstream_cell("swap-b-to-a", "model_swap", config.base_url, config.model_a, "Reply with exactly: synthetic model a return ok", config.timeout_seconds)
        _attach_models_snapshot(swap_to_a, config)
        cells.append(swap_to_a)
    else:
        cells.append(skip_cell("swap-a-to-b", "model_swap", "second_model_not_selected", "A→B→A requires a second cached model.", _model(config.model_a)))

    cells.append(_models_max_cell(config))

    cells.append(_idle_cell(config))
    cells.extend(_long_context_cells(config))
    return cells
