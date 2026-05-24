#!/usr/bin/env node
const { normalizeOnly, runPipeline } = require("./src/pipeline.js");
const { scoreStrategicFilter, scoreDistribution, assignTargetTags } = require("./src/scoring.js");
const taxonomy = require("./src/taxonomy.js");

function parseArgs(argv) {
  const options = {
    node: argv[0] || "help",
    source: "mock",
    strategyKeywords: taxonomy.DEFAULT_STRATEGY_KEYWORDS,
    cardIndex: 0,
    manualPushes: [],
  };

  for (let index = 1; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--source" && argv[index + 1]) {
      options.source = argv[index + 1];
      index += 1;
    } else if (arg === "--strategy" && argv[index + 1]) {
      options.strategyKeywords = taxonomy.parseStrategyKeywords(argv[index + 1]);
      index += 1;
    } else if (arg === "--card" && argv[index + 1]) {
      options.cardIndex = Number(argv[index + 1]);
      index += 1;
    } else if (arg === "--pushes" && argv[index + 1]) {
      options.manualPushes = JSON.parse(argv[index + 1]);
      index += 1;
    }
  }

  return options;
}

function printHelp() {
  console.log(`Version2 node inspector

Usage:
  node inspect-node.js normalize
  node inspect-node.js filter --card 0
  node inspect-node.js distribute --card 0
  node inspect-node.js tags --card 0
  node inspect-node.js insights
  node inspect-node.js feeds
  node inspect-node.js a --pushes '[{"insight_id":"...","actor_tag":"B1_market","action":"push"}]'

Options:
  --source supabase|mock|direct|mcp
  --strategy "年轻人消费, ESG, 实验室钻石"
  --card 0
  --pushes JSON_ARRAY
`);
}

function pickCard(cards, cardIndex) {
  const card = cards[cardIndex];
  if (!card) {
    throw new Error(`Card index ${cardIndex} does not exist. Available range: 0-${Math.max(0, cards.length - 1)}`);
  }
  return card;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.node === "help" || options.node === "--help") {
    printHelp();
    return;
  }

  const basePayload = {
    source: options.source,
    strategy_keywords: options.strategyKeywords,
    manual_pushes: options.manualPushes,
  };

  if (options.node === "normalize") {
    console.log(JSON.stringify(await normalizeOnly(basePayload), null, 2));
    return;
  }

  const normalized = await normalizeOnly(basePayload);
  taxonomy.setDynamicTaxonomy(taxonomy.buildDynamicTaxonomy(normalized.cards, options.strategyKeywords));
  const normalizedCard = pickCard(normalized.cards, options.cardIndex);
  const filteredCard = scoreStrategicFilter(normalizedCard, options.strategyKeywords);
  const distributedCard = scoreDistribution(filteredCard);
  const taggedCard = assignTargetTags(distributedCard);

  if (options.node === "filter") {
    console.log(JSON.stringify(filteredCard, null, 2));
    return;
  }

  if (options.node === "distribute") {
    console.log(JSON.stringify(distributedCard, null, 2));
    return;
  }

  if (options.node === "tags") {
    console.log(JSON.stringify(taggedCard, null, 2));
    return;
  }

  const result = await runPipeline(basePayload);

  if (options.node === "insights") {
    console.log(JSON.stringify(result.insight_cards, null, 2));
    return;
  }

  if (options.node === "feeds") {
    console.log(JSON.stringify(result.feeds, null, 2));
    return;
  }

  if (options.node === "a") {
    console.log(JSON.stringify(result.a_insight_cards, null, 2));
    return;
  }

  throw new Error(`Unknown node: ${options.node}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
