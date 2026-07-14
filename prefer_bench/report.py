from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _number(value: Any, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _rate(value: float | None) -> str:
    return "not measured" if value is None else f"{value * 100:.1f}%"


def render_markdown(result: dict[str, Any]) -> str:
    run = result["run"]
    backend = run["backend"]
    summary = result["summary"]
    lines = [
        "# PreFer benchmark report",
        "",
        f"Run `{run['run_id']}` used source `{run['source_revision']}`"
        f"{' (dirty working tree)' if run['source_dirty'] else ''} with `{backend['base_image']}` "
        f"({backend['revision']}) on preset `{run['preset']}` and `models-max={run['models_max']}`.",
        "",
        f"Started: `{run['started_at']}`  ",
        f"Duration: `{run['duration_ms'] / 1000:.3f}s`  ",
        f"Contract: `{run['contract_version']}`; evaluation corpus: `{run['eval_version']}`  ",
        f"Hardware tier: `{run['hardware'].get('tier', 'unknown')}`",
        "",
        "## Outcome",
        "",
        f"Schema-contract pass rate: **{_rate(summary['schema_contract_pass_rate'])}** "
        f"across `{summary['schema_contract_attempts']}` attempted structured responses  ",
        f"Semantic anomaly rate: **{_rate(summary['semantic_anomaly_rate'])}** "
        f"across `{summary['semantic_evaluations']}` evaluated response documents  ",
        f"Cell status counts: `{json.dumps(summary['cell_counts'], sort_keys=True)}`",
        "",
        "Schema validity and semantic correctness are intentionally separate; a schema-valid response can still contain an impossible date or omit required plan content.",
        "",
        "## Cells",
        "",
        "| Cell | State | Model | Total ms | TTFT ms | Prefill ms | Decode ms | Prompt / output tokens | Peak GPU MiB | Contract | Schema | Semantic anomalies |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | --- | --- | --- |",
    ]
    for cell in result["cells"]:
        measurements = cell["measurements"]
        model = cell["model"] or {}
        requested = model.get("requested_id", "—")
        memory = measurements.get("memory", {})
        anomaly_codes = sorted({item.get("code", "unknown") for item in cell["quality"]["semantic_anomalies"]})
        semantic_evaluated = cell["quality"]["semantic_evaluated"]
        schema_value = cell["quality"]["schema_valid"]
        schema_text = "—" if schema_value is None else ("pass" if schema_value else "fail")
        contract_value = cell["contract"]["pass"]
        contract_text = "—" if contract_value is None else ("pass" if contract_value else "fail")
        state = cell["status"]
        if "skip" in cell:
            state += f" ({cell['skip']['code']})"
        if "error" in cell:
            state += f" ({cell['error']['code']})"
        token_text = f"{measurements.get('prompt_tokens', '—')} / {measurements.get('decode_tokens', '—')}"
        lines.append(
            f"| `{cell['id']}` | {state} | `{requested}` | {_number(measurements.get('total_ms'))} | "
            f"{_number(measurements.get('ttft_ms'))} | {_number(measurements.get('prefill_ms'))} | "
            f"{_number(measurements.get('decode_ms'))} | {token_text} | {_number(memory.get('peak_used_mib'), 0)} | "
            f"{contract_text} | {schema_text} | "
            f"{('—' if not semantic_evaluated else (', '.join(anomaly_codes) if anomaly_codes else 'none'))} |"
        )

    skipped = [cell for cell in result["cells"] if cell["status"] in {"skipped", "unsupported"}]
    if skipped:
        lines.extend(["", "## Skipped or unsupported", ""])
        for cell in skipped:
            reason = cell.get("skip", cell.get("error", {"code": "unspecified", "detail": ""}))
            lines.append(f"- `{cell['id']}` — `{reason.get('code')}`: {reason.get('detail', '')}")

    cleanup = run.get("cleanup", {})
    if cleanup:
        lines.extend([
            "",
            "## Isolation cleanup",
            "",
            f"- Temporary containers absent: `{cleanup.get('temporary_containers_absent')}`",
            f"- Temporary networks absent: `{cleanup.get('temporary_networks_absent')}`",
            f"- Temporary model volume absent: `{cleanup.get('temporary_volume_absent')}`",
            f"- Source model cache mount: `{cleanup.get('source_cache_mount')}`",
            f"- Operator `prefer` unchanged: `{cleanup.get('operator_prefer_unchanged')}` "
            f"(`{cleanup.get('operator_prefer_status_before')}` → `{cleanup.get('operator_prefer_status_after')}`)",
            f"- NeurOn container unchanged: `{cleanup.get('neuron_unchanged')}` "
            f"(`{cleanup.get('neuron_status_before')}` → `{cleanup.get('neuron_status_after')}`)",
            f"- Host port 8080 used: `{cleanup.get('operator_port_8080_used')}`",
        ])

    lines.extend([
        "",
        "## Reproduce",
        "",
        "```text",
        " ".join(run["command"]),
        "```",
        "",
        "## Gates for any later backend spike",
        "",
        "A future isolated backend comparison should answer these questions before any migration decision:",
        "",
        "- Does it pass every promised v1 contract replay cell for configured identities, router discovery IDs, aliases, strict JSON, streaming termination, bounded client cancellation, tools envelopes, and errors?",
        "- Does it avoid regressing schema-contract pass rate or semantic anomaly rate on the same synthetic corpus and prompt version?",
        "- At equal model, quantization, context, and hardware, what measured cold-load, warm, A→B→A, p50/p95 concurrent, TTFT, decode, and memory improvement clears an owner-selected threshold?",
        "- Does it preserve the single-router light-tier swap design and fit the tested hardware without adding provider or reservation lifecycle ownership?",
        "- Does it support the required 8K/32K/128K cells without silently truncating or reporting nominal context as task success?",
        "",
        "No architecture choice follows from this report alone.",
        "",
    ])
    return "\n".join(lines)


def write_report(result: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(result), encoding="utf-8")
