"""End-to-end smoke test: Tavily search → LLM curation → dedup → Supabase write."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

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

# --- Load configs ---
tavily_config = load_tavily_config()
llm_config = load_llm_config()
supabase_config = load_supabase_config()

print(f"Tavily API key: {tavily_config['api_key'][:12]}...")
print(f"LLM model: {llm_config['model']}")
print(f"Supabase URL: {supabase_config['url'][:30]}...")

# --- Build pipeline ---
provider = TavilySearchProvider(api_key=tavily_config["api_key"], max_results=5)
curator = OpenAILLMCurator.from_config()
writer = SupabaseWriter(
    url=supabase_config["url"],
    service_role_key=supabase_config["service_role_key"],
)
collector = MiddleEastCollector(
    search_provider=provider,
    curator=curator,
    supabase_writer=writer,
)

# --- Run collection ---
result = collector.collect(
    CollectionRequest(
        topic="competition",
        strategic_vertical="overseas_retail_channels",
        query_focus="flagship store expansion",
        time_window="14d",
    )
)

# --- Print results ---
print(f"\n=== Generated Queries ({len(result['generated_queries'])}) ===")
for q in result["generated_queries"]:
    print(f"  - {q}")

print(f"\n=== Raw Sources ({len(result['raw_sources'])}) ===")
for src in result["raw_sources"]:
    print(f"  [{src['id'][:8]}...] {src['title']}")
    print(f"    URL: {src['source_url']}")
    print(f"    Snippet: {src['content'][:100]}...")
    print()

print(f"=== Discarded Candidates ({len(result['discarded_candidates'])}) ===")
for item in result["discarded_candidates"][:8]:
    print(f"  - {item['title']}")
    print(f"    Reason: {item['reason']}")
    print()

print(f"=== Intel Cards ({len(result['intel_cards'])}) ===")
for card in result["intel_cards"]:
    print(f"  [{card['id'][:8]}...] {card['title']}")
    print(f"    Source count: {card['metadata']['source_count']}")
    print(f"    Importance:   {card['metadata']['importance_score']:.2f}")
    print(f"    Confidence:   {card['metadata']['confidence_score']:.2f}")
    print(f"    Event key:    {card['metadata']['canonical_event_key']}")
    print()

print(f"=== Persisted to Supabase: {result['persisted']} ===")
print(f"=== Coverage ===")
print(f"  {result['coverage']}")