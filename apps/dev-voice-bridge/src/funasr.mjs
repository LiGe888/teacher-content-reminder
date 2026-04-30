function extractText(payload) {
  if (typeof payload?.text === "string" && payload.text.trim()) {
    return payload.text.trim();
  }

  if (typeof payload?.result === "string" && payload.result.trim()) {
    return payload.result.trim();
  }

  if (typeof payload?.data?.text === "string" && payload.data.text.trim()) {
    return payload.data.text.trim();
  }

  if (Array.isArray(payload?.segments)) {
    return payload.segments
      .map((segment) => String(segment?.text ?? "").trim())
      .filter(Boolean)
      .join("")
      .trim();
  }

  return "";
}

export async function transcribeWithFunASR({
  endpoint,
  audioBuffer,
  mimeType = "audio/wav",
  language = "",
} = {}) {
  if (!endpoint) {
    throw new Error("VOICE_CODER_FUNASR_URL is missing.");
  }

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json; charset=utf-8",
    },
    body: JSON.stringify({
      audioBase64: audioBuffer.toString("base64"),
      mimeType,
      language,
    }),
  });

  let payload;
  try {
    payload = await response.json();
  } catch {
    payload = { error: await response.text() };
  }

  if (!response.ok) {
    const message =
      payload?.error ??
      payload?.message ??
      `FunASR transcription failed with status ${response.status}.`;
    throw new Error(message);
  }

  const text = extractText(payload);
  if (!text) {
    throw new Error("FunASR response did not include text.");
  }

  return text;
}
