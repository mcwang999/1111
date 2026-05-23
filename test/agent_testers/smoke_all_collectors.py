"""Quick smoke test: verify all regional collectors can be instantiated and produce queries."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from airs.mini_agents.base_collector import (
    CollectionRequest,
    StaticSearchProvider,
    OpenAILLMCurator,
)
from airs.mini_agents.middle_east_collector import MiddleEastCollector
from airs.mini_agents.asia_pacific_collector import AsiaPacificCollector
from airs.mini_agents.europe_collector import EuropeCollector
from airs.mini_agents.americas_collector import AmericasCollector
from airs.mini_agents.emerging_markets_collector import EmergingMarketsCollector

import json
import httpx


def make_curator():
    """Mock curator that keeps everything — reads candidate count from the user message."""
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        # Count candidates from the user message JSON
        user_msg = payload["messages"][1]["content"]
        user_data = json.loads(user_msg)
        n_candidates = len(user_data.get("candidates", []))
        decisions = [
            {
                "candidate_index": i,
                "keep": True,
                "reason": "test: keep all",
                "event_key": f"test event {i}",
                "topic": "competition",
                "strategic_vertical": "overseas_retail_channels",
                "relevance_score": 0.75,
            }
            for i in range(n_candidates)
        ]
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"decisions": decisions})}}]})

    return OpenAILLMCurator(api_key="test", model="test", http_client=httpx.Client(transport=httpx.MockTransport(handler)))


collectors = {
    "middle_east": MiddleEastCollector,
    "asia_pacific": AsiaPacificCollector,
    "europe": EuropeCollector,
    "americas": AmericasCollector,
    "emerging_markets": EmergingMarketsCollector,
}

request = CollectionRequest(
    topic="competition",
    strategic_vertical="overseas_retail_channels",
    query_focus="flagship store expansion",
    time_window="14d",
)

for region_name, CollectorClass in collectors.items():
    provider = StaticSearchProvider([
        __import__("airs.mini_agents.base_collector", fromlist=["SearchCandidate"]).SearchCandidate(
            title=f"Test jewellery news in {region_name}",
            url=f"https://example.com/{region_name}-jewellery",
            snippet=f"Jewellery market update in {region_name}.",
            source_name="Test News",
        ),
    ])
    curator = make_curator()
    collector = CollectorClass(search_provider=provider, curator=curator)

    result = collector.collect(request)

    print(f"\n=== {collector.REGION_LABEL} ({region_name}) ===")
    print(f"  REGION: {collector.REGION}")
    print(f"  AGENT_NAME: {collector.AGENT_NAME}")
    print(f"  Queries: {result['generated_queries']}")
    print(f"  Raw sources: {len(result['raw_sources'])}")
    print(f"  Intel cards: {len(result['intel_cards'])}")
    print(f"  Persisted: {result['persisted']}")

    assert result["region"] == region_name, f"Expected region={region_name}, got {result['region']}"
    assert len(result["raw_sources"]) >= 1, f"Expected >=1 raw source, got {len(result['raw_sources'])}"
    assert len(result["intel_cards"]) >= 1, f"Expected >=1 intel card, got {len(result['intel_cards'])}"
    assert result["raw_sources"][0]["metadata"]["region"] == region_name
    assert result["intel_cards"][0]["metadata"]["region"] == region_name
    assert result["intel_cards"][0]["created_by_agent"] == collector.AGENT_NAME

print("\n✅ All 5 regional collectors passed!")