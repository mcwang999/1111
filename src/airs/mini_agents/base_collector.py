"""Base collector with shared logic for all regional collectors.

Subclasses define region-specific constants and prompt text. The base class
provides the full collect() pipeline: search → dedup → LLM curation →
cluster → build raw_sources/intel_cards → persist to Supabase.
"""

from __future__ import annotations

import re
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

VERTICAL_LABELS = {
    "gold_jewellery": "gold jewellery",
    "jade_colored_gems_cultural_jewellery": "jade colored gems cultural jewellery",
    "overseas_retail_channels": "jewellery retail",
}

TOPIC_LABELS = {
    "competition": "competitor and market player moves",
    "product": "product, design, assortment, and consumer preference changes",
    "channel": "retail channels, stores, ecommerce, malls, travel retail, and platforms",
    "social": "social media, community, and consumer conversation signals",
    "regulation": "laws, policy, tax, compliance, labeling, and trade rules",
}

TOPIC_QUERY_HINTS = {
    "competition": ["flagship store", "retail expansion", "brand launch"],
    "product": ["new collection", "jewellery design", "consumer demand"],
    "channel": ["mall retail", "ecommerce", "travel retail"],
    "social": ["social media", "TikTok trend", "Instagram jewellery"],
    "regulation": ["import duty", "consumer regulation", "retail policy"],
}

IMPACT_TAG_LABELS = {
    "supply_chain": "raw materials, sourcing, manufacturing, logistics, inventory, or delivery",
    "compliance": "legal, tax, customs, certification, disclosure, or operating compliance",
    "cost": "procurement cost, landed cost, operating cost, or margin pressure",
    "pricing": "retail pricing, price transparency, discounting, or affordability",
    "inventory": "stock availability, replenishment, allocation, or inventory strategy",
    "logistics": "shipping, freight, ports, customs clearance, or transport delay",
    "sourcing": "supplier, origin, mining, refinery, ESG, or traceability exposure",
    "retail_operations": "store operations, channel execution, staff, service, or customer experience",
    "consumer_demand": "purchase intent, demand, traffic, conversion, or consumer preference",
    "brand_reputation": "brand trust, reputation, sentiment, PR, or competitor perception",
    "gold_price": "gold price, FX, rates, liquidity, or investor behavior",
}

ALLOWED_TOPICS = set(TOPIC_LABELS)
ALLOWED_IMPACT_TAGS = set(IMPACT_TAG_LABELS)
ALLOWED_STRATEGIC_VERTICALS = set(VERTICAL_LABELS) | {"other"}

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
    impact_tags: list[str] = field(default_factory=list)
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
    """OpenAI-compatible chat completions curator."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        http_client: Any | None = None,
        max_retries: int = 5,
    ) -> None:
        import httpx

        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.Client(timeout=180)
        self.max_retries = max_retries

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

        last_exc: Exception | None = None
        last_response_text: str | None = None

        for attempt in range(1, self.max_retries + 1):
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
                last_exc = exc
                print(f"[OpenAILLMCurator] request failed (attempt {attempt}/{self.max_retries}): {exc}")
                if attempt < self.max_retries:
                    delay = min(60, 10 * 2 ** (attempt - 1))  # 10, 20, 40, 60, 60s
                    print(f"[OpenAILLMCurator] retrying in {delay}s...")
                    time.sleep(delay)
                continue

            if response.status_code >= 400:
                last_response_text = response.text[:500]
                print(
                    f"[OpenAILLMCurator] API error {response.status_code} "
                    f"(attempt {attempt}/{self.max_retries}): {last_response_text}"
                )
                if attempt < self.max_retries:
                    delay = min(60, 10 * 2 ** (attempt - 1))
                    print(f"[OpenAILLMCurator] retrying in {delay}s...")
                    time.sleep(delay)
                continue

            # Successful response — attempt to parse
            try:
                resp_json = response.json()
                content = resp_json["choices"][0]["message"]["content"]
                # Strip markdown code block wrapping if present (```json ... ```)
                content = content.strip()
                if content.startswith("```"):
                    first_newline = content.index("\n") if "\n" in content else len(content)
                    content = content[first_newline + 1:]
                    if content.endswith("```"):
                        content = content[:-3].strip()
                data = json.loads(content)
                return self.parse_decisions(data, candidates)
            except (KeyError, IndexError, json.JSONDecodeError) as exc:
                print(f"[OpenAILLMCurator] parse error (attempt {attempt}/{self.max_retries}): {exc}")
                print(f"[OpenAILLMCurator] raw response: {response.text[:500]}")
                if attempt < self.max_retries:
                    delay = 2 ** attempt
                    print(f"[OpenAILLMCurator] retrying in {delay}s...")
                    time.sleep(delay)
                continue

        # All retries exhausted
        if last_exc is not None:
            print(f"[OpenAILLMCurator] all {self.max_retries} attempts failed — last error: {last_exc}")
        elif last_response_text is not None:
            print(f"[OpenAILLMCurator] all {self.max_retries} attempts failed — last API error: {last_response_text}")
        else:
            print(f"[OpenAILLMCurator] all {self.max_retries} attempts failed — parse error after all retries")
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
                impact_tags=self.infer_impact_tags(candidate),
                strategic_vertical=None,
            )
            for i, candidate in enumerate(candidates)
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
                        "topic": "competition|product|channel|social|regulation",
                        "impact_tags": [
                            "supply_chain",
                            "compliance",
                            "cost",
                            "pricing",
                            "inventory",
                            "logistics",
                            "sourcing",
                            "retail_operations",
                            "consumer_demand",
                            "brand_reputation",
                            "gold_price",
                        ],
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
            raw_impact_tags = item.get("impact_tags") or []
            if not isinstance(raw_impact_tags, list):
                raw_impact_tags = []
            impact_tags = [tag for tag in raw_impact_tags if tag in ALLOWED_IMPACT_TAGS]
            # Map unknown topic/vertical to "other" instead of discarding
            if topic not in ALLOWED_TOPICS:
                topic = "other"
            if strategic_vertical not in ALLOWED_STRATEGIC_VERTICALS:
                strategic_vertical = "other"
            if keep and not impact_tags:
                impact_tags = self.infer_impact_tags(candidates[index], topic=topic)
            reason = str(item.get("reason", ""))
            decisions.append(
                CuratedCandidate(
                    candidate_index=index,
                    keep=keep,
                    reason=reason,
                    event_key=item.get("event_key"),
                    relevance_score=max(0.0, min(1.0, relevance_score)),
                    topic=topic,
                    impact_tags=impact_tags,
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

    @staticmethod
    def infer_impact_tags(candidate: SearchCandidate, topic: str | None = None) -> list[str]:
        """Infer conservative business impact tags when LLM output is unavailable."""
        text = f"{candidate.title} {candidate.snippet}".lower()
        inferred: list[str] = []

        def add(tag: str) -> None:
            if tag in ALLOWED_IMPACT_TAGS and tag not in inferred:
                inferred.append(tag)

        if any(term in text for term in ("gold price", "gold prices", "bullion", "xau", "spot gold")):
            add("pricing")
            add("gold_price")
        if any(term in text for term in ("price", "pricing", "discount", "affordability", "margin")):
            add("pricing")
        if any(term in text for term in ("cost", "tariff", "duty", "tax", "inflation", "margin")):
            add("cost")
        if any(term in text for term in ("demand", "consumer", "shopper", "traffic", "conversion")):
            add("consumer_demand")
        if (
            re.search(r"\b(store|flagship|boutique|mall|ecommerce)\b", text)
            or "retail expansion" in text
            or "retail channel" in text
        ):
            add("retail_operations")
        if any(term in text for term in ("inventory", "stock", "replenishment", "allocation")):
            add("inventory")
        if any(term in text for term in ("shipping", "freight", "port", "customs", "delivery", "logistics")):
            add("logistics")
        if any(term in text for term in ("supplier", "sourcing", "origin", "mining", "refinery", "traceability")):
            add("sourcing")
        if any(term in text for term in ("supply chain", "manufacturing", "factory", "production")):
            add("supply_chain")
        if any(term in text for term in ("regulation", "policy", "compliance", "certification", "labeling")):
            add("compliance")
        if re.search(r"\b(brand|reputation|sentiment|trust|pr)\b", text):
            add("brand_reputation")

        if inferred:
            return inferred[:3]
        if topic == "regulation":
            return ["compliance"]
        if topic == "channel":
            return ["retail_operations"]
        if topic == "social":
            return ["consumer_demand"]
        if topic == "product":
            return ["consumer_demand"]
        if topic == "competition":
            return ["brand_reputation"]
        return []


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

    def write_documents_with_dedup(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Insert or update documents using metadata dedup keys when available."""
        written: list[dict[str, Any]] = []
        for doc in docs:
            existing = self.find_existing_document(doc)
            if existing is None:
                written.extend(self.write_documents([doc]))
                continue

            patch = self.merge_duplicate_document(existing, doc)
            updated = self.update_document(existing["id"], patch)
            written.extend(updated)
        return written

    def find_existing_document(self, doc: dict[str, Any]) -> dict[str, Any] | None:
        metadata = doc.get("metadata") or {}
        doc_type = doc.get("doc_type")
        key = None
        value = None
        if doc_type == "raw_source":
            key = "normalized_source_url"
            value = metadata.get(key)
        elif doc_type in {"intel_card", "social_signal_card"}:
            key = "dedup_key"
            value = metadata.get(key)

        if not key or not value:
            return None

        response = self.http_client.get(
            f"{self.url}/rest/v1/documents",
            headers=self._headers(),
            params={
                "select": "*",
                "doc_type": f"eq.{doc_type}",
                f"metadata->>{key}": f"eq.{value}",
                "limit": "1",
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Supabase find_existing_document failed: "
                f"{response.status_code} {response.text[:500]}"
            )
        rows = response.json()
        return rows[0] if rows else None

    def update_document(
        self,
        document_id: str,
        patch: dict[str, Any],
    ) -> list[dict[str, Any]]:
        cleaned = {k: v for k, v in patch.items() if v is not None}
        response = self.http_client.patch(
            f"{self.url}/rest/v1/documents",
            headers=self._headers(),
            params={"id": f"eq.{document_id}"},
            json=cleaned,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Supabase update_document failed: "
                f"{response.status_code} {response.text[:500]}"
            )
        return response.json()

    @classmethod
    def merge_duplicate_document(
        cls,
        existing: dict[str, Any],
        incoming: dict[str, Any],
    ) -> dict[str, Any]:
        existing_meta = existing.get("metadata") or {}
        incoming_meta = incoming.get("metadata") or {}
        metadata = {**existing_meta, **incoming_meta}

        if existing_meta.get("first_seen_at"):
            metadata["first_seen_at"] = existing_meta["first_seen_at"]
        metadata["last_seen_at"] = incoming_meta.get("last_seen_at") or cls.now_iso()
        metadata["briefing_status"] = existing_meta.get(
            "briefing_status",
            incoming_meta.get("briefing_status", "new"),
        )
        metadata["briefed_at"] = existing_meta.get("briefed_at", incoming_meta.get("briefed_at"))
        metadata["briefing_ids"] = cls.unique_list(
            (existing_meta.get("briefing_ids") or [])
            + (incoming_meta.get("briefing_ids") or [])
        )

        metadata["published_at"] = cls.earlier_date(
            existing_meta.get("published_at"),
            incoming_meta.get("published_at"),
        )
        metadata["source_published_at_range"] = cls.merge_date_ranges(
            existing_meta.get("source_published_at_range"),
            incoming_meta.get("source_published_at_range"),
        )

        if incoming.get("doc_type") in {"intel_card", "social_signal_card"}:
            primary_source_id = existing_meta.get("primary_source_id") or incoming_meta.get(
                "primary_source_id"
            )
            source_ids = cls.unique_list(
                [
                    existing_meta.get("primary_source_id"),
                    *(existing_meta.get("supporting_source_ids") or []),
                    incoming_meta.get("primary_source_id"),
                    *(incoming_meta.get("supporting_source_ids") or []),
                ]
            )
            if primary_source_id:
                metadata["primary_source_id"] = primary_source_id
                metadata["supporting_source_ids"] = [
                    source_id for source_id in source_ids if source_id != primary_source_id
                ]
                metadata["source_count"] = len(source_ids)

        for score_key in ("confidence_score", "importance_score"):
            scores = [
                value
                for value in (existing_meta.get(score_key), incoming_meta.get(score_key))
                if isinstance(value, (int, float))
            ]
            if scores:
                metadata[score_key] = max(scores)

        return {
            "title": existing.get("title") or incoming.get("title"),
            "content": existing.get("content") or incoming.get("content"),
            "source_url": existing.get("source_url") or incoming.get("source_url"),
            "metadata": metadata,
        }

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def unique_list(values: list[Any]) -> list[Any]:
        unique: list[Any] = []
        for value in values:
            if value and value not in unique:
                unique.append(value)
        return unique

    @classmethod
    def earlier_date(cls, left: str | None, right: str | None) -> str | None:
        if not left:
            return right
        if not right:
            return left
        left_dt = cls.parse_datetime(left)
        right_dt = cls.parse_datetime(right)
        if left_dt and right_dt:
            return left if left_dt <= right_dt else right
        return min(left, right)

    @classmethod
    def merge_date_ranges(
        cls,
        left: dict[str, str | None] | None,
        right: dict[str, str | None] | None,
    ) -> dict[str, str | None]:
        starts = [value for value in ((left or {}).get("start"), (right or {}).get("start")) if value]
        ends = [value for value in ((left or {}).get("end"), (right or {}).get("end")) if value]
        return {
            "start": cls.earlier_date(starts[0], starts[1]) if len(starts) == 2 else (starts[0] if starts else None),
            "end": cls.later_date(ends[0], ends[1]) if len(ends) == 2 else (ends[0] if ends else None),
        }

    @classmethod
    def later_date(cls, left: str | None, right: str | None) -> str | None:
        if not left:
            return right
        if not right:
            return left
        left_dt = cls.parse_datetime(left)
        right_dt = cls.parse_datetime(right)
        if left_dt and right_dt:
            return left if left_dt >= right_dt else right
        return max(left, right)

    @staticmethod
    def parse_datetime(value: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(value)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                return None

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
# Config loaders
# ---------------------------------------------------------------------------

def load_tavily_config(config_path: str | Path = ".config.yaml") -> dict[str, Any]:
    result = parse_simple_yaml(config_path)
    tavily = result.get("tavily", {})
    if isinstance(tavily, dict):
        return {
            "api_key": tavily.get("api_key", result.get("tavily_api_key", "")),
            "mcp_url": tavily.get("mcp_url", ""),
        }
    return {"api_key": result.get("tavily_api_key", ""), "mcp_url": ""}


def load_llm_config(config_path: str | Path = ".config.yaml") -> dict[str, str]:
    config = parse_simple_yaml(config_path)
    llm = config.get("llm", {})
    openai = config.get("openai", {})
    vercel = config.get("vercel", {})
    opencode_go = config.get("opencode-go", {})
    if not isinstance(llm, dict):
        llm = {}
    if not isinstance(openai, dict):
        openai = {}
    if not isinstance(vercel, dict):
        vercel = {}
    if not isinstance(opencode_go, dict):
        opencode_go = {}
    base_url = str(
        llm.get("base_url")
        or vercel.get("base_url")
        or openai.get("base_url")
        or opencode_go.get("base_url")
        or config.get("llm_base_url")
        or config.get("openai_base_url")
        or "https://api.openai.com/v1"
    )
    if base_url.rstrip("/") == "https://api.vercel.com":
        base_url = "https://ai-gateway.vercel.sh/v1"
    return {
        "api_key": str(
            llm.get("api_key")
            or vercel.get("api_key")
            or openai.get("api_key")
            or opencode_go.get("api_key")
            or config.get("llm_api_key")
            or config.get("openai_api_key")
            or ""
        ),
        "base_url": base_url,
        "model": str(
            llm.get("model")
            or vercel.get("model")
            or openai.get("model")
            or opencode_go.get("model")
            or config.get("llm_model")
            or config.get("openai_model")
            or "deepseekV4-Flash"
        ),
    }


def load_supabase_config(config_path: str | Path = ".config.yaml") -> dict[str, str]:
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
# Base Collector — shared pipeline logic
# ---------------------------------------------------------------------------

class BaseCollector:
    """Base class for regional collector mini-agents.

    Subclasses must set:
        REGION, REGION_LABEL, COUNTRY_TERMS, CITY_TERMS, SEASONAL_TERMS,
        REGION_RELEVANCE_TERMS, AGENT_NAME, RELEVANCE_PROMPT, CITY_QUERY_TERMS
    """

    # --- Subclass must override these ---
    REGION: str = ""
    REGION_LABEL: str = ""
    COUNTRY_TERMS: str = ""
    CITY_TERMS: str = ""
    SEASONAL_TERMS: str = ""
    REGION_RELEVANCE_TERMS: set[str] = set()
    AGENT_NAME: str = ""
    RELEVANCE_PROMPT: str = ""
    CITY_QUERY_TERMS: list[str] = []  # e.g. ["Dubai", "UAE"] for query building

    def __init__(
        self,
        search_provider: SearchProvider | None = None,
        search_providers: dict[str, SearchProvider] | None = None,
        curator: LLMCurator | None = None,
        supabase_writer: SupabaseWriter | None = None,
    ) -> None:
        # Support both single provider (backward compat) and multi-provider dict
        if search_providers is not None:
            self.search_providers = search_providers
        elif search_provider is not None:
            self.search_providers = {"news": search_provider}
        else:
            self.search_providers = {}
        self.curator = curator
        self.supabase_writer = supabase_writer

    def collect(self, request: CollectionRequest) -> dict[str, Any]:
        collected_at = SupabaseWriter.now_iso()
        queries = self.build_queries(request)

        all_candidates: list[SearchCandidate] = []
        # Determine which source types to search
        source_types = request.source_types if request.source_types else ["news"]
        for source_type in source_types:
            provider = self.search_providers.get(source_type)
            if provider is None:
                # Fallback: try "news" provider for unknown source types
                provider = self.search_providers.get("news")
            if provider is None:
                continue
            for query in queries:
                all_candidates.extend(
                    provider.search(
                        query=query,
                        source_type=source_type,
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
                            impact_tags=[],
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
            impact_tags = self.merge_impact_tags(cluster)
            source_dates = self.source_published_at_range([candidate for candidate, _ in cluster])
            for candidate, decision in cluster:
                source_id = self.new_doc_id()
                cluster_source_ids.append(source_id)
                topic = decision.topic or request.topic
                strategic_vertical = decision.strategic_vertical or request.strategic_vertical
                normalized_published_at = self.normalize_published_at(candidate.published_at)
                raw_sources.append(
                    {
                        "id": source_id,
                        "doc_type": "raw_source",
                        "title": candidate.title,
                        "content": candidate.snippet or candidate.title,
                        "source_url": candidate.url,
                        "created_by_agent": self.AGENT_NAME,
                        "metadata": {
                            "region": self.REGION,
                            "topic": topic,
                            "impact_tags": decision.impact_tags,
                            "strategic_vertical": strategic_vertical,
                            "event_key": event_key,
                            "topic_source": "llm_selected" if decision.topic else "request_fallback",
                            "vertical_source": (
                                "llm_selected"
                                if decision.strategic_vertical
                                else "request_fallback"
                            ),
                            "normalized_source_url": self.normalize_url(candidate.url),
                            "source_name": candidate.source_name,
                            "published_at": normalized_published_at,
                            "raw_published_at": candidate.published_at,
                            "first_seen_at": collected_at,
                            "last_seen_at": collected_at,
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
            card_dedup_key = self.card_dedup_key(
                doc_type="intel_card",
                topic=topic,
                strategic_vertical=strategic_vertical,
                event_key=event_key,
            )
            intel_cards.append(
                {
                    "id": self.new_doc_id(),
                    "doc_type": "intel_card",
                    "title": primary.title,
                    "content": primary.snippet or primary.title,
                    "source_url": primary.url,
                    "created_by_agent": self.AGENT_NAME,
                    "metadata": {
                        "region": self.REGION,
                        "topic": topic,
                        "impact_tags": impact_tags,
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
                        "dedup_key": card_dedup_key,
                        "published_at": source_dates["start"],
                        "source_published_at_range": source_dates,
                        "first_seen_at": collected_at,
                        "last_seen_at": collected_at,
                        "briefing_status": "new",
                        "briefed_at": None,
                        "briefing_ids": [],
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
            if all_docs:
                try:
                    self.supabase_writer.write_documents_with_dedup(all_docs)
                    persisted = True
                except Exception as exc:
                    print(f"[{self.AGENT_NAME}] Supabase write_documents failed: {exc}")
            else:
                print(f"[{self.AGENT_NAME}] No documents to persist (search returned empty)")

            run_status = "completed" if persisted else "empty" if not all_docs else "partial"
            error_msg = None if persisted else ("no data" if not all_docs else "Supabase write_documents failed")
            try:
                self.supabase_writer.write_agent_run(
                    agent_name=self.AGENT_NAME,
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
                print(f"[{self.AGENT_NAME}] Supabase write_agent_run failed: {exc}")

        return {
            "region": self.REGION,
            "generated_queries": queries,
            "raw_sources": raw_sources,
            "intel_cards": intel_cards,
            "discarded_candidates": discarded_candidates,
            "persisted": persisted,
            "coverage": {
                "regions": [self.REGION],
                "source_types": request.source_types,
                "time_window": request.time_window,
            },
        }

    def build_agent_prompt(self, request: CollectionRequest) -> str:
        return (
            f"You are the {self.REGION_LABEL} collector mini-agent for AIRS, an overseas strategic "
            "intelligence platform for Chow Tai Fook Jewellery Group.\n"
            "Tavily is your search tool, similar to a Google-like search engine.\n"
            f"Region: {self.REGION} ({self.REGION_LABEL}; {self.COUNTRY_TERMS}; {self.CITY_TERMS}).\n"
            f"Topic: {request.topic}.\n"
            f"Strategic vertical: {request.strategic_vertical}.\n"
            f"Search focus: {request.query_focus}.\n\n"
            f"{self.RELEVANCE_PROMPT}\n\n"
            "Allowed topic values: competition, product, channel, social, regulation.\n"
            "Allowed impact_tags values: supply_chain, compliance, cost, pricing, inventory, "
            "logistics, sourcing, retail_operations, consumer_demand, brand_reputation, "
            "gold_price.\n"
            "Allowed strategic_vertical values: gold_jewellery, "
            "jade_colored_gems_cultural_jewellery, overseas_retail_channels, other.\n"
            "topic is a single primary intelligence category: what kind of jewellery market "
            "change this item mainly describes.\n"
            "impact_tags are multi-select business impact labels: which business areas or "
            "briefing audiences may care about this item.\n"
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
        city_term = self.CITY_QUERY_TERMS[0] if self.CITY_QUERY_TERMS else self.REGION_LABEL
        return [
            f"{self.REGION_LABEL} {vertical} {request.query_focus}",
            f"{city_term} {vertical} {topic} {request.query_focus}",
            f"{self.REGION_LABEL} {vertical} {hints[-1]}",
        ]

    # --- Utility methods (shared, not overridden) ---

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

    @staticmethod
    def merge_impact_tags(
        cluster: list[tuple[SearchCandidate, CuratedCandidate]]
    ) -> list[str]:
        tags = {
            tag
            for _, decision in cluster
            for tag in decision.impact_tags
            if tag in ALLOWED_IMPACT_TAGS
        }
        return sorted(tags)

    def is_relevant_candidate(self, candidate: SearchCandidate) -> bool:
        text = f"{candidate.title} {candidate.snippet}".lower()
        has_region_signal = any(term in text for term in self.REGION_RELEVANCE_TERMS)
        has_jewellery_signal = any(term in text for term in JEWELLERY_RELEVANCE_TERMS)
        return has_region_signal and has_jewellery_signal

    def is_same_event(self, left: SearchCandidate, right: SearchCandidate) -> bool:
        left_text = left.title.lower()
        right_text = right.title.lower()
        title_similarity = SequenceMatcher(None, left_text, right_text).ratio()
        left_full = f"{left.title} {left.snippet[:120]}".lower()
        right_full = f"{right.title} {right.snippet[:120]}".lower()
        full_similarity = SequenceMatcher(None, left_full, right_full).ratio()
        shared_title_words = self.words(left_text) & self.words(right_text)
        long_shared = len([w for w in shared_title_words if len(w) > 4])
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

    def card_dedup_key(
        self,
        doc_type: str,
        topic: str,
        strategic_vertical: str,
        event_key: str,
    ) -> str:
        return "|".join(
            [
                doc_type,
                self.REGION,
                topic,
                strategic_vertical,
                self.slug(event_key),
            ]
        )

    @staticmethod
    def slug(text: str) -> str:
        value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return value[:120] or "unknown"

    @classmethod
    def normalize_published_at(cls, value: str | None) -> str | None:
        if not value:
            return None
        parsed = SupabaseWriter.parse_datetime(value)
        if parsed is not None:
            return parsed.date().isoformat()
        return value

    @classmethod
    def source_published_at_range(
        cls,
        candidates: list[SearchCandidate],
    ) -> dict[str, str | None]:
        dates = [
            normalized
            for normalized in (cls.normalize_published_at(candidate.published_at) for candidate in candidates)
            if normalized
        ]
        if not dates:
            return {"start": None, "end": None}
        start = dates[0]
        end = dates[0]
        for value in dates[1:]:
            start = SupabaseWriter.earlier_date(start, value) or start
            end = SupabaseWriter.later_date(end, value) or end
        return {"start": start, "end": end}
