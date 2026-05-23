"""Full pipeline: X + Tavily + Reddit search → LLM curation → dedup → Supabase write.

Runs all 5 regional collectors with multi-source search (X/Twitter, Tavily, Reddit),
LLM curation, and Supabase persistence.

Usage:
    cd AIRS
    python test/smoke_pipeline.py
    python test/smoke_pipeline.py --region middle_east   # single region
    python test/smoke_pipeline.py --no-supabase           # skip DB write
    python test/smoke_pipeline.py --sources x tavily       # select sources
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
from airs.providers.x_search_provider import XSearchProvider
from airs.mcp.reddit_mcp import RedditMCPProvider


def build_providers(sources: list[str], config_path: str = ".config.yaml"):
    """Build search providers based on requested source types."""
    providers = {}

    if "tavily" in sources:
        tavily_config = load_tavily_config(config_path)
        if tavily_config.get("api_key"):
            providers["news"] = TavilySearchProvider(
                api_key=tavily_config["api_key"], max_results=5
            )
            print(f"  [Tavily] API key: {tavily_config['api_key'][:12]}...")
        else:
            print("  [Tavily] No API key found, skipping")

    if "x" in sources:
        try:
            x_provider = XSearchProvider.from_config(config_path)
            providers["x"] = x_provider
            print(f"  [X] mode={x_provider._mcp_provider.mode if x_provider._mcp_provider else 'fallback'}")
        except Exception as exc:
            print(f"  [X] Failed to initialize: {exc}")

    if "reddit" in sources:
        try:
            reddit_provider = RedditMCPProvider.from_config(config_path)
            providers["social"] = reddit_provider
            print(f"  [Reddit] command={reddit_provider.server_config.command}")
        except Exception as exc:
            print(f"  [Reddit] Failed to initialize: {exc}")

    return providers


# ---------------------------------------------------------------------------
# Region definitions
# ---------------------------------------------------------------------------

REGION_REQUESTS = [
    ("Middle East", MiddleEastCollector, CollectionRequest(
        topic="competition",
        strategic_vertical="overseas_retail_channels",
        query_focus="Chow Tai Fook flagship store expansion",
        time_window="14d",
        source_types=["news", "x"],
    )),
    ("Asia Pacific", AsiaPacificCollector, CollectionRequest(
        topic="competition",
        strategic_vertical="overseas_retail_channels",
        query_focus="jewellery retail expansion Singapore",
        time_window="14d",
        source_types=["news", "x"],
    )),
    ("Europe", EuropeCollector, CollectionRequest(
        topic="product",
        strategic_vertical="gold_jewellery",
        query_focus="luxury jewellery trends",
        time_window="14d",
        source_types=["news", "x"],
    )),
    ("Americas", AmericasCollector, CollectionRequest(
        topic="channel",
        strategic_vertical="overseas_retail_channels",
        query_focus="jewellery retail channels",
        time_window="14d",
        source_types=["news", "x"],
    )),
    ("Emerging Markets", EmergingMarketsCollector, CollectionRequest(
        topic="product",
        strategic_vertical="gold_jewellery",
        query_focus="gold demand India Dubai",
        time_window="14d",
        source_types=["news", "x"],
    )),
]


def main():
    parser = argparse.ArgumentParser(description="AIRS full pipeline smoke test")
    parser.add_argument(
        "--region", "-r",
        choices=["middle_east", "asia_pacific", "europe", "americas", "emerging_markets", "all"],
        default="all",
        help="Which region(s) to run",
    )
    parser.add_argument(
        "--sources", "-s",
        nargs="+",
        default=["tavily", "x"],
        choices=["tavily", "x", "reddit"],
        help="Which search sources to use",
    )
    parser.add_argument(
        "--no-supabase",
        action="store_true",
        help="Skip Supabase write (dry run)",
    )
    parser.add_argument(
        "--config",
        default=".config.yaml",
        help="Path to config file",
    )
    args = parser.parse_args()

    config_path = Path(__file__).resolve().parent.parent.parent / args.config

    print("=" * 70)
    print("  AIRS Full Pipeline: Search → Curate → Dedup → Write")
    print("=" * 70)

    # --- Load configs ---
    print("\n[1/3] Loading configs...")
    llm_config = load_llm_config(config_path)
    print(f"  LLM: {llm_config['model']} @ {llm_config['base_url'][:40]}...")

    supabase_config = load_supabase_config(config_path)
    print(f"  Supabase: {supabase_config['url'][:30]}...")

    # --- Build providers ---
    print("\n[2/3] Building search providers...")
    providers = build_providers(args.sources, config_path)
    print(f"  Active sources: {list(providers.keys())}")

    # --- Build curator & writer ---
    curator = OpenAILLMCurator.from_config(config_path)
    writer = None if args.no_supabase else SupabaseWriter(
        url=supabase_config["url"],
        service_role_key=supabase_config["service_role_key"],
    )
    if args.no_supabase:
        print("  [Supabase] SKIPPED (dry run)")
    else:
        print("  [Supabase] Writer ready")

    # --- Select regions ---
    region_map = {
        "middle_east": 0,
        "asia_pacific": 1,
        "europe": 2,
        "americas": 3,
        "emerging_markets": 4,
    }
    if args.region == "all":
        indices = list(range(len(REGION_REQUESTS)))
    else:
        indices = [region_map[args.region]]

    # --- Run pipeline ---
    print(f"\n[3/3] Running {len(indices)} region(s)...")
    total_sources = 0
    total_cards = 0
    total_discarded = 0
    all_persisted = True

    for idx in indices:
        region_label, CollectorClass, request = REGION_REQUESTS[idx]
        print(f"\n{'='*70}")
        print(f"  {region_label} Collector")
        print(f"  Topic: {request.topic} | Vertical: {request.strategic_vertical}")
        print(f"  Sources: {request.source_types}")
        print(f"{'='*70}")

        start = time.time()
        collector = CollectorClass(
            search_providers=providers,
            curator=curator,
            supabase_writer=writer,
        )
        result = collector.collect(request)
        elapsed = time.time() - start

        print(f"\n  Queries: {result['generated_queries']}")
        print(f"  Raw sources: {len(result['raw_sources'])}")
        print(f"  Intel cards: {len(result['intel_cards'])}")
        print(f"  Discarded: {len(result['discarded_candidates'])}")
        print(f"  Persisted: {result['persisted']}")
        print(f"  Time: {elapsed:.1f}s")

        # Show source breakdown
        source_counts: dict[str, int] = {}
        for src in result["raw_sources"]:
            name = src["metadata"].get("source_name", "unknown")
            source_counts[name] = source_counts.get(name, 0) + 1
        if source_counts:
            print(f"  Sources by type: {source_counts}")

        # Show intel cards
        for card in result["intel_cards"]:
            meta = card["metadata"]
            title = card["title"][:80]
            print(f"    [{card['id'][:8]}...] {title}")
            print(f"      topic={meta.get('topic')}  vertical={meta.get('strategic_vertical')}  "
                  f"importance={meta.get('importance_score', 0):.2f}  confidence={meta.get('confidence_score', 0):.2f}")

        # Show top discarded
        for item in result["discarded_candidates"][:3]:
            print(f"    Discarded: {item['title'][:60]} — {item['reason'][:60]}")

        total_sources += len(result["raw_sources"])
        total_cards += len(result["intel_cards"])
        total_discarded += len(result["discarded_candidates"])
        if not result["persisted"] and writer is not None:
            all_persisted = False

    # --- Summary ---
    print(f"\n{'='*70}")
    print(f"  TOTAL SUMMARY")
    print(f"{'='*70}")
    print(f"  Regions: {len(indices)}")
    print(f"  Total raw sources: {total_sources}")
    print(f"  Total intel cards: {total_cards}")
    print(f"  Total discarded: {total_discarded}")
    if writer is not None:
        print(f"  All persisted to Supabase: {'YES' if all_persisted else 'NO'}")
    else:
        print(f"  Supabase: SKIPPED (dry run)")
    print()


if __name__ == "__main__":
    main()