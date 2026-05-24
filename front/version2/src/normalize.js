const { normalizeText, unique } = require("./taxonomy.js");

function toNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function normalizeSourceIds(card, metadata) {
  const support = card.supporting_source_ids || metadata.supporting_source_ids || metadata.supportingSourceIds || [];
  return Array.isArray(support) ? support.map(String).filter(Boolean) : [];
}

function normalizeCard(rawCard, index = 0) {
  const card = rawCard && typeof rawCard === "object" ? rawCard : {};
  const metadata = card.metadata && typeof card.metadata === "object" ? card.metadata : {};
  const supportingSourceIds = normalizeSourceIds(card, metadata);
  const primarySourceId = String(
    card.primary_source_id ||
      metadata.primary_source_id ||
      metadata.primarySourceId ||
      card.source_id ||
      card.doc_id ||
      card.id ||
      `raw_auto_${index + 1}`,
  );
  const sourceCount = toNumber(
    card.source_count || metadata.source_count || metadata.sourceCount || supportingSourceIds.length + 1,
    supportingSourceIds.length + 1,
  );
  const title = String(card.title || metadata.title || "").trim();
  const summary = String(card.summary || card.content || metadata.summary || metadata.content || "").trim();
  const sourceUrl = String(card.source_url || card.evidence_url || metadata.source_url || metadata.evidence_url || "").trim();

  const normalized = {
    source_id: primarySourceId,
    region: String(card.region || metadata.region || "global").trim(),
    topic: String(card.topic || metadata.topic || "other").trim(),
    strategic_vertical: String(card.strategic_vertical || metadata.strategic_vertical || metadata.vertical || "other").trim(),
    canonical_event_key: String(card.canonical_event_key || metadata.canonical_event_key || metadata.event_key || "").trim(),
    primary_source_id: primarySourceId,
    supporting_source_ids: supportingSourceIds,
    source_count: sourceCount,
    importance_score: toNumber(
      card.importance_score !== undefined && card.importance_score !== null ? card.importance_score : metadata.importance_score,
      0.6,
    ),
    confidence_score: toNumber(
      card.confidence_score !== undefined && card.confidence_score !== null ? card.confidence_score : metadata.confidence_score,
      Math.min(0.9, 0.45 + sourceCount * 0.1),
    ),
    title,
    summary,
    content: String(card.content || metadata.content || summary || "").trim(),
    source_url: sourceUrl,
    evidence_url: sourceUrl,
    published_at: String(card.published_at || metadata.published_at || card.date || "").trim(),
    source_type: String(card.source_type || metadata.source_type || "intel_card").trim(),
    tags: unique([...(Array.isArray(card.tags) ? card.tags : []), ...(Array.isArray(metadata.tags) ? metadata.tags : [])]),
    metadata,
    raw: card,
  };

  normalized.card_id = normalized.primary_source_id;
  normalized.search_text = normalizeText([
    normalized.region,
    normalized.topic,
    normalized.strategic_vertical,
    normalized.title,
    normalized.summary,
    normalized.content,
    normalized.tags.join(" "),
  ].join(" "));

  return normalized;
}

function buildWarnings(card, index) {
  const warnings = [];
  const prefix = `cards[${index}]`;
  [
    "region",
    "topic",
    "strategic_vertical",
    "canonical_event_key",
    "primary_source_id",
    "source_count",
    "importance_score",
    "confidence_score",
  ].forEach((field) => {
    if (card[field] === undefined || card[field] === null || card[field] === "") {
      warnings.push({
        code: "missing_core_field",
        path: `${prefix}.${field}`,
        message: `${field} is missing; pipeline used a fallback value where possible.`,
      });
    }
  });

  ["title", "summary", "source_url"].forEach((field) => {
    if (!card[field]) {
      warnings.push({
        code: "missing_display_field",
        path: `${prefix}.${field}`,
        message: `${field} is recommended for frontend display and source drill-down.`,
      });
    }
  });

  return warnings;
}

function normalizeExternalCards(input) {
  const cards = Array.isArray(input) ? input : [];
  const normalized = cards.map(normalizeCard);
  const warnings = cards.flatMap((card, index) => buildWarnings(card || {}, index));
  return { cards: normalized, warnings };
}

module.exports = {
  normalizeCard,
  normalizeExternalCards,
};
