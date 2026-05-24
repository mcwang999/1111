const http = require("http");
const fs = require("fs");
const path = require("path");
const { normalizeOnly, runPipeline, runPushPreview } = require("./src/pipeline.js");
const { MOCK_CARDS } = require("./src/mock-data.js");
const taxonomy = require("./src/taxonomy.js");
const { configuredFromEnv } = require("./src/adapters/supabase-source.js");
const { extractKeywordsTextRank, extractKeywordsFromText } = require("./src/text.js");

function loadEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return;
  const text = fs.readFileSync(filePath, "utf8");
  text.split(/\r?\n/).forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) return;
    const idx = trimmed.indexOf("=");
    if (idx === -1) return;
    const key = trimmed.slice(0, idx).trim();
    if (!key || Object.prototype.hasOwnProperty.call(process.env, key)) return;
    let value = trimmed.slice(idx + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    process.env[key] = value;
  });
}

loadEnvFile(path.join(__dirname, ".env"));
loadEnvFile(path.join(__dirname, ".env.local"));

const PORT = Number(process.env.PORT || 8788);
const HOST = process.env.HOST || "127.0.0.1";
const PUBLIC_DIR = path.join(__dirname, "public");

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
};

function sendJson(response, statusCode, payload) {
  response.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
  });
  response.end(JSON.stringify(payload, null, 2));
}

function sendStatic(request, response) {
  const url = new URL(request.url, `http://${request.headers.host || "127.0.0.1"}`);
  const requestedPath = url.pathname === "/" ? "/index.html" : url.pathname;
  const filePath = path.normalize(path.join(PUBLIC_DIR, requestedPath));

  if (!filePath.startsWith(PUBLIC_DIR)) {
    sendJson(response, 403, { error: "Forbidden" });
    return true;
  }

  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) return false;

  response.writeHead(200, {
    "Content-Type": MIME_TYPES[path.extname(filePath)] || "application/octet-stream",
  });
  fs.createReadStream(filePath).pipe(response);
  return true;
}

function readJsonBody(request) {
  return new Promise((resolve, reject) => {
    let body = "";
    request.on("data", (chunk) => {
      body += chunk;
      if (body.length > 2_000_000) {
        reject(new Error("Request body too large"));
        request.destroy();
      }
    });
    request.on("end", () => {
      if (!body.trim()) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(body));
      } catch (error) {
        reject(error);
      }
    });
    request.on("error", reject);
  });
}

async function handlePost(request, response, handler, errorLabel) {
  try {
    const payload = await readJsonBody(request);
    const result = await handler(payload);
    sendJson(response, 200, result);
  } catch (error) {
    sendJson(response, 400, {
      error: errorLabel,
      detail: error.message,
    });
  }
}

let CURRENT_STRATEGY = taxonomy.DEFAULT_STRATEGY_KEYWORDS;

function normalizeStrategyInput(input) {
  return taxonomy.parseStrategyKeywords(input);
}

function mergeDefaultStrategy(payload) {
  const next = payload && typeof payload === "object" ? { ...payload } : {};
  if (!next.strategy_keywords && !next.strategyKeywords) {
    next.strategy_keywords = CURRENT_STRATEGY;
  }
  return next;
}

function extractStrategyFromMinutes(payload) {
  const body = payload && typeof payload === "object" ? payload : {};
  const raw =
    body.minutes ||
    body.meeting_minutes ||
    body.text ||
    body.content ||
    body.memo ||
    body.note ||
    "";
  const text = Array.isArray(raw) ? raw.map(String).join("\n") : String(raw || "");
  const method = String(body.method || "textrank").toLowerCase();
  const maxKeywords = Number(body.max_keywords || body.maxKeywords || 8);
  const extracted =
    method === "freq"
      ? extractKeywordsFromText(text, { maxKeywords, minCount: 2 })
      : extractKeywordsTextRank(text, { maxKeywords, windowSize: 4, maxIter: 22, damping: 0.85 });
  const strategyKeywords = extracted.map(String).filter(Boolean);
  const shouldUpdate = Boolean(body.update || body.apply || body.save);
  if (shouldUpdate && strategyKeywords.length) {
    CURRENT_STRATEGY = strategyKeywords;
  }
  return {
    ok: true,
    method,
    strategy_keywords: strategyKeywords,
    updated: shouldUpdate && strategyKeywords.length > 0,
  };
}

const server = http.createServer(async (request, response) => {
  if (request.method === "OPTIONS") {
    sendJson(response, 204, {});
    return;
  }

  if (request.method === "GET" && request.url === "/health") {
    sendJson(response, 200, {
      ok: true,
      service: "strategic-insight-agent-version2",
      supabase_configured: configuredFromEnv(),
    });
    return;
  }

  if (request.method === "GET" && request.url === "/mock-cards") {
    sendJson(response, 200, {
      cards: MOCK_CARDS,
    });
    return;
  }

  if (request.method === "GET" && request.url === "/strategy") {
    sendJson(response, 200, { strategy_keywords: CURRENT_STRATEGY });
    return;
  }

  if (request.method === "PUT" && request.url === "/strategy") {
    try {
      const payload = await readJsonBody(request);
      const next = payload.strategy_keywords || payload.strategyKeywords || payload.keywords;
      const parsed = normalizeStrategyInput(next);
      if (!Array.isArray(parsed) || parsed.length === 0) {
        throw new Error("strategy_keywords must be a non-empty list or comma-separated string");
      }
      CURRENT_STRATEGY = parsed;
      sendJson(response, 200, { ok: true, strategy_keywords: CURRENT_STRATEGY });
    } catch (error) {
      sendJson(response, 400, { error: "Invalid strategy request", detail: error.message });
    }
    return;
  }

  if (request.method === "GET" && sendStatic(request, response)) {
    return;
  }

  if (request.method === "POST" && request.url === "/normalize") {
    await handlePost(
      request,
      response,
      (payload) => normalizeOnly(mergeDefaultStrategy(payload)),
      "Invalid normalize request",
    );
    return;
  }

  if (request.method === "POST" && request.url === "/analyze") {
    await handlePost(request, response, (payload) => runPipeline(mergeDefaultStrategy(payload)), "Invalid analyze request");
    return;
  }

  if (request.method === "POST" && request.url === "/push-preview") {
    await handlePost(
      request,
      response,
      (payload) => runPushPreview(mergeDefaultStrategy(payload)),
      "Invalid push preview request",
    );
    return;
  }

  if (request.method === "POST" && request.url === "/strategy/extract") {
    await handlePost(request, response, extractStrategyFromMinutes, "Invalid strategy extract request");
    return;
  }

  sendJson(response, 404, {
    error: "Not found",
    routes: [
      "GET /health",
      "GET /mock-cards",
      "GET /strategy",
      "PUT /strategy",
      "POST /strategy/extract",
      "POST /normalize",
      "POST /analyze",
      "POST /push-preview",
    ],
  });
});

server.listen(PORT, HOST, () => {
  console.log(`Strategic Insight Agent version2 API listening on http://${HOST}:${PORT}`);
});
