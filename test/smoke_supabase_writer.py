"""Verify SupabaseWriter integration: import, config, and quick smoke test."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from airs.mini_agents.middle_east_collector import (
    SupabaseWriter,
    load_supabase_config,
)

# 1. Config loads
cfg = load_supabase_config()
url = cfg["url"]
key = cfg["service_role_key"]
print(f"Supabase URL: {url[:30]}...")
print(f"Key present: {bool(key)}")
assert url.startswith("https://"), f"Bad URL: {url}"
assert key, "Missing service_role_key"

# 2. SupabaseWriter can be constructed
writer = SupabaseWriter(url=url, service_role_key=key)
print(f"SupabaseWriter created: url={writer.url[:30]}...")

# 3. Quick write test — insert then delete a test document
try:
    docs = [
        {
            "doc_type": "raw_source",
            "title": "AIRS SupabaseWriter integration test",
            "content": "Temporary test document — will be deleted immediately.",
            "metadata": {"test": True, "component": "supabase_writer"},
            "source_url": "https://example.com/airs-supabase-writer-test",
            "created_by_agent": "supabase_writer_test",
        },
    ]
    inserted = writer.write_documents(docs)
    doc_id = inserted[0]["id"]
    print(f"Inserted document id: {doc_id}")

    # Clean up
    from httpx import Request, Response

    resp = writer.http_client.request(
        "DELETE",
        f"{writer.url}/rest/v1/documents?id=eq.{doc_id}",
        headers=writer._headers(),
    )
    print(f"Cleanup DELETE status: {resp.status_code}")
    print("SupabaseWriter integration test PASSED")
except Exception as exc:
    print(f"SupabaseWriter integration test FAILED: {exc}")
    raise SystemExit(1)