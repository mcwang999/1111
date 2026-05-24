let assert;
try {
  assert = require("assert/strict");
} catch (error) {
  const base = require("assert");
  assert = base.strict || base;
}
const http = require("http");
const { spawn } = require("child_process");

const PORT = 8898;
const server = spawn(process.execPath, ["server.js"], {
  cwd: __dirname + "/..",
  env: {
    ...process.env,
    PORT: String(PORT),
    SUPABASE_URL: "",
    SUPABASE_SERVICE_ROLE_KEY: "",
  },
  stdio: ["ignore", "pipe", "pipe"],
});

function waitForServer() {
  return new Promise((resolve, reject) => {
    const stderrChunks = [];
    const timeout = setTimeout(() => {
      const stderrText = stderrChunks.join("").slice(0, 2000);
      reject(new Error(`server did not start in time${stderrText ? `; stderr: ${stderrText}` : ""}`));
    }, 5000);
    server.stdout.on("data", (chunk) => {
      if (String(chunk).includes("version2 API listening")) {
        clearTimeout(timeout);
        resolve();
      }
    });
    server.stderr.on("data", (chunk) => {
      stderrChunks.push(String(chunk));
    });
    server.on("exit", (code) => {
      clearTimeout(timeout);
      const stderrText = stderrChunks.join("").slice(0, 2000);
      reject(new Error(`server exited with code ${code}${stderrText ? `; stderr: ${stderrText}` : ""}`));
    });
  });
}

async function request(path, options) {
  const settings = options && typeof options === "object" ? options : {};
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        hostname: "127.0.0.1",
        port: PORT,
        path,
        method: settings.method || "GET",
        headers: settings.headers || {},
      },
      (res) => {
        let body = "";
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => {
          let json = {};
          try {
            json = body ? JSON.parse(body) : {};
          } catch (error) {
            reject(error);
            return;
          }
          resolve({ response: { status: res.statusCode, headers: res.headers }, json });
        });
      },
    );
    req.on("error", reject);
    if (settings.body) req.write(settings.body);
    req.end();
  });
}

(async () => {
  try {
    await waitForServer();

    const health = await request("/health");
    assert.equal(health.response.status, 200);
    assert.equal(health.json.ok, true);

    const mock = await request("/mock-cards");
    assert.equal(mock.response.status, 200);
    assert.ok(mock.json.cards.length > 0);

    const normalize = await request("/normalize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: "mock" }),
    });
    assert.equal(normalize.response.status, 200);
    assert.ok(normalize.json.cards.length > 0);

    const analyze = await request("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: "mock",
        strategy_keywords: ["年轻人消费", "ESG", "实验室钻石"],
      }),
    });
    assert.equal(analyze.response.status, 200);
    assert.ok(analyze.json.metrics.filtered_count > 0);
    assert.ok(Array.isArray(analyze.json.feeds.B1_market));
    assert.ok(Array.isArray(analyze.json.feeds.C3_north_america));
    assert.ok(analyze.json.ui_schema.user_tags.length >= 8);

    const firstInsight = analyze.json.insight_cards[0];
    const preview = await request("/push-preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: "mock",
        strategy_keywords: ["年轻人消费", "ESG", "实验室钻石"],
        manual_pushes: [
          { insight_id: firstInsight.insight_id, actor_tag: "B1_market", action: "push" },
          { insight_id: firstInsight.insight_id, actor_tag: "B2_product", action: "push" },
        ],
      }),
    });
    assert.equal(preview.response.status, 200);
    assert.ok(preview.json.a_insight_cards.length >= 1);

    console.log("All version2 API tests passed.");
  } finally {
    server.kill();
  }
})().catch((error) => {
  server.kill();
  console.error(error);
  process.exit(1);
});
