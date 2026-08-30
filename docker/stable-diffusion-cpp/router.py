#!/usr/bin/env python3
from __future__ import annotations

import argparse
from email.parser import BytesParser
from email.policy import default as email_policy
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlsplit


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}
PRESTAGE_STATUS_PATH = Path("/tmp/prefer-image-prestage.status")


class RequestError(Exception):
    def __init__(self, status: int, message: str, error_type: str = "invalid_request_error") -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.error_type = error_type


def load_config(path: str | Path) -> dict:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    models = config.get("models")
    if not isinstance(models, list) or not models:
        raise ValueError("image server config must contain models")
    ids = [model.get("id") for model in models]
    if any(not isinstance(model_id, str) or not model_id for model_id in ids):
        raise ValueError("every image model needs an id")
    if len(ids) != len(set(ids)):
        raise ValueError("image model ids must be unique")
    if config.get("max_loaded_models") != 1:
        raise ValueError("the image router currently requires max_loaded_models=1")
    config["default_model"] = config.get("default_model") or ids[0]
    if config["default_model"] not in ids:
        raise ValueError("default_model must name a configured model")
    return config


def extract_model_id(content_type: str, body: bytes, header_model: str | None = None) -> str | None:
    if header_model and header_model.strip():
        return header_model.strip()
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type == "application/json":
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError as exc:
            raise RequestError(400, f"invalid JSON request: {exc.msg}") from exc
        model = payload.get("model")
        return model.strip() if isinstance(model, str) and model.strip() else None
    if media_type == "multipart/form-data":
        try:
            message = BytesParser(policy=email_policy).parsebytes(
                f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
            )
            for part in message.iter_parts():
                if part.get_param("name", header="content-disposition") == "model":
                    value = part.get_content()
                    return value.strip() if isinstance(value, str) and value.strip() else None
        except Exception as exc:
            raise RequestError(400, "invalid multipart image request") from exc
    return None


def prestage_state() -> dict:
    if not PRESTAGE_STATUS_PATH.exists():
        return {"state": "running", "exit_code": None}
    try:
        code = int(PRESTAGE_STATUS_PATH.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return {"state": "unknown", "exit_code": None}
    return {"state": "completed" if code == 0 else "failed", "exit_code": code}


def model_files_present(model: dict) -> bool:
    for artifact in model.get("required_files", []):
        path = Path(artifact["container_path"])
        try:
            if path.stat().st_size != artifact["size"]:
                return False
        except OSError:
            return False
    return True


class ModelManager:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.models = {model["id"]: model for model in config["models"]}
        self.process: subprocess.Popen | None = None
        self.active_model: str | None = None
        self.last_used = time.monotonic()
        self.switch_lock = threading.Lock()
        self.request_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.idle_thread = threading.Thread(target=self._idle_loop, name="image-idle-unload", daemon=True)
        self.idle_thread.start()

    def catalog(self) -> dict:
        active = self.active_model if self._process_running() else None
        return {
            "object": "list",
            "data": [
                {
                    "id": model["id"],
                    "object": "model",
                    "created": 0,
                    "owned_by": "prefer",
                    "display_name": model.get("display_name", model["id"]),
                    "description": model.get("description", ""),
                    "family": model.get("family"),
                    "precision": model.get("precision"),
                    "capabilities": model.get("capabilities", []),
                    "staged": model_files_present(model),
                    "active": model["id"] == active,
                }
                for model in self.config["models"]
            ],
        }

    def health(self) -> dict:
        return {
            "status": "ok",
            "runtime": "stable-diffusion.cpp",
            "configured_models": len(self.models),
            "active_model": self.active_model if self._process_running() else None,
            "prestage": prestage_state(),
        }

    def validate_model(self, model_id: str, capability: str) -> dict:
        model = self.models.get(model_id)
        if model is None:
            raise RequestError(404, f"model '{model_id}' not found")
        if capability not in model.get("capabilities", []):
            raise RequestError(400, f"model '{model_id}' does not support {capability}")
        return model

    def ensure_model(self, model_id: str) -> None:
        with self.switch_lock:
            if self.active_model == model_id and self._process_running():
                return
            self._stop_backend()
            model = self.models[model_id]
            self._wait_for_files(model)
            command = [
                self.config["backend_binary"],
                "--listen-ip",
                self.config["backend_host"],
                "--listen-port",
                str(self.config["backend_port"]),
                *model["args"],
            ]
            print(f"[image-router] loading {model_id}", flush=True)
            self.process = subprocess.Popen(command)
            self.active_model = model_id
            try:
                self._wait_for_backend()
            except Exception:
                self._stop_backend()
                raise
            self.last_used = time.monotonic()
            print(f"[image-router] ready {model_id}", flush=True)

    def proxy(self, method: str, path: str, headers: dict[str, str], body: bytes) -> tuple[int, list[tuple[str, str]], bytes]:
        connection = http.client.HTTPConnection(
            self.config["backend_host"],
            self.config["backend_port"],
            timeout=self.config["backend_request_timeout_ms"] / 1000,
        )
        forwarded_headers = {
            name: value
            for name, value in headers.items()
            if name.lower() not in HOP_BY_HOP_HEADERS and name.lower() != "host"
        }
        forwarded_headers["Host"] = f"{self.config['backend_host']}:{self.config['backend_port']}"
        try:
            connection.request(method, path, body=body, headers=forwarded_headers)
            response = connection.getresponse()
            response_body = response.read()
            response_headers = [
                (name, value)
                for name, value in response.getheaders()
                if name.lower() not in HOP_BY_HOP_HEADERS and name.lower() != "content-length"
            ]
            return response.status, response_headers, response_body
        except (OSError, http.client.HTTPException) as exc:
            raise RequestError(503, f"image backend request failed: {exc}", "server_error") from exc
        finally:
            connection.close()

    def close(self) -> None:
        self.stop_event.set()
        with self.switch_lock:
            self._stop_backend()

    def _wait_for_files(self, model: dict) -> None:
        deadline = time.monotonic() + self.config["startup_timeout_ms"] / 1000
        while not model_files_present(model):
            state = prestage_state()
            if state["state"] == "failed":
                raise RequestError(503, f"model '{model['id']}' prestaging failed", "server_error")
            if state["state"] == "completed":
                raise RequestError(503, f"model '{model['id']}' is not staged", "server_error")
            if time.monotonic() >= deadline:
                raise RequestError(503, f"timed out waiting for model '{model['id']}' artifacts", "server_error")
            time.sleep(1)

    def _wait_for_backend(self) -> None:
        deadline = time.monotonic() + self.config["startup_timeout_ms"] / 1000
        while time.monotonic() < deadline:
            if not self._process_running():
                code = self.process.poll() if self.process else "unknown"
                raise RequestError(503, f"image backend exited during load ({code})", "server_error")
            connection = http.client.HTTPConnection(self.config["backend_host"], self.config["backend_port"], timeout=2)
            try:
                connection.request("GET", "/v1/models")
                response = connection.getresponse()
                response.read()
                if response.status == 200:
                    return
            except OSError:
                pass
            finally:
                connection.close()
            time.sleep(1)
        raise RequestError(503, "timed out starting image backend", "server_error")

    def _process_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def _stop_backend(self) -> None:
        process = self.process
        model_id = self.active_model
        self.process = None
        self.active_model = None
        if process is None or process.poll() is not None:
            return
        print(f"[image-router] unloading {model_id}", flush=True)
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)

    def _idle_loop(self) -> None:
        interval = min(30.0, max(1.0, self.config["idle_unload_ms"] / 4000))
        while not self.stop_event.wait(interval):
            if not self._process_running():
                continue
            if (time.monotonic() - self.last_used) * 1000 < self.config["idle_unload_ms"]:
                continue
            if not self.request_lock.acquire(blocking=False):
                continue
            try:
                with self.switch_lock:
                    if (time.monotonic() - self.last_used) * 1000 >= self.config["idle_unload_ms"]:
                        self._stop_backend()
            finally:
                self.request_lock.release()


class ImageRequestHandler(BaseHTTPRequestHandler):
    manager: ModelManager
    server_version = "PreFerImage/1"

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/health":
            self._json_response(200, self.manager.health())
        elif path == "/v1/models":
            self._json_response(200, self.manager.catalog())
        elif path == "/":
            self._json_response(
                200,
                {
                    "service": "PreFer image",
                    "runtime": "stable-diffusion.cpp",
                    "endpoints": ["GET /v1/models", "POST /v1/images/generations", "POST /v1/images/edits"],
                },
            )
        else:
            self._error_response(RequestError(404, "not found"))

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        capability = {"/v1/images/generations": "generation", "/v1/images/edits": "edit"}.get(path)
        if capability is None:
            self._error_response(RequestError(404, "not found"))
            return
        try:
            body = self._read_body()
            query_model = parse_qs(urlsplit(self.path).query).get("model", [None])[0]
            model_id = extract_model_id(
                self.headers.get("Content-Type", ""),
                body,
                self.headers.get("X-Prefer-Model") or query_model,
            ) or self.manager.config["default_model"]
            self.manager.validate_model(model_id, capability)
            timeout = self.manager.config["busy_timeout_ms"] / 1000
            if not self.manager.request_lock.acquire(timeout=timeout):
                raise RequestError(503, "image server is busy", "server_error")
            try:
                self.manager.ensure_model(model_id)
                status, headers, response_body = self.manager.proxy(
                    "POST", path, dict(self.headers.items()), body
                )
                self.manager.last_used = time.monotonic()
            finally:
                self.manager.request_lock.release()
            self.send_response(status)
            for name, value in headers:
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(response_body)))
            self.send_header("X-Prefer-Model", model_id)
            self.end_headers()
            self.wfile.write(response_body)
        except RequestError as exc:
            self._error_response(exc)
        except Exception as exc:
            self._error_response(RequestError(500, f"unexpected image router error: {exc}", "server_error"))

    def _read_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError as exc:
            raise RequestError(411, "Content-Length is required") from exc
        maximum = self.manager.config["max_request_body_bytes"]
        if length < 0 or length > maximum:
            raise RequestError(413, f"request body exceeds {maximum} bytes")
        return self.rfile.read(length)

    def _json_response(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error_response(self, error: RequestError) -> None:
        self._json_response(
            error.status,
            {"error": {"message": error.message, "type": error.error_type, "code": error.status}},
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="PreFer lazy stable-diffusion.cpp router")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    manager = ModelManager(config)
    prestage_pid = os.environ.get("IMAGE_PRESTAGE_PID")
    if prestage_pid:
        def reap_prestage() -> None:
            try:
                os.waitpid(int(prestage_pid), 0)
            except (ChildProcessError, OSError, ValueError):
                pass

        threading.Thread(target=reap_prestage, name="image-prestage-reaper", daemon=True).start()
    ImageRequestHandler.manager = manager
    server = ThreadingHTTPServer((config["host"], config["port"]), ImageRequestHandler)
    server.daemon_threads = True

    def stop_server(_signum: int, _frame: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop_server)
    signal.signal(signal.SIGINT, stop_server)
    print(f"[image-router] listening on {config['host']}:{config['port']} with {len(config['models'])} models", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        manager.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
