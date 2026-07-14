from __future__ import annotations

from dataclasses import dataclass
import json
import socket
import time
from typing import Any
from urllib import error, request

from .sse import parse_text


class ClientTimeout(TimeoutError):
    pass


class TransportError(RuntimeError):
    pass


@dataclass
class HTTPResult:
    status: int
    headers: dict[str, str]
    body: bytes
    duration_ms: float

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


@dataclass
class StreamResult:
    status: int
    headers: dict[str, str]
    events: list[dict[str, Any]]
    content: str
    done: bool
    cancelled: bool
    ttft_ms: float | None
    duration_ms: float


def _remaining(deadline: float, label: str) -> float:
    value = deadline - time.perf_counter()
    if value <= 0:
        raise ClientTimeout(f"{label} deadline exceeded")
    return value


def _set_read_timeout(handle: Any, seconds: float) -> None:
    # urllib does not expose a public response-timeout setter. CPython's
    # HTTPResponse keeps the socket here; retaining the urlopen timeout is a
    # safe fallback on another implementation.
    fp = getattr(handle, "fp", None)
    raw = getattr(fp, "raw", None)
    sock = getattr(raw, "_sock", None)
    if sock is not None:
        sock.settimeout(max(0.001, seconds))


def _read_all(handle: Any, deadline: float, label: str) -> bytes:
    chunks: list[bytes] = []
    try:
        while True:
            _set_read_timeout(handle, _remaining(deadline, label))
            chunk = handle.read(65536)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
    except (TimeoutError, socket.timeout) as exc:
        raise ClientTimeout(f"{label} deadline exceeded") from exc


def _readline(handle: Any, deadline: float, label: str) -> bytes:
    try:
        _set_read_timeout(handle, _remaining(deadline, label))
        return handle.readline()
    except (TimeoutError, socket.timeout) as exc:
        raise ClientTimeout(f"{label} deadline exceeded") from exc


def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def request_bytes(
    base_url: str,
    method: str,
    path: str,
    body: bytes | None = None,
    timeout: float = 30.0,
    content_type: str = "application/json",
) -> HTTPResult:
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = content_type
    call = request.Request(_url(base_url, path), data=body, headers=headers, method=method)
    started = time.perf_counter()
    deadline = started + timeout
    try:
        with request.urlopen(call, timeout=timeout) as response:
            payload = _read_all(response, deadline, f"client request after {timeout:.3f}s")
            return HTTPResult(
                status=response.status,
                headers={key.lower(): value for key, value in response.headers.items()},
                body=payload,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
    except error.HTTPError as exc:
        return HTTPResult(
            status=exc.code,
            headers={key.lower(): value for key, value in exc.headers.items()},
            body=_read_all(exc, deadline, f"client request after {timeout:.3f}s"),
            duration_ms=(time.perf_counter() - started) * 1000,
        )
    except (TimeoutError, socket.timeout) as exc:
        raise ClientTimeout(f"client deadline exceeded after {timeout:.3f}s") from exc
    except error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise ClientTimeout(f"client deadline exceeded after {timeout:.3f}s") from exc
        raise TransportError(str(exc.reason)) from exc


def request_json(
    base_url: str,
    method: str,
    path: str,
    payload: Any | None = None,
    timeout: float = 30.0,
) -> HTTPResult:
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return request_bytes(base_url, method, path, body=body, timeout=timeout)


def stream_chat(
    base_url: str,
    payload: dict[str, Any],
    timeout: float = 60.0,
    cancel_after_events: int | None = None,
) -> StreamResult:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    call = request.Request(
        _url(base_url, "/v1/chat/completions"),
        data=body,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    started = time.perf_counter()
    deadline = started + timeout
    events: list[dict[str, Any]] = []
    content_parts: list[str] = []
    data_lines: list[str] = []
    done = False
    cancelled = False
    ttft_ms: float | None = None

    def consume_event() -> bool:
        nonlocal done, cancelled, ttft_ms
        data = "\n".join(data_lines)
        data_lines.clear()
        if data == "[DONE]":
            done = True
            return True
        transcript = parse_text(f"data: {data}\n\n", require_done=False)
        event = transcript.events[0]
        events.append(event)
        for choice in event.get("choices", []):
            delta = choice.get("delta", {})
            if isinstance(delta.get("content"), str) and delta["content"]:
                if ttft_ms is None:
                    ttft_ms = (time.perf_counter() - started) * 1000
                content_parts.append(delta["content"])
        if cancel_after_events is not None and len(events) >= cancel_after_events:
            cancelled = True
            return True
        return False

    try:
        with request.urlopen(call, timeout=timeout) as response:
            headers = {key.lower(): value for key, value in response.headers.items()}
            while True:
                raw = _readline(response, deadline, f"stream after {timeout:.3f}s")
                if not raw:
                    if data_lines:
                        consume_event()
                    break
                line = raw.decode("utf-8").rstrip("\r\n")
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
                    continue
                if line != "" or not data_lines:
                    continue
                if consume_event():
                    break
            return StreamResult(
                status=response.status,
                headers=headers,
                events=events,
                content="".join(content_parts),
                done=done,
                cancelled=cancelled,
                ttft_ms=ttft_ms,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
    except error.HTTPError as exc:
        raise TransportError(f"stream request returned HTTP {exc.code}: {exc.read()[:512]!r}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise ClientTimeout(f"stream deadline exceeded after {timeout:.3f}s") from exc
    except error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise ClientTimeout(f"stream deadline exceeded after {timeout:.3f}s") from exc
        raise TransportError(str(exc.reason)) from exc
