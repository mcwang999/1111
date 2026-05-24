const taxonomy = require("./taxonomy.js");

function emptyFeeds() {
  const { USER_TAGS } = taxonomy.getDynamicTaxonomy();
  return USER_TAGS.reduce(
    (feeds, tag) => {
      feeds[tag.id] = [];
      return feeds;
    },
    { A: [] },
  );
}

function buildFeeds(insightCards, aInsightCards) {
  const feeds = emptyFeeds();
  insightCards.forEach((card) => {
    card.target_user_tags.forEach((tag) => {
      if (!feeds[tag]) feeds[tag] = [];
      feeds[tag].push(card);
    });
  });
  feeds.A = aInsightCards;
  Object.keys(feeds).forEach((key) => {
    feeds[key] = feeds[key].slice().sort((a, b) => b.ui.sort_score - a.ui.sort_score);
  });
  return feeds;
}

function buildUiSchema() {
  const { USER_TAGS } = taxonomy.getDynamicTaxonomy();
  return {
    user_tags: [
      ...USER_TAGS.map(({ id, label, level }) => ({ id, label, level })),
      { id: "A", label: "CEO / CFO", level: "A" },
    ],
    priority_options: [
      { id: "high", label: "高优先级" },
      { id: "medium", label: "中优先级" },
      { id: "low", label: "低优先级" },
    ],
    tone_options: [
      { id: "risk", label: "风险" },
      { id: "opportunity", label: "机会" },
      { id: "watch", label: "观察" },
    ],
  };
}

function buildViewModel({ strategyKeywords, warnings, scoredCards, insightCards, aInsightCards, sourceMeta }) {
  const filtered = scoredCards.filter((card) => card.filter_status === "filtered");
  const observed = scoredCards.filter((card) => card.filter_status === "observed");
  const rejected = scoredCards.filter((card) => card.filter_status === "rejected");
  return {
    strategy_keywords: strategyKeywords,
    generated_at: new Date().toISOString(),
    source_meta: sourceMeta,
    normalization_warnings: warnings,
    cards: {
      filtered,
      observed,
      rejected,
    },
    feeds: buildFeeds(insightCards, aInsightCards),
    insight_cards: insightCards,
    a_insight_cards: aInsightCards,
    metrics: {
      card_count: scoredCards.length,
      filtered_count: filtered.length,
      observed_count: observed.length,
      rejected_count: rejected.length,
      insight_count: insightCards.length,
      a_insight_count: aInsightCards.length,
      b_feed_count: insightCards.filter((card) => card.audience_level === "B").length,
      c_feed_count: insightCards.filter((card) => card.audience_level === "C").length,
      warning_count: warnings.length,
    },
    ui_schema: buildUiSchema(),
  };
}

module.exports = {
  buildFeeds,
  buildUiSchema,
  buildViewModel,
};
