/** Matching the documents table schema in Supabase. */
export interface Document {
  id: string;
  doc_type: "intel_card" | "raw_source" | "social_signal_card";
  title: string;
  content: string;
  source_url: string;
  created_by_agent: string;
  created_at: string;
  metadata: {
    region?: string;
    topic?: string;
    impact_tags?: string[];
    strategic_vertical?: string;
    event_key?: string;
    primary_source_id?: string;
    supporting_source_ids?: string[];
    source_name?: string;
    published_at?: string;
    relevance_score?: number;
    confidence_score?: number;
    importance_score?: number;
    dedup_method?: string;
    canonical_event_key?: string;
    source_count?: number;
    llm_relevance_score?: number;
    llm_keep_reason?: string;
    signal_type?: string;
    signal_start_date?: string;
    signal_end_date?: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    [key: string]: any;
  };
}

export interface AgentRun {
  id: string;
  agent_name: string;
  tool_name: string;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown>;
  status: string;
  error_message?: string;
  created_at: string;
}

export interface DocumentFilters {
  doc_type?: string;
  region?: string;
  topic?: string;
  impact_tags?: string[];
  strategic_vertical?: string;
  created_by_agent?: string;
  page?: number;
  limit?: number;
}

export interface Stats {
  total_cards: number;
  total_sources: number;
  total_runs: number;
  by_region: Record<string, number>;
  by_topic: Record<string, number>;
  by_agent: Record<string, number>;
  recent_runs: AgentRun[];
}

export interface ApiResponse<T> {
  data: T[];
  count: number;
  page: number;
  limit: number;
}

// ---------------------------------------------------------------------------
// Labels for display (matching base_collector.py)
// ---------------------------------------------------------------------------
export const REGION_LABELS: Record<string, string> = {
  middle_east: "Middle East",
  americas: "Americas",
  asia_pacific: "Asia Pacific",
  europe: "Europe",
  emerging_markets: "Emerging Markets",
};

export const TOPIC_LABELS: Record<string, string> = {
  competition: "Competitor Moves",
  product: "Product & Design",
  channel: "Retail Channels",
  social: "Social & Community",
  regulation: "Regulation & Policy",
};

export const VERTICAL_LABELS: Record<string, string> = {
  gold_jewellery: "Gold Jewellery",
  jade_colored_gems_cultural_jewellery: "Jade & Colored Gems",
  overseas_retail_channels: "Overseas Retail",
  other: "Other",
};

export const IMPACT_TAG_LABELS: Record<string, string> = {
  supply_chain: "Supply Chain",
  compliance: "Compliance",
  cost: "Cost",
  pricing: "Pricing",
  inventory: "Inventory",
  logistics: "Logistics",
  sourcing: "Sourcing",
  retail_operations: "Retail Operations",
  consumer_demand: "Consumer Demand",
  brand_reputation: "Brand Reputation",
  gold_price: "Gold Price",
};

export const AGENT_LABELS: Record<string, string> = {
  middle_east_collector: "Middle East",
  americas_collector: "Americas",
  asia_pacific_collector: "Asia Pacific",
  europe_collector: "Europe",
  emerging_markets_collector: "Emerging Markets",
  social_media_agent: "Social Media",
};

export type SortField = "created_at" | "title" | "metadata->>published_at";
export type SortDir = "asc" | "desc";
