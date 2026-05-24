import json

import httpx

from airs.mini_agents.base_collector import SearchCandidate, SupabaseWriter
from airs.mini_agents.social_media_agent import SocialMediaAgent, SocialMediaReport


def test_social_media_agent_persists_unified_impact_tags():
    posted_payloads: list[list[dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=[])
        body = json.loads(request.content.decode("utf-8"))
        posted_payloads.append(body)
        return httpx.Response(201, json=body)

    writer = SupabaseWriter(
        url="https://example.supabase.co",
        service_role_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    agent = SocialMediaAgent(supabase_writer=writer)
    report = SocialMediaReport(
        summary="Gold price volatility is shaping social discussion.",
        social_signal_cards=[
            {
                "signal_name": "Gold price concerns",
                "signal_type": "pricing_value",
                "sentiment": "mixed",
                "demand_stage": "consideration",
                "summary": "Consumers discuss gold price pressure.",
                "business_implication": "Gold price movement may affect pricing communication.",
                "post_count": 3,
                "regions": ["Global"],
                "verticals": ["gold_jewellery"],
                "platforms": ["reddit"],
                "evidence_urls": ["https://reddit.com/example"],
            }
        ],
        trending_hashtags=[],
        total_posts_analysed=1,
        raw_candidates=[
            SearchCandidate(
                title="Gold price jewellery discussion",
                url="https://reddit.com/example",
                snippet="Consumers discuss gold price volatility and jewellery pricing.",
                source_name="reddit/r/jewelry",
            )
        ],
    )

    assert agent._persist(
        report=report,
        candidates=report.raw_candidates,
        focus="gold jewellery",
        regions=["Global"],
        time_window="7d",
    )

    written_docs = [doc for batch in posted_payloads for doc in batch]
    social_cards = [doc for doc in written_docs if doc["doc_type"] == "social_signal_card"]
    assert social_cards[0]["metadata"]["topic"] == "social"
    assert social_cards[0]["metadata"]["impact_tags"] == [
        "pricing",
        "consumer_demand",
        "gold_price",
    ]
    assert social_cards[0]["metadata"]["dedup_key"].startswith(
        "social_signal_card|pricing_value|gold_jewellery|global|"
    )
    assert social_cards[0]["metadata"]["published_at"] is None
    assert social_cards[0]["metadata"]["briefing_status"] == "new"
    assert social_cards[0]["metadata"]["briefed_at"] is None
    assert social_cards[0]["metadata"]["briefing_ids"] == []
    assert "first_seen_at" in social_cards[0]["metadata"]
    assert "last_seen_at" in social_cards[0]["metadata"]
    assert "tags" not in social_cards[0]["metadata"]
    assert social_cards[0]["metadata"]["signal_type"] == "pricing_value"
