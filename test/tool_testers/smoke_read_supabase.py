"""Read back intel cards and raw sources from Supabase."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from airs.mini_agents.base_collector import SupabaseWriter, load_supabase_config

cfg = load_supabase_config()
writer = SupabaseWriter(url=cfg["url"], service_role_key=cfg["service_role_key"])

# --- Read intel_cards (regional collectors) + social_signal_cards (social_media_agent) ---
resp = writer.http_client.get(
    f"{writer.url}/rest/v1/documents?doc_type=in.(intel_card,social_signal_card)&select=id,doc_type,title,metadata,created_at&order=created_at.desc&limit=50",
    headers=writer._headers(),
)
cards = resp.json()
print(f"=== Intelligence Cards ({len(cards)}) ===")
for c in cards:
    meta = c["metadata"]
    dtype = c["doc_type"]
    print(f"  [{c['id'][:8]}...] ({dtype}) {c['title'][:100]}")
    print(f"    topic: {meta.get('topic', '?')}  tags: {meta.get('tags', [])}")
    print(f"    vertical: {meta.get('strategic_vertical') or meta.get('verticals', '?')}")
    if dtype == "intel_card":
        print(f"    region: {meta.get('region')}  importance: {meta.get('importance_score')}  confidence: {meta.get('confidence_score')}")
        print(f"    sources: {meta.get('source_count')}  event_key: {meta.get('event_key')}")
        print(f"    topic_source: {meta.get('topic_source')}  vertical_source: {meta.get('vertical_source')}")
        print(f"    dedup_method: {meta.get('dedup_method')}  canonical_event_key: {meta.get('canonical_event_key')}")
        print(f"    primary_source_id: {meta.get('primary_source_id')}")
    if dtype == "social_signal_card":
        print(f"    signal_type: {meta.get('signal_type', '?')}  sentiment: {meta.get('sentiment', '?')}")
        print(f"    platforms: {meta.get('platforms', [])}  regions: {meta.get('regions', [])}")
        print(f"    business_implication: {meta.get('business_implication', '?')[:100]}")
    print(f"    created_by: {c.get('created_by_agent', 'N/A')}  created: {c['created_at']}")
    print()

# --- Read raw_sources ---
resp2 = writer.http_client.get(
    f"{writer.url}/rest/v1/documents?doc_type=eq.raw_source&select=id,title,source_url,metadata,created_at&order=created_at.desc&limit=50",
    headers=writer._headers(),
)
sources = resp2.json()
print(f"=== Raw Sources ({len(sources)}) ===")
for s in sources:
    meta = s["metadata"]
    print(f"  [{s['id'][:8]}...] {s['title']}")
    print(f"    URL: {s['source_url']}")
    print(f"    region: {meta.get('region')}  topic: {meta.get('topic')}  vertical: {meta.get('strategic_vertical')}")
    print(f"    relevance: {meta.get('llm_relevance_score')}  keep_reason: {meta.get('llm_keep_reason', 'N/A')[:80]}")
    print(f"    topic_source: {meta.get('topic_source')}  vertical_source: {meta.get('vertical_source')}")
    print(f"    event_key: {meta.get('event_key')}  source_name: {meta.get('source_name')}")
    print(f"    published_at: {meta.get('published_at')}  evidence_quality: {meta.get('evidence_quality')}")
    print(f"    created_by: {s.get('created_by_agent', 'N/A')}  created: {s['created_at']}")
    print()

# --- Read agent_runs ---
resp3 = writer.http_client.get(
    f"{writer.url}/rest/v1/agent_runs?select=id,agent_name,tool_name,status,output_payload,created_at&order=created_at.desc&limit=20",
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