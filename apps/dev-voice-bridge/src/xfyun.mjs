import { createHmac } from "node:crypto";
import { WebSocket } from "ws";

const DEFAULT_ENDPOINT = "wss://iat-api.xfyun.cn/v2/iat";

function toRFC1123Date(value = new Date()) {
  if (typeof value === "string") {
    return value;
  }

  return value.toUTCString();
}

export function buildXFYunAuthURL({
  endpoint = DEFAULT_ENDPOINT,
  apiKey,
  apiSecret,
  date = new Date(),
} = {}) {
  if (!apiKey || !apiSecret) {
    throw new Error("XFYun API credentials are missing.");
  }

  const url = new URL(endpoint);
  const requestDate = toRFC1123Date(date);
  const requestLine = `GET ${url.pathname} HTTP/1.1`;
  const signatureOrigin = `host: ${url.host}\ndate: ${requestDate}\n${requestLine}`;
  const signature = createHmac("sha256", apiSecret).update(signatureOrigin).digest("base64");
  const authorizationOrigin =
    `api_key="${apiKey}", algorithm="hmac-sha256", headers="host date request-line", signature="${signature}"`;
  const authorization = Buffer.from(authorizationOrigin, "utf8").toString("base64");

  url.searchParams.set("host", url.host);
  url.searchParams.set("date", requestDate);
  url.searchParams.set("authorization", authorization);
  return url.toString();
}

function mapLanguageToBusinessParams(language = "", defaultAccent = "mandarin") {
  const normalized = String(language ?? "")
    .trim()
    .toLowerCase();

  if (!normalized || normalized === "zh" || normalized === "zh-cn") {
    return { language: "zh_cn", accent: defaultAccent || "mandarin" };
  }

  if (normalized === "yue" || normalized.startsWith("zh-hk")) {
    return { language: "zh_cn", accent: "cantonese" };
  }

  if (normalized === "en" || normalized === "en-us") {
    return { language: "en_us", accent: "mandarin" };
  }

  return {
    language: normalized.replaceAll("-", "_"),
    accent: defaultAccent || "mandarin",
  };
}

function extractTextFromResult(result = {}) {
  return (result.ws || [])
    .map((segment) => segment?.cw?.[0]?.w ?? "")
    .join("")
    .trim();
}

function joinSegmentsBySequence(segments) {
  return [...segments.entries()]
    .sort((left, right) => left[0] - right[0])
    .map(([, text]) => text)
    .join("")
    .trim();
}

export function extractPCMFromWav(audioBuffer) {
  const buffer = Buffer.isBuffer(audioBuffer) ? audioBuffer : Buffer.from(audioBuffer);
  if (buffer.length < 44) {
    throw new Error("XFYun expects a WAV file with a PCM header.");
  }

  if (buffer.subarray(0, 4).toString("ascii") !== "RIFF") {
    throw new Error("Invalid WAV header: missing RIFF.");
  }

  if (buffer.subarray(8, 12).toString("ascii") !== "WAVE") {
    throw new Error("Invalid WAV header: missing WAVE.");
  }

  let offset = 12;
  let formatChunk = null;
  let pcmChunk = null;

  while (offset + 8 <= buffer.length) {
    const chunkId = buffer.subarray(offset, offset + 4).toString("ascii");
    const chunkSize = buffer.readUInt32LE(offset + 4);
    const chunkDataStart = offset + 8;
    const chunkDataEnd = chunkDataStart + chunkSize;

    if (chunkDataEnd > buffer.length) {
      throw new Error("Invalid WAV header: chunk length exceeds file size.");
    }

    if (chunkId === "fmt ") {
      formatChunk = buffer.subarray(chunkDataStart, chunkDataEnd);
    } else if (chunkId === "data") {
      pcmChunk = buffer.subarray(chunkDataStart, chunkDataEnd);
    }

    offset = chunkDataEnd + (chunkSize % 2);
  }

  if (!formatChunk || formatChunk.length < 16) {
    throw new Error("Invalid WAV header: missing fmt chunk.");
  }

  if (!pcmChunk) {
    throw new Error("Invalid WAV header: missing data chunk.");
  }

  const audioFormat = formatChunk.readUInt16LE(0);
  const channelCount = formatChunk.readUInt16LE(2);
  const sampleRate = formatChunk.readUInt32LE(4);
  const bitsPerSample = formatChunk.readUInt16LE(14);

  if (audioFormat !== 1) {
    throw new Error("XFYun only supports PCM WAV input in this bridge.");
  }

  if (channelCount !== 1) {
    throw new Error("XFYun requires mono audio.");
  }

  if (bitsPerSample !== 16) {
    throw new Error("XFYun requires 16-bit PCM audio.");
  }

  if (sampleRate !== 8000 && sampleRate !== 16000) {
    throw new Error("XFYun requires 8k or 16k sample rate audio.");
  }

  return {
    pcmBuffer: pcmChunk,
    sampleRate,
  };
}

function chunkPCMBuffer(buffer, frameSize) {
  const chunks = [];
  for (let offset = 0; offset < buffer.length; offset += frameSize) {
    chunks.push(buffer.subarray(offset, Math.min(offset + frameSize, buffer.length)));
  }
  return chunks;
}

function defaultSleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

export async function transcribeWithXFYun({
  appId,
  apiKey,
  apiSecret,
  endpoint = DEFAULT_ENDPOINT,
  domain = "iat",
  accent = "mandarin",
  eos = 2000,
  audioBuffer,
  mimeType = "audio/wav",
  language = "",
  WebSocketImpl = WebSocket,
  sleepFn = defaultSleep,
  date = new Date(),
  timeoutMs = 30000,
} = {}) {
  if (!appId || !apiKey || !apiSecret) {
    throw new Error(
      "XFYun credentials are missing. Set VOICE_CODER_XFYUN_APP_ID, VOICE_CODER_XFYUN_API_KEY, and VOICE_CODER_XFYUN_API_SECRET.",
    );
  }

  const normalizedMimeType = String(mimeType ?? "")
    .split(";")[0]
    .trim()
    .toLowerCase();

  if (
    normalizedMimeType !== "audio/wav" &&
    normalizedMimeType !== "audio/x-wav" &&
    normalizedMimeType !== "audio/wave" &&
    normalizedMimeType !== "audio/vnd.wave"
  ) {
    throw new Error("XFYun transcription expects a normalized WAV recording.");
  }

  const { pcmBuffer, sampleRate } = extractPCMFromWav(audioBuffer);
  if (!pcmBuffer.length) {
    throw new Error("XFYun transcription received an empty audio payload.");
  }

  const authURL = buildXFYunAuthURL({
    endpoint,
    apiKey,
    apiSecret,
    date,
  });
  const socket = new WebSocketImpl(authURL);
  const segments = new Map();
  const frameSize = sampleRate === 16000 ? 1280 : 640;
  const format = `audio/L16;rate=${sampleRate}`;
  const businessLanguage = mapLanguageToBusinessParams(language, accent);

  return new Promise((resolve, reject) => {
    let settled = false;
    let timedOut = false;
    const timeout = setTimeout(() => {
      timedOut = true;
      settleWithError(new Error("XFYun transcription timed out."));
    }, timeoutMs);

    function cleanup() {
      clearTimeout(timeout);
    }

    function settleWithError(error) {
      if (settled) {
        return;
      }
      settled = true;
      cleanup();
      try {
        socket.close();
      } catch {
        // no-op
      }
      reject(error);
    }

    function settleWithText() {
      if (settled) {
        return;
      }

      const transcript = joinSegmentsBySequence(segments);
      if (!transcript) {
        settleWithError(new Error("XFYun transcription response did not include text."));
        return;
      }

      settled = true;
      cleanup();
      try {
        socket.close();
      } catch {
        // no-op
      }
      resolve(transcript);
    }

    async function sendFrames() {
      try {
        const chunks = chunkPCMBuffer(pcmBuffer, frameSize);
        const [firstChunk, ...restChunks] = chunks;

        socket.send(
          JSON.stringify({
            common: {
              app_id: appId,
            },
            business: {
              language: businessLanguage.language,
              domain,
              accent: businessLanguage.accent,
              eos,
              ptt: 1,
              nunum: 1,
            },
            data: {
              status: 0,
              format,
              encoding: "raw",
              audio: firstChunk.toString("base64"),
            },
          }),
        );

        for (const chunk of restChunks) {
          await sleepFn(40);
          socket.send(
            JSON.stringify({
              data: {
                status: 1,
                format,
                encoding: "raw",
                audio: chunk.toString("base64"),
              },
            }),
          );
        }

        await sleepFn(40);
        socket.send(
          JSON.stringify({
            data: {
              status: 2,
            },
          }),
        );
      } catch (error) {
        settleWithError(error);
      }
    }

    socket.on("open", () => {
      void sendFrames();
    });

    socket.on("message", (rawPayload) => {
      if (settled) {
        return;
      }

      let payload;
      try {
        payload = JSON.parse(String(rawPayload));
      } catch (error) {
        settleWithError(new Error(`XFYun returned invalid JSON: ${error.message}`));
        return;
      }

      if (payload?.code && payload.code !== 0) {
        settleWithError(new Error(payload?.message || `XFYun returned code ${payload.code}.`));
        return;
      }

      const result = payload?.data?.result;
      if (result && Number.isInteger(result.sn)) {
        segments.set(result.sn, extractTextFromResult(result));
      }

      if (payload?.data?.status === 2 || result?.ls === true) {
        settleWithText();
      }
    });

    socket.on("error", (error) => {
      settleWithError(error instanceof Error ? error : new Error(String(error)));
    });

    socket.on("close", () => {
      if (settled || timedOut) {
        return;
      }

      if (segments.size > 0) {
        settleWithText();
        return;
      }

      settleWithError(new Error("XFYun connection closed before transcription completed."));
    });
  });
}
