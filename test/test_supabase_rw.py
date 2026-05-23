"""
Minimal Supabase read/write smoke test for AIRS.

Run from the project root:
    python test/test_supabase_rw.py

Config sources, in order:
1. .config.yaml
2. environment variables

Accepted .config.yaml shapes:
    supabase_url: https://xxx.supabase.co
    supabase_service_role_key: ey...

or:
    supabase:
      url: https://xxx.supabase.co
      service_role_key: ey...
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path("D:/ai_hackthon/AIRS/.config.yaml")
TEST_TITLE = "AIRS Supabase smoke test"


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}

    result: dict[str, Any] = {}
    current_section: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if not value:
            current_section = key
            result.setdefault(current_section, {})
            continue

        if raw_line.startswith((" ", "\t")) and current_section:
            section = result.setdefault(current_section, {})
            if isinstance(section, dict):
                section[key] = value
        else:
            current_section = None
            result[key] = value

    return result


def load_config() -> tuple[str, str]:
    config = parse_simple_yaml(CONFIG_PATH)
    supabase_config = config.get("supabase", {})
    if not isinstance(supabase_config, dict):
        supabase_config = {}

    url = (
        config.get("supabase_url")
        or config.get("SUPABASE_URL")
        or supabase_config.get("url")
        or os.getenv("SUPABASE_URL")
        or ""
    )
    key = (
        config.get("supabase_service_role_key")
        or config.get("SUPABASE_SERVICE_ROLE_KEY")
        or supabase_config.get("service_role_key")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    )

    if not url or not key:
        raise RuntimeError(
            "Missing Supabase config. Add supabase_url and supabase_service_role_key "
            "to .config.yaml, or set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )

    return str(url).rstrip("/"), str(key)


def request_json(
    method: str,
    url: str,
    service_role_key: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    request = Request(url=url, data=body, method=method, headers=headers)

    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase HTTP {exc.code}: {raw_error}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Supabase: {exc}") from exc


def main() -> int:
    supabase_url, service_role_key = load_config()
    base = f"{supabase_url}/rest/v1/documents"

    print("Checking Supabase documents table...")
    query = urlencode({"select": "id,title,doc_type", "limit": "1"})
    request_json("GET", f"{base}?{query}", service_role_key)

    print("Writing smoke-test document...")
    inserted = request_json(
        "POST",
        base,
        service_role_key,
        {
            "doc_type": "raw_source",
            "title": TEST_TITLE,
            "content": "Temporary read/write test created by AIRS.",
            "metadata": {"test": True, "component": "supabase_rw"},
            "source_url": "https://example.com/airs-supabase-smoke-test",
            "created_by_agent": "supabase_rw_test",
        },
    )
    if not inserted or not isinstance(inserted, list):
        raise RuntimeError(f"Unexpected insert response: {inserted!r}")

    document_id = inserted[0]["id"]
    print(f"Inserted document id: {document_id}")

    print("Reading smoke-test document back...")
    read_query = urlencode({"select": "id,title,metadata", "id": f"eq.{document_id}"})
    loaded = request_json("GET", f"{base}?{read_query}", service_role_key)
    if not loaded or loaded[0]["title"] != TEST_TITLE:
        raise RuntimeError(f"Readback failed: {loaded!r}")

    print("Deleting smoke-test document...")
    delete_query = urlencode({"id": f"eq.{document_id}"})
    request_json("DELETE", f"{base}?{delete_query}", service_role_key)

    print("Supabase read/write smoke test passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Supabase read/write smoke test failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
