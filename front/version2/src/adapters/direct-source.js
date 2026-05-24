function extractDirectCards(payload = {}) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.cards)) return payload.cards;
  if (Array.isArray(payload.intel_cards)) return payload.intel_cards;
  if (payload.card && typeof payload.card === "object") return [payload.card];
  if (payload.title || payload.primary_source_id || payload.canonical_event_key) return [payload];
  return [];
}

async function fetchDirectCards(payload = {}) {
  return {
    cards: extractDirectCards(payload),
    warnings: [],
    source_meta: {
      source: "direct",
      configured: true,
    },
  };
}

module.exports = {
  extractDirectCards,
  fetchDirectCards,
};
