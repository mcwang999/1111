from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MCPServerConfig:
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


class BaseMCPClient:
    """Minimal synchronous stdio MCP client for local provider adapters."""

    def __init__(
        self,
        config: MCPServerConfig,
        timeout_seconds: float = 30.0,
        proxy_url: str | None = None,
    ) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds
        self.proxy_url = proxy_url
        self._process: subprocess.Popen[str] | None = None
        self._stdout_queue: queue.Queue[str] | None = None
        self._next_id = 1
        self._lock = threading.Lock()

    def __enter__(self) -> BaseMCPClient:
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def start(self) -> None:
        if self._process is not None:
            return

        self._process = self._start_process()
        self._stdout_queue = queue.Queue()
        threading.Thread(target=self._read_stdout, daemon=True).start()
        self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "airs", "version": "0.1.0"},
            },
        )
        self._notify("notifications/initialized", {})

    def _start_process(self) -> subprocess.Popen[str]:
        env = os.environ.copy()
        env.update(self.config.env)
        if self.proxy_url:
            env.update(
                {
                    "HTTP_PROXY": self.proxy_url,
                    "HTTPS_PROXY": self.proxy_url,
                    "ALL_PROXY": self.proxy_url,
                    "http_proxy": self.proxy_url,
                    "https_proxy": self.proxy_url,
                    "all_proxy": self.proxy_url,
                }
            )
        return subprocess.Popen(
            [self.config.command, *self.config.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
        )

    def close(self) -> None:
        if self._process is None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._process.kill()
        self._process = None
        self._stdout_queue = None

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._request("tools/list", {})
        tools = result.get("tools", [])
        return tools if isinstance(tools, list) else []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            process = self._ensure_process()
            request_id = self._next_id
            self._next_id += 1
            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
            self._write(payload)

            while True:
                line = self._read_line()
                if not line:
                    stderr = process.stderr.read() if process.poll() is not None and process.stderr else ""
                    raise RuntimeError(f"MCP server closed stdout. stderr={stderr[:500]}")
                message = json.loads(line)
                if message.get("id") != request_id:
                    continue
                if "error" in message:
                    raise RuntimeError(f"MCP {method} failed: {message['error']}")
                result = message.get("result", {})
                return result if isinstance(result, dict) else {"result": result}

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._ensure_process()
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def _write(self, payload: dict[str, Any]) -> None:
        process = self._ensure_process()
        if process.stdin is None:
            raise RuntimeError("MCP server stdin is not available.")
        process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        process.stdin.flush()

    def _ensure_process(self) -> subprocess.Popen[str]:
        if self._process is None:
            raise RuntimeError("MCP server did not start.")
        return self._process

    def _read_stdout(self) -> None:
        process = self._process
        if process is None:
            return
        if process.stdout is None or self._stdout_queue is None:
            return
        for line in process.stdout:
            self._stdout_queue.put(line)

    def _read_line(self) -> str:
        if self._stdout_queue is None:
            return ""
        try:
            return self._stdout_queue.get(timeout=self.timeout_seconds)
        except queue.Empty:
            self.close()
            raise RuntimeError(f"MCP request timed out after {self.timeout_seconds} seconds.")


class HTTPMCPClient:
    """MCP client that communicates over HTTP (Streamable HTTP transport).

    Connects to a remote MCP server endpoint (e.g. mcp.getxagent.com)
    using JSON-RPC over HTTP POST requests.
    """

    def __init__(
        self,
        url: str,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
        proxy_url: str | None = None,
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.proxy_url = proxy_url
        self._session_id: str | None = None
        self._next_id = 1

    def __enter__(self) -> HTTPMCPClient:
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def start(self) -> None:
        """Initialize the MCP session over HTTP."""
        result = self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "airs", "version": "0.1.0"},
            },
        )
        # Store session ID if provided
        # (session ID is set during _request from response headers)

        # Send initialized notification
        self._notify("notifications/initialized", {})

    def close(self) -> None:
        """No persistent connection to close for HTTP transport."""
        self._session_id = None

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._request("tools/list", {})
        tools = result.get("tools", [])
        return tools if isinstance(tools, list) else []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "tools/call",
            {"name": name, "arguments": arguments},
        )

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        import httpx

        url = self._build_url()
        headers = self._build_headers()

        request_id = self._next_id
        self._next_id += 1

        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        proxies = self.proxy_url if self.proxy_url else None

        with httpx.Client(timeout=self.timeout_seconds, proxy=proxies) as http:
            resp = http.post(url, json=payload, headers=headers)

            # Capture session ID from response headers
            session_id = resp.headers.get("mcp-session-id")
            if session_id:
                self._session_id = session_id

            if resp.status_code >= 400:
                raise RuntimeError(
                    f"MCP HTTP request failed: {resp.status_code} {resp.text[:500]}"
                )

            result = self._parse_response(resp)
            if "error" in result:
                raise RuntimeError(f"MCP {method} failed: {result['error']}")
            return result

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        import httpx

        url = self._build_url()
        headers = self._build_headers()

        payload = {"jsonrpc": "2.0", "method": method, "params": params}

        proxies = self.proxy_url if self.proxy_url else None

        with httpx.Client(timeout=self.timeout_seconds, proxy=proxies) as http:
            http.post(url, json=payload, headers=headers)

    def _build_url(self) -> str:
        url = self.url
        if self.api_key and "apikey" not in url.lower() and "api_key" not in url.lower():
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}apiKey={self.api_key}"
        return url

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    @staticmethod
    def _parse_response(resp: Any) -> dict[str, Any]:
        """Parse an HTTP response that may be JSON or SSE."""
        content_type = resp.headers.get("content-type", "")

        if "text/event-stream" in content_type:
            text = resp.text
            for line in text.split("\n"):
                if line.startswith("data:"):
                    data = line[len("data:"):].strip()
                    try:
                        msg = json.loads(data)
                        if "result" in msg:
                            return msg["result"] if isinstance(msg["result"], dict) else {"result": msg["result"]}
                    except json.JSONDecodeError:
                        continue
            return {}

        try:
            body = resp.json()
        except Exception:
            return {}

        if isinstance(body, dict):
            result = body.get("result", body)
            return result if isinstance(result, dict) else {"result": result}

        return {}
