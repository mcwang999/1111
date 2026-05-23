"""Smoke test: SocialMediaAgent — see raw search results + final signal cards.

Usage:
    cd AIRS
    python test/tool_testers/smoke_social_agent.py
    python test/tool_testers/smoke_social_agent.py --focus "gold jewellery"
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from airs.mini_agents.social_media_agent import SocialMediaAgent


def main():
    parser = argparse.ArgumentParser(description="SocialMediaAgent smoke test")
    parser.add_argument("--focus", default="jewellery industry", help="Analysis focus")
    parser.add_argument("--regions", nargs="+", default=["Global"], help="Regions")
    parser.add_argument("--time-window", default="7d", help="Time window")
    parser.add_argument("--supabase", action="store_true", help="Persist to Supabase")
    parser.add_argument("--config", default=".config.yaml", help="Config path")
    args = parser.parse_args()

    config_path = Path(__file__).resolve().parent.parent.parent / args.config

    print("=" * 70)
    print("  SocialMediaAgent Smoke Test")
    print(f"  focus={args.focus}  regions={args.regions}  time={args.time_window}")
    print("=" * 70)

    # --- Build agent ---
    print("\n[1/4] Building SocialMediaAgent from config ...")
    agent = SocialMediaAgent.from_config(config_path)
    if args.supabase is False:
        agent.supabase_writer = None  # dry-run: skip DB
    print(f"  X provider:      {'yes' if agent.x_provider else 'no'}")
    print(f"  Reddit provider: {'yes' if agent.reddit_provider else 'no'}")
    print(f"  Supabase:        {'enabled' if agent.supabase_writer else 'disabled (dry-run)'}")
    print(f"  LLM curator:     {'yes' if agent.curator else 'no'}")

    # --- Run analysis ---
    print(f"\n[2/4] Searching {args.regions} for '{args.focus}' ...")
    report = agent.analyse(
        focus=args.focus,
        regions=args.regions,
        time_window=args.time_window,
    )

    # --- RAW SEARCH RESULTS ---
    print(f"\n{'='*70}")
    print(f"  RAW SEARCH RESULTS ({len(report.raw_candidates)} total)")
    print(f"{'='*70}")
    for i, c in enumerate(report.raw_candidates, 1):
        print(f"\n  [{i:02d}] {c.title[:120]}")
        print(f"        Source:    {c.source_name}")
        print(f"        URL:       {c.url[:100]}")
        print(f"        Published: {c.published_at or 'N/A'}")
        snippet = c.snippet[:200].replace("\n", " ")
        print(f"        Snippet:   {snippet}...")

    # --- SIGNAL CARDS ---
    print(f"\n{'='*70}")
    print(f"  SOCIAL SIGNAL CARDS ({len(report.social_signal_cards)} cards)")
    print(f"{'='*70}")
    for i, card in enumerate(report.social_signal_cards, 1):
        signal_name = card.get("signal_name") or card.get("topic_name", "?")
        signal_type = card.get("signal_type", "?")
        sentiment = card.get("sentiment", "?")
        summary = card.get("summary", "")[:200]
        post_count = card.get("post_count", 0)
        biz_impl = card.get("business_implication", "")[:150]
        regions = card.get("regions", [])
        verticals = card.get("verticals", [])
        platforms = card.get("platforms", [])
        key_quotes = card.get("key_quotes", [])

        print(f"\n  ┌─ Card #{i} ─────────────────────────────────────────────")
        print(f"  │ signal_name: {signal_name}")
        print(f"  │ signal_type: {signal_type}")
        print(f"  │ sentiment:   {sentiment}")
        print(f"  │ ✅ topic:    social")
        print(f"  │ ✅ tags:     [{signal_type}]")
        print(f"  │ post_count:  {post_count}")
        print(f"  │ regions:     {regions}")
        print(f"  │ verticals:   {verticals}")
        print(f"  │ platforms:   {platforms}")
        print(f"  │ summary:     {summary}")
        print(f"  │ implication: {biz_impl}")
        for j, q in enumerate(key_quotes[:2], 1):
            print(f"  │ quote[{j}]:  {q[:120]}")
        print(f"  └────────────────────────────────────────────────")

    # --- SUMMARY ---
    print(f"\n{'='*70}")
    print(f"  EXECUTIVE SUMMARY")
    print(f"{'='*70}")
    print(f"  {report.summary[:500]}")
    print(f"\n  Total raw posts:     {report.total_posts_analysed}")
    print(f"  Signal cards:        {len(report.social_signal_cards)}")
    print(f"  Trending hashtags:   {report.trending_hashtags[:10]}")
    print(f"  Persisted to DB:     {report.persisted}")
    print()

    # --- Full JSON dump for debugging ---
    print(f"\n{'='*70}")
    print("  Full report JSON (compact)")
    print(f"{'='*70}")
    dump = {
        "summary": report.summary,
        "signal_cards": [
            {
                "signal_name": s.get("signal_name") or s.get("topic_name"),
                "topic": "social",
                "tags": [s.get("signal_type")],
                "signal_type": s.get("signal_type"),
                "sentiment": s.get("sentiment"),
            }
            for s in report.social_signal_cards
        ],
        "total_posts": report.total_posts_analysed,
        "hashtags": report.trending_hashtags[:10],
        "persisted": report.persisted,
    }
    print(json.dumps(dump, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
