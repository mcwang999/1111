import json

import httpx

from airs.mini_agents.base_collector import (
    CollectionRequest,
    LLMCurator,
    OpenAILLMCurator,
    SearchCandidate,
    StaticSearchProvider,
    SupabaseWriter,
    load_supabase_config,
    load_tavily_config,
    TavilySearchProvider,
)
from airs.mini_agents.middle_east_collector import MiddleEastCollector


def make_curator(decisions):
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["model"] == "test-model"
        assert payload["messages"][0]["role"] == "system"
        assert "Middle East collector mini-agent" in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"decisions": decisions}),
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAILLMCurator(api_key="test-key", model="test-model", http_client=client)


def test_middle_east_collector_collects_and_deduplicates_events():
    provider = StaticSearchProvider(
        [
            SearchCandidate(
                title="Pandora opens new flagship store in Dubai",
                url="https://example.com/story?utm_source=news&id=1",
                snippet="Pandora opened a flagship jewellery store in Dubai for premium shoppers.",
                source_name="Example News",
                published_at="2026-05-20",
            ),
            SearchCandidate(
                title="Pandora launches Dubai flagship jewellery store",
                url="https://trade.example.com/pandora-dubai",
                snippet="The jewellery brand opened a Dubai flagship store in the UAE.",
                source_name="Example Trade",
                published_at="2026-05-21",
            ),
        ]
    )
    curator = make_curator(
        [
            {
                "candidate_index": 0,
                "keep": True,
                "reason": "Middle East jewellery retail expansion signal.",
                "event_key": "Pandora Dubai flagship store expansion",
                "topic": "competition",
                "impact_tags": ["retail_operations", "brand_reputation"],
                "strategic_vertical": "overseas_retail_channels",
                "relevance_score": 0.86,
            },
            {
                "candidate_index": 1,
                "keep": True,
                "reason": "Duplicate report for the same Dubai flagship event.",
                "event_key": "Pandora Dubai flagship store expansion",
                "topic": "competition",
                "impact_tags": ["retail_operations"],
                "strategic_vertical": "overseas_retail_channels",
                "relevance_score": 0.82,
            },
        ]
    )
    collector = MiddleEastCollector(search_provider=provider, curator=curator)

    result = collector.collect(
        CollectionRequest(
            topic="competition",
            strategic_vertical="overseas_retail_channels",
            query_focus="flagship store expansion",
            time_window="14d",
        )
    )

    assert result["region"] == "middle_east"
    assert any("Middle East" in query for query in result["generated_queries"])
    assert any("Dubai" in query or "UAE" in query for query in result["generated_queries"])
    assert len(result["raw_sources"]) == 2
    assert len(result["intel_cards"]) == 1

    card = result["intel_cards"][0]
    assert card["metadata"]["region"] == "middle_east"
    assert card["metadata"]["topic"] == "competition"
    assert card["metadata"]["strategic_vertical"] == "overseas_retail_channels"
    assert card["metadata"]["source_count"] == 2
    assert card["metadata"]["supporting_source_ids"]
    assert card["metadata"]["event_key"] == "Pandora Dubai flagship store expansion"
    assert card["metadata"]["topic_source"] == "llm_selected"
    assert card["metadata"]["vertical_source"] == "llm_selected"
    assert card["metadata"]["impact_tags"] == ["brand_reputation", "retail_operations"]


def test_middle_east_collector_changes_queries_by_topic():
    collector = MiddleEastCollector(search_provider=StaticSearchProvider([]), curator=make_curator([]))

    social_result = collector.collect(
        CollectionRequest(
            topic="social",
            strategic_vertical="gold_jewellery",
            query_focus="Ramadan wedding demand",
        )
    )
    macro_result = collector.collect(
        CollectionRequest(
            topic="macro_gold",
            strategic_vertical="gold_jewellery",
            query_focus="gold price volatility",
        )
    )

    assert any("social media" in query for query in social_result["generated_queries"])
    assert any("gold price" in query for query in macro_result["generated_queries"])


def test_middle_east_collector_filters_out_non_regional_or_non_jewellery_noise():
    curator = make_curator(
        [
            {
                "candidate_index": 0,
                "keep": False,
                "reason": "US retail event, not Middle East jewellery.",
                "event_key": None,
                "topic": None,
                "strategic_vertical": None,
                "relevance_score": 0.05,
            },
            {
                "candidate_index": 1,
                "keep": False,
                "reason": "Middle East event but not jewellery or luxury retail.",
                "event_key": None,
                "topic": None,
                "strategic_vertical": None,
                "relevance_score": 0.15,
            },
            {
                "candidate_index": 2,
                "keep": True,
                "reason": "Dubai gold jewellery Ramadan demand signal.",
                "event_key": "Dubai gold jewellery Ramadan collections",
                "topic": "product",
                "strategic_vertical": "gold_jewellery",
                "relevance_score": 0.91,
            },
        ]
    )
    collector = MiddleEastCollector(
        search_provider=StaticSearchProvider(
            [
                SearchCandidate(
                    title="Primark pushes US expansion with new Manhattan flagship",
                    url="https://example.com/primark-manhattan",
                    snippet="Primark opened a flagship store in Manhattan, US.",
                    source_name="Retail News",
                ),
                SearchCandidate(
                    title="DHL Express launches Middle East SAF hub",
                    url="https://example.com/dhl-middle-east",
                    snippet="DHL announced an aviation fuel hub in the Middle East.",
                    source_name="Aviation News",
                ),
                SearchCandidate(
                    title="Dubai gold jewellery retailers expand Ramadan collections",
                    url="https://example.com/dubai-gold-jewellery",
                    snippet="Dubai retailers reported stronger gold jewellery demand before Ramadan.",
                    source_name="Jewellery News",
                ),
            ]
        ),
        curator=curator,
    )

    result = collector.collect(
        CollectionRequest(
            topic="product",
            strategic_vertical="gold_jewellery",
            query_focus="Ramadan demand",
        )
    )

    assert len(result["raw_sources"]) == 1
    assert result["raw_sources"][0]["title"] == "Dubai gold jewellery retailers expand Ramadan collections"
    assert len(result["intel_cards"]) == 1
    assert len(result["discarded_candidates"]) == 2
    assert result["discarded_candidates"][0]["reason"] == "US retail event, not Middle East jewellery."


def test_static_search_provider_records_queries():
    provider = StaticSearchProvider([])
    collector = MiddleEastCollector(search_provider=provider, curator=make_curator([]))
    collector.collect(
        CollectionRequest(
            topic="competition",
            strategic_vertical="overseas_retail_channels",
            query_focus="flagship store expansion",
        )
    )
    assert len(provider.queries) == 3


def test_middle_east_collector_prompt_tells_llm_what_to_search_and_write():
    collector = MiddleEastCollector(search_provider=StaticSearchProvider([]), curator=make_curator([]))

    prompt = collector.build_agent_prompt(
        CollectionRequest(
            topic="social",
            strategic_vertical="gold_jewellery",
            query_focus="Ramadan wedding demand",
        )
    )

    assert "Middle East collector mini-agent" in prompt
    assert "Tavily" in prompt
    assert "gold_jewellery" in prompt
    assert "social" in prompt
    assert "Allowed topic values" in prompt
    assert "Allowed impact_tags values" in prompt
    assert "topic is a single primary intelligence category" in prompt
    assert "impact_tags are multi-select business impact labels" in prompt
    assert "Allowed strategic_vertical values" in prompt
    assert "jewellery" in prompt or "jewelry" in prompt
    assert "competition" in prompt


def test_openai_curator_parses_json_decisions():
    curator = make_curator(
        [
            {
                "candidate_index": 0,
                "keep": True,
                "reason": "Relevant Dubai jewellery signal.",
                "event_key": "Dubai gold jewellery demand rises",
                "topic": "product",
                "impact_tags": ["consumer_demand", "pricing"],
                "strategic_vertical": "gold_jewellery",
                "relevance_score": 0.88,
            }
        ]
    )

    decisions = curator.curate(
        prompt="You are the Middle East collector mini-agent.",
        candidates=[
            SearchCandidate(
                title="Dubai gold jewellery demand rises",
                url="https://example.com/dubai-gold",
                snippet="Dubai retailers report stronger gold demand.",
                source_name="Example",
            )
        ],
        request=CollectionRequest(
            topic="product",
            strategic_vertical="gold_jewellery",
            query_focus="Ramadan demand",
        ),
    )

    assert decisions[0].keep is True
    assert decisions[0].event_key == "Dubai gold jewellery demand rises"
    assert decisions[0].topic == "product"
    assert decisions[0].impact_tags == ["consumer_demand", "pricing"]
    assert decisions[0].strategic_vertical == "gold_jewellery"
    assert decisions[0].relevance_score == 0.88


def test_openai_curator_maps_unknown_topic_and_vertical_to_other():
    curator = make_curator(
        [
            {
                "candidate_index": 0,
                "keep": True,
                "reason": "Relevant but categories are invalid.",
                "event_key": "Dubai jewellery signal",
                "topic": "fashion",
                "strategic_vertical": "beauty",
                "relevance_score": 0.8,
            }
        ]
    )

    decisions = curator.curate(
        prompt="You are the Middle East collector mini-agent.",
        candidates=[
            SearchCandidate(
                title="Dubai gold jewellery demand rises",
                url="https://example.com/dubai-gold",
                snippet="Dubai retailers report stronger gold demand.",
                source_name="Example",
            )
        ],
        request=CollectionRequest(
            topic="product",
            strategic_vertical="gold_jewellery",
            query_focus="Ramadan demand",
        ),
    )

    assert decisions[0].keep is True
    assert decisions[0].topic == "other"
    assert decisions[0].strategic_vertical == "other"


def test_openai_curator_filters_unknown_impact_tags():
    curator = make_curator(
        [
            {
                "candidate_index": 0,
                "keep": True,
                "reason": "Regulatory policy may change landed cost.",
                "event_key": "UAE gold import duty update",
                "topic": "regulation",
                "impact_tags": ["compliance", "supply_chain", "unknown_tag"],
                "strategic_vertical": "gold_jewellery",
                "relevance_score": 0.8,
            }
        ]
    )

    decisions = curator.curate(
        prompt="You are the Middle East collector mini-agent.",
        candidates=[
            SearchCandidate(
                title="UAE gold import duty update",
                url="https://example.com/uae-duty",
                snippet="The policy may affect jewellery import costs.",
                source_name="Example",
            )
        ],
        request=CollectionRequest(
            topic="regulation",
            strategic_vertical="gold_jewellery",
            query_focus="import duty supply chain",
        ),
    )

    assert decisions[0].impact_tags == ["compliance", "supply_chain"]


def test_load_tavily_config():
    config = load_tavily_config("D:/ai_hackthon/AIRS/.config.yaml")
    assert "api_key" in config
    assert config["api_key"].startswith("tvly-")


def test_tavily_search_provider_parse_days():
    assert TavilySearchProvider._parse_days("7d") == 7
    assert TavilySearchProvider._parse_days("14d") == 14
    assert TavilySearchProvider._parse_days("30d") == 30
    assert TavilySearchProvider._parse_days("unknown") == 7


def test_supabase_writer_write_documents():
    """SupabaseWriter.write_documents posts to /rest/v1/documents."""
    posted_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "/rest/v1/documents" in str(request.url)
        body = json.loads(request.content.decode("utf-8"))
        posted_payloads.append(body)
        return httpx.Response(201, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    writer = SupabaseWriter(
        url="https://example.supabase.co",
        service_role_key="test-key",
        http_client=client,
    )

    docs = [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "doc_type": "raw_source",
            "title": "Test source",
            "content": "Test content",
            "source_url": "https://example.com",
            "created_by_agent": "test",
            "metadata": {"region": "middle_east"},
        },
    ]
    result = writer.write_documents(docs)
    assert len(posted_payloads) == 1
    assert posted_payloads[0][0]["doc_type"] == "raw_source"


def test_supabase_writer_write_agent_run():
    """SupabaseWriter.write_agent_run posts to /rest/v1/agent_runs."""
    posted_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        posted_payloads.append(body)
        return httpx.Response(201, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    writer = SupabaseWriter(
        url="https://example.supabase.co",
        service_role_key="test-key",
        http_client=client,
    )

    result = writer.write_agent_run(
        agent_name="middle_east_collector",
        tool_name="tavily_search",
        input_payload={"topic": "competition"},
        output_payload={"raw_source_count": 5},
        status="completed",
    )
    assert len(posted_payloads) == 1
    assert posted_payloads[0]["agent_name"] == "middle_east_collector"
    assert posted_payloads[0]["status"] == "completed"


def test_supabase_writer_strips_none_values():
    """SupabaseWriter.write_documents strips None values from docs."""
    posted_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        posted_payloads.append(body)
        return httpx.Response(201, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    writer = SupabaseWriter(
        url="https://example.supabase.co",
        service_role_key="test-key",
        http_client=client,
    )

    docs = [
        {
            "id": "00000000-0000-0000-0000-000000000002",
            "doc_type": "intel_card",
            "title": "Test card",
            "content": "Test content",
            "source_url": None,
            "created_by_agent": "test",
            "metadata": {"region": "middle_east"},
        },
    ]
    writer.write_documents(docs)
    assert "source_url" not in posted_payloads[0][0]


def test_collector_with_supabase_writer_persists():
    """MiddleEastCollector with SupabaseWriter writes docs and agent_run."""
    posted_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        posted_urls.append(str(request.url))
        body = json.loads(request.content.decode("utf-8"))
        return httpx.Response(201, json=body if isinstance(body, list) else [body])

    http_client = httpx.Client(transport=httpx.MockTransport(handler))

    curator = make_curator(
        [
            {
                "candidate_index": 0,
                "keep": True,
                "reason": "Relevant.",
                "event_key": "Dubai gold demand",
                "topic": "product",
                "strategic_vertical": "gold_jewellery",
                "relevance_score": 0.85,
            },
        ]
    )
    writer = SupabaseWriter(
        url="https://example.supabase.co",
        service_role_key="test-key",
        http_client=http_client,
    )
    collector = MiddleEastCollector(
        search_provider=StaticSearchProvider(
            [
                SearchCandidate(
                    title="Dubai gold demand rises",
                    url="https://example.com/dubai-gold",
                    snippet="Gold demand in Dubai is rising.",
                    source_name="Test",
                ),
            ]
        ),
        curator=curator,
        supabase_writer=writer,
    )

    result = collector.collect(
        CollectionRequest(
            topic="product",
            strategic_vertical="gold_jewellery",
            query_focus="gold demand",
        )
    )

    assert result["persisted"] is True
    assert any("/rest/v1/documents" in url for url in posted_urls)
    assert any("/rest/v1/agent_runs" in url for url in posted_urls)


def test_collector_without_supabase_writer_skips_persist():
    """MiddleEastCollector without SupabaseWriter does not attempt DB writes."""
    curator = make_curator(
        [
            {
                "candidate_index": 0,
                "keep": True,
                "reason": "Relevant.",
                "event_key": "Dubai gold demand",
                "topic": "product",
                "strategic_vertical": "gold_jewellery",
                "relevance_score": 0.85,
            },
        ]
    )
    collector = MiddleEastCollector(
        search_provider=StaticSearchProvider(
            [
                SearchCandidate(
                    title="Dubai gold demand rises",
                    url="https://example.com/dubai-gold",
                    snippet="Gold demand in Dubai is rising.",
                    source_name="Test",
                ),
            ]
        ),
        curator=curator,
    )

    result = collector.collect(
        CollectionRequest(
            topic="product",
            strategic_vertical="gold_jewellery",
            query_focus="gold demand",
        )
    )

    assert result["persisted"] is False


def test_load_supabase_config():
    config = load_supabase_config("D:/ai_hackthon/AIRS/.config.yaml")
    assert "url" in config
    assert "service_role_key" in config
    assert config["url"].startswith("https://")
