let assert;
try {
  assert = require("assert/strict");
} catch (error) {
  const base = require("assert");
  assert = base.strict || base;
}
const { normalizeOnly, runPipeline, runPushPreview } = require("../src/pipeline.js");
const { MOCK_CARDS } = require("../src/mock-data.js");

(async () => {
  const normalized = await normalizeOnly({
    source: "direct",
    cards: [
      {
        region: "us",
        topic: "competition",
        strategic_vertical: "lab_grown_diamond",
        canonical_event_key: "test_event",
        primary_source_id: "raw_test_001",
        supporting_source_ids: ["raw_test_002"],
        source_count: 2,
        importance_score: 0.6,
        confidence_score: 0.7,
      },
    ],
  });

  assert.equal(normalized.cards.length, 1, "should normalize direct cards");
  assert.equal(normalized.cards[0].region, "us", "should preserve region");
  assert.equal(normalized.cards[0].topic, "competition", "should preserve topic");
  assert.equal(normalized.cards[0].strategic_vertical, "lab_grown_diamond", "should preserve strategic_vertical");
  assert.equal(normalized.cards[0].canonical_event_key, "test_event", "should preserve canonical_event_key");
  assert.equal(normalized.cards[0].primary_source_id, "raw_test_001", "should preserve primary_source_id");
  assert.deepEqual(normalized.cards[0].supporting_source_ids, ["raw_test_002"], "should preserve supporting_source_ids");
  assert.equal(normalized.cards[0].source_count, 2, "should preserve source_count");
  assert.equal(normalized.cards[0].importance_score, 0.6, "should preserve importance_score");
  assert.equal(normalized.cards[0].confidence_score, 0.7, "should preserve confidence_score");
  assert.ok(
    normalized.normalization_warnings.some((warning) => warning.code === "missing_display_field"),
    "missing display fields should warn but not fail",
  );

  const result = await runPipeline({
    source: "mock",
    strategy_keywords: ["年轻人消费", "ESG", "实验室钻石"],
  });

  assert.equal(result.metrics.card_count, MOCK_CARDS.length, "should analyze all mock cards");
  assert.ok(result.metrics.filtered_count >= 6, "wide filter should preserve meaningful signals");
  assert.ok(result.metrics.b_feed_count <= result.metrics.c_feed_count + result.metrics.b_feed_count, "metrics should be present");
  assert.ok(Array.isArray(result.feeds.B1_market), "frontend feed B1 should be an array");
  assert.ok(Array.isArray(result.feeds.B2_product), "frontend feed B2 should be an array");
  assert.ok(Array.isArray(result.feeds.B3_supply_chain), "frontend feed B3 should be an array");
  assert.ok(Array.isArray(result.feeds.C1_east_asia), "frontend feed C1 should be an array");
  assert.ok(Array.isArray(result.feeds.C2_southeast_asia), "frontend feed C2 should be an array");
  assert.ok(Array.isArray(result.feeds.C3_north_america), "frontend feed C3 should be an array");
  assert.ok(Array.isArray(result.feeds.C4_oceania), "frontend feed C4 should be an array");
  assert.ok(Array.isArray(result.feeds.A), "frontend feed A should be an array");

  const cTotal = ["C1_east_asia", "C2_southeast_asia", "C3_north_america", "C4_oceania"].reduce(
    (acc, key) => acc + (result.feeds[key] || []).length,
    0,
  );
  const bTotal = ["B1_market", "B2_product", "B3_supply_chain"].reduce(
    (acc, key) => acc + (result.feeds[key] || []).length,
    0,
  );
  assert.ok(cTotal > 0, "should produce C-level feeds");
  assert.ok(bTotal > 0, "should produce B-level feeds");

  const sameEvent = result.insight_cards.filter(
    (card) => card.canonical_event_key === "north_america_lab_diamond_price_drop_2026_q2",
  );
  assert.ok(sameEvent.length > 0, "canonical_event_key should drive insight aggregation");
  assert.ok(sameEvent.every((card) => card.source_ids.length >= 1), "insight should retain source ids");
  assert.ok(sameEvent.every((card) => card.source_urls.length >= 1), "insight should retain source urls");
  assert.ok(
    result.insight_cards.every((card) => card.ui && card.ui.priority && card.ui.tone && typeof card.ui.sort_score === "number"),
    "insight cards should include frontend UI hints",
  );

  const bInsight = result.insight_cards.find((card) => card.audience_level === "B");
  assert.ok(bInsight, "should produce B insight cards");
  const promoted = await runPipeline({
    source: "mock",
    strategy_keywords: ["年轻人消费", "ESG", "实验室钻石"],
    manual_pushes: [
      { insight_id: bInsight.insight_id, actor_tag: "B1_market", action: "push" },
      { insight_id: bInsight.insight_id, actor_tag: "B2_product", action: "push" },
    ],
  });
  assert.ok(promoted.a_insight_cards.length >= 1, "two B pushes should promote to A");
  assert.ok(promoted.a_insight_cards[0].push.push_count >= 2, "A card should expose push count");
  assert.ok(promoted.a_insight_cards[0].promotion_reason, "A card should expose promotion reason");

  const cInsight = result.insight_cards.find((card) => card.audience_level === "C");
  const preview = await runPushPreview({
    source: "mock",
    strategy_keywords: ["年轻人消费", "ESG", "实验室钻石"],
    manual_pushes: [
      { insight_id: cInsight.insight_id, actor_tag: "C1_east_asia", action: "push" },
      { insight_id: cInsight.insight_id, actor_tag: "C2_southeast_asia", action: "push" },
    ],
  });
  assert.ok(preview.a_insight_cards.length >= 1, "two C pushes should promote to A in preview");

  const mcp = await runPipeline({ source: "mcp" });
  assert.equal(mcp.source_meta.configured, false, "mcp source should be explicitly marked unconfigured");
  assert.ok(mcp.normalization_warnings.some((warning) => warning.code === "mcp_not_configured"), "mcp should return a clear warning");

  console.log("All version2 strategic insight tests passed.");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
