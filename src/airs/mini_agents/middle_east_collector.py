from __future__ import annotations

import re
import json
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4


REGION = "middle_east"
REGION_LABEL = "Middle East"
COUNTRY_TERMS = "UAE Saudi Arabia Qatar Kuwait"
CITY_TERMS = "Dubai Abu Dhabi Riyadh Doha"
SEASONAL_TERMS = "Ramadan Eid wedding demand tourism retail"

REGION_RELEVANCE_TERMS = {
    "middle east",
    "uae",
    "dubai",
    "abu dhabi",
    "saudi",
    "saudi arabia",
    "riyadh",
    "qatar",
    "doha",
    "kuwait",
    "gulf",
    "gcc",
    "mena",
    "ramadan",
    "eid",
}

JEWELLERY_RELEVANCE_TERMS = {
    "jewellery",
    "jewelry",
    "jeweller",
    "jeweler",
    "gold",
    "diamond",
    "gem",
    "gems",
    "jade",
    "watch",
    "watches",
    "luxury retail",
}

VERTICAL_LABELS = {
    "gold_jewellery": "gold jewellery",
    "jade_colored_gems_cultural_jewellery": "jade colored gems cultural jewellery",
    "overseas_retail_channels": "jewellery retail",
}

TOPIC_LABELS = {
    "competition": "competitor moves",
    "product": "product trends",
    "platform": "platform channels",
    "social": "social media trends",
    "regulation": "regulation",
    "macro_gold": "gold price macro dynamics",
    "other": "other",
}

TOPIC_QUERY_HINTS = {
    "competition": ["flagship store", "retail expansion", "brand launch"],
    "product": ["new collection", "jewellery design", "consumer demand"],
    "platform": ["mall retail", "ecommerce", "travel retail"],
    "social": ["social media", "TikTok trend", "Instagram jewellery"],
    "regulation": ["import duty", "consumer regulation", "retail policy"],
    "macro_gold": ["gold price", "gold demand", "currency volatility"],
    "other": ["industry news", "market update"],
}

ALLOWED_TOPICS = set(TOPIC_LABELS)
ALLOWED_STRATEGIC_VERTICALS = set(VERTICAL_LABELS) | {"other"}

TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
TRACKING_PREFIXES = ("utm_",)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CollectionRequest:
    topic: str
    strategic_vertical: str
    query_focus: str
    time_window: str = "7d"
    source_types: list[str] = field(default_factory=lambda: ["news"])


@dataclass(frozen=True)
class SearchCandidate:
    title: str
    url: str
    snippet: str
    source_name: str
    published_at: str | None = None


@dataclass(frozen=True)
class CuratedCandidate:
    candidate_index: int
    keep: bool
    reason: str
    event_key: str | None = None
    relevance_score: float = 0.0
    topic: str | None = None
    strategic_vertical: str | None = None


class LLMCurator(Protocol):
    """Protocol for the LLM step that decides what search results become intel cards."""

    def curate(
        self,
        prompt: str,
        candidates: list[SearchCandidate],
        request: CollectionRequest,
    ) -> list[CuratedCandidate]: ...


class OpenAILLMCurator:
    """OpenAI-compatible chat completions curator.

    The model decides which Tavily search results are relevant, which results
    describe the same event, and why each candidate is kept or discarded.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        http_client: Any | None = None,
    ) -> None:
        import httpx

        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.Client(timeout=120)

    @classmethod
    def from_config(cls, config_path: str | Path = ".config.yaml") -> OpenAILLMCurator:
        config = load_llm_config(config_path)
        if not config.get("api_key") or not config.get("model"):
            raise RuntimeError(
                "Missing LLM config. Add llm.api_key and llm.model to .config.yaml."
            )
        return cls(
            api_key=config["api_key"],
            model=config["model"],
            base_url=config.get("base_url") or "https://api.openai.com/v1",
        )

    def curate(
        self,
        prompt: str,
        candidates: list[SearchCandidate],
        request: CollectionRequest,
    ) -> list[CuratedCandidate]:
        if not candidates:
            return []

        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 32768,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": self.build_user_message(candidates, request)},
            ],
        }
        try:
            response = self.http_client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except Exception as exc:
            print(f"[OpenAILLMCurator] request failed: {exc}")
            return self._fallback_rule_decisions(candidates)

        if response.status_code >= 400:
            print(f"[OpenAILLMCurator] API error {response.status_code}: {response.text[:500]}")
            return self._fallback_rule_decisions(candidates)

        try:
            resp_json = response.json()
            content = resp_json["choices"][0]["message"]["content"]
            data = json.loads(content)
            return self.parse_decisions(data, candidates)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            print(f"[OpenAILLMCurator] parse error: {exc}")
            print(f"[OpenAILLMCurator] raw response: {response.text[:500]}")
            return self._fallback_rule_decisions(candidates)

    def _fallback_rule_decisions(
        self, candidates: list[SearchCandidate]
    ) -> list[CuratedCandidate]:
        """Fallback when LLM is unavailable: keep all candidates."""
        return [
            CuratedCandidate(
                candidate_index=i,
                keep=True,
                reason="rule-based fallback: LLM unavailable",
                event_key=None,
                relevance_score=0.5,
                topic=None,
                strategic_vertical=None,
            )
            for i in range(len(candidates))
        ]

    def build_user_message(
        self,
        candidates: list[SearchCandidate],
        request: CollectionRequest,
    ) -> str:
        candidate_payload = [
            {
                "candidate_index": index,
                "title": candidate.title,
                "url": candidate.url,
                "snippet": candidate.snippet,
                "source_name": candidate.source_name,
                "published_at": candidate.published_at,
            }
            for index, candidate in enumerate(candidates)
        ]
        instruction = {
            "task": (
                "Curate Tavily search results for AIRS intelligence collection. "
                "You MUST return a decision for EVERY candidate, even if you discard it. "
                "Do not skip any candidate_index."
            ),
            "topic": request.topic,
            "strategic_vertical": request.strategic_vertical,
            "query_focus": request.query_focus,
            "output_schema": {
                "decisions": [
                    {
                        "candidate_index": 0,
                        "keep": True,
                        "reason": "short evidence-based reason",
                        "event_key": "concise human-readable event summary or null",
                        "topic": "competition|product|platform|social|regulation|macro_gold|other",
                        "strategic_vertical": (
                            "gold_jewellery|jade_colored_gems_cultural_jewellery|"
                            "overseas_retail_channels|other"
                        ),
                        "relevance_score": 0.0,
                    }
                ]
            },
            "candidates": candidate_payload,
        }
        return json.dumps(instruction, ensure_ascii=False)

    def parse_decisions(
        self,
        data: dict[str, Any],
        candidates: list[SearchCandidate],
    ) -> list[CuratedCandidate]:
        decisions: list[CuratedCandidate] = []
        for item in data.get("decisions", []):
            index = int(item.get("candidate_index", -1))
            if not 0 <= index < len(candidates):
                continue
            keep = bool(item.get("keep", False))
            relevance_score = float(item.get("relevance_score", 0.0))
            topic = item.get("topic")
            strategic_vertical = item.get("strategic_vertical")
            # Map unknown topic/vertical to "other" instead of discarding
            if topic not in ALLOWED_TOPICS:
                topic = "other"
            if strategic_vertical not in ALLOWED_STRATEGIC_VERTICALS:
                strategic_vertical = "other"
            reason = str(item.get("reason", ""))
            decisions.append(
                CuratedCandidate(
                    candidate_index=index,
                    keep=keep,
                    reason=reason,
                    event_key=item.get("event_key"),
                    relevance_score=max(0.0, min(1.0, relevance_score)),
                    topic=topic,
                    strategic_vertical=strategic_vertical,
                )
            )
        seen_indexes = {decision.candidate_index for decision in decisions}
        for index in range(len(candidates)):
            if index not in seen_indexes:
                decisions.append(
                    CuratedCandidate(
                        candidate_index=index,
                        keep=False,
                        reason="LLM did not return a decision for this candidate.",
                        event_key=None,
                        relevance_score=0.0,
                    )
                )
        return decisions


# ---------------------------------------------------------------------------
# Search provider protocol and implementations
# ---------------------------------------------------------------------------

class SearchProvider(Protocol):
    """Protocol for pluggable search backends."""

    def search(self, query: str, source_type: str, time_window: str) -> list[SearchCandidate]: ...


class StaticSearchProvider:
    """Returns pre-set candidates. Useful for testing."""

    def __init__(self, candidates: list[SearchCandidate]) -> None:
        self.candidates = candidates
        self.queries: list[str] = []

    def search(self, query: str, source_type: str, time_window: str) -> list[SearchCandidate]:
        self.queries.append(query)
        return self.candidates


class TavilySearchProvider:
    """Searches the web via the Tavily API."""

    def __init__(self, api_key: str, max_results: int = 5) -> None:
        from tavily import TavilyClient

        self.client = TavilyClient(api_key=api_key)
        self.max_results = max_results

    def search(self, query: str, source_type: str, time_window: str) -> list[SearchCandidate]:
        days = self._parse_days(time_window)
        topic = "news" if source_type in ("news", "official", "macro") else "general"
        try:
            response = self.client.search(
                query=query,
                search_depth="basic",
                topic=topic,
                max_results=self.max_results,
                days=days,
            )
        except Exception as exc:
            print(f"[TavilySearchProvider] search failed for query={query!r}: {exc}")
            return []

        candidates: list[SearchCandidate] = []
        for result in response.get("results", []):
            candidates.append(
                SearchCandidate(
                    title=result.get("title", ""),
                    url=result.get("url", ""),
                    snippet=result.get("content", ""),
                    source_name=result.get("source", "tavily"),
                    published_at=result.get("published_date"),
                )
            )
        return candidates

    @staticmethod
    def _parse_days(time_window: str) -> int:
        """Convert a time window like '7d' or '14d' to an integer day count."""
        match = re.match(r"(\d+)d", time_window)
        if match:
            return int(match.group(1))
        return 7


# ---------------------------------------------------------------------------
# Supabase writer
# ---------------------------------------------------------------------------

class SupabaseWriter:
    """Writes documents and agent_runs to Supabase via REST API."""

    def __init__(
        self,
        url: str,
        service_role_key: str,
        http_client: Any | None = None,
    ) -> None:
        import httpx

        self.url = url.rstrip("/")
        self.service_role_key = service_role_key
        self.http_client = http_client or httpx.Client(timeout=30)

    @classmethod
    def from_config(cls, config_path: str | Path = ".config.yaml") -> SupabaseWriter:
        config = load_supabase_config(config_path)
        if not config.get("url") or not config.get("service_role_key"):
            raise RuntimeError(
                "Missing Supabase config. Add supabase.url and "
                "supabase.service_role_key to .config.yaml."
            )
        return cls(url=config["url"], service_role_key=config["service_role_key"])

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def write_documents(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Insert documents into Supabase documents table. Returns inserted rows."""
        if not docs:
            return []
        # Strip None values — Supabase rejects null for NOT NULL columns.
        cleaned: list[dict[str, Any]] = []
        for doc in docs:
            row = {k: v for k, v in doc.items() if v is not None}
            cleaned.append(row)
        response = self.http_client.post(
            f"{self.url}/rest/v1/documents",
            headers=self._headers(),
            json=cleaned,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Supabase write_documents failed: "
                f"{response.status_code} {response.text[:500]}"
            )
        return response.json()

    def write_agent_run(
        self,
        agent_name: str,
        tool_name: str,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
        status: str,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """Insert an agent_runs record. Returns inserted row."""
        payload: dict[str, Any] = {
            "agent_name": agent_name,
            "tool_name": tool_name,
            "input_payload": input_payload,
            "output_payload": output_payload,
            "status": status,
        }
        if error_message:
            payload["error_message"] = error_message
        response = self.http_client.post(
            f"{self.url}/rest/v1/agent_runs",
            headers=self._headers(),
            json=payload,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Supabase write_agent_run failed: "
                f"{response.status_code} {response.text[:500]}"
            )
        return response.json()


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_tavily_config(config_path: str | Path = ".config.yaml") -> dict[str, Any]:
    """Load Tavily config from .config.yaml.

    Supports two shapes:

        tavily:
          api_key: "tvly-..."
          mcp_url: "https://mcp.tavily.com/mcp?..."

    or flat:

        tavily_api_key: "tvly-..."
    """
    result = parse_simple_yaml(config_path)

    # Flatten nested tavily section
    tavily = result.get("tavily", {})
    if isinstance(tavily, dict):
        return {
            "api_key": tavily.get("api_key", result.get("tavily_api_key", "")),
            "mcp_url": tavily.get("mcp_url", ""),
        }
    return {"api_key": result.get("tavily_api_key", ""), "mcp_url": ""}


def load_llm_config(config_path: str | Path = ".config.yaml") -> dict[str, str]:
    """Load OpenAI-compatible LLM config from .config.yaml.

    Supported shapes:

        llm:
          api_key: "sk-..."
          base_url: "https://api.openai.com/v1"
          model: "gpt-4.1-mini"

    or:

        openai:
          api_key: "sk-..."
          base_url: "https://api.openai.com/v1"
          model: "gpt-4.1-mini"

    or:

        opencode-go:
          api_key: "sk-..."
          base_url: "https://..."
          model: "provider/model-name"
    """
    config = parse_simple_yaml(config_path)
    llm = config.get("llm", {})
    openai = config.get("openai", {})
    opencode_go = config.get("opencode-go", {})
    if not isinstance(llm, dict):
        llm = {}
    if not isinstance(openai, dict):
        openai = {}
    if not isinstance(opencode_go, dict):
        opencode_go = {}
    return {
        "api_key": str(
            llm.get("api_key")
            or openai.get("api_key")
            or opencode_go.get("api_key")
            or config.get("llm_api_key")
            or config.get("openai_api_key")
            or ""
        ),
        "base_url": str(
            llm.get("base_url")
            or openai.get("base_url")
            or opencode_go.get("base_url")
            or config.get("llm_base_url")
            or config.get("openai_base_url")
            or "https://api.openai.com/v1"
        ),
        "model": str(
            llm.get("model")
            or openai.get("model")
            or opencode_go.get("model")
            or config.get("llm_model")
            or config.get("openai_model")
            or "deepseekV4-Flash"
        ),
    }


def load_supabase_config(config_path: str | Path = ".config.yaml") -> dict[str, str]:
    """Load Supabase config from .config.yaml.

    Supported shapes:

        supabase:
          url: "https://xxx.supabase.co"
          service_role_key: "ey..."

    or flat:

        supabase_url: "https://xxx.supabase.co"
        supabase_service_role_key: "ey..."
    """
    config = parse_simple_yaml(config_path)
    supabase = config.get("supabase", {})
    if not isinstance(supabase, dict):
        supabase = {}
    return {
        "url": str(
            config.get("supabase_url")
            or supabase.get("url")
            or ""
        ).rstrip("/"),
        "service_role_key": str(
            config.get("supabase_service_role_key")
            or supabase.get("service_role_key")
            or ""
        ),
    }


def parse_simple_yaml(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists() or path.stat().st_size == 0:
        return {}

    result: dict[str, Any] = {}
    current_section: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if not value:
            current_section = key
            result.setdefault(current_section, {})
            continue

        if raw_line.startswith((" ", "\t")) and current_section:
            section = result.setdefault(current_section, {})
            if isinstance(section, dict):
                section[key] = value
        else:
            current_section = None
            result[key] = value

    return result


# ---------------------------------------------------------------------------
# Middle East Collector
# ---------------------------------------------------------------------------

class MiddleEastCollector:
    """Lightweight regional collector mini-agent for the Middle East."""

    def __init__(
        self,
        search_provider: SearchProvider | None = None,
        curator: LLMCurator | None = None,
        supabase_writer: SupabaseWriter | None = None,
    ) -> None:
        self.search_provider = search_provider
        self.curator = curator
        self.supabase_writer = supabase_writer

    def collect(self, request: CollectionRequest) -> dict[str, Any]:
        queries = self.build_queries(request)

        # Gather candidates from search provider
        all_candidates: list[SearchCandidate] = []
        if self.search_provider is not None:
            for query in queries:
                all_candidates.extend(
                    self.search_provider.search(
                        query=query,
                        source_type=request.source_types[0] if request.source_types else "news",
                        time_window=request.time_window,
                    )
                )

        unique_candidates = self.deduplicate_candidates_by_url(all_candidates)

        if self.curator is not None:
            prompt = self.build_agent_prompt(request)
            curation = self.curator.curate(prompt=prompt, candidates=unique_candidates, request=request)
            clusters = self.cluster_candidates_by_llm_group(unique_candidates, curation)
            discarded_candidates = self.build_discarded_candidates(unique_candidates, curation)
        else:
            # Fallback: rule-based clustering with keyword relevance filter
            relevant_candidates = [
                c for c in unique_candidates if self.is_relevant_candidate(c)
            ]
            irrelevant_candidates = [
                c for c in unique_candidates if not self.is_relevant_candidate(c)
            ]
            rule_clusters = self.cluster_candidates(relevant_candidates)
            clusters = {}
            for cluster in rule_clusters:
                event_key = self.readable_event_key(cluster[0])
                pairs = [
                    (
                        candidate,
                        CuratedCandidate(
                            candidate_index=i,
                            keep=True,
                            reason="rule-based: passed keyword relevance filter",
                            event_key=event_key,
                            relevance_score=0.5,
                            topic=None,
                            strategic_vertical=None,
                        ),
                    )
                    for i, candidate in enumerate(cluster)
                ]
                clusters[event_key] = pairs
            discarded_candidates = [
                {
                    "candidate_index": i,
                    "title": c.title,
                    "url": c.url,
                    "reason": "rule-based: failed keyword relevance filter",
                }
                for i, c in enumerate(irrelevant_candidates)
            ]

        raw_sources: list[dict[str, Any]] = []
        intel_cards: list[dict[str, Any]] = []

        for event_key, cluster in clusters.items():
            cluster_source_ids: list[str] = []
            for candidate, decision in cluster:
                source_id = self.new_doc_id()
                cluster_source_ids.append(source_id)
                topic = decision.topic or request.topic
                strategic_vertical = decision.strategic_vertical or request.strategic_vertical
                raw_sources.append(
                    {
                        "id": source_id,
                        "doc_type": "raw_source",
                        "title": candidate.title,
                        "content": candidate.snippet or candidate.title,
                        "source_url": candidate.url,
                        "created_by_agent": "middle_east_collector",
                        "metadata": {
                            "region": REGION,
                            "topic": topic,
                            "strategic_vertical": strategic_vertical,
                            "event_key": event_key,
                            "topic_source": "llm_selected" if decision.topic else "request_fallback",
                            "vertical_source": (
                                "llm_selected"
                                if decision.strategic_vertical
                                else "request_fallback"
                            ),
                            "source_name": candidate.source_name,
                            "published_at": candidate.published_at,
                            "evidence_quality": "snippet_only",
                            "llm_keep_reason": decision.reason,
                            "llm_relevance_score": decision.relevance_score,
                        },
                    }
                )

            primary = cluster[0][0]
            primary_decision = cluster[0][1]
            topic = primary_decision.topic or request.topic
            strategic_vertical = primary_decision.strategic_vertical or request.strategic_vertical
            intel_cards.append(
                {
                    "id": self.new_doc_id(),
                    "doc_type": "intel_card",
                    "title": primary.title,
                    "content": primary.snippet or primary.title,
                    "source_url": primary.url,
                    "created_by_agent": "middle_east_collector",
                    "metadata": {
                        "region": REGION,
                        "topic": topic,
                        "strategic_vertical": strategic_vertical,
                        "event_key": event_key,
                        "topic_source": (
                            "llm_selected" if primary_decision.topic else "request_fallback"
                        ),
                        "vertical_source": (
                            "llm_selected"
                            if primary_decision.strategic_vertical
                            else "request_fallback"
                        ),
                        "canonical_event_key": self.canonical_event_key(primary),
                        "primary_source_id": cluster_source_ids[0],
                        "supporting_source_ids": cluster_source_ids[1:],
                        "source_count": len(cluster_source_ids),
                        "importance_score": max(decision.relevance_score for _, decision in cluster),
                        "confidence_score": min(0.9, 0.45 + 0.15 * len(cluster_source_ids)),
                        "dedup_method": "llm_event_key",
                    },
                }
            )

        # Persist to Supabase if writer is configured
        persisted = False
        if self.supabase_writer is not None:
            all_docs = raw_sources + intel_cards
            try:
                self.supabase_writer.write_documents(all_docs)
                persisted = True
            except Exception as exc:
                print(f"[MiddleEastCollector] Supabase write_documents failed: {exc}")

            run_status = "completed" if persisted else "partial"
            error_msg = None if persisted else "Supabase write_documents failed"
            try:
                self.supabase_writer.write_agent_run(
                    agent_name="middle_east_collector",
                    tool_name="tavily_search",
                    input_payload={
                        "topic": request.topic,
                        "strategic_vertical": request.strategic_vertical,
                        "query_focus": request.query_focus,
                        "time_window": request.time_window,
                        "generated_queries": queries,
                    },
                    output_payload={
                        "raw_source_count": len(raw_sources),
                        "intel_card_count": len(intel_cards),
                        "discarded_count": len(discarded_candidates),
                    },
                    status=run_status,
                    error_message=error_msg,
                )
            except Exception as exc:
                print(f"[MiddleEastCollector] Supabase write_agent_run failed: {exc}")

        return {
            "region": REGION,
            "generated_queries": queries,
            "raw_sources": raw_sources,
            "intel_cards": intel_cards,
            "discarded_candidates": discarded_candidates,
            "persisted": persisted,
            "coverage": {
                "regions": [REGION],
                "source_types": request.source_types,
                "time_window": request.time_window,
            },
        }

    def build_agent_prompt(self, request: CollectionRequest) -> str:
        return (
            "You are the Middle East collector mini-agent for AIRS, an overseas strategic "
            "intelligence platform for Chow Tai Fook Jewellery Group.\n"
            "Tavily is your search tool, similar to a Google-like search engine.\n"
            f"Region: {REGION} ({REGION_LABEL}; {COUNTRY_TERMS}; {CITY_TERMS}).\n"
            f"Topic: {request.topic}.\n"
            f"Strategic vertical: {request.strategic_vertical}.\n"
            f"Search focus: {request.query_focus}.\n\n"
            "RELEVANCE CRITERIA — keep a candidate if it relates to ANY of:\n"
            "- Jewellery, gold, diamonds, gems, jade, watches — including global shows, "
            "trends, and brand news that affect the Middle East market\n"
            "- Luxury retail and premium brands expanding, opening stores, or partnering "
            "in the Middle East / Gulf / MENA region\n"
            "- Competitor moves: any brand opening flagship stores, expanding retail, "
            "launching new collections, or forming partnerships in the region\n"
            "- Product trends: design trends, consumer preferences, seasonal demand "
            "(Ramadan, Eid, wedding season)\n"
            "- Platform & channels: mall retail, ecommerce, travel retail, social media "
            "trends affecting jewellery or luxury retail\n"
            "- Regulation: import duties, consumer protection, retail policy changes\n"
            "- Macro & gold: gold price dynamics, currency volatility, economic outlook "
            "affecting jewellery demand\n"
            "- Hospitality & tourism developments that signal retail expansion "
            "(new luxury hotels, malls, mixed-use developments in the Gulf)\n"
            "- Key companies: Chow Tai Fook, Pandora, LVMH, Richemont, Swatch Group, "
            "Cartier, Tiffany, Bulgari, Signet, Malabar Gold, Damas, etc.\n\n"
            "DISCARD only candidates clearly unrelated to jewellery, luxury retail, "
            "or the Middle East business landscape — such as pure tech (smartphones, SaaS), "
            "aviation, logistics, or politics with no retail angle.\n\n"
            "Allowed topic values: competition, product, platform, social, regulation, macro_gold, other.\n"
            "Allowed strategic_vertical values: gold_jewellery, "
            "jade_colored_gems_cultural_jewellery, overseas_retail_channels, other.\n"
            "For each kept candidate, choose exactly one allowed topic and exactly one allowed "
            "strategic_vertical. Use 'other' when none of the predefined categories fit well. "
            "Use the requested topic/vertical only when it is still the best fit.\n"
            "For each kept candidate, write event_key as a concise human-readable event summary. "
            "Use the same event_key for duplicate reports about the same event. Keep event_key broad "
            "enough to identify the event, not a compressed keyword hash.\n"
            "Do not over-compress the evidence: preserve source-specific facts in raw sources and "
            "only merge items that clearly describe the same event.\n"
            "Do not make final opportunity/risk judgments or predictions."
        )

    def build_queries(self, request: CollectionRequest) -> list[str]:
        vertical = VERTICAL_LABELS.get(request.strategic_vertical, request.strategic_vertical)
        topic = TOPIC_LABELS.get(request.topic, request.topic)
        hints = TOPIC_QUERY_HINTS.get(request.topic, [topic])
        # Keep queries short and focused — avoid repeating query_focus in hints.
        return [
            f"{REGION_LABEL} {vertical} {request.query_focus}",
            f"Dubai UAE {vertical} {topic} {request.query_focus}",
            f"{REGION_LABEL} {vertical} {hints[-1]}",
        ]

    def cluster_candidates(self, candidates: list[SearchCandidate]) -> list[list[SearchCandidate]]:
        clusters: list[list[SearchCandidate]] = []
        seen_urls: set[str] = set()

        for candidate in candidates:
            normalized_url = self.normalize_url(candidate.url)
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)

            for cluster in clusters:
                if self.is_same_event(candidate, cluster[0]):
                    cluster.append(candidate)
                    break
            else:
                clusters.append([candidate])

        return clusters

    def deduplicate_candidates_by_url(
        self, candidates: list[SearchCandidate]
    ) -> list[SearchCandidate]:
        unique: list[SearchCandidate] = []
        seen_urls: set[str] = set()
        for candidate in candidates:
            normalized_url = self.normalize_url(candidate.url)
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            unique.append(candidate)
        return unique

    def cluster_candidates_by_llm_group(
        self,
        candidates: list[SearchCandidate],
        decisions: list[CuratedCandidate],
    ) -> dict[str, list[tuple[SearchCandidate, CuratedCandidate]]]:
        clusters: dict[str, list[tuple[SearchCandidate, CuratedCandidate]]] = {}
        seen_urls: set[str] = set()

        for decision in decisions:
            if not decision.keep:
                continue
            if not 0 <= decision.candidate_index < len(candidates):
                continue

            candidate = candidates[decision.candidate_index]
            normalized_url = self.normalize_url(candidate.url)
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)

            event_key = decision.event_key or self.readable_event_key(candidate)
            clusters.setdefault(event_key, []).append((candidate, decision))

        return clusters

    def build_discarded_candidates(
        self,
        candidates: list[SearchCandidate],
        decisions: list[CuratedCandidate],
    ) -> list[dict[str, Any]]:
        discarded: list[dict[str, Any]] = []
        for decision in decisions:
            if decision.keep:
                continue
            if not 0 <= decision.candidate_index < len(candidates):
                continue
            candidate = candidates[decision.candidate_index]
            discarded.append(
                {
                    "candidate_index": decision.candidate_index,
                    "title": candidate.title,
                    "url": candidate.url,
                    "reason": decision.reason,
                }
            )
        return discarded

    def is_relevant_candidate(self, candidate: SearchCandidate) -> bool:
        text = f"{candidate.title} {candidate.snippet}".lower()
        has_region_signal = any(term in text for term in REGION_RELEVANCE_TERMS)
        has_jewellery_signal = any(term in text for term in JEWELLERY_RELEVANCE_TERMS)
        return has_region_signal and has_jewellery_signal

    def is_same_event(self, left: SearchCandidate, right: SearchCandidate) -> bool:
        # Use title + short snippet prefix for matching, but weight title more.
        left_text = left.title.lower()
        right_text = right.title.lower()
        title_similarity = SequenceMatcher(None, left_text, right_text).ratio()
        # Also check full text for cases where titles differ but content overlaps.
        left_full = f"{left.title} {left.snippet[:120]}".lower()
        right_full = f"{right.title} {right.snippet[:120]}".lower()
        full_similarity = SequenceMatcher(None, left_full, right_full).ratio()
        shared_title_words = self.words(left_text) & self.words(right_text)
        long_shared = len([w for w in shared_title_words if len(w) > 4])
        # Merge if: titles are very similar, OR full text is similar enough, OR many long words overlap.
        return title_similarity >= 0.65 or full_similarity >= 0.55 or long_shared >= 4

    def normalize_url(self, url: str) -> str:
        parts = urlsplit(url.strip())
        query_pairs = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key in TRACKING_KEYS or any(key.startswith(prefix) for prefix in TRACKING_PREFIXES):
                continue
            query_pairs.append((key, value))
        return urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc.lower(),
                parts.path.rstrip("/") or parts.path,
                urlencode(query_pairs),
                "",
            )
        )

    def canonical_event_key(self, candidate: SearchCandidate) -> str:
        terms = [word for word in sorted(self.words(f"{candidate.title} {candidate.snippet}")) if len(word) > 3]
        return "|".join(terms[:8])

    def readable_event_key(self, candidate: SearchCandidate) -> str:
        text = candidate.title.strip() or candidate.snippet.strip()
        return re.sub(r"\s+", " ", text)[:120]

    def words(self, text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    def new_doc_id(self) -> str:
        return str(uuid4())
