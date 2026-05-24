const DEFAULT_STRATEGY_KEYWORDS = ["年轻人消费", "ESG", "实验室钻石"];

const { STOP_TOKENS, normalizeText, parseStrategyKeywords, unique } = require("./text.js");
const { keywordSeeds, buildExpansionMap, tokenize } = require("./text.js");

const BUSINESS_TAGS = [
  {
    id: "B1_market",
    label: "市场负责人",
    level: "B",
    keywords: [],
  },
  {
    id: "B2_product",
    label: "产品负责人",
    level: "B",
    keywords: [],
  },
  {
    id: "B3_supply_chain",
    label: "供应链负责人",
    level: "B",
    keywords: [],
  },
];

const REGION_TAGS = [
  {
    id: "C1_east_asia",
    label: "东亚地区",
    level: "C",
    regions: ["china", "mainland_china", "hong_kong", "taiwan", "japan", "korea", "south_korea", "east_asia"],
    keywords: [],
  },
  {
    id: "C2_southeast_asia",
    label: "东南亚地区",
    level: "C",
    regions: [
      "southeast_asia",
      "singapore",
      "thailand",
      "vietnam",
      "indonesia",
      "malaysia",
      "philippines",
      "sea",
    ],
    keywords: [],
  },
  {
    id: "C3_north_america",
    label: "北美洲地区",
    level: "C",
    regions: ["north_america", "us", "usa", "united_states", "canada", "mexico"],
    keywords: [],
  },
  {
    id: "C4_oceania",
    label: "大洋洲地区",
    level: "C",
    regions: ["oceania", "australia", "new_zealand"],
    keywords: [],
  },
];

const USER_TAGS = [...BUSINESS_TAGS, ...REGION_TAGS];

function buildDynamicTaxonomy(cards, strategyKeywords, previousTaxonomy) {
  const cardList = Array.isArray(cards) ? cards : [];
  const strategy = parseStrategyKeywords(strategyKeywords || DEFAULT_STRATEGY_KEYWORDS);
  const previous = previousTaxonomy || {};

  function mergeList(prevList, nextList, maxItems) {
    return unique([...(prevList || []), ...(nextList || [])]).slice(0, Number(maxItems || 24));
  }

  function mergeMap(prevMap, nextMap, maxItems) {
    const out = {};
    const keys = unique([...Object.keys(prevMap || {}), ...Object.keys(nextMap || {})]);
    keys.forEach((k) => {
      out[k] = mergeList((prevMap || {})[k], (nextMap || {})[k], maxItems);
    });
    return out;
  }

  const strategySeeds = strategy.reduce((index, keyword) => {
    index[keyword] = keywordSeeds(keyword);
    return index;
  }, {});
  const freshStrategyExpansions = buildExpansionMap(strategySeeds, cardList, { maxTerms: 10 });
  const strategyExpansions = mergeMap(previous.STRATEGY_EXPANSIONS, freshStrategyExpansions, 24);

  function buildTopTokensForSubset(selectCards, maxTerms) {
    const texts = cardList.map((card) =>
      normalizeText([card.region, card.topic, card.strategic_vertical, card.title, card.summary, card.content].join(" ")),
    );

    const globalFreq = {};
    let globalTotal = 0;
    texts.forEach((t) => {
      tokenize(t).forEach((tok) => {
        if (!tok || STOP_TOKENS.has(tok)) return;
        globalFreq[tok] = (globalFreq[tok] || 0) + 1;
        globalTotal += 1;
      });
    });

    const subsetText = cardList
      .map((card, index) => ({ card, index }))
      .filter((x) => selectCards(x.card))
      .map((x) => texts[x.index]);

    const subsetFreq = {};
    let subsetTotal = 0;
    subsetText.forEach((t) => {
      tokenize(t).forEach((tok) => {
        if (!tok || STOP_TOKENS.has(tok)) return;
        subsetFreq[tok] = (subsetFreq[tok] || 0) + 1;
        subsetTotal += 1;
      });
    });

    return Object.keys(subsetFreq)
      .map((tok) => {
        const a = subsetFreq[tok] || 0;
        const b = globalFreq[tok] || 0;
        const score = (a / (subsetTotal + 1)) * Math.log((globalTotal + 1) / (b + 1));
        return { tok, score };
      })
      .filter((x) => x.tok.length >= 2 && !STOP_TOKENS.has(x.tok))
      .sort((x, y) => y.score - x.score)
      .slice(0, Number(maxTerms || 14))
      .map((x) => x.tok);
  }

  const businessKeywords = {
    B1_market: buildTopTokensForSubset(
      (card) => ["competition", "social", "macro_gold"].includes(String(card.topic || "")),
      14,
    ),
    B2_product: buildTopTokensForSubset((card) => ["product", "social"].includes(String(card.topic || "")), 14),
    B3_supply_chain: buildTopTokensForSubset(
      (card) => ["supply", "policy", "macro_gold"].includes(String(card.topic || "")),
      14,
    ),
  };

  const regionKeywords = REGION_TAGS.reduce((index, tag) => {
    index[tag.id] = buildTopTokensForSubset(
      (card) => (tag.regions || []).some((r) => normalizeText(r) === normalizeText(card.region)),
      10,
    );
    return index;
  }, {});

  const topicGroups = {
    risk: ["competition", "macro_gold", "policy", "supply"],
    opportunity: ["product", "social"],
    watch: ["other", "watch", "trend"],
  };
  const topicKeywords = {
    risk: buildTopTokensForSubset((card) => (topicGroups.risk || []).includes(String(card.topic || "")), 16),
    opportunity: buildTopTokensForSubset(
      (card) => (topicGroups.opportunity || []).includes(String(card.topic || "")),
      16,
    ),
    watch: buildTopTokensForSubset((card) => (topicGroups.watch || []).includes(String(card.topic || "")), 10),
  };

  const businessTags = BUSINESS_TAGS.map((tag) => ({
    ...tag,
    keywords: mergeList(
      ((previous.BUSINESS_TAGS || []).find((t) => t.id === tag.id) || {}).keywords,
      unique([...(businessKeywords[tag.id] || []), ...keywordSeeds(tag.label), ...keywordSeeds(tag.id)]),
      32,
    ),
  }));
  const regionTags = REGION_TAGS.map((tag) => ({
    ...tag,
    keywords: mergeList(
      ((previous.REGION_TAGS || []).find((t) => t.id === tag.id) || {}).keywords,
      unique([...(regionKeywords[tag.id] || []), ...(tag.regions || []), ...keywordSeeds(tag.label)]),
      28,
    ),
  }));
  const userTags = [...businessTags, ...regionTags];

  return {
    STRATEGY_EXPANSIONS: strategyExpansions,
    BUSINESS_TAGS: businessTags,
    REGION_TAGS: regionTags,
    USER_TAGS: userTags,
    TOPIC_KEYWORDS: topicKeywords,
  };
}

let CURRENT_TAXONOMY = {
  STRATEGY_EXPANSIONS: {},
  BUSINESS_TAGS,
  REGION_TAGS,
  USER_TAGS,
  TOPIC_KEYWORDS: { risk: [], opportunity: [], watch: [] },
};

function setDynamicTaxonomy(taxonomy) {
  if (!taxonomy || typeof taxonomy !== "object") return;
  CURRENT_TAXONOMY = taxonomy;
}

function getDynamicTaxonomy() {
  return CURRENT_TAXONOMY;
}

function refreshDynamicTaxonomy(cards, strategyKeywords) {
  CURRENT_TAXONOMY = buildDynamicTaxonomy(cards, strategyKeywords, CURRENT_TAXONOMY);
  return CURRENT_TAXONOMY;
}

module.exports = {
  DEFAULT_STRATEGY_KEYWORDS,
  normalizeText,
  parseStrategyKeywords,
  unique,
  buildDynamicTaxonomy,
  setDynamicTaxonomy,
  getDynamicTaxonomy,
  refreshDynamicTaxonomy,
};
