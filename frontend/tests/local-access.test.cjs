const assert = require("node:assert/strict");
const { test, before } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");

let isLocalRequest;
before(async () => {
  const source = fs.readFileSync(path.join(__dirname, "../src/lib/local-access.ts"), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2020, target: ts.ScriptTarget.ES2020 },
  });
  ({ isLocalRequest } = await import(`data:text/javascript,${encodeURIComponent(outputText)}`));
});

test("accepts local browser and command-line clients", () => {
  for (const host of ["localhost:3000", "127.0.0.1:3000", "[::1]:3000"]) {
    assert.equal(isLocalRequest(host, `http://${host}`, "same-origin"), true);
    assert.equal(isLocalRequest(host, null, null), true);
  }
});

test("rejects rebinding hosts, foreign origins, and cross-site requests", () => {
  for (const host of [null, "evil.example:3000", "localhost.evil.example", "user@localhost:3000", "localhost:3000/path"]) {
    assert.equal(isLocalRequest(host, null, null), false);
  }
  for (const origin of ["null", "http://evil.example", "https://localhost:3000", "http://localhost:9000"]) {
    assert.equal(isLocalRequest("localhost:3000", origin, null), false);
  }
  assert.equal(isLocalRequest("localhost:3000", null, "cross-site"), false);
});
