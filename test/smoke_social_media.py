"""Smoke test: run the Social Media Analysis Agent end-to-end.

Searches X/Twitter for jewellery-related discussions, analyses hot topics
with LLM, and optionally persists to Supabase.

Usage:
    cd AIRS
    python test/smoke_social_media.py
    python test/smoke_social_media.py --no-supabase
    python test/smoke_social_media.py --regions Singapore Dubai
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from airs.social_media_agent import SocialMediaAgent


def main():
    import argparse

    parser = argparse.ArgumentParser(description="AIRS Social Media Analysis Agent")
    parser.add_argument(
        "--regions", "-r",
        nargs="+",
        default=None,
        help="Regions to analyse (Singapore, Dubai, US, Southeast Asia, Global)",
    )
    parser.add_argument(
        "--focus", "-f",
        default="Chow Tai Fook jewellery overseas",
        help="Focus area for the analysis",
    )
    parser.add_argument(
        "--time-window", "-t",
        default="7d",
        help="Time window (e.g. 7d, 14d, 30d)",
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

    config_path = Path(__file__).resolve().parent.parent / args.config

    print("=" * 70)
    print("  AIRS Social Media Analysis Agent")
    print("=" * 70)
    print(f"  Focus: {args.focus}")
    print(f"  Regions: {args.regions or 'all'}")
    print(f"  Time window: {args.time_window}")
    print(f"  Supabase: {'SKIP (dry run)' if args.no_supabase else 'enabled'}")

    # Build agent
    print("\n[1/2] Initialising agent...")
    agent = SocialMediaAgent.from_config(config_path)

    if args.no_supabase:
        agent.supabase_writer = None

    # Run analysis
    print("\n[2/2] Running social media analysis...")
    report = agent.analyse(
        focus=args.focus,
        regions=args.regions,
        time_window=args.time_window,
    )

    # Print results
    print(f"\n{'='*70}")
    print(f"  ANALYSIS RESULTS")
    print(f"{'='*70}")
    print(f"\n  Posts analysed: {report.total_posts_analysed}")
    print(f"  Social signals found: {len(report.social_signal_cards)}")
    print(f"  Persisted to Supabase: {report.persisted}")

    print(f"\n{'─'*70}")
    print(f"  EXECUTIVE SUMMARY")
    print(f"{'─'*70}")
    print(f"\n{report.summary}")

    print(f"\n{'─'*70}")
    print(f"  SOCIAL SIGNALS")
    print(f"{'─'*70}")
    for i, topic in enumerate(report.social_signal_cards, 1):
        print(f"\n  [{i}] {topic.get('signal_name') or topic.get('topic_name', 'Unknown')}")
        print(f"      Signal type: {topic.get('signal_type', '?')}")
        print(f"      Sentiment: {topic.get('sentiment', '?')}")
        print(f"      Demand stage: {topic.get('demand_stage', '?')}")
        print(f"      Posts: {topic.get('post_count', 0)}")
        print(f"      Regions: {', '.join(topic.get('regions', []))}")
        print(f"      Verticals: {', '.join(topic.get('verticals', []))}")
        print(f"      Platforms: {', '.join(topic.get('platforms', []))}")
        print(f"      Summary: {topic.get('summary', '')[:200]}")
        print(f"      Business implication: {topic.get('business_implication', '')[:200]}")
        quotes = topic.get("key_quotes", [])
        if quotes:
            print(f"      Key quotes:")
            for q in quotes[:3]:
                print(f"        - \"{q[:120]}\"")

    if report.trending_hashtags:
        print(f"\n{'─'*70}")
        print(f"  TRENDING HASHTAGS")
        print(f"{'─'*70}")
        print(f"  {', '.join(report.trending_hashtags[:20])}")

    # Print raw posts summary
    print(f"\n{'─'*70}")
    print(f"  RAW POSTS (top 10)")
    print(f"{'─'*70}")
    for i, c in enumerate(report.raw_candidates[:10], 1):
        print(f"\n  [{i}] {c.title[:100]}")
        print(f"      Source: {c.source_name}")
        print(f"      URL: {c.url[:100]}")

    print(f"\n{'='*70}")
    print(f"  DONE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
