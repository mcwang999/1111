# Dashboard Monitoring Console Design

## Goal

Replace the current dashboard-style demo pages with a practical intelligence card monitoring console for AIRS. The UI should help the user review daily market and social intelligence cards, filter by business metadata, identify cards that have not been briefed, and inspect source/deduplication metadata.

Human-facing labels should be Chinese. Stored metadata values remain English, such as `competition`, `pricing`, `social_signal_card`, and `briefing_status`.

## Recommended Scope

Build the monitoring console as the main dashboard experience:

- `/` becomes the primary monitoring workspace.
- `/cards` becomes a unified intelligence card feed.
- `/cards/[id]` becomes a reliable detail page for both market cards and social signal cards.
- API routes are updated only where needed to support dashboard filtering and stats.

The first version should avoid heavy workflow features such as bulk approval, Feishu sending actions, or direct Supabase mutations from the UI. Those can be layered on after the monitoring view is useful.

## Information Architecture

The console has four visible areas:

- Top status bar: page title, refresh action, total card counts, latest run time.
- KPI strip: market cards, social cards, raw sources, unbriefed cards, high-impact cards, recent agent runs.
- Filter rail or filter bar: card type, region, topic, impact tags, briefing status, signal type, agent, and sort order.
- Main card feed: compact intelligence cards with enough metadata to scan quickly.

The card feed should include both:

- `intel_card`
- `social_signal_card`

Raw sources remain inspectable through existing source pages, but they should not dominate the monitoring console.

## Card Display

Each card should show:

- Chinese type label for market intelligence or social signals.
- Title and short content preview.
- Topic label in Chinese, backed by English metadata.
- Impact tag labels in Chinese, backed by English metadata.
- Region or regions.
- Signal type for social cards.
- Briefing status.
- Published time and last seen time when available.
- Source/post count when available.
- Agent name.
- Confidence, relevance, or importance score when available.

Market cards emphasize `topic`, `impact_tags`, `region`, `strategic_vertical`, `published_at`, `source_count`, and `dedup_key`.

Social cards emphasize `signal_type`, `impact_tags`, `platforms`, `regions`, `sentiment`, `post_count`, `published_at`, and `dedup_key`.

## Labels

Display labels are Chinese, while metadata values remain English.

Topic labels should match the approved Chinese taxonomy:

- `competition`: competitor/market moves
- `product`: product trends
- `channel`: channel changes
- `social`: social sentiment
- `regulation`: regulation and policy

Impact tag labels should match the approved Chinese business impact taxonomy:

- `supply_chain`
- `cost`
- `pricing`
- `inventory`
- `logistics`
- `sourcing`
- `compliance`
- `retail_operations`
- `consumer_demand`
- `brand_reputation`
- `gold_price`

Signal type labels should be added for the social agent values already present in data. Unknown values should fall back to the raw English key.

## API Changes

Update `/api/stats` so it reports:

- `market_cards`
- `social_cards`
- `raw_sources`
- `unbriefed_cards`
- `total_runs`
- breakdowns by region, topic, impact tag, card type, and agent
- recent agent runs

Update `/api/documents` so it can filter by:

- `doc_type`
- `region`
- `topic`
- `impact_tags`
- `strategic_vertical`
- `created_by_agent`
- `briefing_status`
- `signal_type`
- optional date range using `metadata.published_at` when available

Sorting should support created time, published time, last seen time, importance, confidence, and relevance where possible.

## Detail Page

The detail page should work for both `intel_card` and `social_signal_card`.

It should display the card content, Chinese label chips, source URL, top-level `source_url`, metadata fields, and operational fields such as `dedup_key`, `briefing_status`, `briefed_at`, `first_seen_at`, and `last_seen_at`.

The existing source URL issue should be fixed by reading `doc.source_url` as well as metadata source fields.

## Visual Style

Use a dense operational interface rather than a marketing landing page:

- restrained color palette with multiple semantic colors, not a one-note gradient theme
- compact table/list cards
- stable card dimensions and readable metadata chips
- no decorative hero section
- no nested cards
- card radius at 8px or less

The interface should feel like a monitoring desk: fast to scan, calm, and practical.

## Testing

Run dashboard validation after implementation:

- `npm.cmd run lint` from `dashboard`
- `npm.cmd run build` from `dashboard` when feasible
- launch the dev server and inspect the main monitoring page in browser
- verify that market and social cards both appear when Supabase has matching data

## Out Of Scope For This Pass

- editing Supabase rows from the dashboard
- sending Feishu messages from the dashboard
- bulk approve/reject workflows
- authentication or user roles
- charts that require new dependencies
