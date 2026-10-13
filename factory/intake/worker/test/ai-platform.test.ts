import test from "node:test";
import assert from "node:assert/strict";
import { AIPlatformError, getAIPlatformTextResponse } from "../src/ai-platform";

const validConfig = {
  baseUrl: "https://llm.example.test",
  apiKey: "test-key-not-a-real-secret",
  model: "verified-free-model",
  allowedModels: "verified-free-model,another-verified-free-model",
  timeoutSeconds: "10",
};

test("fails closed when the API key is missing", async () => {
  await assert.rejects(
    getAIPlatformTextResponse({ ...validConfig, apiKey: "" }, [], "system"),
    (error: unknown) =>
      error instanceof AIPlatformError &&
      error.statusCode === 503 &&
      !error.message.includes("test-key")
  );
});

test("rejects a model outside the approved allow-list before making a request", async () => {
  let fetchCalled = false;
  const fakeFetch: typeof fetch = async () => {
    fetchCalled = true;
    return new Response(JSON.stringify({ choices: [{ message: { content: "unexpected" } }] }));
  };

  await assert.rejects(
    getAIPlatformTextResponse(
      { ...validConfig, model: "paid-or-unknown-model" },
      [],
      "system",
      fakeFetch
    ),
    (error: unknown) => error instanceof AIPlatformError && error.statusCode === 503
  );
  assert.equal(fetchCalled, false);
});

test("sends a provider-neutral chat-completions request and returns assistant text", async () => {
  let capturedUrl = "";
  let capturedInit: RequestInit | undefined;
  const fakeFetch: typeof fetch = async (input, init) => {
    capturedUrl = String(input);
    capturedInit = init;
    return new Response(
      JSON.stringify({ id: "chatcmpl-test", model: "provider/model-v1", usage: { prompt_tokens: 12, completion_tokens: 8 }, choices: [{ message: { role: "assistant", content: "What problem should this solve?" } }] }),
      { status: 200, headers: {
        "Content-Type": "application/json",
        "X-OmniRoute-Provider": "example-provider",
        "X-OmniRoute-Model": "provider/model-v1",
        "X-OmniRoute-Tokens-In": "12",
        "X-OmniRoute-Tokens-Out": "8",
        "X-OmniRoute-Response-Cost": "0.0000000000",
        "X-OmniRoute-Latency-Ms": "125",
        "X-OmniRoute-Fallback-Attempts": "0",
        "X-OmniRoute-Cache-Hit": "false",
        "X-OmniRoute-Request-Id": "or-req-test",
        "X-OmniRoute-Version": "test-version"
      } }
    );
  };

  const result = await getAIPlatformTextResponse(
    validConfig,
    [{ role: "user", text: "Build a report" }],
    "You are a discovery assistant.",
    fakeFetch
  );

  assert.equal(result.content, "What problem should this solve?");
  assert.equal(result.requestedModel, "verified-free-model");
  assert.equal(result.actualModel, "provider/model-v1");
  assert.equal(result.provider, "example-provider");
  assert.equal(result.inputTokens, 12);
  assert.equal(result.outputTokens, 8);
  assert.equal(result.costUsd, "0.0000000000");
  assert.equal(result.gatewayLatencyMs, 125);
  assert.equal(result.fallbackAttempts, 0);
  assert.equal(result.cacheHit, false);
  assert.equal(result.gatewayRequestId, "or-req-test");
  assert.equal(result.gatewayVersion, "test-version");
  assert.match(result.promptText, /Build a report/);
  assert.equal(capturedUrl, "https://llm.example.test/v1/chat/completions");
  assert.equal((capturedInit?.headers as Record<string, string>).Authorization, "Bearer test-key-not-a-real-secret");
  const body = JSON.parse(String(capturedInit?.body));
  assert.equal(body.model, "verified-free-model");
  assert.equal(body.stream, false);
  assert.deepEqual(body.messages, [
    { role: "system", content: "You are a discovery assistant." },
    { role: "user", content: "Build a report" },
  ]);
});

test("sanitizes upstream quota errors and does not retry or fall back", async () => {
  let callCount = 0;
  const fakeFetch: typeof fetch = async () => {
    callCount += 1;
    return new Response("provider details and sensitive diagnostics", { status: 429 });
  };

  await assert.rejects(
    getAIPlatformTextResponse(validConfig, [], "system", fakeFetch),
    (error: unknown) =>
      error instanceof AIPlatformError &&
      error.statusCode === 503 &&
      error.message.includes("No fallback") &&
      !error.message.includes("sensitive diagnostics")
  );
  assert.equal(callCount, 1);
});

test("sanitizes malformed successful responses", async () => {
  const fakeFetch: typeof fetch = async () => new Response("not-json", { status: 200 });

  await assert.rejects(
    getAIPlatformTextResponse(validConfig, [], "system", fakeFetch),
    (error: unknown) =>
      error instanceof AIPlatformError &&
      error.statusCode === 502 &&
      error.message === "AI Platform returned an invalid response."
  );
});
