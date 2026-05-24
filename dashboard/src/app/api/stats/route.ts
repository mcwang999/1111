import { NextResponse } from "next/server";
import { getSupabaseClient } from "@/lib/supabase";
import type { AgentRun, Document, Stats } from "@/lib/types";

export const dynamic = "force-dynamic";

const CARD_TYPES = new Set(["intel_card", "social_signal_card"]);

export async function GET() {
  const supabase = getSupabaseClient();

  const { data: documents, error: documentsError } = await supabase
    .from("documents")
    .select("doc_type,created_by_agent,metadata");

  if (documentsError) {
    return NextResponse.json({ error: documentsError.message }, { status: 500 });
  }

  const { data: runs, error: runsError } = await supabase
    .from("agent_runs")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(10);

  if (runsError) {
    return NextResponse.json({ error: runsError.message }, { status: 500 });
  }

  const byRegion: Record<string, number> = {};
  const byTopic: Record<string, number> = {};
  const byImpactTag: Record<string, number> = {};
  const byDocType: Record<string, number> = {};
  const byAgent: Record<string, number> = {};

  let marketCards = 0;
  let socialCards = 0;
  let rawSources = 0;
  let unbriefedCards = 0;
  let highImpactCards = 0;

  for (const row of (documents ?? []) as Pick<Document, "doc_type" | "created_by_agent" | "metadata">[]) {
    const meta = row.metadata || {};
    increment(byDocType, row.doc_type);
    increment(byAgent, row.created_by_agent);

    if (row.doc_type === "intel_card") marketCards += 1;
    if (row.doc_type === "social_signal_card") socialCards += 1;
    if (row.doc_type === "raw_source") rawSources += 1;

    if (!CARD_TYPES.has(row.doc_type)) continue;

    if (row.doc_type === "social_signal_card") {
      incrementArray(byRegion, meta.regions);
    } else {
      increment(byRegion, meta.region);
    }

    increment(byTopic, meta.topic);
    incrementArray(byImpactTag, meta.impact_tags);

    const status = meta.briefing_status || "new";
    if (status === "new" || status === "pending") unbriefedCards += 1;

    const score = meta.importance_score ?? meta.relevance_score ?? meta.confidence_score ?? 0;
    if (typeof score === "number" && score >= 0.8) highImpactCards += 1;
  }

  const recentRuns = (runs ?? []) as AgentRun[];
  const stats: Stats = {
    market_cards: marketCards,
    social_cards: socialCards,
    raw_sources: rawSources,
    unbriefed_cards: unbriefedCards,
    high_impact_cards: highImpactCards,
    total_runs: recentRuns.length,
    by_region: byRegion,
    by_topic: byTopic,
    by_impact_tag: byImpactTag,
    by_doc_type: byDocType,
    by_agent: byAgent,
    latest_run_at: recentRuns[0]?.created_at,
    recent_runs: recentRuns,
  };

  return NextResponse.json(stats);
}

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

