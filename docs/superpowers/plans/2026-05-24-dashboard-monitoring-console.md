# Dashboard Monitoring Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current dashboard demo with a practical AIRS intelligence card monitoring console.

**Architecture:** Keep the existing Next.js app and Supabase API route structure. Centralize display labels and metadata helpers in `src/lib/types.ts`, extend API routes for monitoring filters/stats, then rebuild `/`, `/cards`, and `/cards/[id]` around a unified market/social card model.

**Tech Stack:** Next.js 16, React 19, Tailwind CSS 4, Supabase JS, TypeScript.

---

## File Structure

- Modify `dashboard/src/lib/types.ts`: add richer metadata fields, Chinese display labels, doc type labels, briefing status labels, signal type labels, and helper functions.
- Modify `dashboard/src/app/api/stats/route.ts`: return monitoring-oriented counts and breakdowns.
- Modify `dashboard/src/app/api/documents/route.ts`: add filters and sorting for `briefing_status`, `signal_type`, date range, and unified card views.
- Modify `dashboard/src/app/page.tsx`: replace demo overview with monitoring console.
- Modify `dashboard/src/app/cards/page.tsx`: replace intel-only list with unified market/social feed and filters.
- Modify `dashboard/src/app/cards/[id]/page.tsx`: make details reliable for both card types and fix top-level `source_url`.
- Modify `dashboard/src/app/globals.css`: adjust the app visual base for a dense monitoring platform.
- Read `dashboard/node_modules/next/dist/docs/` before code changes if touching framework-specific APIs.

---

### Task 1: Metadata Types And Labels

**Files:**
- Modify: `dashboard/src/lib/types.ts`

- [ ] **Step 1: Extend `Document.metadata`**

Add optional fields used by the new Supabase lifecycle metadata:

```ts
briefing_status?: string;
briefed_at?: string;
briefing_ids?: string[];
first_seen_at?: string;
last_seen_at?: string;
dedup_key?: string;
source_published_at_range?: {
  start?: string;
  end?: string;
};
platforms?: string[];
regions?: string[];
sentiment?: string;
post_count?: number;
source_count?: number;
importance_score?: number;
relevance_score?: number;
confidence_score?: number;
```

- [ ] **Step 2: Add monitoring stat types**

Replace the old `Stats` shape with fields the dashboard needs:

```ts
export interface Stats {
  market_cards: number;
  social_cards: number;
  raw_sources: number;
  unbriefed_cards: number;
  high_impact_cards: number;
  total_runs: number;
  by_region: Record<string, number>;
  by_topic: Record<string, number>;
  by_impact_tag: Record<string, number>;
  by_doc_type: Record<string, number>;
  by_agent: Record<string, number>;
  latest_run_at?: string;
  recent_runs: AgentRun[];
}
```

- [ ] **Step 3: Replace display labels with Chinese labels**

Keep English metadata keys and display Chinese values:

```ts
export const TOPIC_LABELS: Record<string, string> = {
  competition: "竞争动态",
  product: "产品趋势",
  channel: "渠道变化",
  social: "社媒舆情",
  regulation: "法规政策",
};

export const IMPACT_TAG_LABELS: Record<string, string> = {
  supply_chain: "供应链影响",
  cost: "成本影响",
  pricing: "定价影响",
  inventory: "库存影响",
  logistics: "物流影响",
  sourcing: "采购/原料影响",
  compliance: "合规影响",
  retail_operations: "零售运营影响",
  consumer_demand: "消费者需求影响",
  brand_reputation: "品牌声誉影响",
  gold_price: "金价影响",
};
```

- [ ] **Step 4: Add helper functions**

Add small helpers to avoid repeating fallback logic in pages:

```ts
export function labelFor(labels: Record<string, string>, value?: string) {
  if (!value) return "未标注";
  return labels[value] || value;
}

export function getCardPublishedAt(doc: Document) {
  return doc.metadata?.published_at || doc.metadata?.signal_end_date || doc.created_at;
}

export function isCardDocument(doc: Document) {
  return doc.doc_type === "intel_card" || doc.doc_type === "social_signal_card";
}
```

- [ ] **Step 5: Run type validation**

Run:

```powershell
cd dashboard
npm.cmd run lint
```

Expected at this stage: lint may fail because pages still expect the old `Stats` shape. The next tasks fix those usages.

---

### Task 2: Monitoring API Support

**Files:**
- Modify: `dashboard/src/app/api/stats/route.ts`
- Modify: `dashboard/src/app/api/documents/route.ts`

- [ ] **Step 1: Update stats counting**

Implement card-aware counts:

```ts
const marketCards = (counts ?? []).filter((d) => d.doc_type === "intel_card").length;
const socialCards = (counts ?? []).filter((d) => d.doc_type === "social_signal_card").length;
const rawSources = (counts ?? []).filter((d) => d.doc_type === "raw_source").length;
```

Count unbriefed cards from `metadata->>briefing_status` for `intel_card` and `social_signal_card`. Treat empty/missing status and `new` as unbriefed.

- [ ] **Step 2: Add breakdown helpers**

Create local helper functions in `stats/route.ts`:

```ts
function increment(map: Record<string, number>, key?: string | null) {
  const normalized = key || "unknown";
  map[normalized] = (map[normalized] || 0) + 1;
}

function incrementArray(map: Record<string, number>, values?: unknown) {
  if (!Array.isArray(values)) return;
  for (const value of values) {
    if (typeof value === "string" && value) increment(map, value);
  }
}
```

Use one full documents metadata query to compute `by_region`, `by_topic`, `by_impact_tag`, `by_doc_type`, and `by_agent`.

- [ ] **Step 3: Add document filters**

In `/api/documents`, support:

```ts
const briefingStatus = searchParams.get("briefing_status");
if (briefingStatus) query = query.filter("metadata->>briefing_status", "eq", briefingStatus);

const signalType = searchParams.get("signal_type");
if (signalType) query = query.filter("metadata->>signal_type", "eq", signalType);

const publishedFrom = searchParams.get("published_from");
if (publishedFrom) query = query.gte("metadata->>published_at", publishedFrom);

const publishedTo = searchParams.get("published_to");
if (publishedTo) query = query.lte("metadata->>published_at", publishedTo);
```

- [ ] **Step 4: Add unified card mode**

Support `doc_type=cards` as shorthand for both card types:

```ts
if (docType === "cards") {
  query = query.in("doc_type", ["intel_card", "social_signal_card"]);
} else if (docType) {
  query = query.eq("doc_type", docType);
}
```

- [ ] **Step 5: Extend sorting**

Add sort fields:

```ts
last_seen_at: "metadata->>last_seen_at",
importance_score: "metadata->>importance_score",
relevance_score: "metadata->>relevance_score",
confidence_score: "metadata->>confidence_score",
```

- [ ] **Step 6: Validate API route types**

Run:

```powershell
cd dashboard
npm.cmd run lint
```

Expected: route-level TypeScript/ESLint issues are resolved, remaining failures point at pages that still use old shapes.

---

### Task 3: Dashboard Home Monitoring Console

**Files:**
- Modify: `dashboard/src/app/page.tsx`
- Modify: `dashboard/src/app/globals.css`

- [ ] **Step 1: Replace demo home page**

Build a client component that fetches `/api/stats` and `/api/documents?doc_type=cards&limit=8&sort=last_seen_at`.

The page should render:

- title `AIRS 情报监测台`
- refresh button
- KPI strip
- priority feed
- region/topic/tag distributions
- recent agent run table

- [ ] **Step 2: Implement KPI cards**

Render compact KPI cards for:

```ts
[
  { label: "市场情报", value: stats.market_cards },
  { label: "社媒信号", value: stats.social_cards },
  { label: "待简报", value: stats.unbriefed_cards },
  { label: "原始来源", value: stats.raw_sources },
]
```

- [ ] **Step 3: Implement priority feed rows**

Each row should display:

- type label
- title
- topic or signal type
- impact tag chips
- region/platform metadata
- published time
- last seen time
- briefing status

- [ ] **Step 4: Update global visual base**

Use a restrained monitoring palette with neutral background, crisp borders, and card radius no larger than 8px for new UI components.

- [ ] **Step 5: Validate**

Run:

```powershell
cd dashboard
npm.cmd run lint
```

Expected: home page compiles with the new `Stats` shape.

---

### Task 4: Unified Cards Feed

**Files:**
- Modify: `dashboard/src/app/cards/page.tsx`

- [ ] **Step 1: Change default query to unified cards**

Replace the old `doc_type=intel_card` query with:

```ts
const params = new URLSearchParams({ doc_type: "cards", limit: "20" });
```

- [ ] **Step 2: Add card type segmented filter**

Supported values:

```ts
[
  ["cards", "全部卡片"],
  ["intel_card", "市场情报"],
  ["social_signal_card", "社媒信号"],
]
```

- [ ] **Step 3: Add briefing status and signal type filters**

Read and write these URL params:

```ts
const briefingStatus = searchParams.get("briefing_status") || "";
const signalType = searchParams.get("signal_type") || "";
```

Send them to `/api/documents` when selected.

- [ ] **Step 4: Render market and social card metadata**

Market cards show `topic`, `region`, `strategic_vertical`, and `source_count`.

Social cards show `signal_type`, `platforms`, `regions`, `sentiment`, and `post_count`.

Both show `impact_tags`, `briefing_status`, `published_at`, and `last_seen_at`.

- [ ] **Step 5: Validate**

Run:

```powershell
cd dashboard
npm.cmd run lint
```

Expected: `/cards` compiles and no longer hardcodes intel-only behavior.

---

### Task 5: Card Detail Page

**Files:**
- Modify: `dashboard/src/app/cards/[id]/page.tsx`

- [ ] **Step 1: Inspect current detail page**

Read the full file and preserve useful fetch/error handling behavior.

- [ ] **Step 2: Fix source URL display**

Use:

```ts
const sourceUrl = doc.source_url || meta.source_url || meta.url;
```

Render a link only when `sourceUrl` is present.

- [ ] **Step 3: Add metadata sections**

Render:

- topic and impact tag chips
- signal type for social cards
- briefing status
- published time
- first seen time
- last seen time
- dedup key
- agent name
- source/post count

- [ ] **Step 4: Render raw metadata table**

Render stable key/value rows for metadata fields so operational debugging remains possible.

- [ ] **Step 5: Validate**

Run:

```powershell
cd dashboard
npm.cmd run lint
```

Expected: detail page compiles for both `intel_card` and `social_signal_card`.

---

### Task 6: End-To-End Dashboard Verification

**Files:**
- No required source edits unless verification finds a defect.

- [ ] **Step 1: Run lint**

```powershell
cd dashboard
npm.cmd run lint
```

Expected: exits successfully.

- [ ] **Step 2: Run build**

```powershell
cd dashboard
npm.cmd run build
```

Expected: Next.js production build completes. If Supabase env config blocks build, document the exact error.

- [ ] **Step 3: Start dev server**

```powershell
cd dashboard
npm.cmd run dev
```

Expected: local Next server starts on `http://localhost:3000` or another available port.

- [ ] **Step 4: Browser smoke test**

Open:

- `http://localhost:3000`
- `http://localhost:3000/cards`

Verify:

- Chinese labels render correctly.
- Market and social cards both appear when data exists.
- Filters update the URL and fetch results.
- Detail links open and source URLs are usable.

---

## Self-Review

Spec coverage:

- Home monitoring console: Task 3.
- Unified card feed: Task 4.
- Detail page: Task 5.
- API filtering and stats: Task 2.
- Chinese labels with English metadata: Task 1.
- Validation: Task 6.

Placeholder scan:

- No unfinished-marker terms or intentionally vague implementation steps remain.

Type consistency:

- `Stats` fields introduced in Task 1 are consumed by Task 3.
- `/api/documents?doc_type=cards` introduced in Task 2 is consumed by Task 3 and Task 4.
- Metadata fields introduced in Task 1 are displayed in Task 4 and Task 5.
