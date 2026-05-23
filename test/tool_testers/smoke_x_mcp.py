"""Smoke test: verify XAgent MCP provider can connect and search X/Twitter.

Reads API key from .config.yaml and calls the real XAgent MCP endpoint.
This is a live integration test -- it requires network access and a valid API key.

Usage:
    cd AIRS
    python test/smoke_x_mcp.py
"""

import json
import queue
import sys
import threading
import time
from pathlib import Path

# Fix Windows console encoding for Chinese/emoji characters
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from airs.mcp.x_mcp import XMCPProvider


def main():
    config_path = Path(__file__).resolve().parent.parent / ".config.yaml"
    if not config_path.exists():
        print(f"[ERROR] Config file not found: {config_path}")
        sys.exit(1)

    print("=" * 60)
    print("XAgent MCP Smoke Test")
    print("=" * 60)

    # -- 1. Load config -------------------------------------------------------
    print("\n[1/5] Loading config from .config.yaml ...")
    provider = XMCPProvider.from_config(config_path)
    print(f"  mode:        {provider.mode}")
    print(f"  mcp_url:     {provider.mcp_url}")
    print(f"  api_key:     {provider.api_key[:8]}..." if provider.api_key else "  api_key:     (none)")
    print(f"  search_tool: {provider.search_tool}")
    print(f"  max_results: {provider.max_results}")
    print(f"  proxy_url:   {provider.proxy_url}")

    if not provider.api_key:
        print("\n[ERROR] No x_agent.api_key found in .config.yaml")
        sys.exit(1)

    # -- 2. Connect to SSE endpoint -------------------------------------------
    print("\n[2/5] Connecting to XAgent SSE endpoint ...")
    import httpx

    sse_url = provider._build_url()
    headers = provider._build_headers()
    proxies = provider.proxy_url if provider.proxy_url else None

    sse_events: queue.Queue[dict] = queue.Queue()
    post_url_holder: list[str] = [""]
    sse_connected = threading.Event()
    sse_done = threading.Event()

    def _read_sse():
        event_type = ""
        try:
            with httpx.Client(timeout=90, proxy=proxies) as http:
                with http.stream("GET", sse_url, headers=headers) as sse_stream:
                    sse_stream.raise_for_status()
                    print(f"  SSE connected (status: {sse_stream.status_code})")
                    sse_connected.set()

                    for raw_line in sse_stream.iter_lines():
                        if sse_done.is_set():
                            break
                        line = raw_line if isinstance(raw_line, str) else raw_line.decode("utf-8", errors="replace")
                        line = line.strip()
                        if not line:
                            continue

                        if line.startswith("event:"):
                            event_type = line[len("event:"):].strip()
                            print(f"  SSE event type: {event_type}")
                            continue

                        if line.startswith("data:"):
                            data_str = line[len("data:"):].strip()

                            if event_type == "endpoint":
                                post_url_holder[0] = data_str
                                print(f"  POST endpoint: {data_str}")
                                event_type = ""
                                continue

                            try:
                                msg = json.loads(data_str)
                                if isinstance(msg, dict):
                                    sse_events.put(msg)
                                    # Print brief summary
                                    msg_id = msg.get("id", "?")
                                    has_result = "result" in msg
                                    has_error = "error" in msg
                                    print(f"  SSE response: id={msg_id}, has_result={has_result}, has_error={has_error}")
                            except json.JSONDecodeError:
                                pass
                            event_type = ""
        except Exception as exc:
            print(f"  SSE reader error: {exc}")
        finally:
            sse_connected.set()
            sse_done.set()

    sse_thread = threading.Thread(target=_read_sse, daemon=True)
    sse_thread.start()

    if not sse_connected.wait(timeout=30):
        print("[ERROR] Timed out waiting for SSE connection")
        sys.exit(1)

    # Wait for endpoint event
    for _ in range(50):
        if post_url_holder[0]:
            break
        time.sleep(0.1)

    post_url = post_url_holder[0]
    if not post_url:
        print("[ERROR] No endpoint event received from SSE stream")
        sse_done.set()
        sys.exit(1)

    # Build full POST URL
    if post_url.startswith("/"):
        from urllib.parse import urljoin
        post_url = urljoin(sse_url, post_url)

    # -- 3. Initialize MCP session --------------------------------------------
    print("\n[3/5] Initializing MCP session ...")
    with httpx.Client(timeout=30, proxy=proxies) as http:
        init_resp = http.post(
            post_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "airs-smoke-test", "version": "0.1.0"},
                },
            },
            headers=headers,
        )
        print(f"  Init POST status: {init_resp.status_code}")

    # Wait for init response on SSE stream
    init_result = XMCPProvider._wait_for_response(sse_events, request_id=1, timeout=30)
    if init_result is None:
        print("[ERROR] No initialize response received")
        sse_done.set()
        sys.exit(1)

    server_info = init_result.get("serverInfo", {})
    print(f"  Server: {server_info.get('name', '?')} v{server_info.get('version', '?')}")
    print(f"  Protocol: {init_result.get('protocolVersion', '?')}")
    print(f"  Capabilities: {list(init_result.get('capabilities', {}).keys())}")

    # -- 4. Send initialized notification + list tools -------------------------
    print("\n[4/5] Sending initialized notification ...")
    with httpx.Client(timeout=30, proxy=proxies) as http:
        http.post(
            post_url,
            json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            headers=headers,
        )
        print("  Notification sent")

        # List tools
        http.post(
            post_url,
            json={"jsonrpc": "2.0", "id": 10, "method": "tools/list", "params": {}},
            headers=headers,
        )

    tools_result = XMCPProvider._wait_for_response(sse_events, request_id=10, timeout=15)
    if tools_result:
        tools_list = tools_result.get("tools", [])
        print(f"\n  Available tools ({len(tools_list)}):")
        for tool in tools_list[:15]:
            name = tool.get("name", "?")
            desc = tool.get("description", "")[:60]
            print(f"    - {name}: {desc}")
        if len(tools_list) > 15:
            print(f"    ... and {len(tools_list) - 15} more")
    else:
        print("  [WARN] No tools/list response received")

    # -- 5. Search tweets -----------------------------------------------------
    print("\n[5/5] Searching X for 'gold jewellery Dubai' ...")
    with httpx.Client(timeout=30, proxy=proxies) as http:
        http.post(
            post_url,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": provider.search_tool,
                    "arguments": {
                        "query": "gold jewellery Dubai",
                        "max_results": 5,
                        "time_filter": "week",
                    },
                },
            },
            headers=headers,
        )

    search_result = XMCPProvider._wait_for_response(sse_events, request_id=2, timeout=60)
    sse_done.set()

    if search_result is None:
        print("[ERROR] No search response received")
        sys.exit(1)

    # Parse the result
    candidates = provider._result_to_candidates(search_result)

    if not candidates:
        print("  No candidates returned. Raw result preview:")
        print(f"  {json.dumps(search_result, ensure_ascii=False, indent=2)[:1000]}")
    else:
        print(f"\n  Got {len(candidates)} result(s):\n")
        for i, c in enumerate(candidates, 1):
            print(f"  [{i}] {c.title[:100]}")
            print(f"      URL: {c.url[:100]}")
            print(f"      Source: {c.source_name}")
            print(f"      Published: {c.published_at}")
            snippet_preview = c.snippet[:150].replace("\n", " ")
            print(f"      Snippet: {snippet_preview}...")
            print()

    # -- Also test via XMCPProvider.search() -----------------------------------
    print("\n" + "=" * 60)
    print("Testing XMCPProvider.search() directly ...")
    print("=" * 60)

    try:
        results = provider.search("luxury watches Singapore", source_type="social", time_window="7d")
        print(f"\n  Got {len(results)} result(s) from XMCPProvider.search():\n")
        for i, c in enumerate(results[:5], 1):
            print(f"  [{i}] {c.title[:100]}")
            print(f"      Source: {c.source_name}")
            print(f"      URL: {c.url[:100]}")
            print()
    except Exception as exc:
        print(f"\n  [WARN] XMCPProvider.search() failed: {type(exc).__name__}: {exc}")

    print("\n" + "=" * 60)
    print("Smoke test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()