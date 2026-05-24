const taxonomy = require("./taxonomy.js");

function clamp(value, min = 0, max = 100) {
  return Math.max(min, Math.min(max, value));
}

function round(value) {
  return Math.round(value * 100) / 100;
}

function countHits(text, terms) {
  return terms.reduce((sum, term) => {
    const normalized = taxonomy.normalizeText(term);
    return normalized && text.includes(normalized) ? sum + 1 : sum;
  }, 0);
}

function scoreStrategyRelevance(card, strategyKeywords) {
  const { STRATEGY_EXPANSIONS } = taxonomy.getDynamicTaxonomy();
  const matched = [];
  let hits = 0;
  strategyKeywords.forEach((keyword) => {
    const terms = taxonomy.unique([keyword, ...(STRATEGY_EXPANSIONS[keyword] || [])]);
    const termHits = terms.filter((term) => card.search_text.includes(taxonomy.normalizeText(term)));
    if (termHits.length) {
      matched.push(keyword, ...termHits);
      hits += termHits.length;
    }
  });

  const verticalBoosts = [
    card.strategic_vertical.includes("gold") ? 8 : 0,
    card.strategic_vertical.includes("lab") || card.strategic_vertical.includes("diamond") ? 12 : 0,
    card.strategic_vertical.includes("retail") || card.strategic_vertical.includes("channel") ? 8 : 0,
  ];
  return {
    score: clamp(25 + hits * 11 + verticalBoosts.reduce((sum, value) => sum + value, 0)),
    matched_keywords: taxonomy.unique(matched),
  };
}

function scoreUrgency(card) {
  const text = card.search_text;
  const urgentHits = countHits(text, ["urgent", "risk", "drop", "volatility", "tariff", "sanction", "policy", "competition", "紧急", "风险", "下探", "波动", "关税", "制裁", "竞争"]);
  const topicBoost = ["competition", "macro_gold", "policy", "supply"].includes(card.topic) ? 18 : 0;
  return clamp(35 + urgentHits * 10 + topicBoost + Number(card.confidence_score || 0) * 10);
}

function scoreEvidenceStrength(card) {
  return clamp(25 + Math.min(Number(card.source_count || 1), 5) * 15 + Number(card.confidence_score || 0) * 20);
}

function classifyTone(card) {
  const { TOPIC_KEYWORDS } = taxonomy.getDynamicTaxonomy();
  const riskHits = countHits(card.search_text, TOPIC_KEYWORDS.risk || []);
  const opportunityHits = countHits(card.search_text, TOPIC_KEYWORDS.opportunity || []);
  if (riskHits > opportunityHits) return "risk";
  if (opportunityHits > 0) return "opportunity";
  return "watch";
}

function scoreStrategicFilter(card, strategyKeywords) {
  const relevance = scoreStrategyRelevance(card, strategyKeywords);
  const importanceScore = clamp(Number(card.importance_score || 0.6) * 100);
  const confidenceScore = clamp(Number(card.confidence_score || 0.55) * 100);
  const urgencyScore = scoreUrgency(card);
  const evidenceStrengthScore = scoreEvidenceStrength(card);
  const strategyFilterScore = round(
    0.4 * relevance.score +
      0.25 * importanceScore +
      0.15 * urgencyScore +
      0.1 * confidenceScore +
      0.1 * evidenceStrengthScore,
  );
  const hasStrategicHit = relevance.matched_keywords.length > 0;
  const filterStatus =
    strategyFilterScore >= 45 && relevance.score >= 45 && hasStrategicHit
      ? "filtered"
      : strategyFilterScore >= 35
      ? "observed"
      : "rejected";
  const tone = classifyTone(card);

  return {
    ...card,
    relevance_score: round(relevance.score),
    urgency_score: round(urgencyScore),
    evidence_strength_score: round(evidenceStrengthScore),
    strategy_filter_score: strategyFilterScore,
    filter_status: filterStatus,
    matched_keywords: relevance.matched_keywords,
    tone,
    score_breakdown: {
      relevance_score: round(relevance.score),
      importance_score: round(importanceScore),
      urgency_score: round(urgencyScore),
      confidence_score: round(confidenceScore),
      evidence_strength_score: round(evidenceStrengthScore),
      strategy_filter_score: strategyFilterScore,
      minimum_relevance_required: 45,
      has_strategic_hit: hasStrategicHit,
    },
    reasoning: buildFilterReasoning(relevance.matched_keywords, strategyFilterScore, tone, card),
  };
}

function buildFilterReasoning(matchedKeywords, score, tone, card) {
  const matchText = matchedKeywords.length ? `命中 ${matchedKeywords.slice(0, 5).join("、")}` : "战略关键词弱命中";
  const toneText = tone === "risk" ? "风险" : tone === "opportunity" ? "机会" : "观察";
  return `${matchText}；采集重要性 ${round(Number(card.importance_score || 0) * 100)}，置信度 ${round(Number(card.confidence_score || 0) * 100)}，综合判断为${toneText}信号，筛选分 ${score}。`;
}

function scoreDistribution(card) {
  const businessCore = clamp(35 + businessVerticalScore(card) + (card.tone === "risk" ? 12 : 6));
  const { BUSINESS_TAGS } = taxonomy.getDynamicTaxonomy();
  const crossBusinessImpact = clamp(
    35 + tagScores(card, BUSINESS_TAGS).filter((item) => item.score >= 50).length * 18 + (card.source_count > 2 ? 8 : 0),
  );
  const executiveValue = clamp(0.45 * card.strategy_filter_score + 0.35 * businessCore + 0.2 * crossBusinessImpact);
  const bScore = round(0.42 * businessCore + 0.28 * executiveValue + 0.18 * crossBusinessImpact + 0.12 * card.evidence_strength_score);

  const regionalCore = clamp(regionTagScores(card).some((item) => item.score >= 70) ? 85 : card.region === "global" ? 40 : 55);
  const localActionability = clamp(40 + (card.tone === "risk" ? 22 : 12) + (card.topic === "social" || card.topic === "product" ? 10 : 0));
  const cScore = round(0.4 * regionalCore + 0.25 * card.strategy_filter_score + 0.2 * localActionability + 0.15 * card.evidence_strength_score);

  return {
    ...card,
    B_distribution_score: bScore,
    C_distribution_score: cScore,
    distribution: {
      B: {
        score: bScore,
        eligible: bScore >= 65,
        reasoning: bScore >= 65 ? "具备业务判断价值，适合进入业务负责人视野。" : "业务层级相关性不足，暂不主动推给 B 类。",
      },
      C: {
        score: cScore,
        eligible: cScore >= 50,
        reasoning: cScore >= 50 ? "具备地区经营相关性，适合进入地区负责人视野。" : "地区行动价值不足，暂不主动推给 C 类。",
      },
    },
  };
}

function businessVerticalScore(card) {
  const vertical = card.strategic_vertical;
  if (vertical.includes("gold") || vertical.includes("diamond")) return 35;
  if (vertical.includes("retail") || vertical.includes("channel")) return 30;
  if (vertical.includes("supply")) return 32;
  return 18;
}

function tagScores(card, tags) {
  return tags
    .map((tag) => {
      const hitScore = countHits(card.search_text, tag.keywords) * 18;
      const topicScore =
        tag.id === "B1_market" && ["competition", "social", "macro_gold"].includes(card.topic)
          ? 24
          : tag.id === "B2_product" && ["product", "social"].includes(card.topic)
          ? 24
          : tag.id === "B3_supply_chain" && ["supply", "policy", "macro_gold"].includes(card.topic)
          ? 28
          : 0;
      return {
        ...tag,
        score: clamp(25 + hitScore + topicScore),
      };
    })
    .sort((a, b) => b.score - a.score);
}

function regionTagScores(card) {
  const { REGION_TAGS } = taxonomy.getDynamicTaxonomy();
  const normalizedRegion = taxonomy.normalizeText(card.region);
  return REGION_TAGS
    .map((tag) => {
      const regionHit = tag.regions.some((region) => taxonomy.normalizeText(region) === normalizedRegion) ? 55 : 0;
      const textHit = countHits(card.search_text, tag.keywords) * 20;
      return {
        ...tag,
        score: clamp(20 + regionHit + textHit),
      };
    })
    .sort((a, b) => b.score - a.score);
}

function assignTargetTags(card) {
  const { BUSINESS_TAGS } = taxonomy.getDynamicTaxonomy();
  const businessScores = tagScores(card, BUSINESS_TAGS);
  const regionScores = regionTagScores(card);
  const businessTags = card.distribution.B.eligible
    ? businessScores.filter((item) => item.score >= 50).slice(0, 3)
    : [];
  const regionTags = card.distribution.C.eligible
    ? regionScores.filter((item) => item.score >= 55).slice(0, 2)
    : [];
  const targetUserTags = taxonomy.unique([...businessTags.map((item) => item.id), ...regionTags.map((item) => item.id)]);
  return {
    ...card,
    target_user_tags: targetUserTags,
    tag_scores: {
      B: businessScores.map(({ id, label, score }) => ({ id, label, score })),
      C: regionScores.map(({ id, label, score }) => ({ id, label, score })),
    },
  };
}

function priorityFromScore(score) {
  if (score >= 75) return "high";
  if (score >= 55) return "medium";
  return "low";
}

module.exports = {
  clamp,
  round,
  scoreStrategicFilter,
  scoreDistribution,
  assignTargetTags,
  priorityFromScore,
};
