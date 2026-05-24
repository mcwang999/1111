# Strategic Insight Agent Version2

Version2 is a zero-dependency Node.js backend for strategic insight routing.

It accepts external intelligence cards from mock data, direct request payloads, or a future MCP tool adapter, then returns frontend-ready feeds for B/C users and A-level promoted insight cards.

## Requirements

- Node.js >= 12

## Run

```bash
cd version2
node server.js
```

On another computer after unzipping:

```bash
cd strategic-insight-agent-version2
npm start
```

No dependency installation is required.

Default API:

```text
http://127.0.0.1:8788
```

The demo UI is served from the same backend:

```text
http://127.0.0.1:8788/
```

This demo page includes login + work-suite shell + plugin panel.

## APIs

- `GET /health`
- `GET /mock-cards`
- `POST /normalize`
- `POST /analyze`
- `POST /push-preview`
- `GET /strategy`
- `PUT /strategy`
- `POST /strategy/extract`

## Supabase Cards Source

Cards can be loaded from Supabase `documents` table via PostgREST:

- table: `documents`
- filter: `doc_type = 'intel_card'`
- select: `id,title,content,source_url,metadata,created_at`

Environment variables:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_CARD_LIMIT` (optional, default: 50)

Run analysis against Supabase:

```bash
curl -s http://127.0.0.1:8788/analyze ^
  -H "Content-Type: application/json" ^
  -d "{\"source\":\"supabase\",\"strategy_keywords\":[\"年轻人消费\",\"ESG\",\"实验室钻石\"]}"
```

If `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are configured, omitting `source` will default to Supabase.

## Strategy Input

### Manual strategy keywords

`PUT /strategy` updates the in-memory strategy keywords used by `/analyze` when request payload does not provide `strategy_keywords`.

```bash
curl -s http://127.0.0.1:8788/strategy ^
  -X PUT -H "Content-Type: application/json" ^
  -d "{\"strategy_keywords\":[\"年轻人消费\",\"ESG\",\"实验室钻石\"]}"
```

### Extract keywords from meeting minutes

`POST /strategy/extract` accepts meeting minutes text and returns extracted strategy keywords.

- `method`: `"textrank"` (default) or `"freq"`
- `max_keywords`: default 8
- `apply`: `true` to also update current strategy keywords

```bash
curl -s http://127.0.0.1:8788/strategy/extract ^
  -H "Content-Type: application/json" ^
  -d "{\"minutes\":\"...会议纪要文本...\",\"method\":\"textrank\",\"max_keywords\":8,\"apply\":true}"
```

Model choice:

- TextRank (Mihalcea & Tarau, 2004) is unsupervised, needs no labeled data, and works well when you want a deterministic, explainable baseline without external dependencies.
- Freq is a fast fallback for very short minutes and as a sanity-check baseline.

References / projects:

- Rada Mihalcea, Paul Tarau. TextRank: Bringing Order into Texts. EMNLP 2004.
- https://github.com/summanlp/textrank
- https://github.com/LIAAD/yake
- https://github.com/MaartenGr/KeyBERT (stronger semantic keywords but requires embedding models)

Feishu integration (reserved seam):

- Push minutes into `/strategy/extract` daily via a scheduler (Windows Task Scheduler / cron / CI), or implement a Feishu bot/webhook that forwards the minutes text to this endpoint.

## Test

```bash
npm test
```

If the API test reports that port `8788` is already in use, stop the existing process or run:

```bash
PORT=8790 npm start
```

## Node-by-node Testing

Run these from `version2`:

```bash
node inspect-node.js normalize
node inspect-node.js filter --card 0
node inspect-node.js distribute --card 0
node inspect-node.js tags --card 0
node inspect-node.js insights
node inspect-node.js feeds
node inspect-node.js a --pushes '[{"insight_id":"B:market:north_america_lab_diamond_price_drop_2026_q2","actor_tag":"B1_market","action":"push"},{"insight_id":"B:market:north_america_lab_diamond_price_drop_2026_q2","actor_tag":"B2_product","action":"push"}]'
```

Use `--card 1`, `--card 2`, etc. to inspect different mock intelligence cards.

## Analyze Input

```json
{
  "source": "direct",
  "strategy_keywords": ["年轻人消费", "ESG", "实验室钻石"],
  "cards": [
    {
      "region": "us",
      "topic": "competition",
      "strategic_vertical": "lab_grown_diamond",
      "canonical_event_key": "north_america_lab_diamond_price_drop_2026_q2",
      "primary_source_id": "raw_us_001",
      "supporting_source_ids": ["raw_us_002"],
      "source_count": 2,
      "importance_score": 0.6,
      "confidence_score": 0.7,
      "title": "美国实验室钻石零售价继续下探",
      "summary": "美国多个线上珠宝平台下调实验室钻石定价。",
      "source_url": "https://example.com/us-lab-diamond"
    }
  ],
  "manual_pushes": [
    {
      "insight_id": "B:lab_grown_diamond:north_america_lab_diamond_price_drop_2026_q2",
      "actor_tag": "B1_market",
      "action": "push"
    }
  ]
}
```

## External Intelligence Card Fields

The teammate-owned source layer should ideally return these core fields:

- `region`
- `topic`
- `strategic_vertical`
- `canonical_event_key`
- `primary_source_id`
- `supporting_source_ids`
- `source_count`
- `importance_score`
- `confidence_score`

Recommended display and drill-down fields:

- `title`
- `summary` or `content`
- `source_url` or `evidence_url`

Missing display fields produce `normalization_warnings` but do not block the pipeline.

## MCP Adapter

`src/adapters/mcp-source.js` reserves the integration seam:

```js
async function fetchFromMcpTool({ strategyKeywords, sourceOptions }) {}
```

Once the MCP tool name, input schema, and output shape are known, update only this adapter. If the MCP tool returns the 9 core fields above, the rest of the pipeline does not need to change.

## Frontend Contract

`POST /analyze` returns:

- `cards.filtered / observed / rejected`
- `feeds.B1_market`
- `feeds.B2_product`
- `feeds.B3_supply_chain`
- `feeds.C1_east_asia`
- `feeds.C2_southeast_asia`
- `feeds.C3_north_america`
- `feeds.C4_oceania`
- `feeds.A`
- `insight_cards`
- `a_insight_cards`
- `ui_schema`

Every insight card includes stable ids, source cards, source ids, source URLs, scores, score explanation, push state, and UI hints.

## Dynamic Taxonomy (No hard-coded dictionaries)

Version2 builds all keyword dictionaries from the current cards corpus and the current `strategy_keywords`:

- `STRATEGY_EXPANSIONS`: generated from card co-occurrence signals, iteratively merged with the previous run in memory.
- `BUSINESS_TAGS` / `REGION_TAGS`: generated by extracting representative tokens from card subsets per tag category.
- `TOPIC_KEYWORDS`: generated from card subsets per topic to reduce data loss caused by hard-coded vocab.

The scoring and filtering thresholds remain unchanged; only the dictionary source becomes adaptive.
