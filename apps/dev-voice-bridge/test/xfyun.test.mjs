import test from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";

import {
  buildXFYunAuthURL,
  extractPCMFromWav,
  transcribeWithXFYun,
} from "../src/xfyun.mjs";

function createMonoPcmWavBuffer({
  sampleRate = 16000,
  samples = [0, 1200, -1200, 2400],
} = {}) {
  const pcm = Buffer.alloc(samples.length * 2);
  samples.forEach((sample, index) => {
    pcm.writeInt16LE(sample, index * 2);
  });

  const output = Buffer.alloc(44 + pcm.length);
  output.write("RIFF", 0, "ascii");
  output.writeUInt32LE(36 + pcm.length, 4);
  output.write("WAVE", 8, "ascii");
  output.write("fmt ", 12, "ascii");
  output.writeUInt32LE(16, 16);
  output.writeUInt16LE(1, 20);
  output.writeUInt16LE(1, 22);
  output.writeUInt32LE(sampleRate, 24);
  output.writeUInt32LE(sampleRate * 2, 28);
  output.writeUInt16LE(2, 32);
  output.writeUInt16LE(16, 34);
  output.write("data", 36, "ascii");
  output.writeUInt32LE(pcm.length, 40);
  pcm.copy(output, 44);
  return output;
}

test("builds an authenticated XFYun websocket url", () => {
  const url = buildXFYunAuthURL({
    endpoint: "wss://iat-api.xfyun.cn/v2/iat",
    apiKey: "xf-api-key",
    apiSecret: "xf-api-secret",
    date: "Wed, 10 Jul 2019 07:35:43 GMT",
  });

  const parsed = new URL(url);
  assert.equal(parsed.origin, "wss://iat-api.xfyun.cn");
  assert.equal(parsed.pathname, "/v2/iat");
  assert.equal(parsed.searchParams.get("host"), "iat-api.xfyun.cn");
  assert.equal(parsed.searchParams.get("date"), "Wed, 10 Jul 2019 07:35:43 GMT");

  const authorizationOrigin = Buffer.from(
    parsed.searchParams.get("authorization"),
    "base64",
  ).toString("utf8");
  assert.match(authorizationOrigin, /api_key="xf-api-key"/);
  assert.match(authorizationOrigin, /algorithm="hmac-sha256"/);
  assert.match(authorizationOrigin, /headers="host date request-line"/);
});

test("extracts mono pcm frames from a wav buffer", () => {
  const wavBuffer = createMonoPcmWavBuffer({
    sampleRate: 16000,
    samples: [10, -10, 42],
  });

  const { pcmBuffer, sampleRate } = extractPCMFromWav(wavBuffer);
  assert.equal(sampleRate, 16000);
  assert.equal(pcmBuffer.length, 6);
  assert.equal(pcmBuffer.readInt16LE(0), 10);
  assert.equal(pcmBuffer.readInt16LE(2), -10);
  assert.equal(pcmBuffer.readInt16LE(4), 42);
});

test("streams pcm frames to XFYun and returns the merged transcript", async () => {
  const sentPayloads = [];

  class MockWebSocket extends EventEmitter {
    constructor(url) {
      super();
      this.url = url;
      queueMicrotask(() => this.emit("open"));
    }

    send(payload) {
      const parsed = JSON.parse(payload);
      sentPayloads.push(parsed);

      if (parsed.data?.status === 0) {
        queueMicrotask(() =>
          this.emit(
            "message",
            Buffer.from(
              JSON.stringify({
                code: 0,
                message: "success",
                data: {
                  status: 1,
                  result: {
                    sn: 1,
                    ls: false,
                    ws: [{ cw: [{ w: "你好" }] }],
                  },
                },
              }),
              "utf8",
            ),
          ),
        );
        return;
      }

      if (parsed.data?.status === 2) {
        queueMicrotask(() =>
          this.emit(
            "message",
            Buffer.from(
              JSON.stringify({
                code: 0,
                message: "success",
                data: {
                  status: 2,
                  result: {
                    sn: 2,
                    ls: true,
                    ws: [{ cw: [{ w: "世界" }] }],
                  },
                },
              }),
              "utf8",
            ),
          ),
        );
      }
    }

    close() {
      queueMicrotask(() => this.emit("close"));
    }
  }

  const transcript = await transcribeWithXFYun({
    appId: "xf-app-id",
    apiKey: "xf-api-key",
    apiSecret: "xf-api-secret",
    audioBuffer: createMonoPcmWavBuffer({
      sampleRate: 16000,
      samples: new Array(1600).fill(200),
    }),
    mimeType: "audio/wav",
    language: "zh-CN",
    WebSocketImpl: MockWebSocket,
    sleepFn: async () => {},
    timeoutMs: 1000,
  });

  assert.equal(transcript, "你好世界");
  assert.equal(sentPayloads[0].common.app_id, "xf-app-id");
  assert.equal(sentPayloads[0].business.language, "zh_cn");
  assert.equal(sentPayloads[0].business.domain, "iat");
  assert.equal(sentPayloads[0].business.accent, "mandarin");
  assert.equal(sentPayloads[0].data.format, "audio/L16;rate=16000");
  assert.equal(sentPayloads[0].data.encoding, "raw");
  assert.equal(sentPayloads.at(-1).data.status, 2);
});

test("surfaces XFYun service errors", async () => {
  class MockWebSocket extends EventEmitter {
    constructor() {
      super();
      queueMicrotask(() => this.emit("open"));
    }

    send() {
      queueMicrotask(() =>
        this.emit(
          "message",
          Buffer.from(
            JSON.stringify({
              code: 11200,
              message: "service not authorized",
            }),
            "utf8",
          ),
        ),
      );
    }

    close() {
      queueMicrotask(() => this.emit("close"));
    }
  }

  await assert.rejects(
    () =>
      transcribeWithXFYun({
        appId: "xf-app-id",
        apiKey: "xf-api-key",
        apiSecret: "xf-api-secret",
        audioBuffer: createMonoPcmWavBuffer(),
        mimeType: "audio/wav",
        WebSocketImpl: MockWebSocket,
        sleepFn: async () => {},
        timeoutMs: 1000,
      }),
    /service not authorized/,
  );
});
