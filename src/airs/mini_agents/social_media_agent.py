"""Social Media Analysis Agent for AIRS.

Searches X/Twitter and Reddit for jewellery industry discussions,
then uses LLM to produce structured social signal cards.

Each signal card has:
  - topic: "social" (fixed)
  - impact_tags: multi-select business impact tags shared with regional collectors
  - signal_type: social-specific signal category

Pipeline:
    1. Multi-query search across X and Reddit
    2. Deduplicate results
    3. LLM analysis → structured social signal cards
    4. Persist to Supabase (optional)

Usage::

    from airs.mini_agents.social_media_agent import SocialMediaAgent

    agent = SocialMediaAgent.from_config()
    report = agent.analyse(
        focus="jewellery industry",
        regions=["Global"],
        time_window="7d",
    )
    print(report.summary)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from airs.mini_agents.base_collector import (
    SearchCandidate,
    OpenAILLMCurator,
    SupabaseWriter,
    load_supabase_config,
)
from airs.providers.x_search_provider import XSearchProvider
from airs.mcp.reddit_mcp import RedditMCPProvider


# ---------------------------------------------------------------------------
# Default search queries
# ---------------------------------------------------------------------------

DEFAULT_REGION_QUERIES: dict[str, list[str]] = {
    "Global": [
        "jewellery market trend",
        "luxury jewellery demand",
        "diamond engagement ring trend",
        "gold price jewellery demand",
        "jewellery brand competition",
    ],
}

SOCIAL_SIGNAL_IMPACT_TAGS: dict[str, list[str]] = {
    "trend": ["consumer_demand"],
    "purchase_intent": ["consumer_demand"],
    "pain_point": ["brand_reputation"],
    "brand_sentiment": ["brand_reputation"],
    "occasion": ["consumer_demand"],
    "pricing_value": ["pricing", "consumer_demand"],
}

ANALYSIS_PROMPT = """\
You are the Social Media Intelligence Analyst for AIRS, a jewellery industry
intelligence platform.

Your task: analyse the following social media posts (from X/Twitter and Reddit)
and produce a structured hot-topic report.

## Context
- Focus: {focus}
- Business verticals: {verticals}

## Instructions
1. Identify 3-8 **hot topics** — themes that appear repeatedly or have high
   engagement across the posts.
2. For each hot topic, provide:
   - `topic_name`: short descriptive name (English)
   - `sentiment`: "positive" | "negative" | "neutral" | "mixed"
   - `summary`: 1-3 sentence analysis
   - `post_count`: how many posts relate to this topic
   - `key_quotes`: up to 3 representative snippets
   - `business_implication`: 1-2 sentence assessment
   - `regions`: list of relevant regions
   - `verticals`: list of relevant verticals
3. Provide an overall `summary`: 2-4 sentence executive summary.
4. Provide `trending_hashtags`: list of any notable hashtags or mentions.

## Output format
Return a JSON object with this exact structure:

{{
  "summary": "...",
  "hot_topics": [
    {{
      "topic_name": "...",
      "sentiment": "...",
      "summary": "...",
      "post_count": 0,
      "key_quotes": ["...", "..."],
      "business_implication": "...",
      "regions": ["..."],
      "verticals": ["..."]
    }}
  ],
  "trending_hashtags": ["..."],
  "total_posts_analysed": 0
}}

## Posts to analyse
{posts}
"""

SOCIAL_SIGNAL_ANALYSIS_PROMPT = """\
You are the Social Media Intelligence Analyst for AIRS, a jewellery industry
intelligence platform.

Your task: analyse the following social media posts and produce structured
social_signal_cards. Social media should be treated as consumer/community
signals, not as news-event intelligence.

## Context
- Focus: {focus}
- Business verticals: {verticals}

## Instructions
1. Identify 3-8 social signals across the posts.
2. For each signal, choose:
   - `signal_type`: trend | purchase_intent | pain_point | brand_sentiment | occasion | pricing_value
   - `sentiment`: positive | negative | neutral | mixed
   - `demand_stage`: awareness | consideration | purchase | post_purchase
3. Preserve traceability with representative quotes and evidence URLs.
4. Provide business implications for the jewellery industry.

## Output format
Return valid JSON only with this exact structure:

{{
  "summary": "...",
  "social_signal_cards": [
    {{
      "signal_name": "...",
      "signal_type": "trend",
      "sentiment": "mixed",
      "demand_stage": "consideration",
      "summary": "...",
      "post_count": 0,
      "key_quotes": ["...", "..."],
      "business_implication": "...",
      "regions": ["..."],
      "verticals": ["gold_jewellery"],
      "platforms": ["x"],
      "evidence_urls": ["..."]
    }}
  ],
  "trending_hashtags": ["..."],
  "total_posts_analysed": 0
}}

## Posts to analyse
{posts}
"""


@dataclass
class SocialMediaReport:
    """Structured output from the social media analysis agent."""

    summary: str
    social_signal_cards: list[dict[str, Any]]
    trending_hashtags: list[str]
    total_posts_analysed: int
    raw_candidates: list[SearchCandidate]
    persisted: bool = False

    @property
    def hot_topics(self) -> list[dict[str, Any]]:
        """Backward-compatible alias for older smoke scripts."""
        return self.social_signal_cards


class SocialMediaAgent:
    """Analyses social media discussions relevant to CTF's jewellery business.

    Searches X/Twitter (and optionally Reddit) for jewellery-related posts,
    deduplicates them, then uses an LLM to identify hot topics, sentiment,
    and business implications.
    """

    def __init__(
        self,
        x_provider: XSearchProvider | None = None,
        reddit_provider: RedditMCPProvider | None = None,
        curator: OpenAILLMCurator | None = None,
        supabase_writer: SupabaseWriter | None = None,
        max_results_per_query: int = 10,
    ) -> None:
        self.x_provider = x_provider
        self.reddit_provider = reddit_provider
        self.curator = curator
        self.supabase_writer = supabase_writer
        self.max_results_per_query = max_results_per_query

    @classmethod
    def from_config(cls, config_path: str | Path = ".config.yaml") -> SocialMediaAgent:
        """Build agent from .config.yaml."""
        config_path = Path(config_path)

        # X provider
        x_provider = XSearchProvider.from_config(config_path)

        # Reddit provider
        try:
            reddit_provider = RedditMCPProvider.from_config(config_path)
        except Exception:
            reddit_provider = None

        # LLM curator
        curator = OpenAILLMCurator.from_config(config_path)

        # Supabase writer (optional)
        supa_config = load_supabase_config(config_path)
        writer = None
        if supa_config.get("url") and supa_config.get("service_role_key"):
            writer = SupabaseWriter(
                url=supa_config["url"],
                service_role_key=supa_config["service_role_key"],
            )

        return cls(
            x_provider=x_provider,
            reddit_provider=reddit_provider,
            curator=curator,
            supabase_writer=writer,
        )

    # ------------------------------------------------------------------
    # Main analysis
    # ------------------------------------------------------------------

    def analyse(
        self,
        focus: str = "jewellery industry",
        regions: list[str] | None = None,
        verticals: list[str] | None = None,
        time_window: str = "7d",
        extra_queries: list[str] | None = None,
    ) -> SocialMediaReport:
        """Run the full social media analysis pipeline.

        Args:
            focus: High-level focus area for the analysis.
            regions: List of regions to search. Defaults to Global.
            verticals: Business verticals relevant to the analysis.
            time_window: Time window like "7d" or "14d".
            extra_queries: Additional search queries beyond the defaults.

        Returns:
            SocialMediaReport with social signal cards, summary, and raw data.
        """
        if regions is None:
            regions = list(DEFAULT_REGION_QUERIES.keys())
        if verticals is None:
            verticals = ["gold_jewellery", "jade_colored_gems_cultural_jewellery", "overseas_retail_channels"]

        # 1. Build queries
        queries = self._build_queries(regions, focus, extra_queries)
        print(f"[SocialMediaAgent] Built {len(queries)} queries for regions: {regions}")

        # 2. Search
        all_candidates = self._search_all(queries, time_window)
        print(f"[SocialMediaAgent] Found {len(all_candidates)} raw results")

        # 3. Deduplicate
        unique = self._deduplicate(all_candidates)
        print(f"[SocialMediaAgent] After dedup: {len(unique)} unique posts")

        if not unique:
            return SocialMediaReport(
                summary="No social media posts found for the given queries.",
                social_signal_cards=[],
                trending_hashtags=[],
                total_posts_analysed=0,
                raw_candidates=[],
            )

        # 4. LLM analysis
        report = self._analyse_with_llm(unique, focus=focus, verticals=verticals)

        # 5. Persist to Supabase (optional)
        persisted = False
        if self.supabase_writer is not None:
            persisted = self._persist(report, unique, focus, regions, time_window)

        report.persisted = persisted
        return report

    # ------------------------------------------------------------------
    # Query building
    # ------------------------------------------------------------------

    def _build_queries(
        self,
        regions: list[str],
        focus: str,
        extra_queries: list[str] | None = None,
    ) -> list[str]:
        queries: list[str] = []
        for region in regions:
            region_queries = DEFAULT_REGION_QUERIES.get(region, [])
            if region_queries:
                queries.extend(region_queries)
            else:
                queries.append(f"{focus} {region}")

        if extra_queries:
            queries.extend(extra_queries)

        # Deduplicate queries while preserving order
        seen: set[str] = set()
        unique_queries: list[str] = []
        for q in queries:
            normalised = q.lower().strip()
            if normalised not in seen:
                seen.add(normalised)
                unique_queries.append(q)

        return unique_queries

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _search_all(
        self, queries: list[str], time_window: str
    ) -> list[SearchCandidate]:
        all_candidates: list[SearchCandidate] = []

        if self.x_provider is not None:
            for query in queries:
                print(f"  [X] Searching: {query}")
                try:
                    results = self.x_provider.search(
                        query=query, source_type="x", time_window=time_window
                    )
                    all_candidates.extend(results)
                    print(f"  [X]   → {len(results)} results")
                except Exception as exc:
                    print(f"  [X]   → Error: {exc}")

        if self.reddit_provider is not None:
            for query in queries:
                print(f"  [Reddit] Searching: {query}")
                try:
                    results = self.reddit_provider.search(
                        query=query, source_type="reddit", time_window=time_window
                    )
                    all_candidates.extend(results)
                    print(f"  [Reddit]   → {len(results)} results")
                except Exception as exc:
                    print(f"  [Reddit]   → Error: {exc}")

        return all_candidates

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    @staticmethod
    def _deduplicate(candidates: list[SearchCandidate]) -> list[SearchCandidate]:
        unique: list[SearchCandidate] = []
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()

        for c in candidates:
            # Normalise URL for dedup
            url_key = re.sub(r"[?#].*$", "", c.url.lower().rstrip("/"))
            if url_key in seen_urls:
                continue
            seen_urls.add(url_key)

            # Also dedup by title similarity
            title_key = c.title.lower().strip()[:80]
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)

            unique.append(c)

        return unique

    # ------------------------------------------------------------------
    # LLM analysis
    # ------------------------------------------------------------------

    def _analyse_with_llm(
        self,
        candidates: list[SearchCandidate],
        focus: str = "jewellery industry",
        verticals: list[str] | None = None,
    ) -> SocialMediaReport:
        if self.curator is None:
            return self._rule_based_analysis(candidates)

        if verticals is None:
            verticals = ["gold_jewellery", "jade_colored_gems_cultural_jewellery", "overseas_retail_channels"]

        # Build the posts text for the LLM prompt
        posts_text = self._format_candidates(candidates)
        prompt = SOCIAL_SIGNAL_ANALYSIS_PROMPT.format(
            focus=focus,
            verticals=", ".join(verticals),
            posts=posts_text,
        )

        # Call LLM
        try:
            payload = {
                "model": self.curator.model,
                "temperature": 0.3,
                "max_tokens": 8192,
                "messages": [
                    {"role": "system", "content": "You are a social media intelligence analyst for a luxury jewellery company. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
            }
            response = self.curator.http_client.post(
                f"{self.curator.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.curator.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except Exception as exc:
            print(f"[SocialMediaAgent] LLM request failed: {exc}")
            return self._rule_based_analysis(candidates)

        if response.status_code >= 400:
            print(f"[SocialMediaAgent] LLM API error {response.status_code}: {response.text[:300]}")
            return self._rule_based_analysis(candidates)

        try:
            resp_json = response.json()
            content = resp_json["choices"][0]["message"]["content"]
            # Strip markdown code block if present
            content = content.strip()
            if content.startswith("```"):
                first_newline = content.index("\n") if "\n" in content else len(content)
                content = content[first_newline + 1:]
                if content.endswith("```"):
                    content = content[:-3].strip()
            data = json.loads(content)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            print(f"[SocialMediaAgent] LLM parse error: {exc}")
            return self._rule_based_analysis(candidates)

        return SocialMediaReport(
            summary=data.get("summary", ""),
            social_signal_cards=data.get(
                "social_signal_cards",
                data.get("hot_topics", []),
            ),
            trending_hashtags=data.get("trending_hashtags", []),
            total_posts_analysed=len(candidates),
            raw_candidates=candidates,
        )

    def _rule_based_analysis(self, candidates: list[SearchCandidate]) -> SocialMediaReport:
        """Fallback analysis when LLM is unavailable."""
        # Group by simple keyword matching
        topic_groups: dict[str, list[SearchCandidate]] = {}
        keywords_map = {
            "Gold Price & Demand": ["gold price", "gold demand", "gold jewellery", "gold market"],
            "Retail Expansion": ["store opening", "flagship", "retail expansion", "new store"],
            "Brand Buzz": ["luxury brand", "brand launch", "brand campaign", "brand reputation"],
            "Wedding & Bridal": ["wedding", "bridal", "engagement ring", "solitaire"],
            "Competition": ["competitor", "Pandora", "Signet", "Tiffany", "Cartier", "LVMH", "Richemont"],
            "Regulation & Duty": ["import duty", "tax", "regulation", "customs"],
        }

        for candidate in candidates:
            text = f"{candidate.title} {candidate.snippet}".lower()
            matched = False
            for topic, keywords in keywords_map.items():
                if any(kw.lower() in text for kw in keywords):
                    topic_groups.setdefault(topic, []).append(candidate)
                    matched = True
            if not matched:
                topic_groups.setdefault("Other", []).append(candidate)

        hot_topics = []
        for topic_name, group in sorted(topic_groups.items(), key=lambda x: -len(x[1])):
            hot_topics.append({
                "signal_name": topic_name,
                "topic_name": topic_name,
                "signal_type": self._infer_signal_type(topic_name),
                "sentiment": "mixed",
                "demand_stage": "consideration",
                "summary": f"{len(group)} posts about {topic_name.lower()}",
                "post_count": len(group),
                "key_quotes": [c.title[:120] for c in group[:3]],
                "business_implication": "Requires further analysis",
                "regions": [],
                "verticals": [],
                "platforms": sorted({self._platform_from_source(c.source_name) for c in group}),
                "evidence_urls": [c.url for c in group[:5] if c.url],
            })

        # Extract hashtags
        hashtags: set[str] = set()
        for c in candidates:
            for tag in re.findall(r"#(\w+)", f"{c.title} {c.snippet}"):
                hashtags.add(f"#{tag}")

        return SocialMediaReport(
            summary=f"Found {len(candidates)} social media posts across {len(topic_groups)} topics.",
            social_signal_cards=hot_topics,
            trending_hashtags=sorted(hashtags, key=lambda t: (-len([c for c in candidates if t.lower() in f"{c.title} {c.snippet}".lower()]), t))[:20],
            total_posts_analysed=len(candidates),
            raw_candidates=candidates,
        )

    @staticmethod
    def _infer_signal_type(topic_name: str) -> str:
        text = topic_name.lower()
        if "wedding" in text or "bridal" in text:
            return "occasion"
        if "price" in text or "demand" in text:
            return "pricing_value"
        if "brand" in text or "competition" in text:
            return "brand_sentiment"
        if "retail" in text:
            return "trend"
        return "trend"

    @staticmethod
    def _platform_from_source(source_name: str) -> str:
        text = source_name.lower()
        if text.startswith("x/"):
            return "x"
        if "reddit" in text:
            return "reddit"
        if "instagram" in text:
            return "instagram"
        return "social"

    @staticmethod
    def _format_candidates(candidates: list[SearchCandidate]) -> str:
        lines: list[str] = []
        for i, c in enumerate(candidates, 1):
            lines.append(f"--- Post {i} ---")
            lines.append(f"Title: {c.title}")
            lines.append(f"Source: {c.source_name}")
            lines.append(f"URL: {c.url}")
            if c.published_at:
                lines.append(f"Date: {c.published_at}")
            lines.append(f"Content: {c.snippet[:500]}")
            lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist(
        self,
        report: SocialMediaReport,
        candidates: list[SearchCandidate],
        focus: str,
        regions: list[str],
        time_window: str,
    ) -> bool:
        if self.supabase_writer is None:
            return False

        docs: list[dict[str, Any]] = []
        collected_at = SupabaseWriter.now_iso()
        source_dates = self._source_published_at_range(candidates)

        # One intel_card for the overall report
        report_id = str(uuid4())
        docs.append({
            "id": report_id,
            "doc_type": "social_media_report",
            "title": f"Social Media Analysis: {focus}",
            "content": report.summary,
            "source_url": "",
            "created_by_agent": "social_media_agent",
            "metadata": {
                "agent": "social_media_agent",
                "focus": focus,
                "regions": regions,
                "time_window": time_window,
                "total_posts_analysed": report.total_posts_analysed,
                "social_signal_count": len(report.social_signal_cards),
                "trending_hashtags": report.trending_hashtags[:10],
                "published_at": source_dates["end"],
                "source_published_at_range": source_dates,
                "first_seen_at": collected_at,
                "last_seen_at": collected_at,
                "type": "social_media_report",
            },
        })

        # One social_signal_card per social signal
        for topic in report.social_signal_cards:
            evidence_urls = topic.get("evidence_urls") or [
                c.url for c in candidates[:5] if c.url
            ]
            platforms = topic.get("platforms") or sorted(
                {self._platform_from_source(c.source_name) for c in candidates}
            )
            signal_type = topic.get("signal_type", "trend")
            impact_tags = self._impact_tags_for_signal(topic)
            signal_dates = self._source_published_at_range(
                [
                    candidate
                    for candidate in candidates
                    if candidate.url in set(evidence_urls)
                ]
                or candidates
            )
            docs.append({
                "id": str(uuid4()),
                "doc_type": "social_signal_card",
                "title": f"[Social] {topic.get('signal_name') or topic.get('topic_name', 'Unknown Signal')}",
                "content": topic.get("summary", ""),
                "source_url": evidence_urls[0] if evidence_urls else "",
                "created_by_agent": "social_media_agent",
                "metadata": {
                    "agent": "social_media_agent",
                    "topic": "social",
                    "impact_tags": impact_tags,
                    "dedup_key": self._signal_dedup_key(topic),
                    "focus": focus,
                    "regions": topic.get("regions", []),
                    "verticals": topic.get("verticals", []),
                    "signal_type": signal_type,
                    "sentiment": topic.get("sentiment", "mixed"),
                    "demand_stage": topic.get("demand_stage", "consideration"),
                    "post_count": topic.get("post_count", 0),
                    "business_implication": topic.get("business_implication", ""),
                    "key_quotes": topic.get("key_quotes", [])[:3],
                    "platforms": platforms,
                    "evidence_urls": evidence_urls,
                    "published_at": signal_dates["end"],
                    "source_published_at_range": signal_dates,
                    "first_seen_at": collected_at,
                    "last_seen_at": collected_at,
                    "briefing_status": "new",
                    "briefed_at": None,
                    "briefing_ids": [],
                    "type": "social_signal_card",
                    "report_id": report_id,
                },
            })

        # Raw sources
        for c in candidates:
            docs.append({
                "id": str(uuid4()),
                "doc_type": "raw_source",
                "title": c.title[:200],
                "content": c.snippet[:1000],
                "source_url": c.url,
                "created_by_agent": "social_media_agent",
                "metadata": {
                    "agent": "social_media_agent",
                    "normalized_source_url": self._normalize_url(c.url),
                    "source_name": c.source_name,
                    "published_at": self._normalize_published_at(c.published_at),
                    "raw_published_at": c.published_at,
                    "first_seen_at": collected_at,
                    "last_seen_at": collected_at,
                    "type": "social_media_post",
                },
            })

        try:
            self.supabase_writer.write_documents_with_dedup(docs)
            print(f"[SocialMediaAgent] Persisted {len(docs)} documents to Supabase")
            return True
        except Exception as exc:
            print(f"[SocialMediaAgent] Supabase write failed: {exc}")
            return False

    @staticmethod
    def _impact_tags_for_signal(topic: dict[str, Any]) -> list[str]:
        signal_type = topic.get("signal_type", "trend")
        tags: list[str] = []

        def add(tag: str) -> None:
            if tag not in tags:
                tags.append(tag)

        for tag in SOCIAL_SIGNAL_IMPACT_TAGS.get(signal_type, ["consumer_demand"]):
            add(tag)

        candidate = SearchCandidate(
            title=str(topic.get("signal_name") or topic.get("topic_name") or ""),
            url="",
            snippet=" ".join(
                [
                    str(topic.get("summary", "")),
                    str(topic.get("business_implication", "")),
                ]
            ),
            source_name="social_signal",
        )
        for tag in OpenAILLMCurator.infer_impact_tags(candidate, topic="social"):
            add(tag)

        return tags[:3]

    @classmethod
    def _signal_dedup_key(cls, topic: dict[str, Any]) -> str:
        signal_type = topic.get("signal_type", "trend")
        verticals = "-".join(sorted(str(v) for v in topic.get("verticals", []))) or "unknown"
        regions = "-".join(sorted(str(r).lower() for r in topic.get("regions", []))) or "global"
        signal_name = str(topic.get("signal_name") or topic.get("topic_name") or "unknown")
        return "|".join(
            [
                "social_signal_card",
                signal_type,
                cls._slug(verticals),
                cls._slug(regions),
                cls._slug(signal_name),
            ]
        )

    @staticmethod
    def _slug(text: str) -> str:
        value = re.sub(r"[^a-z0-9_]+", "-", text.lower()).strip("-")
        return value[:120] or "unknown"

    @staticmethod
    def _normalize_url(url: str) -> str:
        parts = urlsplit(url.strip())
        query_pairs = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key in {"fbclid", "gclid", "mc_cid", "mc_eid"} or key.startswith("utm_"):
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

    @staticmethod
    def _normalize_published_at(value: str | None) -> str | None:
        if not value:
            return None
        parsed = SupabaseWriter.parse_datetime(value)
        if parsed is not None:
            return parsed.date().isoformat()
        return value

    @classmethod
    def _source_published_at_range(
        cls,
        candidates: list[SearchCandidate],
    ) -> dict[str, str | None]:
        dates = [
            normalized
            for normalized in (cls._normalize_published_at(candidate.published_at) for candidate in candidates)
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
