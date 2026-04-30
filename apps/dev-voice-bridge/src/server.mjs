import { createServer } from "node:http";
import { randomUUID } from "node:crypto";
import { networkInterfaces } from "node:os";
import { extname, join, normalize } from "node:path";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { getFrontmostApp, pasteText } from "./apple.mjs";
import { loadConfig, refreshGlossary } from "./config.mjs";
import { appendHistory, readHistory } from "./history.mjs";
import { normalizeDeveloperText } from "./normalize.mjs";
import {
  listProviderStatuses,
  resolveProviderStatus,
  transcribeAudioWithProvider,
} from "./providers.mjs";
import { writeGlossaryFile } from "./glossary.mjs";

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".webmanifest": "application/manifest+json; charset=utf-8",
};

function json(response, statusCode, payload) {
  response.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  response.end(JSON.stringify(payload));
}

function notFound(response) {
  json(response, 404, { error: "Not found" });
}

async function readJsonBody(request, maxBytes = 20 * 1024 * 1024) {
  const chunks = [];
  let total = 0;

  for await (const chunk of request) {
    total += chunk.length;
    if (total > maxBytes) {
      throw new Error("Request body too large.");
    }
    chunks.push(chunk);
  }

  const raw = Buffer.concat(chunks).toString("utf8");
  return raw ? JSON.parse(raw) : {};
}

async function serveStatic(request, response) {
  const config = request.appConfig;
  const url = new URL(request.url, `http://${request.headers.host}`);
  const routePath = url.pathname === "/" ? "/index.html" : url.pathname;
  const filePath = normalize(join(config.publicDir, routePath));

  if (!filePath.startsWith(config.publicDir)) {
    notFound(response);
    return;
  }

  try {
    const content = await readFile(filePath);
    const contentType = MIME_TYPES[extname(filePath)] ?? "application/octet-stream";
    response.writeHead(200, { "Content-Type": contentType });
    response.end(content);
  } catch {
    notFound(response);
  }
}

function listLocalUrls(host, port) {
  const urls = [`http://localhost:${port}`];
  const interfaces = networkInterfaces();

  for (const entries of Object.values(interfaces)) {
    for (const entry of entries ?? []) {
      if (entry.family === "IPv4" && !entry.internal) {
        urls.push(`http://${entry.address}:${port}`);
      }
    }
  }

  if (host !== "0.0.0.0" && host !== "::") {
    urls.push(`http://${host}:${port}`);
  }

  return [...new Set(urls)];
}

async function handleTranscribe(request, response, context) {
  const { config, transcribeFn } = context;
  const body = await readJsonBody(request);
  const {
    text = "",
    audioBase64 = "",
    mimeType = "audio/webm",
    language = "",
    provider = "",
  } = body;

  let transcript = String(text ?? "").trim();

  if (!transcript) {
    if (!audioBase64) {
      json(response, 400, { error: "Either text or audioBase64 is required." });
      return;
    }

    const providerStatus = resolveProviderStatus(config, provider);
    if (!providerStatus.ready) {
      json(response, 400, {
        error: `${providerStatus.title} is not configured. You can still use manual text input for bridge testing.`,
      });
      return;
    }

    const audioBuffer = Buffer.from(audioBase64, "base64");
    transcript = await transcribeFn({
      config,
      provider,
      audioBuffer,
      mimeType,
      language,
    });
  }

  const normalizedText = normalizeDeveloperText(transcript, config.glossary);
  json(response, 200, {
    transcript,
    normalizedText,
    usedGlossary: config.glossary.length > 0,
  });
}

async function handleGlossary(request, response, context) {
  const { config } = context;

  if (request.method === "GET") {
    json(response, 200, {
      defaultItems: config.defaultGlossary,
      userItems: config.userGlossary,
      mergedItems: config.glossary,
    });
    return;
  }

  if (request.method === "POST") {
    const body = await readJsonBody(request);
    const items = Array.isArray(body.items) ? body.items : [];
    const normalized = writeGlossaryFile(config.userGlossaryPath, items);
    config.userGlossary = normalized;
    refreshGlossary(config);
    json(response, 200, {
      ok: true,
      defaultItems: config.defaultGlossary,
      userItems: config.userGlossary,
      mergedItems: config.glossary,
    });
    return;
  }

  notFound(response);
}

async function handleCommit(request, response, context) {
  const { config, pasteTextFn, appendHistoryFn } = context;
  const body = await readJsonBody(request);
  const {
    text = "",
    mode = "chat",
    targetApp = "",
  } = body;

  const finalText = String(text ?? "").trim();
  if (!finalText) {
    json(response, 400, { error: "Text is required." });
    return;
  }

  const result = await pasteTextFn({
    text: finalText,
    targetApp: targetApp || null,
    dryRun: config.dryRun,
  });

  const entry = {
    id: randomUUID(),
    createdAt: new Date().toISOString(),
    mode,
    targetApp: result.targetApp,
    action: result.action,
    text: finalText,
    dryRun: result.dryRun,
  };

  appendHistoryFn(config.historyPath, entry);
  json(response, 200, {
    ok: true,
    ...result,
    historyEntry: entry,
  });
}

async function handleApi(request, response, context) {
  const { config, getFrontmostAppFn, readHistoryFn } = context;
  const url = new URL(request.url, `http://${request.headers.host}`);

  if (request.method === "GET" && url.pathname === "/api/health") {
    const providerStatus = resolveProviderStatus(config);
    json(response, 200, {
      ok: true,
      provider: providerStatus.id,
      providerTitle: providerStatus.title,
      model: providerStatus.model,
      apiKeyConfigured: providerStatus.ready,
      providers: listProviderStatuses(config),
      dryRun: config.dryRun,
      insertOnly: true,
      urls: listLocalUrls(config.host, config.port),
    });
    return;
  }

  if (request.method === "GET" && url.pathname === "/api/target") {
    try {
      const appName = await getFrontmostAppFn();
      json(response, 200, { appName });
    } catch (error) {
      json(response, 500, { error: error.message });
    }
    return;
  }

  if (request.method === "GET" && url.pathname === "/api/history") {
    json(response, 200, { items: readHistoryFn(config.historyPath).slice(0, 20) });
    return;
  }

  if (url.pathname === "/api/glossary") {
    await handleGlossary(request, response, context);
    return;
  }

  if (request.method === "POST" && url.pathname === "/api/transcribe") {
    await handleTranscribe(request, response, context);
    return;
  }

  if (request.method === "POST" && url.pathname === "/api/commit") {
    await handleCommit(request, response, context);
    return;
  }

  notFound(response);
}

export function createRequestHandler(options = {}) {
  const config = options.config ?? loadConfig();
  const context = {
    config,
    getFrontmostAppFn: options.getFrontmostAppFn ?? getFrontmostApp,
    pasteTextFn: options.pasteTextFn ?? pasteText,
    transcribeFn: options.transcribeFn ?? transcribeAudioWithProvider,
    readHistoryFn: options.readHistoryFn ?? readHistory,
    appendHistoryFn: options.appendHistoryFn ?? appendHistory,
  };

  return async (request, response) => {
    request.appConfig = config;

    try {
      if ((request.url ?? "").startsWith("/api/")) {
        await handleApi(request, response, context);
        return;
      }

      await serveStatic(request, response);
    } catch (error) {
      json(response, 500, { error: error.message ?? "Unknown server error." });
    }
  };
}

export function createAppServer(options = {}) {
  return createServer(createRequestHandler(options));
}

export function startServer(options = {}) {
  const config = options.config ?? loadConfig();
  const server = createAppServer({ ...options, config });
  server.listen(config.port, config.host, () => {
    console.log("Dev Voice Bridge MVP is running.");
    for (const url of listLocalUrls(config.host, config.port)) {
      console.log(`- ${url}`);
    }
  });
  return server;
}

const isMainModule = process.argv[1] === fileURLToPath(import.meta.url);
if (isMainModule) {
  startServer();
}
