let assert;
try {
  assert = require("assert/strict");
} catch (error) {
  const base = require("assert");
  assert = base.strict || base;
}

const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "..", "public", "index.html"), "utf8");

assert.ok(
  html.includes("Polaris 每日战略简报"),
  "logged-in shell should still contain the Polaris daily strategic brief label in the logged-in experience",
);
assert.ok(
  html.includes("worksuite-shell"),
  "logged-in shell should define the new worksuite shell layout wrapper",
);
assert.ok(
  html.includes("inbox-search"),
  "logged-in shell should include the Feishu-like search block in the second column",
);
assert.ok(
  html.includes("thread-list"),
  "logged-in shell should expose a thread list container for the second column",
);
assert.ok(
  html.includes("grid-template-columns: 96px 384px minmax(420px, 1fr);"),
  "logged-in shell should use a three-column layout",
);
assert.ok(
  html.includes('label: "消息", badge: 7, active: true') && !html.includes('label: "Polaris 每日战略简报", badge: 1, active: true'),
  "logged-in shell should show messages as the active left-rail entry and remove the old Polaris rail shortcut",
);
assert.ok(
  html.includes("Polaris 战略简报"),
  "logged-in shell should present the migrated strategy brief inside the third column",
);
assert.ok(
  !html.includes('<aside class="plugin feishu-plugin">'),
  "logged-in shell should no longer render a dedicated fourth plugin column",
);
assert.ok(
  html.includes('window.location.protocol === "file:"'),
  "frontend should detect file protocol and fall back to the local API host",
);
assert.ok(
  html.includes("brief-tab-btn") && html.includes("brief-action-btn"),
  "strategy brief area should expose clickable controls instead of plain text-only affordances",
);

console.log("UI shell structure tests passed.");
