import json
import sys

import pytest

from airs.providers.base_mcp import BaseMCPClient, MCPServerConfig


def test_base_mcp_client_times_out_when_server_does_not_answer():
    client = BaseMCPClient(
        MCPServerConfig(
            command=sys.executable,
            args=["-c", "import time; time.sleep(5)"],
        ),
        timeout_seconds=0.2,
    )

    with pytest.raises(RuntimeError, match="timed out"):
        client.start()


def test_base_mcp_client_merges_proxy_env_into_child_process():
    client = BaseMCPClient(
        MCPServerConfig(
            command=sys.executable,
            args=[
                "-c",
                (
                    "import json, os; "
                    "print(json.dumps({'jsonrpc':'2.0','id':1,'result':{'proxy':os.environ.get('HTTPS_PROXY')}}), flush=True); "
                    "input()"
                ),
            ],
        ),
        proxy_url="http://127.0.0.1:7890",
    )

    try:
        client._process = client._start_process()
        line = client._process.stdout.readline()
        result = json.loads(line)["result"]
    finally:
        client.close()

    assert result == {"proxy": "http://127.0.0.1:7890"}
