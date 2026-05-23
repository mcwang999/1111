import { NextResponse } from "next/server";
import { getSupabaseClient } from "@/lib/supabase";
import type { AgentRun, Stats } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  const supabase = getSupabaseClient();
  // Total counts by doc_type
  const { data: counts } = await supabase
    .from("documents")
    .select("doc_type");

  const totalCards = (counts ?? []).filter((d) => d.doc_type === "intel_card").length;
  const totalSources = (counts ?? []).filter((d) => d.doc_type !== "intel_card").length;

  // Breakdown by region (for intel_cards)
  const { data: regionData } = await supabase
    .from("documents")
    .select("metadata->>region")
    .eq("doc_type", "intel_card");

  const byRegion: Record<string, number> = {};
  for (const row of regionData ?? []) {
    const r = (row as Record<string, string>)["metadata->>region"] || "unknown";
    byRegion[r] = (byRegion[r] || 0) + 1;
  }

  // Breakdown by topic (for intel_cards)
  const { data: topicData } = await supabase
    .from("documents")
    .select("metadata->>topic")
    .eq("doc_type", "intel_card");

  const byTopic: Record<string, number> = {};
  for (const row of topicData ?? []) {
    const t = (row as Record<string, string>)["metadata->>topic"] || "unknown";
    byTopic[t] = (byTopic[t] || 0) + 1;
  }

  // Breakdown by agent
  const { data: agentData } = await supabase
    .from("documents")
    .select("created_by_agent");

  const byAgent: Record<string, number> = {};
  for (const row of agentData ?? []) {
    const a = row.created_by_agent || "unknown";
    byAgent[a] = (byAgent[a] || 0) + 1;
  }

  // Recent agent runs
  const { data: runs } = await supabase
    .from("agent_runs")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(10);

  const stats: Stats = {
    total_cards: totalCards,
    total_sources: totalSources,
    total_runs: (runs ?? []).length,
    by_region: byRegion,
    by_topic: byTopic,
    by_agent: byAgent,
    recent_runs: (runs ?? []) as AgentRun[],
  };

  return NextResponse.json(stats);
}
