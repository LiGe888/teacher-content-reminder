import { randomUUID } from "node:crypto";

const DEFAULT_ENDPOINT =
  "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash";

function resolveCanonicalMimeType(mimeType) {
  const normalized = String(mimeType ?? "")
    .trim()
    .toLowerCase();

  if (
    normalized === "audio/wav" ||
    normalized === "audio/x-wav" ||
    normalized === "audio/wave" ||
    normalized === "audio/vnd.wave"
  ) {
    return "audio/wav";
  }

  if (normalized === "audio/mpeg" || normalized === "audio/mp3") {
    return "audio/mpeg";
  }

  if (normalized.startsWith("audio/ogg")) {
    return "audio/ogg";
  }

  return "";
}

function buildRequestHeaders({ apiKey, appKey, accessKey, resourceId }) {
  const headers = {
    "Content-Type": "application/json; charset=utf-8",
    "X-Api-Resource-Id": resourceId || "volc.bigasr.auc_turbo",
    "X-Api-Request-Id": randomUUID(),
    "X-Api-Sequence": "-1",
  };

  if (apiKey) {
    headers["X-Api-Key"] = apiKey;
  }

  if (appKey) {
    headers["X-Api-App-Key"] = appKey;
  }

  if (accessKey) {
    headers["X-Api-Access-Key"] = accessKey;
  }

  return headers;
}

export async function transcribeWithDoubao({
  apiKey,
  appKey,
  accessKey,
  uid = "voice-bridge",
  resourceId = "volc.bigasr.auc_turbo",
  endpoint = DEFAULT_ENDPOINT,
  model = "bigmodel",
  audioBuffer,
  mimeType = "audio/wav",
  language = "",
} = {}) {
  if (!apiKey && !appKey) {
    throw new Error(
      "Doubao credentials are missing. Set VOICE_CODER_DOUBAO_API_KEY or VOICE_CODER_DOUBAO_APP_KEY.",
    );
  }

  if (!model) {
    throw new Error("Doubao model is missing.");
  }

  const canonicalMimeType = resolveCanonicalMimeType(mimeType);
  if (!canonicalMimeType) {
    throw new Error(
      "Doubao speech transcription only supports WAV / MP3 / OGG Opus input.",
    );
  }

  const response = await fetch(endpoint, {
    method: "POST",
    headers: buildRequestHeaders({ apiKey, appKey, accessKey, resourceId }),
    body: JSON.stringify({
      user: {
        uid: String(uid || appKey || "voice-bridge"),
      },
      audio: {
        data: audioBuffer.toString("base64"),
      },
      request: {
        model_name: model,
        enable_itn: true,
        enable_punc: true,
        enable_ddc: true,
      },
    }),
  });

  let payload = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }

  const providerStatusCode = response.headers.get("X-Api-Status-Code") ?? "";
  const providerMessage = response.headers.get("X-Api-Message") ?? "";
  const providerSucceeded =
    response.ok && (!providerStatusCode || providerStatusCode === "20000000");

  if (!providerSucceeded) {
    const message =
      payload?.message ??
      payload?.error?.message ??
      providerMessage ??
      `Doubao transcription failed with status ${response.status}.`;
    throw new Error(message);
  }

  const text = String(payload?.result?.text ?? "").trim();
  if (!text) {
    throw new Error("Doubao transcription response did not include text.");
  }

  return text;
}
