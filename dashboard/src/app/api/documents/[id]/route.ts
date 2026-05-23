import { type NextRequest, NextResponse } from "next/server";
import { getSupabaseClient } from "@/lib/supabase";

/**
 * GET /api/documents/:id
 *
 * Returns the document + linked raw sources (for intel_card traceability).
 */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const supabase = getSupabaseClient();

  // Fetch the document
  const { data: doc, error: docErr } = await supabase
    .from("documents")
    .select("*")
    .eq("id", id)
    .single();

  if (docErr || !doc) {
    return NextResponse.json({ error: docErr?.message || "Not found" }, { status: 404 });
  }

  // If it's an intel_card, fetch linked raw sources
  let linkedSources: unknown[] = [];
  if (doc.doc_type === "intel_card") {
    const sourceIds: string[] = [];
    if (doc.metadata?.primary_source_id) {
      sourceIds.push(doc.metadata.primary_source_id);
    }
    if (doc.metadata?.supporting_source_ids?.length) {
      sourceIds.push(...doc.metadata.supporting_source_ids);
    }

    if (sourceIds.length > 0) {
      const { data: sources } = await supabase
        .from("documents")
        .select("*")
        .in("id", sourceIds);
      linkedSources = sources || [];
    }
  }

  return NextResponse.json({ document: doc, linked_sources: linkedSources });
}
