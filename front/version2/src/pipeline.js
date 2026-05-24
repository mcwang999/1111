const { fetchDirectCards } = require("./adapters/direct-source.js");
const { fetchMockCards } = require("./adapters/mock-source.js");
const { fetchFromMcpTool } = require("./adapters/mcp-source.js");
const { fetchFromSupabase, configuredFromEnv } = require("./adapters/supabase-source.js");
const { normalizeExternalCards } = require("./normalize.js");
const taxonomy = require("./taxonomy.js");
const { scoreStrategicFilter, scoreDistribution, assignTargetTags } = require("./scoring.js");
const { buildInsightCards, applyPushes, buildAInsights } = require("./insights.js");
const { buildViewModel } = require("./view-model.js");

async function resolveSource(payload = {}) {
  const hinted = payload.cards || payload.intel_cards ? "direct" : configuredFromEnv() ? "supabase" : "mock";
  const source = String(payload.source || hinted).toLowerCase();
  if (source === "direct") return fetchDirectCards(payload);
  if (source === "supabase") return fetchFromSupabase(payload);
  if (source === "mcp") {
    return fetchFromMcpTool({
      strategyKeywords: taxonomy.parseStrategyKeywords(payload.strategy_keywords || payload.strategyKeywords || taxonomy.DEFAULT_STRATEGY_KEYWORDS),
      sourceOptions: payload.source_options || payload.sourceOptions || {},
    });
  }
  return fetchMockCards();
}

async function normalizeOnly(payload = {}) {
  const sourceResult = await resolveSource(payload);
  const normalized = normalizeExternalCards(sourceResult.cards);
  return {
    source_meta: sourceResult.source_meta,
    cards: normalized.cards,
    normalization_warnings: [...(sourceResult.warnings || []), ...normalized.warnings],
  };
}

async function runPipeline(payload = {}) {
  const strategyKeywords = taxonomy.parseStrategyKeywords(
    payload.strategy_keywords || payload.strategyKeywords || taxonomy.DEFAULT_STRATEGY_KEYWORDS,
  );
  const sourceResult = await resolveSource(payload);
  const normalized = normalizeExternalCards(sourceResult.cards);
  const warnings = [...(sourceResult.warnings || []), ...normalized.warnings];
  taxonomy.refreshDynamicTaxonomy(normalized.cards, strategyKeywords);
  const scoredCards = normalized.cards
    .map((card) => scoreStrategicFilter(card, strategyKeywords))
    .map(scoreDistribution)
    .map(assignTargetTags);
  const eligibleCards = scoredCards.filter((card) => card.filter_status === "filtered" && card.target_user_tags.length > 0);
  const insightCards = applyPushes(buildInsightCards(eligibleCards), payload.manual_pushes || []);
  const aInsightCards = buildAInsights(insightCards);

  return buildViewModel({
    strategyKeywords,
    warnings,
    scoredCards,
    insightCards,
    aInsightCards,
    sourceMeta: sourceResult.source_meta,
  });
}

async function runPushPreview(payload = {}) {
  const result = await runPipeline(payload);
  return {
    a_insight_cards: result.a_insight_cards,
    feeds: {
      A: result.feeds.A,
    },
    metrics: {
      a_insight_count: result.metrics.a_insight_count,
    },
  };
}

module.exports = {
  resolveSource,
  normalizeOnly,
  runPipeline,
  runPushPreview,
};
