"""Smoke test: Feishu Briefing Agent — fetch competition intel and send via Feishu CLI."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from airs.mini_agents.feishu_briefing_agent import FeishuBriefingAgent

# --- Config ---
TOPIC = "competition"
USER_ID = "ou_637d11ca8e120fcbb9b2ef2776315175"  # Your Feishu open_id
HOURS = 168  # 7 days
DRY_RUN = False  # Set to False to actually send

# --- Run ---
agent = FeishuBriefingAgent.from_config()

# Step 1: Fetch intel items
print(f"Fetching competition intel from Supabase (last {HOURS//24} days)...")
items = agent.fetch_intel_items(topic=TOPIC, hours=HOURS, limit=20)
print(f"Found {len(items)} items:")
for item in items:
    meta = item.metadata
    print(f"  [{item.doc_type}] {item.title[:80]}")
    print(f"    region: {meta.get('region', '?')}  impact_tags: {meta.get('impact_tags', [])}")
    print(f"    importance: {meta.get('importance_score', 0)}  confidence: {meta.get('confidence_score', 0)}")
    print()

# Step 2: Format and optionally send
print("=" * 60)
print("Formatting briefing...")
result = agent.run(
    topic=TOPIC,
    user_id=USER_ID,
    as_bot=True,
    hours=HOURS,
    limit=20,
    dry_run=DRY_RUN,
)

print(f"\nBriefing result: success={result.success}, items={result.items_count}")
if result.error:
    print(f"Error: {result.error}")

print("\n" + "=" * 60)
print("MARKDOWN CONTENT:")
print("=" * 60)
print(result.markdown_content)

if not DRY_RUN:
    print("\n" + "=" * 60)
    print("Feishu CLI output:")
    print(result.feishu_output)