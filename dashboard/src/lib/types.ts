/** Matching the documents table schema in Supabase. */
export interface Document {
  id: string;
  doc_type: "intel_card" | "raw_source" | "social_signal_card";
  title: string;
  content: string;
  source_url: string;
  created_by_agent: string;
  created_at: string;
  metadata: DocumentMetadata;
}

export interface DocumentMetadata {
  region?: string;
  regions?: string[];
  topic?: string;
  impact_tags?: string[];
  strategic_vertical?: string;
  event_key?: string;
  primary_source_id?: string;
  supporting_source_ids?: string[];
  source_name?: string;
  source_url?: string;
  url?: string;
  published_at?: string;
  source_published_at_range?: {
    start?: string;
    end?: string;
  };
  relevance_score?: number;
  confidence_score?: number;
  importance_score?: number;
  dedup_method?: string;
  dedup_key?: string;
  canonical_event_key?: string;
  source_count?: number;
  post_count?: number;
  llm_relevance_score?: number;
  llm_keep_reason?: string;
  signal_type?: string;
  signal_start_date?: string;
  signal_end_date?: string;
  platforms?: string[];
  sentiment?: string;
  briefing_status?: string;
  briefed_at?: string;
  briefing_ids?: string[];
  first_seen_at?: string;
  last_seen_at?: string;
  normalized_source_url?: string;
  raw_published_at?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
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
  briefing_status?: string;
  signal_type?: string;
  published_from?: string;
  published_to?: string;
  page?: number;
  limit?: number;
}

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

export interface ApiResponse<T> {
  data: T[];
  count: number;
  page: number;
  limit: number;
}

export const REGION_LABELS: Record<string, string> = {
  middle_east: "中东",
  americas: "美洲",
  asia_pacific: "亚太",
  europe: "欧洲",
  emerging_markets: "新兴市场",
};

export const TOPIC_LABELS: Record<string, string> = {
  competition: "竞争动态",
  product: "产品趋势",
  channel: "渠道变化",
  social: "社媒舆情",
  regulation: "法规政策",
};

export const VERTICAL_LABELS: Record<string, string> = {
  gold_jewellery: "黄金珠宝",
  jade_colored_gems_cultural_jewellery: "玉石彩宝文化珠宝",
  overseas_retail_channels: "海外零售渠道",
  other: "其他",
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

export const DOC_TYPE_LABELS: Record<string, string> = {
  cards: "全部卡片",
  intel_card: "市场情报",
  social_signal_card: "社媒信号",
  raw_source: "原始来源",
};

export const BRIEFING_STATUS_LABELS: Record<string, string> = {
  new: "待简报",
  pending: "待简报",
  briefed: "已简报",
  skipped: "已跳过",
  archived: "已归档",
};

export const SIGNAL_TYPE_LABELS: Record<string, string> = {
  trend: "趋势",
  purchase_intent: "购买意向",
  pain_point: "痛点",
  brand_sentiment: "品牌情绪",
  occasion: "消费场景",
  pricing_value: "价格价值",
};

export const SENTIMENT_LABELS: Record<string, string> = {
  positive: "正面",
  negative: "负面",
  neutral: "中性",
  mixed: "混合",
};

export const AGENT_LABELS: Record<string, string> = {
  middle_east_collector: "中东 Agent",
  americas_collector: "美洲 Agent",
  asia_pacific_collector: "亚太 Agent",
  europe_collector: "欧洲 Agent",
  emerging_markets_collector: "新兴市场 Agent",
  social_media_agent: "社媒 Agent",
};

export type SortField =
  | "created_at"
  | "title"
  | "published_at"
  | "last_seen_at"
  | "importance_score"
  | "relevance_score"
  | "confidence_score";

export type SortDir = "asc" | "desc";

export function labelFor(labels: Record<string, string>, value?: string) {
  if (!value) return "未标注";
  return labels[value] || value;
}

export function getCardPublishedAt(doc: Document) {
  return doc.metadata?.published_at || doc.metadata?.signal_end_date || doc.created_at;
}

export function getCardLastSeenAt(doc: Document) {
  return doc.metadata?.last_seen_at || doc.created_at;
}

export function getBriefingStatus(doc: Document) {
  return doc.metadata?.briefing_status || "new";
}

export function isCardDocument(doc: Document) {
  return doc.doc_type === "intel_card" || doc.doc_type === "social_signal_card";
}

export function formatDateTime(value?: string) {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

export function formatShortDateTime(value?: string) {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

export function formatScore(value?: number) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return value.toFixed(2);
}

