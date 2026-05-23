import json

import httpx

from airs.mini_agents.base_collector import OpenAILLMCurator, SearchCandidate
from airs.social_media_agent import SocialMediaAgent


class StubXProvider:
    def __init__(self, candidates):
        self.candidates = candidates
        self.calls = []

    def search(self, query, source_type, time_window):
        self.calls.append((query, source_type, time_window))
        return self.candidates


class StubWriter:
    def __init__(self):
        self.documents = []

    def write_documents(self, documents):
        self.documents.extend(documents)
        return documents


def make_curator(payload):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        prompt = body["messages"][1]["content"]
        assert "social_signal_cards" in prompt
        assert "signal_type" in prompt
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(payload),
                        }
                    }
                ]
            },
        )

    return OpenAILLMCurator(
        api_key="test-key",
        model="test-model",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_social_media_agent_creates_social_signal_cards_from_llm():
    candidate = SearchCandidate(
        title="Dubai shoppers discuss 22k gold jewellery for weddings",
        url="https://x.com/gold/status/1",
        snippet="People compare Dubai 22k gold prices before wedding season.",
        source_name="X/@gold",
        published_at="2026-05-20T00:00:00Z",
    )
    curator = make_curator(
        {
            "summary": "Gold wedding demand is visible in Dubai social chatter.",
            "social_signal_cards": [
                {
                    "signal_name": "Dubai wedding gold purchase intent",
                    "signal_type": "purchase_intent",
                    "sentiment": "mixed",
                    "demand_stage": "consideration",
                    "summary": "Users discuss whether 22k gold is still worth buying.",
                    "post_count": 1,
                    "key_quotes": ["People compare Dubai 22k gold prices"],
                    "business_implication": "Transparent price messaging may matter.",
                    "regions": ["Dubai"],
                    "verticals": ["gold_jewellery"],
                    "platforms": ["x"],
                    "evidence_urls": ["https://x.com/gold/status/1"],
                }
            ],
            "trending_hashtags": ["#gold"],
            "total_posts_analysed": 1,
        }
    )
    agent = SocialMediaAgent(
        x_provider=StubXProvider([candidate]),
        curator=curator,
        supabase_writer=None,
    )

    report = agent.analyse(
        focus="gold jewellery",
        regions=["Dubai"],
        time_window="7d",
    )

    assert report.total_posts_analysed == 1
    assert len(report.social_signal_cards) == 1
    card = report.social_signal_cards[0]
    assert card["signal_type"] == "purchase_intent"
    assert card["sentiment"] == "mixed"
    assert card["demand_stage"] == "consideration"
    assert card["platforms"] == ["x"]


def test_social_media_agent_persists_social_signal_cards():
    candidate = SearchCandidate(
        title="Singapore shoppers ask about diamond rings",
        url="https://x.com/diamond/status/2",
        snippet="Need advice on engagement rings in Singapore.",
        source_name="X/@diamond",
    )
    writer = StubWriter()
    agent = SocialMediaAgent(
        x_provider=StubXProvider([candidate]),
        curator=None,
        supabase_writer=writer,
    )

    report = agent.analyse(
        focus="diamond jewellery",
        regions=["Singapore"],
        time_window="7d",
    )

    assert report.persisted is True
    signal_docs = [doc for doc in writer.documents if doc["doc_type"] == "social_signal_card"]
    assert signal_docs
    signal_doc = signal_docs[0]
    assert signal_doc["metadata"]["type"] == "social_signal_card"
    assert signal_doc["metadata"]["signal_type"]
    assert signal_doc["metadata"]["platforms"] == ["x"]
    assert signal_doc["metadata"]["evidence_urls"]
