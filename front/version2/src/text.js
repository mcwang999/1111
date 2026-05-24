const STOP_TOKENS = new Set([
  "the",
  "and",
  "for",
  "with",
  "from",
  "this",
  "that",
  "will",
  "into",
  "over",
  "more",
  "less",
  "about",
  "have",
  "has",
  "are",
  "were",
  "been",
  "not",
  "but",
  "can",
  "may",
  "new",
  "also",
  "市场",
  "品牌",
  "产品",
  "行业",
  "公司",
  "地区",
  "我们",
  "他们",
  "会议",
  "纪要",
  "讨论",
  "推进",
  "跟进",
  "问题",
  "需要",
  "目标",
  "计划",
  "时间",
  "今天",
  "本周",
  "下周",
]);

function normalizeText(value) {
  return String(value || "").toLowerCase().replace(/_/g, " ");
}

function parseStrategyKeywords(input) {
  if (Array.isArray(input)) {
    return input.map(String).map((item) => item.trim()).filter(Boolean);
  }
  return String(input || "")
    .split(/[,，、\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function tokenize(text) {
  const raw = normalizeText(text);
  const tokens = [];
  const alnum = raw.match(/[a-z0-9]+/g) || [];
  alnum.forEach((t) => tokens.push(t));
  const cjk = raw.match(/[\u4e00-\u9fff]+/g) || [];
  cjk.forEach((seg) => {
    const s = String(seg);
    if (s.length <= 1) {
      tokens.push(s);
      return;
    }
    for (let i = 0; i < s.length - 1; i += 1) {
      tokens.push(s.slice(i, i + 2));
    }
  });
  return tokens.filter(Boolean);
}

function unique(items) {
  return Array.from(new Set((items || []).filter(Boolean)));
}

function keywordSeeds(keyword) {
  const base = normalizeText(keyword);
  const variants = [];
  if (base.includes(" ")) {
    variants.push(base.replace(/\s+/g, "_"));
    variants.push(base.replace(/\s+/g, "-"));
    variants.push(base.replace(/\s+/g, ""));
  }
  if (base.includes("-")) {
    variants.push(base.replace(/-/g, " "));
    variants.push(base.replace(/-/g, "_"));
    variants.push(base.replace(/-/g, ""));
  }
  if (base.includes("_")) {
    variants.push(base.replace(/_/g, " "));
    variants.push(base.replace(/_/g, "-"));
    variants.push(base.replace(/_/g, ""));
  }
  return unique([base, ...variants, ...tokenize(base)]);
}

function buildExpansionMap(seedsByKey, cards, options = {}) {
  const maxTerms = Number(options.maxTerms || 10);
  const fields = options.fields || ["region", "topic", "strategic_vertical", "title", "summary", "content"];
  const texts = (cards || []).map((card) => normalizeText(fields.map((f) => card[f]).join(" ")));

  const globalFreq = {};
  let globalTotal = 0;
  texts.forEach((t) => {
    tokenize(t).forEach((tok) => {
      if (!tok || STOP_TOKENS.has(tok)) return;
      globalFreq[tok] = (globalFreq[tok] || 0) + 1;
      globalTotal += 1;
    });
  });

  const expanded = {};
  Object.entries(seedsByKey).forEach(([key, seeds]) => {
    const subsetIdx = texts
      .map((t, i) => (seeds.some((s) => s && t.includes(s)) ? i : -1))
      .filter((i) => i >= 0);
    const subsetFreq = {};
    let subsetTotal = 0;
    subsetIdx.forEach((i) => {
      tokenize(texts[i]).forEach((tok) => {
        if (!tok || STOP_TOKENS.has(tok)) return;
        subsetFreq[tok] = (subsetFreq[tok] || 0) + 1;
        subsetTotal += 1;
      });
    });

    const scored = Object.keys(subsetFreq)
      .map((tok) => {
        const a = subsetFreq[tok] || 0;
        const b = globalFreq[tok] || 0;
        const score = (a / (subsetTotal + 1)) * Math.log((globalTotal + 1) / (b + 1));
        return { tok, score };
      })
      .filter((x) => x.tok.length >= 2 && !STOP_TOKENS.has(x.tok))
      .sort((x, y) => y.score - x.score)
      .slice(0, maxTerms)
      .map((x) => x.tok);

    expanded[key] = unique([...seeds, ...scored]);
  });

  return expanded;
}

function extractKeywordsFromText(text, options = {}) {
  const maxKeywords = Number(options.maxKeywords || 8);
  const minCount = Number(options.minCount || 2);
  const tokens = tokenize(text).filter((t) => t && !STOP_TOKENS.has(t) && t.length >= 2);
  const freq = {};
  tokens.forEach((t) => {
    freq[t] = (freq[t] || 0) + 1;
  });
  return Object.keys(freq)
    .filter((k) => freq[k] >= minCount)
    .sort((a, b) => freq[b] - freq[a])
    .slice(0, maxKeywords);
}

function extractKeywordsTextRank(text, options = {}) {
  const maxKeywords = Number(options.maxKeywords || 8);
  const windowSize = Number(options.windowSize || 4);
  const maxIter = Number(options.maxIter || 20);
  const damping = Number(options.damping || 0.85);
  const minTokenLen = Number(options.minTokenLen || 2);

  const tokens = tokenize(text).filter((t) => t && !STOP_TOKENS.has(t) && t.length >= minTokenLen);
  const nodes = unique(tokens);
  if (!nodes.length) return [];

  const edges = nodes.reduce((index, node) => {
    index[node] = new Set();
    return index;
  }, {});

  for (let i = 0; i < tokens.length; i += 1) {
    const a = tokens[i];
    for (let j = i + 1; j < Math.min(tokens.length, i + windowSize); j += 1) {
      const b = tokens[j];
      if (!a || !b || a === b) continue;
      edges[a].add(b);
      edges[b].add(a);
    }
  }

  const scores = nodes.reduce((index, node) => {
    index[node] = 1;
    return index;
  }, {});

  for (let iter = 0; iter < maxIter; iter += 1) {
    const next = {};
    nodes.forEach((node) => {
      const neighbors = Array.from(edges[node] || []);
      const sum = neighbors.reduce((acc, neighbor) => {
        const outDegree = (edges[neighbor] || new Set()).size || 1;
        return acc + scores[neighbor] / outDegree;
      }, 0);
      next[node] = (1 - damping) + damping * sum;
    });
    nodes.forEach((node) => {
      scores[node] = next[node];
    });
  }

  const freq = tokens.reduce((index, t) => {
    index[t] = (index[t] || 0) + 1;
    return index;
  }, {});

  return nodes
    .map((node) => ({ node, score: scores[node] * (1 + Math.log((freq[node] || 1) + 1)) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, maxKeywords)
    .map((x) => x.node);
}

module.exports = {
  STOP_TOKENS,
  normalizeText,
  parseStrategyKeywords,
  tokenize,
  unique,
  keywordSeeds,
  buildExpansionMap,
  extractKeywordsFromText,
  extractKeywordsTextRank,
};
