# AIRS Mini-Agents Development Guide

## 1. Positioning

In AIRS, mini-agents are lightweight capability units exposed through MCP tools. They are not full autonomous business analysts.

The first MVP mini-agent is the collector mini-agent:

```text
collect_market_intel
```

Its job is to execute retrieval requests, collect public information from multiple sources, deduplicate candidates, and write traceable raw sources and draft intel cards into the shared database.

The collector mini-agent must not make final strategic judgments. Analysis quality, evidence sufficiency, prediction, and briefing composition belong to higher-level agents.

## 2. Responsibility Boundary

### Collector mini-agent owns

- Convert a collection request into query work items.
- Search multiple source types.
- Respect simple query dependencies.
- Normalize and deduplicate URLs.
- Deduplicate title and snippet similarity.
- Perform lightweight event-level clustering.
- Extract source title, URL, source name, publish time, snippet, and evidence quote.
- Create `raw_source` documents.
- Create draft `intel_card` documents.
- Return created document IDs to the caller.

### Collector mini-agent does not own

- Final opportunity/risk judgment.
- Evidence sufficiency decision.
- Demand or market prediction.
- Briefing composition.
- Feishu delivery.
- Enterprise role-based distribution.

## 3. System Relationship

```text
Analysis Agent / Prediction Agent
  -> calls collect_market_intel when evidence is insufficient
  -> Collector Mini-Agent executes retrieval
  -> writes raw_source and intel_card documents
  -> returns created doc IDs
  -> Analysis Agent / Prediction Agent continues reasoning
```

This keeps the system light:

```text
mini-agent = retrieval executor
higher-level agent = reasoning owner
shared DB = memory and provenance layer
```

## 4. MCP Interface

The initial MCP tool should be:

```text
collect_market_intel(params)
```

Input:

```json
{
  "region": "middle_east",
  "topic": "competition",
  "strategic_vertical": "overseas_retail_channels",
  "time_window": "14d",
  "query_focus": "flagship store expansion",
  "source_types": ["news", "industry", "official"]
}
```

Output:

```json
{
  "request_id": "retrieval_001",
  "created_source_ids": ["src_101", "src_102"],
  "created_card_ids": ["card_201"],
  "coverage": {
    "regions": ["middle_east"],
    "source_types": ["news", "industry", "official"],
    "time_window": "14d"
  }
}
```

The tool should return IDs, not long summaries. Higher-level agents should retrieve details from the shared database.

## 5. Internal Pipeline

The collector mini-agent should run this pipeline:

```text
CollectionRequest
  -> Query Planner
  -> Multi-source Search
  -> Candidate Normalization
  -> URL Deduplication
  -> Title/Snippet Similarity Deduplication
  -> Lightweight Event Clustering
  -> Selective Extraction
  -> raw_source document creation
  -> draft intel_card document creation
  -> CollectionResult
```

Each stage should be implemented as a small function or class. Do not put the whole collector into one long prompt or one large Python file.

## 6. Query Planner

The query planner turns a request into 3-5 query work items.

Example request:

```json
{
  "region": "middle_east",
  "topic": "social",
  "strategic_vertical": "gold_jewellery",
  "time_window": "14d",
  "query_focus": "Ramadan wedding demand",
  "source_types": ["news", "social_trend"]
}
```

Example query work items:

```json
[
  {
    "query": "Middle East gold jewellery social media Ramadan wedding demand",
    "source_type": "news",
    "depends_on": []
  },
  {
    "query": "Dubai UAE Saudi gold jewellery Ramadan wedding demand",
    "source_type": "news",
    "depends_on": []
  },
  {
    "query": "gold jewellery Ramadan wedding trend TikTok Middle East",
    "source_type": "social_trend",
    "depends_on": [0]
  }
]
```

Planner rules:

- Always include region label.
- Always include strategic vertical label.
- Always include topic label.
- Add specific country/city terms for regions when helpful.
- Keep queries short enough for search APIs.
- Do not generate more than 5 queries in MVP unless the caller explicitly asks for broad coverage.

## 7. Source Types

MVP source types:

```text
news
industry
official
macro
social_trend
marketplace
```

Recommended first implementation:

```text
news: general web search or GDELT
industry: whitelist jewellery industry media
official: competitor official news and press pages
macro: World Gold Council, gold price and macro news
social_trend: one selected trend source
marketplace: lightweight search result surfaces only
```

Avoid large-scale scraping in MVP. Prefer search APIs, RSS, official pages, or a small whitelist.

## 8. Prompt Contract

If the mini-agent uses an LLM internally, use a strict prompt contract.

System prompt:

```text
You are a market intelligence collector mini-agent for AIRS.

Your role is retrieval execution, not strategic analysis.

You must:
- Generate focused search work items from the request.
- Use only returned search or source content as evidence.
- Keep each event separate.
- Create traceable raw_source and draft intel_card records.
- Include source_url for every raw_source.
- Mark evidence_quality as snippet_only if full page content is unavailable.

You must not:
- Make final opportunity or risk judgments.
- Claim evidence is sufficient for business action.
- Produce forecasts.
- Produce daily briefings.
- Merge distinct events into one card.
```

Output format:

```json
{
  "raw_sources": [
    {
      "title": "string",
      "source_url": "string",
      "source_name": "string",
      "published_at": "YYYY-MM-DD or null",
      "snippet": "string",
      "evidence_quote": "string",
      "evidence_quality": "full_text_verified | snippet_only | source_unreadable"
    }
  ],
  "draft_intel_cards": [
    {
      "title": "string",
      "summary": "string",
      "region": "string",
      "topic": "string",
      "strategic_vertical": "string",
      "canonical_event_key": "string",
      "primary_source_id": "string",
      "supporting_source_ids": ["string"],
      "importance_score": 0.0,
      "confidence_score": 0.0
    }
  ]
}
```

## 9. Deduplication Rules

Deduplication must happen before creating intel cards.

### Level 1: URL normalization

Normalize:

- Scheme and host casing.
- Trailing slash.
- Tracking parameters such as `utm_*`, `fbclid`, `gclid`.
- URL fragment.

Example:

```text
https://example.com/story/?utm_source=x&id=1#section
-> https://example.com/story?id=1
```

### Level 2: title and snippet similarity

Cluster candidates that describe the same event with slightly different wording.

Example:

```text
Pandora opens new flagship store in Dubai
Pandora launches Dubai flagship jewellery store
```

These should be treated as one event cluster.

### Level 3: event-level key

Create a lightweight `canonical_event_key`:

```text
main_entity | region_or_city | event_action | approximate_time_window
```

Example:

```text
pandora|dubai|opens_flagship_store|2026-05
```

Multiple sources should support one card:

```text
raw_source_1
raw_source_2
raw_source_3
  -> intel_card_1
```

Repeated sources are not wasted. They can increase `confidence_score`.

## 10. Document Creation

### raw_source document

Use `doc_type = raw_source`.

Required fields:

```json
{
  "doc_type": "raw_source",
  "title": "Pandora opens new flagship store in Dubai",
  "content": "Search snippet or extracted page text.",
  "source_url": "https://example.com/story",
  "created_by_agent": "collector_mini_agent",
  "metadata": {
    "region": "middle_east",
    "topic": "competition",
    "strategic_vertical": "overseas_retail_channels",
    "source_type": "news",
    "source_name": "Example News",
    "published_at": "2026-05-20",
    "evidence_quality": "snippet_only"
  }
}
```

### intel_card document

Use `doc_type = intel_card`.

Required fields:

```json
{
  "doc_type": "intel_card",
  "title": "Pandora opens Dubai flagship store",
  "content": "A competitor expanded premium retail presence in Dubai.",
  "created_by_agent": "collector_mini_agent",
  "metadata": {
    "region": "middle_east",
    "topic": "competition",
    "strategic_vertical": "overseas_retail_channels",
    "importance_score": 0.6,
    "confidence_score": 0.75,
    "canonical_event_key": "pandora|dubai|opens_flagship_store|2026-05",
    "primary_source_id": "src_101",
    "supporting_source_ids": ["src_102"],
    "source_count": 2,
    "evidence_quality": "snippet_only"
  }
}
```

## 11. Confidence and Importance

The collector can assign preliminary scores only.

`confidence_score` should reflect source reliability and cross-source support:

```text
0.40 single snippet from weak source
0.55 single snippet from acceptable source
0.70 full text or official source
0.80 two independent sources
0.90 official source plus independent confirmation
```

`importance_score` should be conservative:

```text
0.40 minor mention
0.60 relevant overseas signal
0.75 strong signal for region/topic/vertical
0.85 high-impact competitor, regulation, macro, or channel event
```

The collector must not use high scores to imply final business action. Higher-level agents decide business impact.

## 12. Error Handling

The collector should return partial results when possible.

Expected failure modes:

- Search provider timeout.
- Page fetch failure.
- Source unreadable.
- Empty result set.
- Duplicate-only result set.
- Invalid request filters.

Behavior:

```text
search timeout -> log in agent_runs and continue other queries
page unreadable -> store snippet_only raw_source if search snippet exists
empty result -> return empty created IDs with coverage metadata
duplicate-only result -> return no new cards and include dedup summary
invalid request -> fail fast with clear validation error
```

## 13. Observability

Each mini-agent run should write an `agent_runs` record.

Minimum fields:

```json
{
  "agent_name": "collector_mini_agent",
  "tool_name": "collect_market_intel",
  "input_payload": {},
  "output_payload": {
    "created_source_ids": [],
    "created_card_ids": [],
    "deduped_candidate_count": 0
  },
  "status": "completed",
  "error_message": null
}
```

For MVP, this can be implemented after the core pipeline works. The collector code should still return enough information to populate this record.

## 14. Current MVP File Layout

```text
src/airs/mini_agents/__init__.py
src/airs/mini_agents/middle_east_collector.py
test/test_middle_east_collector.py
```

Responsibilities:

- `middle_east_collector.py`: complete lightweight Middle East collector example, including region config, query generation, URL normalization, event clustering, raw source creation, and intel card creation.
- `test_middle_east_collector.py`: executable examples for multi-topic query generation and duplicate-event handling.

This single-file structure is intentional for the first MVP. Once two or more regional collectors share enough duplicated code, extract common pieces into:

```text
src/airs/mini_agents/shared/query_planner.py
src/airs/mini_agents/shared/dedup.py
src/airs/mini_agents/shared/pipeline.py
```

## 15. MVP Test Cases

### Query planning

Given:

```text
region = middle_east
topic = social
vertical = gold_jewellery
query_focus = Ramadan wedding demand
```

Assert:

- At least 3 query work items.
- Each query contains region context.
- At least one query contains vertical context.
- Source types are preserved.

### Deduplication

Given two candidates:

```text
Pandora opens new flagship store in Dubai
Pandora launches Dubai flagship jewellery store
```

Assert:

- One event cluster.
- Two raw sources.
- One intel card.
- `source_count = 2`.

### Pipeline

Given static search provider returns two duplicate event candidates.

Assert:

- `created_source_ids` length is 2.
- `created_card_ids` length is 1.
- The intel card metadata contains `primary_source_id`.
- The intel card metadata contains `supporting_source_ids`.

### MCP tool

Given valid `collect_market_intel` input.

Assert:

- Response includes `request_id`.
- Response includes `created_source_ids`.
- Response includes `created_card_ids`.
- Response includes `coverage`.

## 16. Development Order

Build mini-agents in this order:

1. Domain models for collection request and result.
2. Query planner.
3. Search provider interface and static test provider.
4. URL normalization.
5. Candidate clustering.
6. Collector pipeline using in-memory repository.
7. Database repository integration.
8. MCP tool wrapper.
9. Real search provider.
10. Agent run logging.

Do not start with real web search. First make the pipeline deterministic with static candidates.

## 17. Definition of Done

The collector mini-agent is done for MVP when:

- It can accept a structured collection request.
- It can generate query work items.
- It can consume search candidates from a provider.
- It can deduplicate duplicate reports.
- It can create raw source documents.
- It can create draft intel cards.
- It can return created IDs.
- It can be called through an MCP tool.
- Unit tests cover query planning, deduplication, and pipeline behavior.

## 18. Future Mini-Agents

After the general collector works, add specialized mini-agents by changing source packs, not by rewriting the whole pipeline.

Possible future collectors:

```text
gold_macro_collector
competitor_official_collector
industry_trade_collector
social_trend_collector
marketplace_signal_collector
```

Each specialized collector should still follow the same contract:

```text
request -> query work items -> source candidates -> dedup -> raw_source -> intel_card -> IDs
```

Specialization should live in:

- source selection
- query templates
- parser hints
- source credibility scoring

It should not change the higher-level MCP contract unless necessary.
