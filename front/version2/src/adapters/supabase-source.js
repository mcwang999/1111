const https = require("https");
const { URL } = require("url");
const querystring = require("querystring");

function requestJson(url, options) {
  return new Promise((resolve, reject) => {
    const target = new URL(url);
    const req = https.request(
      {
        method: options.method || "GET",
        hostname: target.hostname,
        port: target.port || 443,
        path: target.pathname + (target.search || ""),
        headers: options.headers || {},
      },
      (res) => {
        let body = "";
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => {
          if (res.statusCode >= 400) {
            reject(new Error(`HTTP ${res.statusCode}: ${body.slice(0, 400)}`));
            return;
          }
          try {
            resolve(body ? JSON.parse(body) : null);
          } catch (error) {
            reject(error);
          }
        });
      },
    );
    req.on("error", reject);
    if (options.body) req.write(options.body);
    req.end();
  });
}

function buildHeaders(serviceRoleKey) {
  return {
    apikey: serviceRoleKey,
    Authorization: `Bearer ${serviceRoleKey}`,
    "Content-Type": "application/json",
  };
}

function toRawCard(row) {
  const meta = row && typeof row.metadata === "object" ? row.metadata : {};
  return {
    region: meta.region || null,
    topic: meta.topic || null,
    strategic_vertical: meta.strategic_vertical || meta.vertical || null,
    canonical_event_key: meta.canonical_event_key || meta.event_key || row.id,
    primary_source_id: meta.primary_source_id || null,
    supporting_source_ids: meta.supporting_source_ids || [],
    source_count: meta.source_count || null,
    importance_score: meta.importance_score || null,
    confidence_score: meta.confidence_score || null,
    title: row.title || meta.title || null,
    summary: row.content || meta.summary || null,
    content: row.content || meta.content || null,
    source_url: row.source_url || meta.source_url || meta.evidence_url || null,
    evidence_url: row.source_url || meta.source_url || meta.evidence_url || null,
    metadata: meta,
    supabase_document_id: row.id || null,
    created_at: row.created_at || null,
  };
}

function configuredFromEnv() {
  return Boolean(process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY);
}

async function fetchFromSupabase(params = {}) {
  const supabaseUrl = String(params.url || process.env.SUPABASE_URL || "").replace(/\/+$/, "");
  const key = String(params.serviceRoleKey || process.env.SUPABASE_SERVICE_ROLE_KEY || "");
  const limit = Number(params.limit || process.env.SUPABASE_CARD_LIMIT || 50);
  if (!supabaseUrl || !key) {
    return {
      source_meta: { source: "supabase", configured: false },
      warnings: [
        {
          code: "supabase_not_configured",
          message: "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing; falling back to other sources.",
        },
      ],
      cards: [],
    };
  }
  const qs = querystring.stringify({
    doc_type: "eq.intel_card",
    select: "id,title,content,source_url,metadata,created_at",
    order: "created_at.desc",
    limit: String(limit),
  });
  const url = `${supabaseUrl}/rest/v1/documents?${qs}`;
  const rows = await requestJson(url, { headers: buildHeaders(key) });
  const cards = Array.isArray(rows) ? rows.map(toRawCard) : [];
  return {
    source_meta: { source: "supabase", configured: true, limit },
    warnings: [],
    cards,
  };
}

module.exports = {
  configuredFromEnv,
  fetchFromSupabase,
};
