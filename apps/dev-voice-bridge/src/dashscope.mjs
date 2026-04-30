function mimeToDataUri(mimeType, audioBuffer) {
  const safeMimeType = mimeType || "audio/wav";
  return `data:${safeMimeType};base64,${audioBuffer.toString("base64")}`;
}

function extractContentText(content) {
  if (typeof content === "string") {
    return content.trim();
  }

  if (Array.isArray(content)) {
    return content
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }

        if (typeof item?.text === "string") {
          return item.text;
        }

        return "";
      })
      .join("")
      .trim();
  }

  return "";
}

export async function transcribeWithDashScope({
  apiKey,
  model,
  audioBuffer,
  mimeType = "audio/wav",
  language = "",
  baseURL = "https://dashscope.aliyuncs.com/compatible-mode/v1",
} = {}) {
  if (!apiKey) {
    throw new Error("DASHSCOPE_API_KEY is missing.");
  }

  if (!model) {
    throw new Error("DashScope model is missing.");
  }

  const response = await fetch(`${baseURL.replace(/\/$/, "")}/chat/completions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json; charset=utf-8",
    },
    body: JSON.stringify({
      model,
      messages: [
        {
          role: "user",
          content: [
            {
              type: "input_audio",
              input_audio: {
                data: mimeToDataUri(mimeType, audioBuffer),
              },
            },
          ],
        },
      ],
      stream: false,
      asr_options: {
        enable_itn: true,
        ...(language ? { language } : {}),
      },
    }),
  });

  const payload = await response.json();
  if (!response.ok) {
    const message =
      payload?.error?.message ??
      payload?.message ??
      `DashScope transcription failed with status ${response.status}.`;
    throw new Error(message);
  }

  const text = extractContentText(payload?.choices?.[0]?.message?.content);
  if (!text) {
    throw new Error("DashScope transcription response did not include text.");
  }

  return text;
}
