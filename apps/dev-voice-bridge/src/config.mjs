import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  mergeGlossaries,
  readGlossaryFile,
} from "./glossary.mjs";

const SRC_DIR = dirname(fileURLToPath(import.meta.url));
const APP_ROOT = resolve(SRC_DIR, "..");

function coercePort(value, fallback) {
  const parsed = Number.parseInt(value ?? "", 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function resolveProvider(value) {
  const normalized = String(value ?? "")
    .trim()
    .toLowerCase();

  if (normalized === "xfyun" || normalized === "iflytek" || normalized === "xunfei") {
    return "xfyun";
  }

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

  return "";
}

function resolveDefaultProvider() {
  const explicit = resolveProvider(process.env.VOICE_CODER_TRANSCRIBE_PROVIDER);
  if (explicit) {
    return explicit;
  }

  if (
    process.env.VOICE_CODER_XFYUN_APP_ID &&
    process.env.VOICE_CODER_XFYUN_API_KEY &&
    process.env.VOICE_CODER_XFYUN_API_SECRET
  ) {
    return "xfyun";
  }

  if (process.env.VOICE_CODER_DOUBAO_API_KEY || process.env.VOICE_CODER_DOUBAO_APP_KEY) {
    return "doubao";
  }

  if (process.env.OPENAI_API_KEY) {
    return "openai";
  }

  if (process.env.DASHSCOPE_API_KEY) {
    return "dashscope";
  }

  if (process.env.VOICE_CODER_FUNASR_URL) {
    return "funasr";
  }

  return "openai";
}

export function refreshGlossary(config) {
  const defaultGlossary = readGlossaryFile(config.defaultGlossaryPath, []);
  const userGlossary = readGlossaryFile(config.userGlossaryPath, []);
  config.defaultGlossary = defaultGlossary;
  config.userGlossary = userGlossary;
  config.glossary = mergeGlossaries(defaultGlossary, userGlossary);
  return config.glossary;
}

export function loadConfig() {
  const transcribeProvider = resolveDefaultProvider();
  const legacyTranscribeModel = process.env.VOICE_CODER_TRANSCRIBE_MODEL ?? "";
  const defaultGlossaryPath =
    process.env.VOICE_CODER_GLOSSARY_PATH ??
    join(APP_ROOT, "config", "default-glossary.json");
  const userGlossaryPath =
    process.env.VOICE_CODER_USER_GLOSSARY_PATH ??
    join(APP_ROOT, "data", "user-glossary.json");

  const config = {
    appRoot: APP_ROOT,
    publicDir: join(APP_ROOT, "public"),
    historyPath: join(APP_ROOT, "data", "history.json"),
    defaultGlossaryPath,
    userGlossaryPath,
    defaultGlossary: [],
    userGlossary: [],
    glossary: [],
    host: process.env.VOICE_CODER_HOST ?? "0.0.0.0",
    port: coercePort(process.env.VOICE_CODER_PORT, 4317),
    openAIApiKey: process.env.OPENAI_API_KEY ?? "",
    openAIModel:
      process.env.VOICE_CODER_OPENAI_MODEL ??
      (transcribeProvider === "openai" && legacyTranscribeModel
        ? legacyTranscribeModel
        : "gpt-4o-mini-transcribe"),
    xfyunAppId: process.env.VOICE_CODER_XFYUN_APP_ID ?? "",
    xfyunApiKey: process.env.VOICE_CODER_XFYUN_API_KEY ?? "",
    xfyunApiSecret: process.env.VOICE_CODER_XFYUN_API_SECRET ?? "",
    xfyunEndpoint:
      process.env.VOICE_CODER_XFYUN_ENDPOINT ?? "wss://iat-api.xfyun.cn/v2/iat",
    xfyunDomain:
      process.env.VOICE_CODER_XFYUN_DOMAIN ??
      process.env.VOICE_CODER_XFYUN_MODEL ??
      (transcribeProvider === "xfyun" && legacyTranscribeModel ? legacyTranscribeModel : "iat"),
    xfyunAccent: process.env.VOICE_CODER_XFYUN_ACCENT ?? "mandarin",
    xfyunEos: coercePort(process.env.VOICE_CODER_XFYUN_EOS, 2000),
    xfyunModel:
      process.env.VOICE_CODER_XFYUN_MODEL ??
      process.env.VOICE_CODER_XFYUN_DOMAIN ??
      (transcribeProvider === "xfyun" && legacyTranscribeModel ? legacyTranscribeModel : "iat"),
    doubaoApiKey: process.env.VOICE_CODER_DOUBAO_API_KEY ?? "",
    doubaoAppKey: process.env.VOICE_CODER_DOUBAO_APP_KEY ?? "",
    doubaoAccessKey: process.env.VOICE_CODER_DOUBAO_ACCESS_KEY ?? "",
    doubaoUid:
      process.env.VOICE_CODER_DOUBAO_UID ??
      process.env.VOICE_CODER_DOUBAO_APP_KEY ??
      "voice-bridge",
    doubaoEndpoint:
      process.env.VOICE_CODER_DOUBAO_ENDPOINT ??
      "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash",
    doubaoResourceId:
      process.env.VOICE_CODER_DOUBAO_RESOURCE_ID ?? "volc.bigasr.auc_turbo",
    doubaoModel:
      process.env.VOICE_CODER_DOUBAO_MODEL ??
      (transcribeProvider === "doubao" && legacyTranscribeModel
        ? legacyTranscribeModel
        : "bigmodel"),
    dashScopeApiKey: process.env.DASHSCOPE_API_KEY ?? "",
    dashScopeBaseURL:
      process.env.VOICE_CODER_DASHSCOPE_BASE_URL ??
      "https://dashscope.aliyuncs.com/compatible-mode/v1",
    dashScopeModel:
      process.env.VOICE_CODER_DASHSCOPE_MODEL ?? "qwen3-asr-flash",
    funASREndpoint: process.env.VOICE_CODER_FUNASR_URL ?? "",
    funASRModel:
      process.env.VOICE_CODER_FUNASR_MODEL ?? "funasr-local",
    transcribeProvider,
    dryRun: process.env.VOICE_CODER_DRY_RUN === "1",
  };

  config.transcribeModel =
    config.transcribeProvider === "xfyun"
      ? config.xfyunModel
      : config.transcribeProvider === "doubao"
      ? config.doubaoModel
      : config.transcribeProvider === "dashscope"
      ? config.dashScopeModel
      : config.transcribeProvider === "funasr"
        ? config.funASRModel
        : config.openAIModel;

  refreshGlossary(config);
  return config;
}
