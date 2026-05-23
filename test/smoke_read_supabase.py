"""Read back intel cards and raw sources from Supabase."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from airs.mini_agents.middle_east_collector import SupabaseWriter, load_supabase_config

cfg = load_supabase_config()
writer = SupabaseWriter(url=cfg["url"], service_role_key=cfg["service_role_key"])

# --- Read intel_cards ---
resp = writer.http_client.get(
    f"{writer.url}/rest/v1/documents?doc_type=eq.intel_card&select=id,title,metadata,created_at&order=created_at.desc&limit=10",
    headers=writer._headers(),
)
cards = resp.json()
print(f"=== Intel Cards ({len(cards)}) ===")
for c in cards:
    meta = c["metadata"]
    print(f"  [{c['id'][:8]}...] {c['title']}")
    print(f"    topic: {meta.get('topic')}  vertical: {meta.get('strategic_vertical')}")
    print(f"    importance: {meta.get('importance_score')}  confidence: {meta.get('confidence_score')}")
    print(f"    sources: {meta.get('source_count')}  event: {meta.get('event_key')}")
    print(f"    created: {c['created_at']}")
    print()

# --- Read raw_sources ---
resp2 = writer.http_client.get(
    f"{writer.url}/rest/v1/documents?doc_type=eq.raw_source&select=id,title,source_url,metadata,created_at&order=created_at.desc&limit=10",
    headers=writer._headers(),
)
sources = resp2.json()
print(f"=== Raw Sources ({len(sources)}) ===")
for s in sources:
    meta = s["metadata"]
    print(f"  [{s['id'][:8]}...] {s['title']}")
    print(f"    URL: {s['source_url']}")
    print(f"    topic: {meta.get('topic')}  relevance: {meta.get('llm_relevance_score')}")
    print(f"    created: {s['created_at']}")
    print()

# --- Read agent_runs ---
resp3 = writer.http_client.get(
    f"{writer.url}/rest/v1/agent_runs?select=id,agent_name,tool_name,status,output_payload,created_at&order=created_at.desc&limit=5",
    headers=writer._headers(),
)
runs = resp3.json()
print(f"=== Agent Runs ({len(runs)}) ===")
for r in runs:
    out = r["output_payload"]
    print(f"  [{r['id'][:8]}...] {r['agent_name']} / {r['tool_name']}  status={r['status']}")
    print(f"    raw_sources: {out.get('raw_source_count')}  intel_cards: {out.get('intel_card_count')}  discarded: {out.get('discarded_count')}")
    print(f"    created: {r['created_at']}")
    print()

# --- Total count ---
resp4 = writer.http_client.get(
    f"{writer.url}/rest/v1/documents?select=id",
    headers={**writer._headers(), "Prefer": "count=exact"},
)
total = len(resp4.json())
print(f"=== Total documents in table: {total} ===")