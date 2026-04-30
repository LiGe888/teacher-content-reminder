import { transcribeWithDoubao } from "./doubao.mjs";
import { transcribeWithDashScope } from "./dashscope.mjs";
import { transcribeWithFunASR } from "./funasr.mjs";
import { transcribeWithOpenAI } from "./openai.mjs";

export const TRANSCRIPTION_PROVIDER_IDS = ["doubao", "openai", "dashscope", "funasr"];

const PROVIDER_TITLES = {
  doubao: "豆包语音",
  openai: "OpenAI",
  dashscope: "阿里云百炼",
  funasr: "FunASR",
};

function normalizeProviderId(value, fallback = "openai") {
  const normalized = String(value ?? "")
    .trim()
    .toLowerCase();

  if (normalized === "doubao" || normalized === "volcengine" || normalized === "bytedance") {
    return "doubao";
  }

  if (normalized === "aliyun" || normalized === "dashscope") {
    return "dashscope";
  }

  if (normalized === "funasr") {
    return "funasr";
  }

  if (normalized === "openai") {
    return "openai";
  }

  return fallback;
}

function normalizeLanguage(language, providerId) {
  const value = String(language ?? "").trim();
  if (!value || value.toLowerCase() === "auto") {
    return "";
  }

  const normalized = value.replace("_", "-").toLowerCase();

  if (providerId === "dashscope") {
    if (normalized.startsWith("zh-hk") || normalized.startsWith("yue")) {
      return "yue";
    }

    if (normalized.startsWith("zh")) {
      return "zh";
    }

    if (normalized.startsWith("en")) {
      return "en";
    }

    return normalized.split("-")[0];
  }

  if (normalized.startsWith("zh")) {
    return "zh";
  }

  if (normalized.startsWith("en")) {
    return "en";
  }

  return normalized.split("-")[0];
}

function buildProviderStatus(config, providerId) {
  switch (providerId) {
    case "doubao":
      return {
        id: providerId,
        title: PROVIDER_TITLES[providerId],
        kind: "cloud",
        model: config.doubaoModel,
        configured: Boolean(config.doubaoApiKey || config.doubaoAppKey),
        ready: Boolean(config.doubaoApiKey || config.doubaoAppKey),
      };
    case "dashscope":
      return {
        id: providerId,
        title: PROVIDER_TITLES[providerId],
        kind: "cloud",
        model: config.dashScopeModel,
        configured: Boolean(config.dashScopeApiKey),
        ready: Boolean(config.dashScopeApiKey),
      };
    case "funasr":
      return {
        id: providerId,
        title: PROVIDER_TITLES[providerId],
        kind: "local",
        model: config.funASRModel,
        configured: Boolean(config.funASREndpoint),
        ready: Boolean(config.funASREndpoint),
      };
    case "openai":
    default:
      return {
        id: "openai",
        title: PROVIDER_TITLES.openai,
        kind: "cloud",
        model: config.openAIModel,
        configured: Boolean(config.openAIApiKey),
        ready: Boolean(config.openAIApiKey),
      };
  }
}

export function listProviderStatuses(config) {
  return TRANSCRIPTION_PROVIDER_IDS.map((providerId) => buildProviderStatus(config, providerId));
}

export function resolveProviderStatus(config, requestedProvider = "") {
  const fallback = normalizeProviderId(config.transcribeProvider, "openai");
  const providerId = normalizeProviderId(requestedProvider, fallback);
  return buildProviderStatus(config, providerId);
}

export async function transcribeAudioWithProvider({
  config,
  provider = "",
  audioBuffer,
  mimeType = "audio/wav",
  language = "",
} = {}) {
  const providerStatus = resolveProviderStatus(config, provider);
  const normalizedLanguage = normalizeLanguage(language, providerStatus.id);

  if (!providerStatus.ready) {
    switch (providerStatus.id) {
      case "doubao":
        throw new Error(
          "VOICE_CODER_DOUBAO_API_KEY or VOICE_CODER_DOUBAO_APP_KEY is missing.",
        );
      case "dashscope":
        throw new Error("DASHSCOPE_API_KEY is missing.");
      case "funasr":
        throw new Error("VOICE_CODER_FUNASR_URL is missing.");
      case "openai":
      default:
        throw new Error("OPENAI_API_KEY is missing.");
    }
  }

  switch (providerStatus.id) {
    case "doubao":
      return transcribeWithDoubao({
        apiKey: config.doubaoApiKey,
        appKey: config.doubaoAppKey,
        accessKey: config.doubaoAccessKey,
        uid: config.doubaoUid,
        endpoint: config.doubaoEndpoint,
        resourceId: config.doubaoResourceId,
        model: providerStatus.model,
        audioBuffer,
        mimeType,
        language: normalizedLanguage,
      });
    case "dashscope":
      return transcribeWithDashScope({
        apiKey: config.dashScopeApiKey,
        model: providerStatus.model,
        baseURL: config.dashScopeBaseURL,
        audioBuffer,
        mimeType,
        language: normalizedLanguage,
      });
    case "funasr":
      return transcribeWithFunASR({
        endpoint: config.funASREndpoint,
        audioBuffer,
        mimeType,
        language: normalizedLanguage,
      });
    case "openai":
    default:
      return transcribeWithOpenAI({
        apiKey: config.openAIApiKey,
        model: providerStatus.model,
        audioBuffer,
        mimeType,
        language: normalizedLanguage,
      });
  }
}
