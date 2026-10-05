// Node driver for factory/tests/test_intake_worker_auth.py.
//
// Exercises the real built Worker (dist/index.js, bundled from
// factory/intake/worker/src/index.ts) against the Cloudflare Access JWT gate
// added for FF-P03-01 (D-NEW-002 Option A). Only Node built-ins are used
// (node:crypto, node:assert, node:url, global fetch/crypto/Request/Response)
// so this never needs its own node_modules resolution.
//
// Usage: node worker_auth_driver.mjs <path-to-dist/index.js>
// Exit code 0 = all assertions passed; non-zero = failure (see stderr).

import { generateKeyPairSync, createSign, randomUUID } from "node:crypto";
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const distPath = process.argv[2];
if (!distPath) {
  console.error("Usage: node worker_auth_driver.mjs <path-to-dist/index.js>");
  process.exit(2);
}

const { default: worker } = await import(pathToFileURL(distPath).href);

const TEST_AUD = "test-access-application-aud";
const TEST_TEAM_DOMAIN = "test-team";
const TEST_KID = "test-signing-key-1";
const CERTS_URL = `https://${TEST_TEAM_DOMAIN}.cloudflareaccess.com/cdn-cgi/access/certs`;

// --- Generate a throwaway RSA keypair standing in for Access's signing key ---
const { publicKey, privateKey } = generateKeyPairSync("rsa", {
  modulusLength: 2048,
  publicKeyEncoding: { format: "jwk" },
  privateKeyEncoding: { format: "jwk" },
});

const jwks = {
  keys: [{ ...publicKey, kid: TEST_KID, alg: "RS256", use: "sig" }],
};

function base64url(input) {
  const buf = Buffer.isBuffer(input) ? input : Buffer.from(input);
  return buf.toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function signAccessJwt({ aud = TEST_AUD, kid = TEST_KID, email = "tester@example.com", exp, extraHeader = {} } = {}) {
  const header = { alg: "RS256", typ: "JWT", kid, ...extraHeader };
  const nowSeconds = Math.floor(Date.now() / 1000);
  const payload = {
    aud,
    email,
    iat: nowSeconds,
    exp: exp === undefined ? nowSeconds + 3600 : exp,
  };

  const headerB64 = base64url(JSON.stringify(header));
  const payloadB64 = base64url(JSON.stringify(payload));
  const signingInput = `${headerB64}.${payloadB64}`;

  const sign = createSign("RSA-SHA256");
  sign.update(signingInput);
  sign.end();
  const signature = sign.sign({ key: privateKey, format: "jwk" });

  return `${signingInput}.${base64url(signature)}`;
}

// --- Mock global fetch: only the Access JWKS endpoint is expected to be hit ---
const realFetch = globalThis.fetch;
globalThis.fetch = async (input, init) => {
  const url = typeof input === "string" ? input : input.url;
  if (url === CERTS_URL) {
    return new Response(JSON.stringify(jwks), { status: 200, headers: { "Content-Type": "application/json" } });
  }
  throw new Error(`Unexpected fetch() call in test to: ${url}`);
};

// --- Fake D1 binding, just enough for handleCreateConversation's INSERT ... RETURNING * ---
function makeFakeD1() {
  return {
    prepare(sql) {
      const statement = {
        bind(..._args) {
          return statement;
        },
        async first() {
          if (/INSERT INTO conversations/i.test(sql)) {
            const now = new Date().toISOString();
            return { id: randomUUID(), status: "draft", created_at: now, updated_at: now };
          }
          return null;
        },
        async all() {
          return { results: [] };
        },
      };
      return statement;
    },
  };
}

function makeEnv(overrides = {}) {
  return {
    DB: makeFakeD1(),
    GITHUB_REPO_CREATE_TOKEN: "test-token",
    GEMINI_API_KEY: "test-gemini-key",
    ENVIRONMENT: "test",
    GITHUB_ORG: "test-org",
    VERSION: "test",
    CLOUDFLARE_ACCESS_AUD: TEST_AUD,
    CLOUDFLARE_ACCESS_TEAM_DOMAIN: TEST_TEAM_DOMAIN,
    ...overrides,
  };
}

function request(path, { method = "GET", headers = {} } = {}) {
  return new Request(`https://worker.test${path}`, { method, headers });
}

const results = [];

async function check(name, fn) {
  try {
    await fn();
    results.push({ name, ok: true });
    console.log(`PASS: ${name}`);
  } catch (error) {
    results.push({ name, ok: false, error: error instanceof Error ? error.message : String(error) });
    console.error(`FAIL: ${name}`);
    console.error(error);
  }
}

await check("POST /conversations with no Access header returns 401", async () => {
  const res = await worker.fetch(request("/conversations", { method: "POST" }), makeEnv());
  assert.equal(res.status, 401);
  const body = await res.json();
  assert.match(body.error, /Unauthorized/i);
});

await check("POST /conversations with malformed Access header returns 401", async () => {
  const res = await worker.fetch(
    request("/conversations", { method: "POST", headers: { "Cf-Access-Jwt-Assertion": "not-a-jwt" } }),
    makeEnv()
  );
  assert.equal(res.status, 401);
});

await check("POST /conversations with wrong-audience JWT returns 401", async () => {
  const token = signAccessJwt({ aud: "some-other-application-aud" });
  const res = await worker.fetch(
    request("/conversations", { method: "POST", headers: { "Cf-Access-Jwt-Assertion": token } }),
    makeEnv()
  );
  assert.equal(res.status, 401);
});

await check("POST /conversations with expired JWT returns 401", async () => {
  const token = signAccessJwt({ exp: Math.floor(Date.now() / 1000) - 60 });
  const res = await worker.fetch(
    request("/conversations", { method: "POST", headers: { "Cf-Access-Jwt-Assertion": token } }),
    makeEnv()
  );
  assert.equal(res.status, 401);
});

await check("POST /conversations with unknown kid returns 401", async () => {
  const token = signAccessJwt({ kid: "some-other-kid" });
  const res = await worker.fetch(
    request("/conversations", { method: "POST", headers: { "Cf-Access-Jwt-Assertion": token } }),
    makeEnv()
  );
  assert.equal(res.status, 401);
});

await check("POST /conversations with valid Access JWT is allowed through (201)", async () => {
  const token = signAccessJwt();
  const res = await worker.fetch(
    request("/conversations", { method: "POST", headers: { "Cf-Access-Jwt-Assertion": token } }),
    makeEnv()
  );
  assert.equal(res.status, 201);
  const body = await res.json();
  assert.ok(body.conversation);
  assert.equal(body.conversation.status, "draft");
});

await check("GET /version with no Access header is public (200)", async () => {
  const res = await worker.fetch(request("/version", { method: "GET" }), makeEnv());
  assert.equal(res.status, 200);
});

await check("GET /ollama/status with no Access header is public (not 401)", async () => {
  const res = await worker.fetch(request("/ollama/status", { method: "GET" }), makeEnv());
  assert.notEqual(res.status, 401);
});

await check("POST /conversations when CLOUDFLARE_ACCESS_AUD unset returns 401 (fails closed)", async () => {
  const token = signAccessJwt();
  const res = await worker.fetch(
    request("/conversations", { method: "POST", headers: { "Cf-Access-Jwt-Assertion": token } }),
    makeEnv({ CLOUDFLARE_ACCESS_AUD: "" })
  );
  assert.equal(res.status, 401);
});

globalThis.fetch = realFetch;

const failed = results.filter((r) => !r.ok);
if (failed.length > 0) {
  console.error(`\n${failed.length}/${results.length} checks failed.`);
  process.exit(1);
}
console.log(`\nAll ${results.length} checks passed.`);
process.exit(0);
