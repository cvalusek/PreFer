#!/usr/bin/env python3
"""Expose a stable OpenAI-compatible port while model staging is in progress."""

from __future__ import annotations

import http.client
import json
import os
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


class GatewayState:
    def __init__(self, config: dict, staging_pid: int, extra_args: list[str]) -> None:
        self.config = config
        self.staging_pid = staging_pid
        self.extra_args = extra_args
        self.lock = threading.Lock()
        self.phase = "staging"
        self.detail = "model staging is in progress"
        self.backend: subprocess.Popen | None = None

    @property
    def backend_host(self) -> str:
        return str(self.config.get("backend_host", "127.0.0.1"))

    @property
    def backend_port(self) -> int:
        return int(self.config.get("backend_port", 8001))

    def snapshot(self) -> dict:
        with self.lock:
            backend = self.backend
            return {
                "status": "ready" if self.phase == "ready" else self.phase,
                "detail": self.detail,
                "backend_pid": backend.pid if backend is not None else None,
                "models": self.config.get("models", []),
            }

    def set_phase(self, phase: str, detail: str) -> None:
        with self.lock:
            self.phase = phase
            self.detail = detail

    def is_ready(self) -> bool:
        with self.lock:
            return self.phase == "ready"

    def stop_backend(self) -> None:
        with self.lock:
            backend = self.backend
        if backend is not None and backend.poll() is None:
            backend.terminate()
            try:
                backend.wait(timeout=15)
            except subprocess.TimeoutExpired:
                backend.kill()

    def backend_is_healthy(self) -> bool:
        try:
            connection = http.client.HTTPConnection(self.backend_host, self.backend_port, timeout=2)
            connection.request("GET", "/health")
            response = connection.getresponse()
            response.read()
            connection.close()
            return 200 <= response.status < 300
        except OSError:
            return False

    def monitor(self) -> None:
        try:
            if self.staging_pid > 0:
                _, status = os.waitpid(self.staging_pid, 0)
                if status != 0:
                    self.set_phase("error", f"model staging exited with status {status}")
                    return
            command = self.config.get("command")
            if not isinstance(command, list) or not command or any(not isinstance(item, str) for item in command):
                self.set_phase("error", "server config has no valid command")
                return
            self.set_phase("starting", "model staged; starting vLLM")
            self.backend = subprocess.Popen([*command, *self.extra_args])
            while self.backend.poll() is None:
                if self.backend_is_healthy():
                    self.set_phase("ready", "vLLM health endpoint is responding")
                    return
                time.sleep(1)
            self.set_phase("error", f"vLLM exited with status {self.backend.returncode}")
        except Exception as error:  # pragma: no cover - defensive process boundary
            self.set_phase("error", f"gateway monitor failed: {error}")


def json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")


class GatewayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("[vllm-gateway] " + (format % args) + "\n")

    @property
    def state(self) -> GatewayState:
        return self.server.gateway_state  # type: ignore[attr-defined]

    def send_json(self, status: int, payload: object) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/health":
            self.send_json(200, self.state.snapshot())
            return
        if path == "/readyz":
            snapshot = self.state.snapshot()
            self.send_json(200 if self.state.is_ready() else 503, snapshot)
            return
        if path == "/v1/models":
            models = []
            for model in self.state.config.get("models", []):
                models.append(
                    {
                        "id": model["request_model_id"],
                        "object": "model",
                        "owned_by": "prefer-vllm",
                        "permission": [],
                        "root": model["request_model_id"],
                        "aliases": model.get("aliases", []),
                    }
                )
            self.send_json(200, {"object": "list", "data": models})
            return
        if path.startswith("/v1/"):
            self.proxy_request()
            return
        self.send_json(404, {"error": {"message": "not found", "type": "invalid_request_error"}})

    def do_POST(self) -> None:  # noqa: N802
        if urlsplit(self.path).path.startswith("/v1/"):
            self.proxy_request()
            return
        self.send_json(404, {"error": {"message": "not found", "type": "invalid_request_error"}})

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def proxy_request(self) -> None:
        if not self.state.is_ready():
            self.send_json(503, {"error": {"message": self.state.snapshot()["detail"], "type": "server_error"}})
            return
        length_header = self.headers.get("Content-Length")
        try:
            length = int(length_header or "0")
        except ValueError:
            self.send_json(400, {"error": {"message": "invalid Content-Length", "type": "invalid_request_error"}})
            return
        body = self.rfile.read(length) if length else b""
        if body and self.headers.get_content_type() == "application/json":
            try:
                payload = json.loads(body)
                if isinstance(payload, dict) and isinstance(payload.get("model"), str):
                    aliases = {
                        alias: model["request_model_id"]
                        for model in self.state.config.get("models", [])
                        for alias in model.get("aliases", [])
                    }
                    if payload["model"] in aliases:
                        payload["model"] = aliases[payload["model"]]
                        body = json_bytes(payload)
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        headers = {}
        for name, value in self.headers.items():
            if name.lower() not in {"host", "content-length", "connection"}:
                headers[name] = value
        headers["Content-Length"] = str(len(body))
        headers["Connection"] = "close"
        connection = http.client.HTTPConnection(self.state.backend_host, self.state.backend_port, timeout=3600)
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            self.send_response(response.status, response.reason)
            for name, value in response.getheaders():
                if name.lower() not in {"connection", "keep-alive", "transfer-encoding", "content-length"}:
                    self.send_header(name, value)
            self.send_header("Connection", "close")
            if response.getheader("Content-Length") is not None:
                self.send_header("Content-Length", response.getheader("Content-Length"))
            self.end_headers()
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
            self.close_connection = True
        except (OSError, http.client.HTTPException) as error:
            if not self.wfile.closed:
                try:
                    self.send_json(502, {"error": {"message": f"backend request failed: {error}", "type": "server_error"}})
                except (BrokenPipeError, ConnectionResetError):
                    pass
        finally:
            connection.close()


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: router.py SERVER_CONFIG STAGING_PID [SERVER_ARGS ...]")
    config_path = sys.argv[1]
    try:
        staging_pid = int(sys.argv[2])
    except ValueError as error:
        raise SystemExit("staging PID must be an integer") from error
    with open(config_path, encoding="utf-8") as handle:
        config = json.load(handle)
    state = GatewayState(config, staging_pid, sys.argv[3:])
    server = ThreadingHTTPServer((str(config.get("host", "0.0.0.0")), int(config.get("port", 8000))), GatewayHandler)
    server.gateway_state = state  # type: ignore[attr-defined]
    monitor = threading.Thread(target=state.monitor, name="vllm-monitor", daemon=True)
    monitor.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        state.stop_backend()
        server.server_close()


if __name__ == "__main__":
    main()
