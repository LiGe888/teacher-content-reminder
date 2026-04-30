import test from "node:test";
import assert from "node:assert/strict";

import { loadConfig } from "../src/config.mjs";

function withEnv(overrides, fn) {
  const previous = new Map(
    Object.keys(overrides).map((key) => [key, Object.prototype.hasOwnProperty.call(process.env, key) ? process.env[key] : undefined]),
  );

  try {
    for (const [key, value] of Object.entries(overrides)) {
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }

    return fn();
  } finally {
    for (const [key, value] of previous.entries()) {
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }
  }
}

test("prefers doubao when Doubao credentials are configured", () => {
  withEnv(
    {
      VOICE_CODER_TRANSCRIBE_PROVIDER: "",
      VOICE_CODER_TRANSCRIBE_MODEL: undefined,
      VOICE_CODER_DOUBAO_API_KEY: "doubao-key",
      VOICE_CODER_DOUBAO_APP_KEY: "",
      VOICE_CODER_DOUBAO_UID: undefined,
      OPENAI_API_KEY: "",
      DASHSCOPE_API_KEY: "",
      VOICE_CODER_FUNASR_URL: "",
    },
    () => {
      const config = loadConfig();
      assert.equal(config.transcribeProvider, "doubao");
      assert.equal(config.transcribeModel, "bigmodel");
    },
  );
});

test("resolves the volcengine alias to doubao and applies legacy model fallback", () => {
  withEnv(
    {
      VOICE_CODER_TRANSCRIBE_PROVIDER: "volcengine",
      VOICE_CODER_TRANSCRIBE_MODEL: "legacy-doubao-model",
      VOICE_CODER_DOUBAO_API_KEY: "",
      VOICE_CODER_DOUBAO_APP_KEY: "doubao-app-key",
      VOICE_CODER_DOUBAO_UID: undefined,
    },
    () => {
      const config = loadConfig();
      assert.equal(config.transcribeProvider, "doubao");
      assert.equal(config.transcribeModel, "legacy-doubao-model");
      assert.equal(config.doubaoUid, "doubao-app-key");
    },
  );
});
