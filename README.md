# AIRS — Overseas Strategic Intelligence Platform

POLARIS is an AI-powered strategic intelligence platform. It continuously collects, curates, and delivers jewellery industry intelligence across global markets — from competitor moves and regulatory changes to social media signals — and pushes daily briefings to Feishu (Lark).

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Sources                              │
│  Tavily (Web News) · X/Twitter · Reddit · (Instagram)          │
└──────────┬──────────────┬──────────────┬───────────────────────┘
           │              │              │
           ▼              ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  MCP Clients │  │  MCP Clients │  │  MCP Clients │
│  (Tavily)    │  │  (X Agent)   │  │  (Reddit)    │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       ▼                 ▼                 ▼
┌──────────────────────────────────────────────────────────────┐
│                    Mini-Agent Layer                            │
│                                                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐  │
│  │ Regional         │  │ Social Media    │  │ Feishu       │  │
│  │ Collectors       │  │ Agent           │  │ Briefing     │  │
│  │ (5 regions)      │  │                 │  │ Agent        │  │
│  │                  │  │ X + Reddit →    │  │              │  │
│  │ Tavily/X/Reddit  │  │ Social Signals  │  │ Supabase →   │  │
│  │ → LLM Curation  │  │ → LLM Analysis │  │ Feishu CLI  │  │
│  │ → Intel Cards   │  │ → Signal Cards  │  │ → Briefing   │  │
│  └────────┬────────┘  └───────┬────────┘  └──────┬───────┘  │
│           │                    │                    │          │
└───────────┼────────────────────┼────────────────────┼──────────┘
            │                    │                    │
            ▼                    ▼                    │
┌──────────────────────────────────────────┐         │
│              Supabase (PostgreSQL)        │         │
│                                          │         │
│  documents                               │         │
│  ├── intel_card (regional intelligence)  │         │
│  ├── social_signal_card                  │         │
│  ├── raw_source                          │         │
│  └── social_media_report                 │         │
│                                          │         │
│  agent_runs (pipeline audit log)         │         │
│  tasks (async job queue)                 │         │
│  briefing_references                    │         │
└──────────────────────────────────────────┘         │
                                                      │
                                                      ▼
                                            ┌─────────────────┐
                                            │   Feishu / Lark  │
                                            │   (Daily Briefing│
                                            │    via lark-cli)  │
                                            └─────────────────┘
```

## Project Structure

```
AIRS/
├── src/airs/
│   ├── mini_agents/                    # Core intelligence agents
│   │   ├── base_collector.py           # BaseCollector, SupabaseWriter, LLM curator
│   │   ├── middle_east_collector.py    # Middle East regional collector
│   │   ├── asia_pacific_collector.py   # Asia-Pacific regional collector
│   │   ├── europe_collector.py         # Europe regional collector
│   │   ├── americas_collector.py       # Americas regional collector
│   │   ├── emerging_markets_collector.py
│   │   ├── social_media_agent.py       # X + Reddit social signal agent
│   │   └── feishu_briefing_agent.py    # Supabase → Feishu briefing delivery
│   ├── mcp/                            # MCP (Model Context Protocol) clients
│   │   ├── base_mcp.py                # Synchronous stdio MCP client
│   │   ├── reddit_mcp.py              # Reddit search via MCP
│   │   └── x_mcp.py                   # X/Twitter search via MCP
│   └── providers/                      # Direct API providers
│       ├── x_search_provider.py        # X/Twitter HTTP search
│       ├── reddit_search_provider.py   # Reddit HTTP search
│       └── instagram_search_provider.py
├── test/
│   ├── agent_testers/                  # End-to-end pipeline tests
│   │   ├── smoke_pipeline.py           # Full pipeline: search → LLM → Supabase
│   │   ├── smoke_full_pipeline.py      # Multi-source pipeline
│   │   ├── smoke_all_collectors.py     # All 5 regional collectors
│   │   ├── test_social_media_agent.py
│   │   ├── test_middle_east_collector.py
│   │   └── test_briefing_orchestrator.py
│   └── tool_testers/                   # Individual tool smoke tests
│       ├── smoke_tavily.py
│       ├── smoke_x_mcp.py
│       ├── smoke_reddit.py
│       ├── smoke_social_agent.py
│       ├── smoke_read_supabase.py
│       └── smoke_feishu_briefing.py
├── dashboard/                           # Next.js web dashboard
├── docs/
│   └── supabase_schema.sql             # Database schema
├── .config.yaml                         # API keys & service config
├── pyproject.toml
└── requirements.txt
```

## Intelligence Topics & Verticals

### Topics
| Key | Label | Description |
|-----|-------|-------------|
| `competition` | Competitor and market player moves | Competitor actions, market share shifts, new entrants |
| `product` | Product, design, assortment changes | New collections, design trends, consumer preferences |
| `channel` | Retail channels and platforms | Store openings/closings, ecommerce, travel retail |
| `social` | Social media and community signals | Viral trends, consumer sentiment, influencer activity |
| `regulation` | Laws, policy, compliance | Import duties, trade rules, labeling requirements |

### Strategic Verticals
| Key | Label |
|-----|-------|
| `gold_jewellery` | Gold jewellery |
| `jade_colored_gems_cultural_jewellery` | Jade, colored gems, cultural jewellery |
| `overseas_retail_channels` | Jewellery retail |

### Impact Tags
`supply_chain` · `compliance` · `cost` · `pricing` · `inventory` · `logistics` · `sourcing` · `retail_operations` · `consumer_demand` · `brand_reputation` · `gold_price`

## Regional Collectors

Each regional collector follows the same pipeline:

1. **Search** — Multi-source queries (Tavily, X/Twitter, Reddit) with region-specific terms
2. **Deduplicate** — URL normalization and title similarity dedup
3. **LLM Curation** — OpenAI-compatible LLM decides keep/discard, assigns topic, impact tags, vertical
4. **Cluster** — Group related articles by event key
5. **Build Intel Cards** — Structured intelligence documents with metadata
6. **Persist** — Write to Supabase with dedup (upsert on `dedup_key`)

| Collector | Region | Key Markets |
|-----------|--------|-------------|
| `MiddleEastCollector` | `middle_east` | UAE, Saudi Arabia, Qatar, Kuwait |
| `AsiaPacificCollector` | `asia_pacific` | China, India, Japan, SE Asia |
| `EuropeCollector` | `europe` | UK, France, Italy, Switzerland |
| `AmericasCollector` | `americas` | USA, Canada, Brazil |
| `EmergingMarketsCollector` | `emerging_markets` | Africa, Turkey, CIS |

## Social Media Agent

The `SocialMediaAgent` searches X/Twitter and Reddit for jewellery-related discussions, then uses LLM analysis to produce **social signal cards** — structured insights about trends, sentiment, and business implications.

- Signal types: `trend` · `purchase_intent` · `pain_point` · `brand_sentiment` · `occasion` · `pricing_value`
- Outputs: `social_signal_card` documents in Supabase

## Feishu Briefing Agent

The `FeishuBriefingAgent` queries Supabase for intelligence cards matching a topic, formats them into a Chinese Markdown briefing, and delivers it via Feishu CLI (`lark-cli`).

```python
from airs.mini_agents.feishu_briefing_agent import FeishuBriefingAgent

agent = FeishuBriefingAgent.from_config()

# Dry run (format only, don't send)
result = agent.run(topic="competition", user_id="ou_xxx", dry_run=True)

# Send to Feishu
result = agent.run(topic="competition", user_id="ou_xxx", as_bot=True)
```

### Briefing Format
- 📋 Title with topic label (e.g. "竞品与市场动态")
- Impact tag distribution summary
- 🔴🟡🟢 Importance levels (high/medium/low)
- Per-card: region, vertical, impact tags, confidence, source links
- Social signal section (if available)

## Database Schema (Supabase)

### `documents` table
All intelligence artifacts are stored in a single `documents` table with `doc_type` discrimination:

| `doc_type` | Description |
|-----------|-------------|
| `raw_source` | Original search result (URL, snippet, metadata) |
| `intel_card` | Curated intelligence card (regional collectors) |
| `social_signal_card` | Social media signal card |
| `social_media_report` | Overall social media analysis report |

Key metadata fields: `topic`, `impact_tags`, `strategic_vertical`, `region`, `importance_score`, `confidence_score`, `dedup_key`, `briefing_status`

### Other tables
- `agent_runs` — Pipeline execution audit log
- `tasks` — Async job queue
- `briefing_references` — Links briefing docs to their source cards

## Configuration

Create `.config.yaml` in the project root:

```yaml
supabase:
  url: "https://your-project.supabase.co"
  service_role_key: "eyJ..."

tavily:
  api_key: "tvly-..."
  mcp_url: "https://mcp.tavily.com/mcp/?tavilyApiKey=tvly-..."

openai:
  api_key: "sk-..."
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o"

x_agent:
  api_key: "sk_..."
  mode: http
  mcp_url: "https://api.getxagent.com/sse"
  search_tool: twitter_search_tweets
  max_results: 10
  proxy_url: "http://127.0.0.1:7890"

reddit_mcp:
  command: "npx.cmd"
  args: "-y reddit-mcp-buddy"
  proxy_url: "http://127.0.0.1:7890"
  timeout_seconds: "60"
```

## Quick Start

### Install dependencies

```bash
pip install -e .
# or
pip install httpx pydantic tavily-python
```

### Set up Feishu CLI

```bash
npm install -g @larksuite/cli
npx skills add larksuite/cli -y -g
lark-cli config init --new
lark-cli auth login --recommend
```

### Run a regional collector

```bash
cd AIRS
python test/agent_testers/smoke_pipeline.py --region middle_east
```

### Run the social media agent

```bash
python test/tool_testers/smoke_social_agent.py
```

### Send a Feishu briefing

```bash
python test/tool_testers/smoke_feishu_briefing.py
```

### Read back from Supabase

```bash
python test/tool_testers/smoke_read_supabase.py
```

## Tech Stack

| Layer | Technology |
|-------|-------------|
| Language | Python 3.10+ |
| LLM | OpenAI-compatible API (DeepSeek, GPT-4o, etc.) |
| Search | Tavily, X/Twitter (MCP), Reddit (MCP) |
| Database | Supabase (PostgreSQL + pgvector) |
| Delivery | Feishu CLI (lark-cli) |
| Dashboard | Next.js (TypeScript) |

