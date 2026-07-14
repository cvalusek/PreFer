from __future__ import annotations

import json
import time
from typing import Any, Callable

from .contract import (
    load_corpus,
    validate_chat_response,
    validate_error_response,
    validate_models_response,
    validate_tool_calls,
)
from .evaluate import evaluate_content
from .http_client import ClientTimeout, request_bytes, request_json, stream_chat


E2B_CONFIGURED = "unsloth/gemma-4-E2B-it-qat-GGUF:UD-Q4_K_XL"
E2B_ROUTER = "unsloth/gemma-4-E2B-it-qat-GGUF:Q4_K_XL"
E2B_ALIAS = "gemma-4-e2b"


def _chat(model: str, content: str = "Reply with exactly: pong", **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 32,
        "temperature": 0,
    }
    payload.update(extra)
    return payload


def replay_contract(base_url: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, operation: Callable[[], tuple[bool, str]]) -> None:
        started = time.perf_counter()
        try:
            passed, detail = operation()
            checks.append({"name": name, "pass": bool(passed), "detail": detail, "duration_ms": round((time.perf_counter() - started) * 1000, 3)})
        except Exception as exc:  # Contract replay must report every cell.
            checks.append({"name": name, "pass": False, "detail": f"{type(exc).__name__}: {exc}", "duration_ms": round((time.perf_counter() - started) * 1000, 3)})

    def models() -> tuple[bool, str]:
        response = request_json(base_url, "GET", "/v1/models", timeout=2)
        errors = validate_models_response(response.json())
        return response.status == 200 and not errors, f"status={response.status} errors={errors}"

    check("models_minimal_envelope", models)

    for label, model in (("router_id", E2B_ROUTER), ("alias", E2B_ALIAS)):
        def nonstream(model: str = model) -> tuple[bool, str]:
            response = request_json(base_url, "POST", "/v1/chat/completions", _chat(model), timeout=2)
            errors = validate_chat_response(response.json())
            return response.status == 200 and not errors, f"status={response.status} errors={errors}"
        check(f"chat_nonstream_{label}", nonstream)

    def configured_identity_behavior() -> tuple[bool, str]:
        response = request_json(base_url, "POST", "/v1/chat/completions", _chat(E2B_CONFIGURED), timeout=2)
        if response.status < 400:
            errors = validate_chat_response(response.json())
            behavior = "accepted_extension"
        else:
            errors = validate_error_response(response.json())
            behavior = "rejected_not_promised_route"
        return not errors, f"status={response.status} behavior={behavior} errors={errors}"

    check("configured_identity_has_bounded_extension_or_error_behavior", configured_identity_behavior)

    def structured() -> tuple[bool, str]:
        case = load_corpus()["cases"][0]
        body = _chat(
            E2B_ALIAS,
            f"{case['instruction']}\n\nSOURCE:\n{case['source']}",
            response_format={
                "type": "json_schema",
                "json_schema": {"name": case["id"], "strict": True, "schema": case["output_schema"]},
            },
        )
        response = request_json(base_url, "POST", "/v1/chat/completions", body, timeout=2)
        envelope_errors = validate_chat_response(response.json())
        content = response.json()["choices"][0]["message"]["content"] if not envelope_errors else None
        evaluation = evaluate_content(content, case["output_schema"], case["semantic_rules"])
        passed = response.status == 200 and not envelope_errors and evaluation["schema_valid"] and not evaluation["semantic_anomalies"]
        return passed, f"envelope_errors={envelope_errors} schema_valid={evaluation['schema_valid']} anomalies={evaluation['semantic_anomalies']}"

    check("structured_json_separates_schema_and_semantics", structured)

    def streaming() -> tuple[bool, str]:
        response = stream_chat(base_url, _chat(E2B_ALIAS, stream=True), timeout=2)
        return response.status == 200 and response.done and response.content == "pong", f"done={response.done} content={response.content!r} events={len(response.events)}"

    check("stream_sse_shape_and_done", streaming)

    tool = {
        "type": "function",
        "function": {
            "name": "lookup_fixture",
            "description": "Read a synthetic fixture record",
            "parameters": {
                "type": "object",
                "required": ["record_id"],
                "properties": {"record_id": {"type": "string"}},
                "additionalProperties": False,
            },
        },
    }

    def tool_call() -> tuple[bool, str]:
        response = request_json(base_url, "POST", "/v1/chat/completions", _chat(E2B_ALIAS, "Use lookup_fixture for SYN-42.", tools=[tool]), timeout=2)
        payload = response.json()
        envelope_errors = validate_chat_response(payload)
        calls = payload.get("choices", [{}])[0].get("message", {}).get("tool_calls")
        tool_errors = validate_tool_calls(calls)
        return response.status == 200 and not envelope_errors and not tool_errors, f"envelope_errors={envelope_errors} tool_errors={tool_errors}"

    check("tool_call_conditional_envelope", tool_call)

    def tool_result() -> tuple[bool, str]:
        body = _chat(E2B_ALIAS, tools=[tool])
        body["messages"] = [
            {"role": "user", "content": "Use lookup_fixture for SYN-42."},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call_fixture_1", "type": "function", "function": {"name": "lookup_fixture", "arguments": "{\"record_id\":\"SYN-42\"}"}}]},
            {"role": "tool", "tool_call_id": "call_fixture_1", "content": "{\"state\":\"ready\"}"},
        ]
        response = request_json(base_url, "POST", "/v1/chat/completions", body, timeout=2)
        errors = validate_chat_response(response.json())
        return response.status == 200 and not errors, f"status={response.status} errors={errors}"

    check("tool_result_message_envelope", tool_result)

    def rejected(response_status: int, payload: Any) -> tuple[bool, str]:
        errors = validate_error_response(payload)
        return response_status >= 400 and not errors, f"status={response_status} errors={errors}"

    check("error_malformed_json", lambda: rejected(*(lambda r: (r.status, r.json()))(request_bytes(base_url, "POST", "/v1/chat/completions", b"{", timeout=2))))
    check("error_missing_model", lambda: rejected(*(lambda r: (r.status, r.json()))(request_json(base_url, "POST", "/v1/chat/completions", {"messages": [{"role": "user", "content": "x"}]}, timeout=2))))
    check("error_unknown_model_or_alias", lambda: rejected(*(lambda r: (r.status, r.json()))(request_json(base_url, "POST", "/v1/chat/completions", _chat("missing-model"), timeout=2))))
    check("error_malformed_structured_request", lambda: rejected(*(lambda r: (r.status, r.json()))(request_json(base_url, "POST", "/v1/chat/completions", _chat(E2B_ALIAS, response_format={"type": "json_schema"}), timeout=2))))
    check("error_malformed_tool", lambda: rejected(*(lambda r: (r.status, r.json()))(request_json(base_url, "POST", "/v1/chat/completions", _chat(E2B_ALIAS, tools=[{"type": "function"}]), timeout=2))))

    def size_limit() -> tuple[bool, str]:
        response = request_json(base_url, "POST", "/v1/chat/completions", _chat(E2B_ALIAS, "x" * 70000), timeout=2)
        return rejected(response.status, response.json())

    check("bounded_size_rejection_is_error_envelope", size_limit)

    def timeout() -> tuple[bool, str]:
        try:
            request_json(base_url, "POST", "/v1/chat/completions", _chat(E2B_ALIAS, "__fixture_delay__"), timeout=0.05)
        except ClientTimeout:
            return True, "client deadline classified as timeout"
        return False, "request unexpectedly completed before the deadline"

    check("client_timeout_is_bounded", timeout)

    def cancellation() -> tuple[bool, str]:
        response = stream_chat(base_url, _chat(E2B_ALIAS, stream=True), timeout=2, cancel_after_events=1)
        return response.cancelled and not response.done and response.duration_ms < 2000, f"cancelled={response.cancelled} done={response.done} duration_ms={response.duration_ms:.3f}"

    check("client_stream_close_is_bounded", cancellation)

    passed = sum(1 for item in checks if item["pass"])
    return {
        "schema_version": "prefer.contract-replay.v1",
        "checks": checks,
        "summary": {"passed": passed, "failed": len(checks) - passed, "total": len(checks)},
    }
