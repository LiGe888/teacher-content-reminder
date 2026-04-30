import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { Readable } from "node:stream";
import { fileURLToPath } from "node:url";

import { createRequestHandler } from "../src/server.mjs";

const TEST_DIR = dirname(fileURLToPath(import.meta.url));
const APP_ROOT = resolve(TEST_DIR, "..");

function createMockResponse() {
  return {
    statusCode: 200,
    headers: {},
    body: "",
    writeHead(statusCode, headers) {
      this.statusCode = statusCode;
      this.headers = headers;
    },
    end(chunk = "") {
      this.body += chunk;
    },
  };
}

function createMockRequest({ method = "GET", url = "/", body = null } = {}) {
  const payload =
    body === null || body === undefined
      ? []
      : [Buffer.from(typeof body === "string" ? body : JSON.stringify(body), "utf8")];
  const request = Readable.from(payload);
  request.method = method;
  request.url = url;
  request.headers = {
    host: "127.0.0.1",
    "content-type": "application/json",
  };
  return request;
}

async function withHandler(runAssertions) {
  const tempDir = mkdtempSync(join(tmpdir(), "voice-bridge-test-"));
  const historyItems = [];
  const pastedPayloads = [];

  const config = {
    publicDir: join(APP_ROOT, "public"),
    historyPath: join(tempDir, "history.json"),
    defaultGlossaryPath: join(APP_ROOT, "config", "default-glossary.json"),
    userGlossaryPath: join(tempDir, "user-glossary.json"),
    openAIApiKey: "",
    openAIModel: "gpt-4o-mini-transcribe",
    doubaoApiKey: "",
    doubaoAppKey: "",
    doubaoAccessKey: "",
    doubaoUid: "voice-bridge",
    doubaoEndpoint: "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash",
    doubaoResourceId: "volc.bigasr.auc_turbo",
    doubaoModel: "bigmodel",
    dashScopeApiKey: "",
    dashScopeBaseURL: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    dashScopeModel: "qwen3-asr-flash",
    funASREndpoint: "",
    funASRModel: "funasr-local",
    transcribeProvider: "openai",
    transcribeModel: "gpt-4o-mini-transcribe",
    dryRun: true,
    host: "127.0.0.1",
    port: 0,
    defaultGlossary: [
      { spoken: "claude code", written: "Claude Code" },
      { spoken: "fast api", written: "FastAPI" },
    ],
    userGlossary: [],
    glossary: [
      { spoken: "claude code", written: "Claude Code" },
      { spoken: "fast api", written: "FastAPI" },
    ],
  };

  const requestHandler = createRequestHandler({
    config,
    getFrontmostAppFn: async () => "Claude",
    pasteTextFn: async ({ text, targetApp, dryRun }) => {
      pastedPayloads.push({ text, targetApp, dryRun });
      return {
        dryRun,
        targetApp: targetApp || "Claude",
        action: "insert_only",
        textLength: text.length,
      };
    },
    readHistoryFn: () => historyItems,
    appendHistoryFn: (_historyPath, entry) => {
      historyItems.unshift(entry);
      return historyItems;
    },
  });

  try {
    await runAssertions({
      historyItems,
      pastedPayloads,
      invoke: async ({ method = "GET", url = "/", body = null } = {}) => {
        const request = createMockRequest({ method, url, body });
        const response = createMockResponse();
        await requestHandler(request, response);
        return {
          status: response.statusCode,
          headers: response.headers,
          json: () => JSON.parse(response.body || "{}"),
          text: () => response.body,
        };
      },
    });
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

test("health endpoint reports insert-only mode", async () => {
  await withHandler(async ({ invoke }) => {
    const response = await invoke({ url: "/api/health" });
    const payload = response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.ok, true);
    assert.equal(payload.insertOnly, true);
    assert.equal(payload.apiKeyConfigured, false);
    assert.equal(payload.provider, "openai");
    assert.equal(Array.isArray(payload.providers), true);
  });
});

test("manual text transcribe endpoint normalizes glossary and filenames", async () => {
  await withHandler(async ({ invoke }) => {
    const response = await invoke({
      method: "POST",
      url: "/api/transcribe",
      body: {
        text: "ask claude code to review main dot py new line focus on fast api routes",
      },
    });

    const payload = response.json();
    assert.equal(response.status, 200);
    assert.equal(
      payload.normalizedText,
      "ask Claude Code to review main.py\nfocus on FastAPI routes",
    );
  });
});

test("commit endpoint inserts text and records history", async () => {
  await withHandler(async ({ invoke, historyItems, pastedPayloads }) => {
    const response = await invoke({
      method: "POST",
      url: "/api/commit",
      body: {
        text: "hello from server test",
        mode: "chat",
        targetApp: "Codex",
      },
    });

    const payload = response.json();
    assert.equal(response.status, 200);
    assert.equal(payload.ok, true);
    assert.equal(payload.action, "insert_only");
    assert.equal(payload.targetApp, "Codex");
    assert.equal(pastedPayloads.length, 1);
    assert.equal(pastedPayloads[0].text, "hello from server test");
    assert.equal(historyItems.length, 1);
    assert.equal(historyItems[0].targetApp, "Codex");
  });
});

test("static manifest is served with the expected content type", async () => {
  await withHandler(async ({ invoke }) => {
    const response = await invoke({ url: "/manifest.webmanifest" });
    const body = response.text();

    assert.equal(response.status, 200);
    assert.equal(
      response.headers["Content-Type"] || response.headers["content-type"],
      "application/manifest+json; charset=utf-8",
    );
    assert.match(body, /"name": "Dev Voice Bridge"/);
  });
});

test("glossary endpoint saves and returns user glossary entries", async () => {
  await withHandler(async ({ invoke }) => {
    const saveResponse = await invoke({
      method: "POST",
      url: "/api/glossary",
      body: {
        items: [
          { spoken: "co pilot", written: "Copilot" },
          { spoken: "p n p m", written: "pnpm" },
        ],
      },
    });

    const savePayload = saveResponse.json();
    assert.equal(saveResponse.status, 200);
    assert.equal(savePayload.ok, true);
    assert.equal(savePayload.userItems.length, 2);

    const getResponse = await invoke({ url: "/api/glossary" });
    const getPayload = getResponse.json();
    assert.equal(getResponse.status, 200);
    assert.equal(getPayload.userItems.length, 2);
    assert.equal(getPayload.mergedItems.some((item) => item.written === "pnpm"), true);
  });
});

test("audio transcription forwards provider and language to the transcribe function", async () => {
  const calls = [];

  await withHandler(async ({ invoke }) => {
    const config = {
      publicDir: join(APP_ROOT, "public"),
      historyPath: join(tmpdir(), "unused-history.json"),
      defaultGlossaryPath: join(APP_ROOT, "config", "default-glossary.json"),
      userGlossaryPath: join(tmpdir(), "unused-user-glossary.json"),
      openAIApiKey: "",
      openAIModel: "gpt-4o-mini-transcribe",
      doubaoApiKey: "",
      doubaoAppKey: "",
      doubaoAccessKey: "",
      doubaoUid: "voice-bridge",
      doubaoEndpoint: "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash",
      doubaoResourceId: "volc.bigasr.auc_turbo",
      doubaoModel: "bigmodel",
      dashScopeApiKey: "dashscope-key",
      dashScopeBaseURL: "https://dashscope.aliyuncs.com/compatible-mode/v1",
      dashScopeModel: "qwen3-asr-flash",
      funASREndpoint: "",
      funASRModel: "funasr-local",
      transcribeProvider: "dashscope",
      transcribeModel: "qwen3-asr-flash",
      dryRun: true,
      host: "127.0.0.1",
      port: 0,
      defaultGlossary: [],
      userGlossary: [],
      glossary: [],
    };

    const requestHandler = createRequestHandler({
      config,
      transcribeFn: async (payload) => {
        calls.push(payload);
        return "你好，Claude Code";
      },
      getFrontmostAppFn: async () => "Claude",
      pasteTextFn: async ({ text, targetApp, dryRun }) => ({
        dryRun,
        targetApp: targetApp || "Claude",
        action: "insert_only",
        textLength: text.length,
      }),
      readHistoryFn: () => [],
      appendHistoryFn: () => [],
    });

    const request = createMockRequest({
      method: "POST",
      url: "/api/transcribe",
      body: {
        provider: "dashscope",
        language: "zh-CN",
        mimeType: "audio/wav",
        audioBase64: Buffer.from("fake-audio", "utf8").toString("base64"),
      },
    });
    const response = createMockResponse();
    await requestHandler(request, response);

    assert.equal(response.statusCode, 200);
    const payload = JSON.parse(response.body);
    assert.equal(payload.transcript, "你好，Claude Code");
    assert.equal(calls.length, 1);
    assert.equal(calls[0].provider, "dashscope");
    assert.equal(calls[0].language, "zh-CN");
  });
});
