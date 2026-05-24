import json

from airs.mini_agents.briefing_orchestrator import (
    BriefingOrchestrator,
    FeishuDeliveryResult,
)


class FakeResponse:
    def __init__(self, status_code=200, data=None, text=""):
        self.status_code = status_code
        self._data = data if data is not None else []
        self.text = text or json.dumps(self._data)

    def json(self):
        return self._data


class FakeHttpClient:
    def __init__(self, cards):
        self.cards = cards
        self.get_requests = []

    def get(self, url, headers=None, params=None):
        self.get_requests.append({"url": url, "headers": headers, "params": params})
        return FakeResponse(data=self.cards)


class FakeWriter:
    def __init__(self, cards):
        self.url = "https://example.supabase.co"
        self.http_client = FakeHttpClient(cards)
        self.written_docs = []
        self.updated_docs = []

    def _headers(self):
        return {"apikey": "test"}

    def write_documents(self, docs):
        written = []
        for index, doc in enumerate(docs):
            row = {**doc, "id": doc.get("id") or f"briefing-{index}"}
            self.written_docs.append(row)
            written.append(row)
        return written

    def update_document(self, document_id, patch):
        self.updated_docs.append({"id": document_id, "patch": patch})
        return [{"id": document_id, **patch}]


def make_market_card(card_id="card-1", dedup_key="event-1"):
    return {
        "id": card_id,
        "doc_type": "intel_card",
        "title": "Gold volatility tests jewellers",
        "content": "Chow Tai Fook discusses pricing and youth demand amid gold volatility.",
        "source_url": "https://example.com/gold",
        "created_by_agent": "middle_east_collector",
        "created_at": "2026-05-24T00:00:00Z",
        "metadata": {
            "region": "middle_east",
            "topic": "competition",
            "impact_tags": ["pricing", "gold_price"],
            "strategic_vertical": "gold_jewellery",
            "dedup_key": dedup_key,
            "published_at": "2026-05-23",
            "source_count": 2,
            "importance_score": 0.8,
            "confidence_score": 0.7,
            "briefing_status": "new",
            "briefing_ids": ["old-briefing"],
        },
    }


def make_social_card(card_id="social-1", dedup_key="social-event-1"):
    return {
        "id": card_id,
        "doc_type": "social_signal_card",
        "title": "[Social] Gold price sensitivity among buyers",
        "content": "Consumers discuss affordability and timing purchases around gold prices.",
        "source_url": "https://reddit.com/example",
        "created_by_agent": "social_media_agent",
        "created_at": "2026-05-24T00:00:00Z",
        "metadata": {
            "topic": "social",
            "impact_tags": ["pricing", "consumer_demand", "gold_price"],
            "signal_type": "pricing_value",
            "sentiment": "mixed",
            "platforms": ["reddit"],
            "regions": ["Global"],
            "verticals": ["gold_jewellery"],
            "dedup_key": dedup_key,
            "published_at": "2026-05-23",
            "briefing_status": "new",
            "briefing_ids": [],
        },
    }


def test_fetch_eligible_cards_reads_new_intel_and_social_cards():
    writer = FakeWriter([make_market_card(), make_social_card()])
    orchestrator = BriefingOrchestrator(writer)

    cards = orchestrator.fetch_eligible_cards(limit=10)

    assert len(cards) == 2
    params = writer.http_client.get_requests[0]["params"]
    assert params["doc_type"] == "in.(intel_card,social_signal_card)"
    assert params["metadata->>briefing_status"] == "eq.new"
    assert params["limit"] == "10"


def test_compose_briefing_dedupes_and_includes_social_signal_type():
    duplicate = make_market_card(card_id="card-duplicate", dedup_key="event-1")
    orchestrator = BriefingOrchestrator(FakeWriter([]))

    cards = orchestrator.dedupe_cards([make_market_card(), duplicate, make_social_card()])
    text = orchestrator.compose_briefing(cards, briefing_date="2026-05-24")

    assert len(cards) == 2
    assert "今日海外珠宝市场简报" in text
    assert "竞争动态" in text
    assert "社媒舆情" in text
    assert "signal_type: pricing_value" in text
    assert text.count("Gold volatility tests jewellers") == 1


def test_dry_run_does_not_send_or_mark_cards_briefed():
    writer = FakeWriter([make_market_card(), make_social_card()])
    sent_payloads = []
    orchestrator = BriefingOrchestrator(
        writer,
        feishu_sender=lambda text: sent_payloads.append(text),
    )

    result = orchestrator.run(dry_run=True)

    assert result["delivery_status"] == "dry_run"
    assert result["included_card_count"] == 2
    assert sent_payloads == []
    assert writer.written_docs == []
    assert writer.updated_docs == []


def test_successful_send_writes_briefing_and_marks_cards_briefed():
    writer = FakeWriter([make_market_card(), make_social_card()])
    orchestrator = BriefingOrchestrator(
        writer,
        feishu_sender=lambda text: FeishuDeliveryResult(
            success=True,
            status="sent",
            message_id="msg-123",
            stdout='{"message_id":"msg-123"}',
        ),
    )

    result = orchestrator.run(dry_run=False, briefing_date="2026-05-24")

    assert result["delivery_status"] == "sent"
    assert result["feishu_message_id"] == "msg-123"
    assert result["briefing_id"] == writer.written_docs[0]["id"]
    assert writer.written_docs[0]["doc_type"] == "briefing"
    assert writer.written_docs[0]["metadata"]["social_signal_card_count"] == 1
    assert len(writer.updated_docs) == 2
    patched = writer.updated_docs[0]["patch"]["metadata"]
    assert patched["briefing_status"] == "briefed"
    assert patched["delivery_status"] == "sent"
    assert patched["feishu_message_id"] == "msg-123"
    assert patched["briefing_ids"] == ["old-briefing", result["briefing_id"]]


def test_failed_send_does_not_mark_cards_briefed():
    writer = FakeWriter([make_market_card()])
    orchestrator = BriefingOrchestrator(
        writer,
        feishu_sender=lambda text: FeishuDeliveryResult(
            success=False,
            status="failed",
            error="network error",
        ),
    )

    result = orchestrator.run(dry_run=False)

    assert result["delivery_status"] == "failed"
    assert writer.written_docs == []
    assert writer.updated_docs == []
