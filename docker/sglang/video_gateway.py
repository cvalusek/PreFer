#!/usr/bin/env python3
"""Small compatibility gateway for SGLang's diffusion video API.

The diffusion server owns GPU execution and listens on an internal port.  This
process owns the stable PreFer port, local-file input policy, model aliases,
and readiness semantics shared with the other runtimes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.request import Request, url2pathname, urlopen
import uuid


DEFAULT_MAX_BODY = 1024 * 1024 * 1024
DEFAULT_READY_DELAY = 2.0
DEFAULT_PROBE_INTERVAL = 2.0
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class GatewayError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "invalid_request"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def json_bytes(payload: object) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def error_payload(error: GatewayError) -> dict:
    return {"error": {"message": error.message, "type": "invalid_request_error", "code": error.code}}


def safe_filename(value: str) -> str:
    value = Path(value).name
    value = SAFE_FILENAME.sub("_", value).strip("._")
    return value[:160] or "upload.bin"


def path_is_within(path: Path, roots: list[Path]) -> bool:
    resolved = path.resolve(strict=False)
    resolved_roots = [root.resolve(strict=False) for root in roots]
    return any(resolved == root or root in resolved.parents for root in resolved_roots)


def local_file_uri(uri: str, roots: list[Path]) -> str:
    if not isinstance(uri, str) or not uri.startswith("file://"):
        raise GatewayError("video conditions must use local file:// URIs", code="remote_input_uri")
    parsed = urlsplit(uri)
    if parsed.netloc not in ("", "localhost"):
        raise GatewayError("video conditions must use local file:// URIs", code="remote_input_uri")
    path = Path(url2pathname(unquote(parsed.path)))
    if not path.is_absolute() or not path_is_within(path, roots) or not path.is_file():
        raise GatewayError("video condition file does not exist in an allowed input mount", code="invalid_input_file")
    return path.resolve().as_uri()


def parse_content_disposition(value: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for item in value.split(";"):
        item = item.strip()
        if "=" not in item:
            continue
        key, raw = item.split("=", 1)
        fields[key.strip().lower()] = raw.strip().strip('"')
    return fields


def parse_multipart(content_type: str, body: bytes) -> tuple[dict[str, str], dict[str, tuple[str, bytes]]]:
    match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;]+))", content_type, flags=re.IGNORECASE)
    if not match:
        raise GatewayError("multipart/form-data requires a boundary", code="invalid_multipart")
    boundary = (match.group(1) or match.group(2)).encode("utf-8")
    fields: dict[str, str] = {}
    files: dict[str, tuple[str, bytes]] = {}
    marker = b"--" + boundary
    for section in body.split(marker)[1:]:
        if section.startswith(b"\r\n"):
            section = section[2:]
        if section.endswith(b"\r\n"):
            section = section[:-2]
        if not section or section == b"--":
            continue
        if b"\r\n\r\n" not in section:
            raise GatewayError("multipart part is missing headers", code="invalid_multipart")
        header_blob, part = section.split(b"\r\n\r\n", 1)
        headers = {}
        for line in header_blob.decode("utf-8", errors="replace").split("\r\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.lower().strip()] = value.strip()
        disposition = parse_content_disposition(headers.get("content-disposition", ""))
        name = disposition.get("name")
        if not name:
            raise GatewayError("multipart part is missing a field name", code="invalid_multipart")
        if part.endswith(b"\r\n"):
            part = part[:-2]
        if "filename" in disposition:
            files[name] = (safe_filename(disposition["filename"]), part)
        else:
            fields[name] = part.decode("utf-8")
    return fields, files


class VideoGateway:
    def __init__(self, config: dict, extra_args: list[str]):
        self.config = config
        self.extra_args = extra_args
        gateway = config.get("gateway", {})
        server = config.get("server", {})
        self.listen_host = os.environ.get("SGLANG_GATEWAY_HOST", "0.0.0.0")
        self.listen_port = int(os.environ.get("SGLANG_GATEWAY_PORT", config.get("port", 30000)))
        self.upstream = f"http://{gateway.get('upstream_host', '127.0.0.1')}:{int(gateway.get('upstream_port', 30001))}"
        self.model_id = str(gateway.get("model_id") or config["models"][0]["request_model_id"])
        self.source_model_id = str(server.get("model_path") or config.get("model_path") or self.model_id)
        self.model = dict(config["models"][0])
        self.server = dict(server)
        self.input_root = Path(gateway.get("input_mount", "/inputs"))
        self.output_root = Path(gateway.get("output_mount", "/outputs"))
        self.model_root = Path(os.environ.get("PREFER_MODELS_DIR", "/models"))
        self.max_body = int(os.environ.get("SGLANG_VIDEO_MAX_INPUT_BYTES", DEFAULT_MAX_BODY))
        self.ready_delay = float(os.environ.get("SGLANG_READY_DELAY_SECONDS", DEFAULT_READY_DELAY))
        self.probe_interval = float(os.environ.get("SGLANG_READY_PROBE_SECONDS", DEFAULT_PROBE_INTERVAL))
        self.process: subprocess.Popen[bytes] | None = None
        self.httpd: ThreadingHTTPServer | None = None
        self.ready = threading.Event()
        self.started_at = time.time()
        self.last_probe_error = "upstream warmup is still in progress"

    @property
    def allowed_input_roots(self) -> list[Path]:
        return [self.input_root, self.model_root]

    def command(self) -> list[str]:
        command = self.config.get("command")
        if not isinstance(command, list) or not command or any(not isinstance(item, str) for item in command):
            raise SystemExit("[sglang-video-gateway] invalid upstream command in server config")
        return [*command, *self.extra_args]

    def start_upstream(self) -> None:
        print(f"[sglang-video-gateway] starting upstream diffusion server: {' '.join(self.command())}", flush=True)
        self.process = subprocess.Popen(self.command(), env=os.environ.copy())

    def stop_upstream(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)

    def probe(self, path: str) -> None:
        request = Request(f"{self.upstream}{path}", headers={"Accept": "application/json"})
        with urlopen(request, timeout=3) as response:
            if not 200 <= response.status < 300:
                raise GatewayError(f"upstream returned HTTP {response.status}", status=503, code="upstream_not_ready")

    def readiness_loop(self) -> None:
        while self.process is None or self.process.poll() is None:
            if time.time() - self.started_at >= self.ready_delay:
                try:
                    self.probe("/health")
                    self.probe("/v1/models")
                    self.ready.set()
                    self.last_probe_error = ""
                except (GatewayError, OSError, URLError, HTTPError) as error:
                    self.ready.clear()
                    self.last_probe_error = str(error)
            time.sleep(self.probe_interval)
        self.ready.clear()
        self.last_probe_error = f"upstream exited with status {self.process.returncode}"

    def status(self) -> dict:
        upstream_alive = self.process is not None and self.process.poll() is None
        return {
            "status": "ok" if upstream_alive else "failed",
            "runtime": "sglang",
            "runtime_mode": "diffusion",
            "upstream_alive": upstream_alive,
            "ready": self.ready.is_set(),
            "model": self.model_id,
            "detail": self.last_probe_error or "ready",
        }

    def resolve_task(self, value: object) -> str:
        aliases = {str(key): str(value) for key, value in self.model.get("capability_aliases", {}).items()}
        aliases.update({"t2v": "t2va", "i2v": "fl2va", "v2v": "ref2va"})
        if value is None:
            tasks = self.model.get("tasks") or ["t2va"]
            return str(tasks[0])
        if not isinstance(value, str) or not value:
            raise GatewayError("task must be a non-empty string")
        resolved = aliases.get(value, value)
        if resolved not in set(self.model.get("tasks") or []):
            raise GatewayError(f"task {value!r} is not enabled for model {self.model_id}", code="unsupported_task")
        return resolved

    def normalize_conditions(self, conditions: object) -> list[dict]:
        if conditions is None:
            return []
        if not isinstance(conditions, list):
            raise GatewayError("conditions must be a list")
        contract = self.model.get("input_contract", {})
        maximum = contract.get("max_conditions")
        if isinstance(maximum, int) and len(conditions) > maximum:
            raise GatewayError(f"at most {maximum} conditions are supported", code="too_many_conditions")
        normalized = []
        for condition in conditions:
            if not isinstance(condition, dict):
                raise GatewayError("each video condition must be an object")
            item = dict(condition)
            uri = item.get("uri")
            if uri is None:
                for remote_key in ("url", "image_url", "video_url"):
                    if remote_key in item:
                        raise GatewayError("remote video inputs are not supported; upload a local file", code="remote_input_uri")
            else:
                item["uri"] = local_file_uri(uri, self.allowed_input_roots)
            normalized.append(item)
        return normalized

    def normalize_request(self, payload: object) -> dict:
        if not isinstance(payload, dict):
            raise GatewayError("video request must be a JSON object")
        request = dict(payload)
        requested_model = request.get("model", self.model_id)
        aliases = set(self.model.get("aliases") or []) | {self.model_id}
        if requested_model not in aliases and requested_model != self.source_model_id:
            raise GatewayError(f"unknown video model alias: {requested_model}", code="unknown_model")
        request["model"] = self.source_model_id
        request["task"] = self.resolve_task(request.get("task"))
        request["conditions"] = self.normalize_conditions(request.get("conditions"))
        duration = request.get("seconds", request.get("duration"))
        output_contract = self.model.get("output_contract", {})
        duration_range = output_contract.get("duration_seconds", [4, 15])
        if duration is not None:
            try:
                duration_value = float(duration)
            except (TypeError, ValueError) as error:
                raise GatewayError("seconds must be numeric") from error
            if not duration_range[0] <= duration_value <= duration_range[1]:
                raise GatewayError(
                    f"seconds must be between {duration_range[0]} and {duration_range[1]}",
                    code="invalid_duration",
                )
        return request

    def save_uploads(self, files: dict[str, tuple[str, bytes]]) -> dict[str, str]:
        job_root = self.input_root / f"prefer-{uuid.uuid4().hex}"
        job_root.mkdir(parents=True, exist_ok=True)
        upload_uris = {}
        for field, (filename, data) in files.items():
            if len(data) > self.max_body:
                raise GatewayError("uploaded input exceeds the configured request limit", status=413, code="input_too_large")
            destination = job_root / safe_filename(filename)
            destination.write_bytes(data)
            upload_uris[field] = destination.resolve().as_uri()
        return upload_uris

    def parse_video_body(self, handler: BaseHTTPRequestHandler) -> dict:
        content_length = int(handler.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise GatewayError("video request body is required")
        if content_length > self.max_body:
            raise GatewayError("video request exceeds the configured request limit", status=413, code="input_too_large")
        body = handler.rfile.read(content_length)
        content_type = handler.headers.get("Content-Type", "application/json")
        if content_type.lower().startswith("multipart/form-data"):
            fields, files = parse_multipart(content_type, body)
            raw_request = fields.get("request", fields.get("json", "{}"))
            try:
                payload = json.loads(raw_request)
            except json.JSONDecodeError as error:
                raise GatewayError("multipart request/json field must contain valid JSON") from error
            upload_uris = self.save_uploads(files)
            if not isinstance(payload, dict):
                raise GatewayError("multipart request field must contain a JSON object")
            for condition in payload.get("conditions", []) or []:
                if isinstance(condition, dict) and condition.get("upload"):
                    field = condition.pop("upload")
                    if field not in upload_uris:
                        raise GatewayError(f"multipart upload field not found: {field}")
                    condition["uri"] = upload_uris[field]
            return payload
        try:
            return json.loads(body)
        except json.JSONDecodeError as error:
            raise GatewayError("video request body must be valid JSON") from error

    def proxy(self, method: str, path: str, body: bytes | None, content_type: str | None) -> tuple[int, str, bytes]:
        headers = {"Accept": "application/json, video/mp4"}
        if body is not None:
            headers["Content-Type"] = content_type or "application/json"
        request = Request(f"{self.upstream}{path}", data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=300) as response:
                return response.status, response.headers.get("Content-Type", "application/octet-stream"), response.read()
        except HTTPError as error:
            return error.code, error.headers.get("Content-Type", "application/json"), error.read()
        except (URLError, OSError) as error:
            raise GatewayError(f"diffusion upstream is unavailable: {error}", status=503, code="upstream_unavailable") from error

    def models_payload(self, upstream_payload: object) -> dict:
        upstream_data = upstream_payload.get("data", []) if isinstance(upstream_payload, dict) else []
        source_id = self.source_model_id
        if isinstance(upstream_data, list) and upstream_data and isinstance(upstream_data[0], dict):
            source_id = str(upstream_data[0].get("id") or source_id)
        record = {
            "id": self.model_id,
            "object": "model",
            "owned_by": "prefer",
            "source_model_id": source_id,
            "runtime_mode": "diffusion",
            "tasks": self.model.get("tasks", []),
            "capabilities": self.model.get("capabilities", []),
            "aliases": self.model.get("aliases", []),
        }
        return {"object": "list", "data": [record]}

    def handle_video(self, handler: BaseHTTPRequestHandler) -> tuple[int, str, bytes]:
        if not self.ready.is_set():
            raise GatewayError("diffusion server is still warming up", status=503, code="upstream_not_ready")
        payload = self.normalize_request(self.parse_video_body(handler))
        return self.proxy("POST", "/v1/videos", json_bytes(payload), "application/json")


class GatewayHandler(BaseHTTPRequestHandler):
    gateway: VideoGateway

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[sglang-video-gateway] {self.address_string()} {fmt % args}", file=sys.stderr, flush=True)

    def send_bytes(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, payload: object) -> None:
        self.send_bytes(status, "application/json", json_bytes(payload))

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == "/health":
            status = self.gateway.status()
            self.send_json(200 if status["status"] == "ok" else 503, status)
            return
        if parsed.path == "/readyz":
            status = self.gateway.status()
            self.send_json(200 if status["ready"] else 503, status)
            return
        if parsed.path == "/v1/models":
            if not self.gateway.ready.is_set():
                self.send_json(503, error_payload(GatewayError("diffusion server is still warming up", 503, "upstream_not_ready")))
                return
            code, content_type, body = self.gateway.proxy("GET", self.path, None, None)
            if code >= 400:
                self.send_bytes(code, content_type, body)
                return
            try:
                body = json_bytes(self.gateway.models_payload(json.loads(body)))
                content_type = "application/json"
            except json.JSONDecodeError:
                pass
            self.send_bytes(code, content_type, body)
            return
        try:
            code, content_type, body = self.gateway.proxy("GET", self.path, None, None)
            self.send_bytes(code, content_type, body)
        except GatewayError as error:
            self.send_json(error.status, error_payload(error))

    def do_POST(self) -> None:
        parsed = urlsplit(self.path)
        try:
            if parsed.path == "/v1/videos":
                code, content_type, body = self.gateway.handle_video(self)
            else:
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length > self.gateway.max_body:
                    raise GatewayError("request exceeds the configured request limit", 413, "input_too_large")
                raw = self.rfile.read(content_length) if content_length else None
                code, content_type, body = self.gateway.proxy("POST", self.path, raw, self.headers.get("Content-Type"))
            self.send_bytes(code, content_type, body)
        except GatewayError as error:
            self.send_json(error.status, error_payload(error))


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: video_gateway.py SERVER_CONFIG [extra upstream args]")
    config_path = Path(sys.argv[1])
    config = json.loads(config_path.read_text(encoding="utf-8"))
    gateway = VideoGateway(config, sys.argv[2:])
    GatewayHandler.gateway = gateway
    server = ThreadingHTTPServer((gateway.listen_host, gateway.listen_port), GatewayHandler)
    gateway.httpd = server

    def stop(_signum: int, _frame: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    gateway.start_upstream()
    threading.Thread(target=gateway.readiness_loop, daemon=True).start()
    try:
        print(f"[sglang-video-gateway] listening on {gateway.listen_host}:{gateway.listen_port}", flush=True)
        server.serve_forever()
    finally:
        server.server_close()
        gateway.stop_upstream()


if __name__ == "__main__":
    main()
