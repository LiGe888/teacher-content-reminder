function mimeToExtension(mimeType) {
  switch (mimeType) {
    case "audio/mp4":
    case "audio/m4a":
      return "m4a";
    case "audio/webm":
      return "webm";
    case "audio/wav":
      return "wav";
    default:
      return "webm";
  }
}

export async function transcribeWithOpenAI({
  apiKey,
  model,
  audioBuffer,
  mimeType = "audio/webm",
  language = "",
} = {}) {
  if (!apiKey) {
    throw new Error("OPENAI_API_KEY is missing.");
  }

  const form = new FormData();
  const extension = mimeToExtension(mimeType);
  const file = new Blob([audioBuffer], { type: mimeType });

  form.append("file", file, `voice.${extension}`);
  form.append("model", model);

  if (language) {
    form.append("language", language);
  }

  const response = await fetch("https://api.openai.com/v1/audio/transcriptions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
    },
    body: form,
  });

  const payload = await response.json();
  if (!response.ok) {
    const message =
      payload?.error?.message ??
      `OpenAI transcription failed with status ${response.status}.`;
    throw new Error(message);
  }

  if (!payload.text) {
    throw new Error("OpenAI transcription response did not include text.");
  }

  return payload.text;
}
