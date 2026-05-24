"""End-to-end smoke test: regional collectors + social media agent + readback.

Usage:
    cd AIRS
    python test/agent_testers/smoke_full_pipeline.py
    python test/agent_testers/smoke_full_pipeline.py --region middle_east
    python test/agent_testers/smoke_full_pipeline.py --no-supabase
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from airs.mini_agents.base_collector import (  # noqa: E402
    OpenAILLMCurator,
    SupabaseWriter,
    load_llm_config,
    load_supabase_config,
)
from airs.mini_agents.social_media_agent import SocialMediaAgent  # noqa: E402
from smoke_pipeline import REGION_REQUESTS, build_providers  # noqa: E402


REGION_INDEX = {
    "middle_east": 0,
    "asia_pacific": 1,
    "europe": 2,
    "americas": 3,
    "emerging_markets": 4,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="AIRS combined full pipeline smoke test")
    parser.add_argument(
        "--region",
        "-r",
        choices=[*REGION_INDEX, "all"],
        default="all",
        help="Which regional collector(s) to run",
    )
    parser.add_argument(
        "--sources",
        "-s",
        nargs="+",
        default=["tavily", "x"],
        choices=["tavily", "x", "reddit"],
        help="Search sources for regional collectors",
    )
    parser.add_argument("--social-focus", default="jewellery industry", help="Social analysis focus")
    parser.add_argument("--social-regions", nargs="+", default=["Global"], help="Social regions")
    parser.add_argument("--social-time-window", default="7d", help="Social search time window")
    parser.add_argument("--skip-regional", action="store_true", help="Skip regional collectors")
    parser.add_argument("--skip-social", action="store_true", help="Skip social media agent")
    parser.add_argument("--no-supabase", action="store_true", help="Dry run: do not write Supabase")
    parser.add_argument("--readback-limit", type=int, default=20, help="Recent cards to read back")
    parser.add_argument("--config", default=".config.yaml", help="Config path relative to repo root")
    args = parser.parse_args()

    config_path = ROOT / args.config

    print("=" * 76)
    print("  AIRS Combined Smoke: Regional Collectors + Social Agent + Readback")
    print("=" * 76)

    print("\n[1/5] Loading configs...")
    llm_config = load_llm_config(config_path)
    supabase_config = load_supabase_config(config_path)
    print(f"  LLM: {llm_config['model']} @ {llm_config['base_url'][:40]}...")
    print(f"  Supabase: {supabase_config['url'][:30]}...")

    writer = None if args.no_supabase else SupabaseWriter(
        url=supabase_config["url"],
        service_role_key=supabase_config["service_role_key"],
    )
    print(f"  Supabase writes: {'disabled' if args.no_supabase else 'enabled'}")

    regional_summary = run_regional_collectors(args, config_path, writer)
    social_summary = run_social_agent(args, config_path, writer)

    if writer is None:
        print("\n[5/5] Supabase readback skipped (dry run)")
        readback_summary: dict[str, Any] = {}
    else:
        readback_summary = read_back_recent_cards(writer, args.readback_limit)

    print_final_summary(regional_summary, social_summary, readback_summary, writer is not None)


def run_regional_collectors(
    args: argparse.Namespace,
    config_path: Path,
    writer: SupabaseWriter | None,
) -> dict[str, Any]:
    if args.skip_regional:
        print("\n[2/5] Regional collectors skipped")
        return {"regions": 0, "raw_sources": 0, "intel_cards": 0, "discarded": 0}

    print("\n[2/5] Building regional search providers...")
    providers = build_providers(args.sources, str(config_path))
    print(f"  Active regional sources: {list(providers.keys())}")

    curator = OpenAILLMCurator.from_config(config_path)
    indices = list(range(len(REGION_REQUESTS))) if args.region == "all" else [REGION_INDEX[args.region]]

    print(f"\n[3/5] Running {len(indices)} regional collector(s)...")
    totals = {"regions": len(indices), "raw_sources": 0, "intel_cards": 0, "discarded": 0}

    for idx in indices:
        region_label, collector_class, request = REGION_REQUESTS[idx]
        print(f"\n{'-' * 76}")
        print(f"  {region_label}: topic={request.topic} vertical={request.strategic_vertical}")
        start = time.time()
        collector = collector_class(
            search_providers=providers,
            curator=curator,
            supabase_writer=writer,
        )
        result = collector.collect(request)
        elapsed = time.time() - start

        raw_count = len(result["raw_sources"])
        card_count = len(result["intel_cards"])
        discarded_count = len(result["discarded_candidates"])
        totals["raw_sources"] += raw_count
        totals["intel_cards"] += card_count
        totals["discarded"] += discarded_count

        print(
            f"  raw_sources={raw_count} intel_cards={card_count} "
            f"discarded={discarded_count} persisted={result['persisted']} time={elapsed:.1f}s"
        )
        for card in result["intel_cards"][:3]:
            meta = card["metadata"]
            print(
                f"    [{card['id'][:8]}] {card['title'][:90]} | "
                f"topic={meta.get('topic')} impact_tags={meta.get('impact_tags', [])}"
            )

    return totals


def run_social_agent(
    args: argparse.Namespace,
    config_path: Path,
    writer: SupabaseWriter | None,
) -> dict[str, Any]:
    if args.skip_social:
        print("\n[4/5] Social media agent skipped")
        return {"raw_posts": 0, "signal_cards": 0, "persisted": False}

    print("\n[4/5] Running social media agent...")
    agent = SocialMediaAgent.from_config(config_path)
    agent.supabase_writer = writer
    start = time.time()
    report = agent.analyse(
        focus=args.social_focus,
        regions=args.social_regions,
        time_window=args.social_time_window,
    )
    elapsed = time.time() - start

    print(
        f"  raw_posts={len(report.raw_candidates)} signal_cards={len(report.social_signal_cards)} "
        f"persisted={report.persisted} time={elapsed:.1f}s"
    )
    for card in report.social_signal_cards[:5]:
        signal_name = card.get("signal_name") or card.get("topic_name", "Unknown Signal")
        print(
            f"    [social] {str(signal_name)[:90]} | "
            f"signal_type={card.get('signal_type')} "
            f"impact_tags={SocialMediaAgent._impact_tags_for_signal(card)}"
        )

    return {
        "raw_posts": len(report.raw_candidates),
        "signal_cards": len(report.social_signal_cards),
        "persisted": report.persisted,
    }


def read_back_recent_cards(writer: SupabaseWriter, limit: int) -> dict[str, Any]:
    print("\n[5/5] Reading recent Supabase cards...")
    response = writer.http_client.get(
        f"{writer.url}/rest/v1/documents",
        headers=writer._headers(),
        params={
            "doc_type": "in.(intel_card,social_signal_card)",
            "select": "id,doc_type,title,metadata,created_at",
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Readback failed: {response.status_code} {response.text[:500]}")

    rows = response.json()
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for row in rows:
        doc_type = row["doc_type"]
        metadata = row.get("metadata") or {}
        by_type[doc_type] = by_type.get(doc_type, 0) + 1
        status = metadata.get("briefing_status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1

    print(f"  Recent cards read: {len(rows)}")
    print(f"  By type: {by_type}")
    print(f"  By briefing_status: {by_status}")
    for row in rows[:10]:
        metadata = row.get("metadata") or {}
        if row["doc_type"] == "social_signal_card":
            label = f"signal_type={metadata.get('signal_type')}"
        else:
            label = f"impact_tags={metadata.get('impact_tags', [])}"
        print(
            f"    [{row['id'][:8]}] ({row['doc_type']}) {row['title'][:80]} | "
            f"{label} status={metadata.get('briefing_status')}"
        )

    return {"count": len(rows), "by_type": by_type, "by_status": by_status}


def print_final_summary(
    regional: dict[str, Any],
    social: dict[str, Any],
    readback: dict[str, Any],
    wrote_supabase: bool,
) -> None:
    print(f"\n{'=' * 76}")
    print("  COMBINED SUMMARY")
    print(f"{'=' * 76}")
    print(
        "  Regional: "
        f"regions={regional['regions']} raw_sources={regional['raw_sources']} "
        f"intel_cards={regional['intel_cards']} discarded={regional['discarded']}"
    )
    print(
        "  Social: "
        f"raw_posts={social['raw_posts']} signal_cards={social['signal_cards']} "
        f"persisted={social['persisted']}"
    )
    if wrote_supabase:
        print(f"  Readback: {readback.get('count', 0)} recent cards")
    else:
        print("  Supabase: dry run")
    print()


if __name__ == "__main__":
    main()
