from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable


class SSEError(ValueError):
    pass


@dataclass
class SSETranscript:
    events: list[dict]
    done: bool


def _dispatch(data_lines: list[str], events: list[dict]) -> bool:
    if not data_lines:
        return False
    payload = "\n".join(data_lines)
    if payload == "[DONE]":
        return True
    try:
        event = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SSEError(f"invalid JSON SSE payload: {exc.msg}") from exc
    if not isinstance(event, dict):
        raise SSEError("SSE chunk must be a JSON object")
    if event.get("object") != "chat.completion.chunk":
        raise SSEError("SSE chunk object must be chat.completion.chunk")
    choices = event.get("choices")
    if not isinstance(choices, list):
        raise SSEError("SSE chunk choices must be an array")
    for choice in choices:
        if not isinstance(choice, dict) or not isinstance(choice.get("delta", {}), dict):
            raise SSEError("SSE choice delta must be an object")
    events.append(event)
    return False


def parse_lines(lines: Iterable[str], require_done: bool = True) -> SSETranscript:
    events: list[dict] = []
    data_lines: list[str] = []
    done = False
    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if line == "":
            done = _dispatch(data_lines, events) or done
            data_lines = []
            if done:
                break
            continue
        if line.startswith(":"):
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if data_lines and not done:
        done = _dispatch(data_lines, events)
    if require_done and not done:
        raise SSEError("stream ended without data: [DONE]")
    return SSETranscript(events=events, done=done)


def parse_text(text: str, require_done: bool = True) -> SSETranscript:
    return parse_lines(text.splitlines(keepends=True), require_done=require_done)
