const taxonomy = require("./taxonomy.js");
const { priorityFromScore, round } = require("./scoring.js");

function tagLabel(tagId) {
  const { BUSINESS_TAGS, REGION_TAGS } = taxonomy.getDynamicTaxonomy();
  const tag = [...BUSINESS_TAGS, ...REGION_TAGS].find((item) => item.id === tagId);
  return tag ? tag.label : tagId;
}

function groupKeyForCard(card, audienceLevel, targetTag) {
  const eventKey =
    card.canonical_event_key ||
    [card.topic, card.strategic_vertical, card.region].filter(Boolean).join(":") ||
    [card.topic, card.strategic_vertical].filter(Boolean).join(":");
  return `${audienceLevel}:${targetTag}:${eventKey}`;
}

function buildInsightId(audienceLevel, groupingScope, eventKey) {
  return `${audienceLevel}:${groupingScope}:${eventKey}`.replace(/\s+/g, "_");
}

function makeSourceCard(card) {
  return {
    card_id: card.card_id,
    title: card.title,
    summary: card.summary,
    region: card.region,
    topic: card.topic,
    strategic_vertical: card.strategic_vertical,
    canonical_event_key: card.canonical_event_key,
    primary_source_id: card.primary_source_id,
    supporting_source_ids: card.supporting_source_ids,
    source_ids: taxonomy.unique([card.primary_source_id, ...(card.supporting_source_ids || [])]),
    source_count: card.source_count,
    source_url: card.source_url,
    confidence_score: card.confidence_score,
    importance_score: card.importance_score,
  };
}

function aggregateForTag(cards, audienceLevel, targetTag) {
  const groups = cards.reduce((index, card) => {
    const key = groupKeyForCard(card, audienceLevel, targetTag);
    if (!index[key]) index[key] = [];
    index[key].push(card);
    return index;
  }, {});

  return Object.values(groups).map((group) => buildInsightCard(group, audienceLevel, targetTag));
}

function buildInsightCard(group, audienceLevel, targetTag) {
  const top = group.slice().sort((a, b) => b.strategy_filter_score - a.strategy_filter_score)[0];
  const avgFilter = average(group, "strategy_filter_score");
  const avgB = average(group, "B_distribution_score");
  const avgC = average(group, "C_distribution_score");
  const avgConfidence = average(group, "confidence_score") * 100;
  const eventKey = top.canonical_event_key || [top.topic, top.strategic_vertical, top.region].join(":");
  const insightId = buildInsightId(audienceLevel, targetTag.replace(/^B\d_|^C\d_/, ""), eventKey);
  const sourceCards = group.map(makeSourceCard);
  const sourceIds = taxonomy.unique(sourceCards.flatMap((card) => card.source_ids));
  const sourceUrls = taxonomy.unique(sourceCards.map((card) => card.source_url));
  const score = audienceLevel === "B" ? Math.max(avgFilter, avgB) : Math.max(avgFilter, avgC);
  const tone = chooseTone(group);

  return {
    insight_id: insightId,
    audience_level: audienceLevel,
    target_user_tags: [targetTag],
    target_user_labels: [tagLabel(targetTag)],
    title: buildTitle(top, audienceLevel, targetTag),
    insight: buildInsightText(group, audienceLevel, targetTag),
    summary: buildSummary(group, audienceLevel),
    source_cards: sourceCards,
    source_ids: sourceIds,
    source_urls: sourceUrls,
    canonical_event_key: top.canonical_event_key,
    scores: {
      strategy_filter_score: round(avgFilter),
      B_distribution_score: round(avgB),
      C_distribution_score: round(avgC),
      confidence_score: round(avgConfidence),
      source_count: sourceIds.length,
    },
    score_explanation: `由 ${group.length} 张情报卡聚合，关联 ${sourceIds.length} 个 raw_source；平均战略筛选分 ${round(avgFilter)}，平均置信度 ${round(avgConfidence)}。`,
    push: {
      push_count: 0,
      pushed_by_tags: [],
      can_push: true,
    },
    ui: {
      priority: priorityFromScore(score),
      badge: badgeForTone(tone),
      tone,
      sort_score: round(score),
    },
  };
}

function average(group, field) {
  if (!group.length) return 0;
  return group.reduce((sum, item) => sum + Number(item[field] || 0), 0) / group.length;
}

function chooseTone(group) {
  const counts = group.reduce((index, card) => {
    index[card.tone] = (index[card.tone] || 0) + 1;
    return index;
  }, {});
  if ((counts.risk || 0) >= (counts.opportunity || 0) && counts.risk) return "risk";
  if (counts.opportunity) return "opportunity";
  return "watch";
}

function regionLabel(region) {
  const { REGION_TAGS } = taxonomy.getDynamicTaxonomy();
  const normalized = taxonomy.normalizeText(region);
  for (const tag of REGION_TAGS) {
    if (tag.regions.some((item) => taxonomy.normalizeText(item) === normalized)) return tag.label;
  }
  return region || "相关地区";
}

function verticalLabel(vertical) {
  const labels = {
    gold_jewellery: "黄金珠宝业务",
    overseas_retail_channels: "海外零售渠道",
    lab_grown_diamond: "实验室钻石业务",
    watches: "腕表业务",
  };
  return labels[vertical] || vertical || "相关业务";
}

function topicLabel(topic) {
  const labels = {
    competition: "竞争信号",
    product: "产品信号",
    social: "消费与社媒信号",
    macro_gold: "金价与宏观信号",
    supply: "供应链信号",
    policy: "政策合规信号",
  };
  return labels[topic] || topic || "外部信号";
}

function buildTitle(top, audienceLevel, targetTag) {
  if (audienceLevel === "B") {
    return `${verticalLabel(top.strategic_vertical)}出现${topicLabel(top.topic)}，建议${tagLabel(targetTag)}关注`;
  }
  return `${regionLabel(top.region)}出现${topicLabel(top.topic)}，建议${tagLabel(targetTag)}跟进`;
}

function buildInsightText(group, audienceLevel) {
  const top = group[0];
  const titles = group.map((item) => item.title).filter(Boolean).slice(0, 3);
  const evidence = titles.length ? titles.join("；") : group.map((item) => item.summary).filter(Boolean).slice(0, 2).join("；");
  if (audienceLevel === "B") {
    return `${verticalLabel(top.strategic_vertical)}正在受到外部信号影响：${evidence}。该洞察更适合从业务板块层面评估产品、市场或供应链动作。`;
  }
  return `${regionLabel(top.region)}本地经营环境出现变化：${evidence}。该洞察更适合由地区负责人补充当地渠道、竞品和消费者反馈。`;
}

function buildSummary(group, audienceLevel) {
  const regions = taxonomy.unique(group.map((item) => item.region)).join("、");
  const topics = taxonomy.unique(group.map((item) => item.topic)).join("、");
  return `${audienceLevel} 级洞察，覆盖 ${regions || "相关地区"} 的 ${topics || "外部信号"}，由 ${group.length} 张情报卡聚合。`;
}

function badgeForTone(tone) {
  if (tone === "risk") return "风险";
  if (tone === "opportunity") return "机会";
  return "观察";
}

function buildInsightCards(cards) {
  const tagCards = cards.reduce((index, card) => {
    card.target_user_tags.forEach((tag) => {
      if (!index[tag]) index[tag] = [];
      index[tag].push(card);
    });
    return index;
  }, {});

  const insights = [];
  Object.entries(tagCards).forEach(([tag, groupedCards]) => {
    const audienceLevel = tag.startsWith("B") ? "B" : "C";
    insights.push(...aggregateForTag(groupedCards, audienceLevel, tag));
  });

  return insights.sort((a, b) => b.ui.sort_score - a.ui.sort_score);
}

function normalizeManualPush(push, index) {
  const actorTag = push.actor_tag || push.user_tag || push.tag || push.actor_id || "";
  const insightId = push.insight_id || push.card_id || push.id || "";
  return {
    insight_id: String(insightId),
    actor_tag: String(actorTag),
    action: String(push.action || "push").toLowerCase(),
    timestamp: push.timestamp || null,
    note: push.note || "",
    id: push.id || `push_${index + 1}`,
  };
}

function applyPushes(insightCards, manualPushes = []) {
  const pushes = (Array.isArray(manualPushes) ? manualPushes : []).map(normalizeManualPush).filter((push) => push.insight_id && push.actor_tag && push.action === "push");
  const byInsight = pushes.reduce((index, push) => {
    if (!index[push.insight_id]) index[push.insight_id] = [];
    index[push.insight_id].push(push);
    return index;
  }, {});

  return insightCards.map((card) => {
    const cardPushes = byInsight[card.insight_id] || [];
    return {
      ...card,
      push: {
        ...card.push,
        push_count: taxonomy.unique(cardPushes.map((push) => push.actor_tag)).length,
        pushed_by_tags: taxonomy.unique(cardPushes.map((push) => push.actor_tag)),
        pushed_by_labels: taxonomy.unique(cardPushes.map((push) => tagLabel(push.actor_tag))),
        can_push: true,
      },
    };
  });
}

function buildAInsights(insightCards) {
  const byEvent = insightCards.reduce((index, card) => {
    const key = card.canonical_event_key || card.insight_id;
    if (!index[key]) index[key] = [];
    index[key].push(card);
    return index;
  }, {});

  return Object.values(byEvent)
    .map((group) => promoteGroupToA(group))
    .filter(Boolean)
    .sort((a, b) => b.ui.sort_score - a.ui.sort_score);
}

function promoteGroupToA(group) {
  const pushedTags = taxonomy.unique(group.flatMap((card) => card.push.pushed_by_tags || []));
  const bTags = pushedTags.filter((tag) => tag.startsWith("B"));
  const cTags = pushedTags.filter((tag) => tag.startsWith("C"));
  const hasBusinessConsensus = bTags.length >= 2;
  const hasCrossRegionTrend = cTags.length >= 2;
  if (!hasBusinessConsensus && !hasCrossRegionTrend) return null;

  const top = group.slice().sort((a, b) => b.ui.sort_score - a.ui.sort_score)[0];
  const reason =
    hasBusinessConsensus && hasCrossRegionTrend
      ? "consensus_and_trend"
      : hasBusinessConsensus
      ? "business_consensus"
      : "cross_region_trend";

  return {
    ...top,
    insight_id: `A:${top.canonical_event_key || top.insight_id}`,
    audience_level: "A",
    target_user_tags: ["A_executive"],
    target_user_labels: ["CEO / CFO"],
    title: top.title.replace(/，建议.+$/, "，已形成集团层关注信号"),
    insight: `${top.insight} 该卡片已由 ${pushedTags.length} 个 B/C 负责人 push，满足 A 级升级条件。`,
    promotion_reason: reason,
    push: {
      push_count: pushedTags.length,
      pushed_by_tags: pushedTags,
      pushed_by_labels: pushedTags.map(tagLabel),
      can_push: false,
    },
    ui: {
      ...top.ui,
      badge: reason === "business_consensus" ? "业务共识" : reason === "cross_region_trend" ? "跨地区趋势" : "共识+趋势",
      sort_score: round(top.ui.sort_score + pushedTags.length * 5),
    },
  };
}

module.exports = {
  buildInsightCards,
  applyPushes,
  buildAInsights,
  tagLabel,
};
