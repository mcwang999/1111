"""Social Media Analysis Agent for AIRS.

Searches X/Twitter (and optionally Reddit) for jewellery-related discussions,
then uses LLM to analyse hot topics, sentiment, and emerging trends relevant
to Chow Tai Fook's overseas business.

Pipeline:
    1. Multi-query search across social platforms
    2. Deduplicate results
    3. LLM analysis → structured hot-topic report
    4. Persist to Supabase (optional)

Usage::

    from airs.social_media_agent import SocialMediaAgent

    agent = SocialMediaAgent.from_config()
    report = agent.analyse(
        focus="Chow Tai Fook jewellery overseas expansion",
        regions=["Singapore", "Dubai", "US"],
        time_window="7d",
    )
    print(report["summary"])
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from airs.mini_agents.base_collector import (
    SearchCandidate,
    OpenAILLMCurator,
    SupabaseWriter,
    load_supabase_config,
)
from airs.mini_agents.x_search_provider import XSearchProvider


# ---------------------------------------------------------------------------
# Brand & business keywords
# ---------------------------------------------------------------------------

BRAND_KEYWORDS = {
    # Brand names
    "Chow Tai Fook", "CTF", "周大福",
    "Hearts On Fire", "HOF", "赫兹斐亚",
    # Product categories
    "jewellery", "jewelry", "jeweller", "jeweler",
    "gold", "diamond", "gem", "gems", "jade",
    "watch", "watches", "luxury retail",
    "bridal", "engagement ring", "solitaire",
    "bracelet", "necklace", "earring",
    # Business context
    "flagship store", "retail expansion", "store opening",
    "luxury brand", "luxury market",
}

# Region-specific query templates
REGION_QUERIES: dict[str, list[str]] = {
    "Singapore": [
        "Chow Tai Fook Singapore",
        "CTF jewellery Singapore store",
        "周大福 新加坡",
        "luxury jewellery Singapore retail",
        "diamond ring Singapore",
    ],
    "Dubai": [
        "Chow Tai Fook Dubai",
        "gold jewellery Dubai demand",
        "周大福 迪拜",
        "luxury retail Dubai expansion",
        "Dubai gold price jewellery",
    ],
    "US": [
        "Hearts On Fire diamond",
        "luxury jewellery US retail",
        "Chow Tai Fook America",
        "diamond engagement ring trend US",
        "jewelry store expansion US",
    ],
    "Southeast Asia": [
        "Chow Tai Fook Southeast Asia",
        "周大福 东南亚",
        "jewellery retail Malaysia Thailand",
        "gold demand Southeast Asia",
        "luxury brand expansion ASEAN",
    ],
    "Global": [
        "Chow Tai Fook overseas expansion",
        "周大福 海外",
        "luxury jewellery market trend 2025",
        "gold price impact jewellery demand",
        "jewellery brand competition global",
    ],
}

ANALYSIS_PROMPT = """\
You are the Social Media Intelligence Analyst for AIRS, an overseas strategic
intelligence platform for Chow Tai Fook Jewellery Group.

Your task: analyse the following social media posts (mostly from X/Twitter) and
produce a structured hot-topic report.

## Context
- Chow Tai Fook (CTF) is a leading jewellery retailer expanding overseas.
- Key brands: Chow Tai Fook, Hearts On Fire.
- Focus regions: Singapore, Dubai, US, Southeast Asia.
- Business verticals: gold jewellery, jade/coloured gems, overseas retail channels.

## Instructions
1. Identify 3-8 **hot topics** — themes that appear repeatedly or have high
   engagement across the posts.
2. For each hot topic, provide:
   - `topic_name`: short descriptive name (English)
   - `sentiment`: "positive" | "negative" | "neutral" | "mixed"
   - `summary`: 1-3 sentence analysis of what people are saying
   - `post_count`: how many posts relate to this topic
   - `key_quotes`: up to 3 representative snippets from the posts
   - `business_implication`: 1-2 sentence assessment of what this means for CTF
   - `regions`: list of relevant regions
   - `verticals`: list of relevant verticals from [gold_jewellery, jade_colored_gems_cultural_jewellery, overseas_retail_channels]
3. Provide an overall `summary`: 2-4 sentence executive summary of the social
   media landscape for CTF's jewellery business.
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
You are the Social Media Intelligence Analyst for AIRS, an overseas strategic
intelligence platform for Chow Tai Fook Jewellery Group.

Your task: analyse the following social media posts and produce structured
social_signal_cards. Social media should be treated as consumer/community
signals, not as news-event intelligence.

## Context
- Chow Tai Fook (CTF) is a leading jewellery retailer expanding overseas.
- Key brands: Chow Tai Fook, Hearts On Fire.
- Business verticals: gold_jewellery, jade_colored_gems_cultural_jewellery,
  overseas_retail_channels.

## Instructions
1. Identify 3-8 social signals across the posts.
2. For each signal, choose:
   - `signal_type`: trend | pain_point | purchase_intent | brand_sentiment | occasion | pricing_value
   - `sentiment`: positive | negative | neutral | mixed
   - `demand_stage`: awareness | consideration | purchase | post_purchase
3. Preserve traceability with representative quotes and evidence URLs.
4. Provide business implications for CTF's overseas jewellery business.

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
        curator: OpenAILLMCurator | None = None,
        supabase_writer: SupabaseWriter | None = None,
        max_results_per_query: int = 10,
    ) -> None:
        self.x_provider = x_provider
        self.curator = curator
        self.supabase_writer = supabase_writer
        self.max_results_per_query = max_results_per_query

    @classmethod
    def from_config(cls, config_path: str | Path = ".config.yaml") -> SocialMediaAgent:
        """Build agent from .config.yaml."""
        config_path = Path(config_path)

        # X provider
        x_provider = XSearchProvider.from_config(config_path)

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
            curator=curator,
            supabase_writer=writer,
        )

    # ------------------------------------------------------------------
    # Main analysis
    # ------------------------------------------------------------------

    def analyse(
        self,
        focus: str = "Chow Tai Fook jewellery overseas",
        regions: list[str] | None = None,
        time_window: str = "7d",
        extra_queries: list[str] | None = None,
    ) -> SocialMediaReport:
        """Run the full social media analysis pipeline.

        Args:
            focus: High-level focus area for the analysis.
            regions: List of regions to search. Defaults to all.
            time_window: Time window like "7d" or "14d".
            extra_queries: Additional search queries beyond the defaults.

        Returns:
            SocialMediaReport with hot topics, summary, and raw data.
        """
        if regions is None:
            regions = list(REGION_QUERIES.keys())

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
        report = self._analyse_with_llm(unique)

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
            region_queries = REGION_QUERIES.get(region, [])
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
        self, candidates: list[SearchCandidate]
    ) -> SocialMediaReport:
        if self.curator is None:
            return self._rule_based_analysis(candidates)

        # Build the posts text for the LLM prompt
        posts_text = self._format_candidates(candidates)
        prompt = SOCIAL_SIGNAL_ANALYSIS_PROMPT.format(posts=posts_text)

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
            "Brand Buzz": ["Chow Tai Fook", "CTF", "周大福", "Hearts On Fire"],
            "Wedding & Bridal": ["wedding", "bridal", "engagement ring", "solitaire"],
            "Competition": ["competitor", "Pandora", "Signet", "Tiffany", "Cartier", "LVMH"],
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
            docs.append({
                "id": str(uuid4()),
                "doc_type": "social_signal_card",
                "title": f"[Social] {topic.get('signal_name') or topic.get('topic_name', 'Unknown Signal')}",
                "content": topic.get("summary", ""),
                "source_url": evidence_urls[0] if evidence_urls else "",
                "created_by_agent": "social_media_agent",
                "metadata": {
                    "agent": "social_media_agent",
                    "focus": focus,
                    "regions": topic.get("regions", []),
                    "verticals": topic.get("verticals", []),
                    "signal_type": topic.get("signal_type", "trend"),
                    "sentiment": topic.get("sentiment", "mixed"),
                    "demand_stage": topic.get("demand_stage", "consideration"),
                    "post_count": topic.get("post_count", 0),
                    "business_implication": topic.get("business_implication", ""),
                    "key_quotes": topic.get("key_quotes", [])[:3],
                    "platforms": platforms,
                    "evidence_urls": evidence_urls,
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
                    "source_name": c.source_name,
                    "published_at": c.published_at,
                    "type": "social_media_post",
                },
            })

        try:
            self.supabase_writer.write_documents(docs)
            print(f"[SocialMediaAgent] Persisted {len(docs)} documents to Supabase")
            return True
        except Exception as exc:
            print(f"[SocialMediaAgent] Supabase write failed: {exc}")
            return False
