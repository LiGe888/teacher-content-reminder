import test from "node:test";
import assert from "node:assert/strict";

import { transcribeWithDoubao } from "../src/doubao.mjs";

test("transcribes audio with Doubao API key auth", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];

  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ result: { text: "你好，豆包" } }), {
      status: 200,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "X-Api-Status-Code": "20000000",
        "X-Api-Message": "OK",
      },
    });
  };

  try {
    const result = await transcribeWithDoubao({
      apiKey: "doubao-key",
      uid: "voice-bridge-user",
      audioBuffer: Buffer.from("wav-data", "utf8"),
      mimeType: "audio/wav",
    });

    assert.equal(result, "你好，豆包");
    assert.equal(calls.length, 1);
    assert.equal(
      calls[0].url,
      "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash",
    );
    assert.equal(calls[0].options.method, "POST");
    assert.equal(calls[0].options.headers["X-Api-Key"], "doubao-key");
    assert.equal(calls[0].options.headers["X-Api-Resource-Id"], "volc.bigasr.auc_turbo");

    const payload = JSON.parse(calls[0].options.body);
    assert.equal(payload.user.uid, "voice-bridge-user");
    assert.equal(payload.audio.data, Buffer.from("wav-data", "utf8").toString("base64"));
    assert.equal(payload.request.model_name, "bigmodel");
    assert.equal(payload.request.enable_itn, true);
    assert.equal(payload.request.enable_punc, true);
    assert.equal(payload.request.enable_ddc, true);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("surfaces provider message when Doubao rejects a request", async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () =>
    new Response(JSON.stringify({ message: "音频格式不正确" }), {
      status: 400,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "X-Api-Status-Code": "45000151",
        "X-Api-Message": "invalid audio format",
      },
    });

  try {
    await assert.rejects(
      () =>
        transcribeWithDoubao({
          appKey: "legacy-app-key",
          accessKey: "legacy-access-key",
          audioBuffer: Buffer.from("not-a-real-file", "utf8"),
          mimeType: "audio/ogg;codecs=opus",
        }),
      /音频格式不正确/,
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("rejects unsupported mime types before issuing a request", async () => {
  await assert.rejects(
    () =>
      transcribeWithDoubao({
        apiKey: "doubao-key",
        audioBuffer: Buffer.from("webm-data", "utf8"),
        mimeType: "audio/webm",
      }),
    /WAV \/ MP3 \/ OGG Opus/,
  );
});
