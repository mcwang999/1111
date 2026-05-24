const { MOCK_CARDS } = require("../mock-data.js");

async function fetchMockCards() {
  return {
    cards: MOCK_CARDS,
    warnings: [],
    source_meta: {
      source: "mock",
      configured: true,
    },
  };
}

module.exports = {
  fetchMockCards,
};
