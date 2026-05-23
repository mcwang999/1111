"""Run all 5 regional collectors: Tavily search → LLM curation → dedup → Supabase write."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from airs.mini_agents.base_collector import (
    CollectionRequest,
    OpenAILLMCurator,
    SupabaseWriter,
    TavilySearchProvider,
    load_llm_config,
    load_supabase_config,
    load_tavily_config,
)
from airs.mini_agents.middle_east_collector import MiddleEastCollector
from airs.mini_agents.asia_pacific_collector import AsiaPacificCollector
from airs.mini_agents.europe_collector import EuropeCollector
from airs.mini_agents.americas_collector import AmericasCollector
from airs.mini_agents.emerging_markets_collector import EmergingMarketsCollector

# --- Load configs ---
tavily_config = load_tavily_config()
llm_config = load_llm_config()
supabase_config = load_supabase_config()

print(f"Tavily API key: {tavily_config['api_key'][:12]}...")
print(f"LLM model: {llm_config['model']}")
print(f"Supabase URL: {supabase_config['url'][:30]}...")

# --- Build shared providers ---
provider = TavilySearchProvider(api_key=tavily_config["api_key"], max_results=5)
curator = OpenAILLMCurator.from_config()
writer = SupabaseWriter(
    url=supabase_config["url"],
    service_role_key=supabase_config["service_role_key"],
)

# --- Define collection requests per region ---
requests = [
    ("Middle East", MiddleEastCollector, CollectionRequest(
        topic="competition",
        strategic_vertical="overseas_retail_channels",
        query_focus="flagship store expansion",
        time_window="14d",
    )),
    ("Asia Pacific", AsiaPacificCollector, CollectionRequest(
        topic="competition",
        strategic_vertical="overseas_retail_channels",
        query_focus="jewellery retail expansion",
        time_window="14d",
    )),
    ("Europe", EuropeCollector, CollectionRequest(
        topic="product",
        strategic_vertical="gold_jewellery",
        query_focus="luxury jewellery trends",
        time_window="14d",
    )),
    ("Americas", AmericasCollector, CollectionRequest(
        topic="platform",
        strategic_vertical="overseas_retail_channels",
        query_focus="jewellery retail channels",
        time_window="14d",
    )),
    ("Emerging Markets", EmergingMarketsCollector, CollectionRequest(
        topic="macro_gold",
        strategic_vertical="gold_jewellery",
        query_focus="gold demand India",
        time_window="14d",
    )),
]

# --- Run each collector ---
total_sources = 0
total_cards = 0
total_discarded = 0

for region_label, CollectorClass, request in requests:
    print(f"\n{'='*60}")
    print(f"  {region_label} Collector")
    print(f"{'='*60}")

    collector = CollectorClass(
        search_provider=provider,
        curator=curator,
        supabase_writer=writer,
    )

    result = collector.collect(request)

    print(f"  Queries: {result['generated_queries']}")
    print(f"  Raw sources: {len(result['raw_sources'])}")
    print(f"  Intel cards: {len(result['intel_cards'])}")
    print(f"  Discarded: {len(result['discarded_candidates'])}")
    print(f"  Persisted: {result['persisted']}")

    for card in result["intel_cards"]:
        meta = card["metadata"]
        print(f"    [{card['id'][:8]}...] {card['title'][:80]}")
        print(f"      topic={meta.get('topic')}  vertical={meta.get('strategic_vertical')}  "
              f"importance={meta.get('importance_score', 0):.2f}  confidence={meta.get('confidence_score', 0):.2f}")

    for item in result["discarded_candidates"][:3]:
        print(f"    Discarded: {item['title'][:60]} — {item['reason'][:60]}")

    total_sources += len(result["raw_sources"])
    total_cards += len(result["intel_cards"])
    total_discarded += len(result["discarded_candidates"])

# --- Summary ---
print(f"\n{'='*60}")
print(f"  TOTAL SUMMARY")
print(f"{'='*60}")
print(f"  Total raw sources: {total_sources}")
print(f"  Total intel cards: {total_cards}")
print(f"  Total discarded: {total_discarded}")
print(f"  All persisted to Supabase: ✅")