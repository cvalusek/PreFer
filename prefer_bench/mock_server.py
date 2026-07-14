from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from typing import Iterator

from .contract import ContractError, load_json, validate_chat_request
from .paths import FIXTURES_ROOT


MAX_MOCK_BODY = 65536


class ContractMockHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _error(self, status: int, message: str, error_type: str = "invalid_request_error") -> None:
        self._json(status, {"error": {"code": status, "message": message, "type": error_type}})

    def do_GET(self) -> None:
        if self.path == "/v1/models":
            self._json(200, load_json(FIXTURES_ROOT / "models.json"))
        else:
            self._error(404, "endpoint is outside the fixture contract", "not_found_error")

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self._error(404, "endpoint is outside the fixture contract", "not_found_error")
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_MOCK_BODY:
            self.rfile.read(length)
            self._error(413, "fixture request exceeds the mock size limit")
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self._error(400, "malformed JSON")
            return
        if not isinstance(payload, dict):
            self._error(400, "request must be a JSON object")
            return
        if any(message.get("content") == "__fixture_delay__" for message in payload.get("messages", []) if isinstance(message, dict)):
            time.sleep(0.25)
        try:
            validate_chat_request(payload)
        except ContractError as exc:
            status = 404 if "unknown model" in str(exc) else 400
            self._error(status, str(exc))
            return
        if payload.get("stream"):
            body = (FIXTURES_ROOT / "stream.sse").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                midpoint = max(1, len(body) // 2)
                self.wfile.write(body[:midpoint])
                self.wfile.flush()
                time.sleep(0.01)
                self.wfile.write(body[midpoint:])
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            return
        if payload.get("tools"):
            fixture = "chat-tool-result.json" if any(message.get("role") == "tool" for message in payload["messages"]) else "chat-tool-call.json"
        elif payload.get("response_format"):
            fixture = "chat-structured.json"
        else:
            fixture = "chat-nonstream.json"
        response = load_json(FIXTURES_ROOT / fixture)
        response["model"] = payload["model"]
        self._json(200, response)


@contextmanager
def contract_mock_server() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), ContractMockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
