async function fetchFromMcpTool({ strategyKeywords = [], sourceOptions = {} } = {}) {
  const fallbackCards = Array.isArray(sourceOptions.fallback_cards) ? sourceOptions.fallback_cards : null;
  if (fallbackCards) {
    return {
      cards: fallbackCards,
      warnings: [
        {
          code: "mcp_fallback_used",
          message: "MCP tool is not configured yet; source_options.fallback_cards were used.",
        },
      ],
      source_meta: {
        source: "mcp",
        configured: false,
        strategy_keywords: strategyKeywords,
      },
    };
  }

  return {
    cards: [],
    warnings: [
      {
        code: "mcp_not_configured",
        message: "MCP tool adapter is reserved. Provide tool name, input schema, and output schema to enable it.",
      },
    ],
    source_meta: {
      source: "mcp",
      configured: false,
      expected_input: {
        strategy_keywords: strategyKeywords,
        source_options: sourceOptions,
      },
    },
  };
}

module.exports = {
  fetchFromMcpTool,
};
