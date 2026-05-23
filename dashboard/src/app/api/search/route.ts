import { type NextRequest, NextResponse } from "next/server";
import { getSupabaseClient } from "@/lib/supabase";

/**
 * GET /api/search?q=...&doc_type=intel_card&page=1&limit=20
 *
 * Simple ILIKE search across title and content.
 */
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);

  const q = (searchParams.get("q") || "").trim();
  if (!q) {
    return NextResponse.json({ data: [], count: 0, page: 1, limit: 20 });
  }

  const supabase = getSupabaseClient();
  let query = supabase.from("documents").select("*", { count: "exact" });

  const docType = searchParams.get("doc_type");
  if (docType) query = query.eq("doc_type", docType);

  // Search in title OR content
  query = query.or(`title.ilike.%${q}%,content.ilike.%${q}%`);

  const page = Math.max(1, parseInt(searchParams.get("page") || "1", 10));
  const limit = Math.min(100, Math.max(1, parseInt(searchParams.get("limit") || "20", 10)));
  const from = (page - 1) * limit;
  query = query.range(from, from + limit - 1).order("created_at", { ascending: false });

  const { data, error, count } = await query;

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ data, count, page, limit });
}
