# AIRS Overseas Strategic Intelligence Platform MVP Design

## 1. Purpose

AIRS is an internal overseas strategic intelligence platform for Chow Tai Fook Jewellery Group. It is not a one-off research report generator. It is a continuous intelligence pipeline that collects public market signals, turns them into traceable intelligence records, supports analysis and prediction agents, and distributes structured daily briefings to different business audiences.

The MVP focuses on three strategic verticals:

- Gold jewellery
- Jade, colored gems, and cultural jewellery
- Overseas retail channels

The MVP tracks five overseas regions:

- Asia Pacific
- Middle East
- Europe
- Americas
- Emerging markets

The platform serves three audience types:

- Regional leaders, who need all relevant topics in their region.
- Strategic vertical leaders, who need cross-region intelligence for one business vertical.
- Headquarters strategy team, who need high-priority opportunities, risks, anomalies, and forecasts.

## 2. Product Shape

AIRS should feel like an internal enterprise intelligence platform plus an automated briefing pipeline.

The daily flow is:

```text
Public sources
  -> collector mini-agents
  -> raw sources and draft intel cards
  -> shared intelligence database
  -> analysis and prediction agents
  -> structured briefings
  -> internal console and Feishu distribution
```

Every briefing item must be traceable back to its source documents, evidence snippets, analysis records, and prediction records. Feishu is only the delivery channel. The database and internal console remain the system of record.

## 3. Architecture

The recommended MVP architecture is:

```text
Internal Console
  -> Backend API / Workflow Orchestrator
  -> Agent Layer
       - Analysis Agent
       - Prediction Agent
       - Briefing Agent
  -> MCP Tool Server
       - collect_market_intel
       - search_intel_documents
       - build_context_pack
       - save_analysis
       - save_prediction
       - save_briefing
  -> Shared Intelligence DB
       - Supabase PostgreSQL
       - pgvector
  -> Feishu Distribution
```

Core principles:

- Agents do not pass long free-form context to each other.
- Agents exchange lightweight identifiers such as `task_id`, `doc_id`, `card_id`, and `briefing_id`.
- Public evidence is written to the shared database before it is used in analysis.
- Analysis, prediction, and briefing outputs must include evidence references.
- Collection capability is exposed as MCP tools so every higher-level agent can request additional evidence.

## 4. Shared Intelligence Database

The MVP should use Supabase PostgreSQL with pgvector. This keeps the implementation approachable while supporting both structured filtering and RAG-style semantic retrieval.

The database has four core tables in the MVP:

### `documents`

Stores all intelligence artifacts:

- `raw_source`
- `intel_card`
- `analysis`
- `prediction`
- `briefing`

Suggested fields:

```text
id
doc_type
title
content
metadata jsonb
embedding vector
source_url
created_by_agent
created_at
updated_at
```

Important metadata fields:

```text
region
country
topic
strategic_vertical
source_type
published_at
importance_score
confidence_score
evidence_quality
canonical_event_key
primary_source_id
supporting_source_ids
evidence_doc_ids
trace_ids
```

### `tasks`

Tracks work that agents need to perform:

```text
id
task_type
status
requested_by_agent
assigned_agent
input_payload jsonb
result_payload jsonb
created_at
updated_at
completed_at
```

Task types include:

- `collection`
- `analysis`
- `retrieval_request`
- `prediction`
- `briefing_generation`
- `feishu_distribution`

### `agent_runs`

Records every meaningful tool or agent execution for observability:

```text
id
agent_name
tool_name
input_payload jsonb
output_payload jsonb
status
error_message
created_at
completed_at
```

### `briefing_references`

Keeps briefing provenance explicit:

```text
id
briefing_doc_id
briefing_item_id
referenced_doc_id
reference_type
created_at
```

Reference types include:

- `raw_source`
- `intel_card`
- `analysis`
- `prediction`

## 5. Collector Mini-Agent

Collector mini-agents are lightweight retrieval executors. They should reuse the engineering ideas from the previous CrewAI research agent, but only inside the collection capability.

The collector's responsibilities:

- Generate query TODOs from a collection request.
- Execute multi-source search.
- Respect simple TODO dependencies.
- Normalize and deduplicate URLs.
- Deduplicate by title and snippet similarity.
- Perform lightweight event-level deduplication.
- Extract title, URL, source name, published time, snippet, and evidence quote.
- Create `raw_source` documents.
- Create draft `intel_card` documents.
- Return created document IDs to the calling agent.

The collector does not:

- Make final strategic judgments.
- Decide whether evidence is sufficient.
- Produce forecasts.
- Generate briefings.
- Merge distinct events into one card.

The public MCP interface should stay simple:

```text
collect_market_intel(region, topic, strategic_vertical, time_window, query_focus, source_types)
```

Expected response:

```json
{
  "request_id": "retrieval_001",
  "created_source_ids": ["src_101", "src_102"],
  "created_card_ids": ["card_201", "card_202"],
  "coverage": {
    "regions": ["middle_east"],
    "source_types": ["news", "industry", "social_trend"],
    "time_window": "14d"
  }
}
```

## 6. Collection Pipeline

The collector mini-agent runs this lightweight internal pipeline:

```text
Collection request
  -> query TODO planner
  -> multi-source search
  -> candidate normalization
  -> URL deduplication
  -> title/snippet similarity deduplication
  -> lightweight event clustering
  -> selective content extraction
  -> raw source creation
  -> draft intel card creation
  -> return doc IDs
```

The collector may use these source categories:

- General web search
- News search or GDELT
- Jewellery industry media
- Competitor official sites and press pages
- Gold and macro sources
- Social trend tools
- Marketplace or ecommerce search surfaces

The first MVP should not overbuild source coverage. A practical starting set is:

- One general web search provider
- GDELT or one news search provider
- A small whitelist of jewellery industry media
- Competitor official sites or press pages
- One trend source such as Google Trends, TikTok Creative Center, or Meta Ad Library

## 7. Deduplication Strategy

Deduplication must go beyond URL matching.

The MVP uses three levels:

### URL normalized hash

Normalize URL before hashing:

- Remove tracking parameters.
- Normalize scheme and host.
- Remove trailing slash.
- Prefer canonical URL when available.

### Title and snippet similarity

Use title plus snippet to catch near-duplicate search results before fetching full pages.

Examples of duplicates:

```text
Pandora opens new flagship store in Dubai
Pandora launches Dubai flagship jewellery store
```

### Lightweight event-level deduplication

Generate `canonical_event_key` from:

```text
main entity + region/country + action/event type + approximate time window
```

Example:

```text
pandora|dubai|opens_flagship_store|2026-05
```

Multiple raw sources can support one intel card:

```text
raw_source_1
raw_source_2
raw_source_3
  -> one intel_card
```

Repeated sources should not simply be discarded. They should become supporting sources and can increase confidence.

## 8. Analysis Agent

The Analysis Agent reads intelligence from the shared database and produces topic-specific interpretations.

It can call:

```text
search_intel_documents
build_context_pack
collect_market_intel
save_analysis
```

The analysis flow is:

```text
analysis task
  -> retrieve current intel cards and sources
  -> build context pack
  -> judge evidence sufficiency
  -> request extra collection if needed
  -> write analysis document
```

The Analysis Agent owns the decision to request supplementary retrieval. The collector only executes the retrieval request.

Every analysis output must include:

```text
conclusion
impact_assessment
risk_or_opportunity
affected_region
affected_strategic_vertical
recommended_actions
confidence_score
evidence_sufficiency
evidence_doc_ids
```

Evidence sufficiency values:

- `sufficient`
- `partial`
- `insufficient_needs_retrieval`

## 9. Prediction Agent

The Prediction Agent turns recent intelligence and historical signals into short-horizon strategic forecasts.

It can call:

```text
search_intel_documents
build_context_pack
get_trend_snapshot
collect_market_intel
save_prediction
```

Forecast examples:

- Next 30-day demand signal for Middle East gold jewellery.
- Competitive pressure in Asia Pacific retail channels.
- Social trend momentum for jade, colored gems, and cultural jewellery.
- Gold price volatility risk and possible impact on product and inventory strategy.

Every prediction output must include:

```text
prediction_type
forecast_horizon
prediction
confidence_score
evidence_doc_ids
risk_factors
suggested_actions
```

Prediction documents are stored in `documents` with `doc_type = prediction`, so they can be reused by the Briefing Agent.

## 10. Briefing Agent

The Briefing Agent composes structured daily briefings from stored intel cards, analyses, and predictions.

It does not perform broad web search directly. If it finds an evidence gap, it creates or requests a retrieval task through the same collection interface.

Briefing types:

### Regional leader briefing

Scope:

```text
one region + all relevant topics and strategic verticals
```

Sections:

- Executive summary
- Key opportunities
- Key risks
- Competitive moves
- Product and consumer signals
- Platform, social, and channel signals
- Macro or gold price watch
- Recommended actions
- Source references

### Strategic vertical leader briefing

Scope:

```text
one strategic vertical + all overseas regions
```

Sections:

- Executive summary
- Regional signal comparison
- Opportunities
- Risks
- Trend and forecast
- Recommended actions
- Source references

### Headquarters strategy briefing

Scope:

```text
global high-priority opportunities, risks, anomalies, and forecasts
```

Sections:

- Global executive summary
- Top opportunities
- Top risks
- Anomaly watch
- Forecast highlights
- Decisions needed
- Source references

## 11. MCP Tool Surface

The MVP MCP tools should be small and reusable.

### Collection

```text
collect_market_intel(params)
```

Runs collector mini-agent logic and writes raw sources and draft intel cards.

### Search

```text
search_intel_documents(query, filters, top_k)
```

Combines metadata filtering and pgvector semantic search.

### Context Building

```text
build_context_pack(task_type, query, filters, doc_ids)
```

Builds a bounded context package for analysis, prediction, or briefing.

### Trend Snapshot

```text
get_trend_snapshot(filters, time_window)
```

Returns basic counts and distributions across topic, region, strategic vertical, confidence, and importance.

### Persistence

```text
save_analysis(payload)
save_prediction(payload)
save_briefing(payload)
```

Writes outputs with explicit evidence references.

## 12. Feishu Distribution

Feishu is a distribution layer, not the source of truth.

The MVP can use a webhook or CLI integration to send:

- Regional briefings to regional groups.
- Strategic vertical briefings to product or channel owners.
- Headquarters briefing to strategy stakeholders.

After distribution, write back:

```text
feishu_message_id
feishu_chat_id
delivery_status
delivered_at
```

The internal console should still show the complete briefing and provenance trail.

## 13. MVP Scope

The first build should include:

- Supabase PostgreSQL with pgvector.
- `documents`, `tasks`, `agent_runs`, and `briefing_references` tables.
- One general `collect_market_intel` MCP tool.
- One `search_intel_documents` MCP tool.
- One `build_context_pack` MCP tool.
- One Analysis Agent.
- One Prediction Agent.
- One Briefing Agent.
- Feishu webhook or CLI distribution.
- A simple internal console for briefing review and source traceability.

The first build should avoid:

- Large-scale scraping.
- Many specialized collectors.
- Complex task scheduling.
- Full enterprise permissioning.
- Overly complex trend modeling.
- A fully autonomous collector that decides analysis sufficiency.

## 14. Success Criteria

The MVP is successful if it can:

- Collect public overseas market signals from multiple sources.
- Deduplicate repeated reports into event-level intel cards.
- Store all evidence in a shared SQL and vector-searchable database.
- Let analysis and prediction agents request supplementary collection.
- Generate at least one regional briefing and one strategic vertical briefing.
- Show source traceability for every briefing item.
- Distribute a structured briefing through Feishu.
- Demonstrate that agents collaborate through MCP tools and shared memory instead of long context passing.

## 15. Open Decisions

These decisions can be finalized during implementation planning:

- Which web search provider to use first.
- Whether the first trend source is Google Trends, TikTok Creative Center, or Meta Ad Library.
- Whether the internal console should be Streamlit, Gradio, or a lightweight web app.
- Whether collector mini-agent logic is implemented as plain Python functions or a small CrewAI/LangGraph internal flow.

The recommended MVP default is:

```text
FastAPI backend
Supabase PostgreSQL + pgvector
plain Python collector pipeline behind MCP tools
Streamlit or Gradio internal console
Feishu webhook for distribution
```
