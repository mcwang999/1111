import { type NextRequest, NextResponse } from "next/server";
import { getSupabaseClient } from "@/lib/supabase";

/**
 * GET /api/documents
 *
 * Query params: doc_type, region, topic, strategic_vertical, impact_tags,
 *               created_by_agent, page, limit, sort, dir
 */
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const supabase = getSupabaseClient();

  let query = supabase.from("documents").select("*", { count: "exact" });

  // -- filters --
  const docType = searchParams.get("doc_type");
  if (docType) query = query.eq("doc_type", docType);

  const region = searchParams.get("region");
  if (region) query = query.filter("metadata->>region", "eq", region);

  const topic = searchParams.get("topic");
  if (topic) query = query.filter("metadata->>topic", "eq", topic);

  const vertical = searchParams.get("strategic_vertical");
  if (vertical) query = query.filter("metadata->>strategic_vertical", "eq", vertical);

  const agent = searchParams.get("created_by_agent");
  if (agent) query = query.eq("created_by_agent", agent);

  const tags = searchParams.get("impact_tags");
  if (tags) {
    const tagList = tags.split(",").map((t) => t.trim()).filter(Boolean);
    if (tagList.length > 0) {
      // JSONB array overlap: document has ANY of the requested tags
      query = query.filter("metadata->impact_tags", "ov", JSON.stringify(tagList));
    }
  }

  // -- sorting --
  const sortField = searchParams.get("sort") || "created_at";
  const sortDir = searchParams.get("dir") === "asc" ? "asc" as const : "desc" as const;

  // Map friendly sort fields to actual columns / jsonb paths
  const sortMap: Record<string, string> = {
    created_at: "created_at",
    title: "title",
    published_at: "metadata->>published_at",
    relevance_score: "metadata->>relevance_score",
    confidence_score: "metadata->>confidence_score",
  };
  const orderCol = sortMap[sortField] || "created_at";
  query = query.order(orderCol, { ascending: sortDir === "asc", nullsFirst: false });

  // -- pagination --
  const page = Math.max(1, parseInt(searchParams.get("page") || "1", 10));
  const limit = Math.min(100, Math.max(1, parseInt(searchParams.get("limit") || "20", 10)));
  const from = (page - 1) * limit;
  query = query.range(from, from + limit - 1);

  const { data, error, count } = await query;

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ data, count, page, limit });
}
