const healthText = document.querySelector("#healthText");
const targetText = document.querySelector("#targetText");
const recordButton = document.querySelector("#recordButton");
const refreshTargetButton = document.querySelector("#refreshTargetButton");
const transcriptInput = document.querySelector("#transcriptInput");
const normalizeButton = document.querySelector("#normalizeButton");
const commitButton = document.querySelector("#commitButton");
const messageBox = document.querySelector("#messageBox");
const modeSelect = document.querySelector("#modeSelect");
const historyList = document.querySelector("#historyList");
const refreshHistoryButton = document.querySelector("#refreshHistoryButton");
const previewModeText = document.querySelector("#previewModeText");
const browserHintText = document.querySelector("#browserHintText");
const capMediaRecorder = document.querySelector("#capMediaRecorder");
const capSpeechRecognition = document.querySelector("#capSpeechRecognition");
const capPwa = document.querySelector("#capPwa");
const targetModeText = document.querySelector("#targetModeText");
const pinnedTargetText = document.querySelector("#pinnedTargetText");
const pinTargetButton = document.querySelector("#pinTargetButton");
const clearPinnedTargetButton = document.querySelector("#clearPinnedTargetButton");
const installPwaButton = document.querySelector("#installPwaButton");
const installHintBox = document.querySelector("#installHintBox");
const glossaryList = document.querySelector("#glossaryList");
const refreshGlossaryButton = document.querySelector("#refreshGlossaryButton");
const addGlossaryRowButton = document.querySelector("#addGlossaryRowButton");
const saveGlossaryButton = document.querySelector("#saveGlossaryButton");
const defaultGlossaryCount = document.querySelector("#defaultGlossaryCount");
const userGlossaryCount = document.querySelector("#userGlossaryCount");

let mediaRecorder = null;
let recordedChunks = [];
let isRecording = false;
let speechRecognition = null;
let speechRecognitionEnabled = false;
let liveFinalTranscript = "";
let liveInterimTranscript = "";
let pinnedTargetApp = localStorage.getItem("voiceBridge.pinnedTargetApp") || "";
let deferredInstallPrompt = null;
let userGlossaryItems = [];
let activeProviderId = "openai";
let activeProviderTitle = "OpenAI";

const SpeechRecognitionCtor =
  globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition || null;
const supportsMediaRecorder = Boolean(globalThis.MediaRecorder);
const isIos = /iPhone|iPad|iPod/i.test(navigator.userAgent);
const isAndroid = /Android/i.test(navigator.userAgent);
const isChromeFamily =
  /Chrome|CriOS|EdgA|EdgiOS/i.test(navigator.userAgent) &&
  !/DuckDuckGo|FxiOS/i.test(navigator.userAgent);
const supportsPwaInstall = "serviceWorker" in navigator;

function setMessage(text, tone = "") {
  messageBox.textContent = text;
  messageBox.className = `message ${tone}`.trim();
}

function setCapabilityBadge(element, supported, supportedLabel, fallbackLabel) {
  element.textContent = supported ? supportedLabel : fallbackLabel;
  element.className = `compat-badge ${supported ? "yes" : "no"}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function refreshTargetMode() {
  const usingPinnedTarget = Boolean(pinnedTargetApp);
  targetModeText.textContent = usingPinnedTarget ? "固定投递到锁定应用" : "默认使用当前前台应用";
  pinnedTargetText.textContent = usingPinnedTarget ? pinnedTargetApp : "未锁定";
  clearPinnedTargetButton.disabled = !usingPinnedTarget;
}

function saveModePreference() {
  localStorage.setItem("voiceBridge.mode", modeSelect.value);
}

function loadModePreference() {
  const savedMode = localStorage.getItem("voiceBridge.mode");
  if (savedMode && [...modeSelect.options].some((option) => option.value === savedMode)) {
    modeSelect.value = savedMode;
  }
}

function savePinnedTargetApp(value) {
  pinnedTargetApp = value;
  if (value) {
    localStorage.setItem("voiceBridge.pinnedTargetApp", value);
  } else {
    localStorage.removeItem("voiceBridge.pinnedTargetApp");
  }
  refreshTargetMode();
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Unknown request error.");
  }
  return payload;
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = String(reader.result || "");
      resolve(result.split(",")[1] || "");
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

function normalizeMimeType(mimeType) {
  return String(mimeType ?? "")
    .split(";")[0]
    .trim()
    .toLowerCase();
}

function isDoubaoSupportedMimeType(mimeType) {
  const normalized = String(mimeType ?? "")
    .trim()
    .toLowerCase();

  return (
    normalized === "audio/wav" ||
    normalized === "audio/x-wav" ||
    normalized === "audio/wave" ||
    normalized === "audio/vnd.wave" ||
    normalized === "audio/mpeg" ||
    normalized === "audio/mp3" ||
    normalized.startsWith("audio/ogg")
  );
}

function writeWavString(view, offset, text) {
  for (let index = 0; index < text.length; index += 1) {
    view.setUint8(offset + index, text.charCodeAt(index));
  }
}

function encodeAudioBufferAsWav(audioBuffer) {
  const channelCount = Math.min(audioBuffer.numberOfChannels || 1, 2);
  const sampleRate = audioBuffer.sampleRate;
  const frameCount = audioBuffer.length;
  const bytesPerSample = 2;
  const blockAlign = channelCount * bytesPerSample;
  const dataSize = frameCount * blockAlign;
  const output = new ArrayBuffer(44 + dataSize);
  const view = new DataView(output);

  writeWavString(view, 0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeWavString(view, 8, "WAVE");
  writeWavString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, channelCount, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bytesPerSample * 8, true);
  writeWavString(view, 36, "data");
  view.setUint32(40, dataSize, true);

  let offset = 44;
  for (let frame = 0; frame < frameCount; frame += 1) {
    for (let channel = 0; channel < channelCount; channel += 1) {
      const input = audioBuffer.getChannelData(channel)[frame] ?? 0;
      const sample = Math.max(-1, Math.min(1, input));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      offset += bytesPerSample;
    }
  }

  return new Blob([output], { type: "audio/wav" });
}

async function convertAudioBlobToWav(blob) {
  const AudioContextCtor = globalThis.AudioContext || globalThis.webkitAudioContext;
  if (!AudioContextCtor) {
    throw new Error("当前浏览器无法把录音转换成豆包可识别的 WAV。");
  }

  const audioContext = new AudioContextCtor();
  try {
    const buffer = await blob.arrayBuffer();
    const audioBuffer = await audioContext.decodeAudioData(buffer.slice(0));
    return encodeAudioBufferAsWav(audioBuffer);
  } finally {
    if (typeof audioContext.close === "function") {
      await audioContext.close().catch(() => {});
    }
  }
}

async function prepareRecordedAudioForTranscription(blob, mimeType) {
  if (activeProviderId !== "doubao") {
    return {
      blob,
      mimeType,
    };
  }

  if (isDoubaoSupportedMimeType(mimeType)) {
    return {
      blob,
      mimeType: normalizeMimeType(mimeType),
    };
  }

  const convertedBlob = await convertAudioBlobToWav(blob);
  return {
    blob: convertedBlob,
    mimeType: "audio/wav",
  };
}

function pickRecorderMimeType() {
  if (!supportsMediaRecorder || typeof MediaRecorder.isTypeSupported !== "function") {
    return "";
  }

  const candidates =
    activeProviderId === "doubao"
      ? ["audio/ogg;codecs=opus", "audio/webm;codecs=opus", "audio/webm", "audio/mp4"]
      : ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];

  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) || "";
}

async function refreshHealth() {
  const payload = await fetchJson("/api/health");
  activeProviderId = payload.provider || "openai";
  activeProviderTitle = payload.providerTitle || activeProviderTitle;
  const mode = payload.apiKeyConfigured
    ? `${activeProviderTitle} 转写已启用`
    : `${activeProviderTitle} 未配置，可手动输入`;
  const dryRun = payload.dryRun ? "，当前为 dry-run" : "";
  healthText.textContent = `${mode}${dryRun}`;
}

async function refreshTarget() {
  try {
    const payload = await fetchJson("/api/target");
    targetText.textContent = payload.appName || "未知";
  } catch (error) {
    targetText.textContent = "读取失败";
    setMessage(error.message, "error");
  }
}

function renderHistory(items) {
  if (!items.length) {
    historyList.innerHTML = '<p class="history-empty">暂无历史记录</p>';
    return;
  }

  historyList.innerHTML = items
    .map(
      (item) => `
        <article class="history-item">
          <div class="history-meta">
            <strong>${item.targetApp || "unknown"}</strong>
            <span>${item.mode} · ${item.action || "insert_only"}</span>
          </div>
          <p>${(item.text || "").replaceAll("<", "&lt;").replaceAll(">", "&gt;")}</p>
        </article>
      `,
    )
    .join("");
}

async function refreshHistory() {
  const payload = await fetchJson("/api/history");
  renderHistory(payload.items || []);
}

function renderGlossaryRows(items) {
  if (!items.length) {
    glossaryList.innerHTML = "";
    return;
  }

  glossaryList.innerHTML = items
    .map(
      (item, index) => `
        <div class="glossary-row" data-index="${index}">
          <input
            type="text"
            data-field="spoken"
            value="${escapeHtml(item.spoken || "")}"
            placeholder="spoken，例如 fast api"
          />
          <input
            type="text"
            data-field="written"
            value="${escapeHtml(item.written || "")}"
            placeholder="written，例如 FastAPI"
          />
          <button type="button" class="secondary glossary-remove" data-remove-index="${index}">
            删除
          </button>
        </div>
      `,
    )
    .join("");
}

function syncGlossaryStateFromDom() {
  const rows = [...glossaryList.querySelectorAll(".glossary-row")];
  userGlossaryItems = rows
    .map((row) => ({
      spoken: row.querySelector('[data-field="spoken"]')?.value.trim() || "",
      written: row.querySelector('[data-field="written"]')?.value.trim() || "",
    }))
    .filter((entry) => entry.spoken || entry.written);
  userGlossaryCount.textContent = String(
    userGlossaryItems.filter((entry) => entry.spoken && entry.written).length,
  );
}

function addGlossaryRow(entry = { spoken: "", written: "" }) {
  syncGlossaryStateFromDom();
  userGlossaryItems.push(entry);
  renderGlossaryRows(userGlossaryItems);
  syncGlossaryStateFromDom();
}

function removeGlossaryRow(index) {
  syncGlossaryStateFromDom();
  userGlossaryItems = userGlossaryItems.filter((_, itemIndex) => itemIndex !== index);
  renderGlossaryRows(userGlossaryItems);
  syncGlossaryStateFromDom();
}

async function refreshGlossary() {
  const payload = await fetchJson("/api/glossary");
  defaultGlossaryCount.textContent = String((payload.defaultItems || []).length);
  userGlossaryItems = payload.userItems || [];
  renderGlossaryRows(userGlossaryItems);
  syncGlossaryStateFromDom();
}

async function saveGlossary() {
  syncGlossaryStateFromDom();
  const items = userGlossaryItems.filter((entry) => entry.spoken && entry.written);
  const payload = await fetchJson("/api/glossary", {
    method: "POST",
    body: JSON.stringify({ items }),
  });
  defaultGlossaryCount.textContent = String((payload.defaultItems || []).length);
  userGlossaryItems = payload.userItems || [];
  renderGlossaryRows(userGlossaryItems);
  syncGlossaryStateFromDom();
  setMessage("已保存自定义术语。", "success");
}

function refreshPreviewMode() {
  previewModeText.textContent = SpeechRecognitionCtor
    ? "浏览器实时预览可用"
    : "当前浏览器不支持，停止后转写";
}

function refreshBrowserCompatibility() {
  setCapabilityBadge(capMediaRecorder, supportsMediaRecorder, "可用", "不可用");
  setCapabilityBadge(
    capSpeechRecognition,
    Boolean(SpeechRecognitionCtor),
    "实时预览可用",
    "将回退",
  );
  setCapabilityBadge(capPwa, supportsPwaInstall, "可安装", "不支持");

  if (isAndroid && isChromeFamily) {
    browserHintText.textContent = "当前看起来是 Android Chrome，适合实时预览和添加到主屏幕。";
    return;
  }

  if (isIos && isChromeFamily) {
    browserHintText.textContent =
      "当前看起来是 iPhone/iPad 上的 Chrome，录音没问题，但实时预览通常会回退到停止后转写。";
    return;
  }

  if (isIos) {
    browserHintText.textContent =
      "当前是 iOS 浏览器，录音一般可用，实时预览能力取决于 WebKit 支持情况。";
    return;
  }

  browserHintText.textContent =
    "当前浏览器可继续使用；如果你追求最佳实时预览，优先用 Android Chrome。";
}

async function registerPwaSupport() {
  if (!supportsPwaInstall) {
    installPwaButton.disabled = true;
    return;
  }

  try {
    await navigator.serviceWorker.register("/sw.js");
  } catch {
    // PWA registration is optional for the MVP.
  }
}

function refreshInstallHint() {
  if (deferredInstallPrompt) {
    installPwaButton.disabled = false;
    installHintBox.textContent = "当前浏览器支持安装，你可以把它加到主屏幕，像独立应用一样打开。";
    return;
  }

  if (isIos) {
    installPwaButton.disabled = true;
    installHintBox.textContent = "iPhone/iPad 请用浏览器的“添加到主屏幕”完成安装。";
    return;
  }

  if (supportsPwaInstall) {
    installPwaButton.disabled = true;
    installHintBox.textContent = "如果浏览器还没出现安装资格提示，先用几次这个页面，Chrome 往往会稍后开放安装。";
    return;
  }

  installPwaButton.disabled = true;
  installHintBox.textContent = "当前浏览器不支持安装为 PWA，但不影响直接使用。";
}

function mergeLiveTranscript() {
  return `${liveFinalTranscript}${liveInterimTranscript}`.trim();
}

function renderLiveTranscript() {
  const merged = mergeLiveTranscript();
  if (merged) {
    transcriptInput.value = merged;
  }
}

async function transcribeManualText() {
  const payload = await fetchJson("/api/transcribe", {
    method: "POST",
    body: JSON.stringify({
      text: transcriptInput.value,
    }),
  });
  transcriptInput.value = payload.normalizedText;
  setMessage("已完成归一化。", "success");
}

async function commitText() {
  const text = transcriptInput.value.trim();
  if (!text) {
    setMessage("请先录音或输入文本。", "error");
    return;
  }

  const payload = await fetchJson("/api/commit", {
    method: "POST",
    body: JSON.stringify({
      text,
      mode: modeSelect.value,
      targetApp: pinnedTargetApp,
    }),
  });

  const suffix = payload.dryRun ? "（dry-run，未真实执行）" : "";
  setMessage(`已插入到 ${payload.targetApp}${suffix}，现在请手动回车发送。`, "success");
  await refreshTarget();
  await refreshHistory();
}

async function pinCurrentTargetApp() {
  const payload = await fetchJson("/api/target");
  if (!payload.appName) {
    throw new Error("当前没有读到可锁定的前台应用。");
  }
  targetText.textContent = payload.appName;
  savePinnedTargetApp(payload.appName);
  setMessage(`已锁定目标应用：${payload.appName}`, "success");
}

function clearPinnedTarget() {
  savePinnedTargetApp("");
  setMessage("已取消锁定，之后会使用当前前台应用。", "success");
}

async function installPwa() {
  if (deferredInstallPrompt) {
    deferredInstallPrompt.prompt();
    const choice = await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    refreshInstallHint();
    if (choice?.outcome === "accepted") {
      setMessage("已触发安装流程。", "success");
      return;
    }
    setMessage("已取消安装，稍后仍可再次尝试。", "");
    return;
  }

  if (isIos) {
    setMessage("请使用浏览器分享菜单里的“添加到主屏幕”。", "");
    return;
  }

  setMessage("当前浏览器还没有给出可安装提示，但页面仍可直接使用。", "");
}

function setupSpeechRecognition() {
  if (!SpeechRecognitionCtor) {
    speechRecognition = null;
    speechRecognitionEnabled = false;
    return;
  }

  speechRecognition = new SpeechRecognitionCtor();
  speechRecognition.lang = navigator.language || "zh-CN";
  speechRecognition.continuous = true;
  speechRecognition.interimResults = true;

  speechRecognition.onresult = (event) => {
    liveInterimTranscript = "";

    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index];
      const piece = result[0]?.transcript ?? "";
      if (result.isFinal) {
        liveFinalTranscript += piece.endsWith(" ") ? piece : `${piece} `;
      } else {
        liveInterimTranscript += piece;
      }
    }

    renderLiveTranscript();
  };

  speechRecognition.onerror = () => {
    speechRecognitionEnabled = false;
    refreshPreviewMode();
  };
}

function stopSpeechRecognition() {
  return new Promise((resolve) => {
    if (!speechRecognitionEnabled || !speechRecognition) {
      resolve();
      return;
    }

    const current = speechRecognition;
    speechRecognitionEnabled = false;
    current.onend = () => resolve();
    current.stop();
  });
}

async function finalizeTranscriptFromStop() {
  const liveText = mergeLiveTranscript();
  const hasLivePreview = Boolean(liveText);

  if (hasLivePreview) {
    const payload = await fetchJson("/api/transcribe", {
      method: "POST",
      body: JSON.stringify({
        text: liveText,
      }),
    });
    transcriptInput.value = payload.normalizedText;
    return "已用实时预览结果完成归一化，可以继续编辑后插入。";
  }

  const recordedMimeType = mediaRecorder.mimeType || "audio/webm";
  const recordedBlob = new Blob(recordedChunks, { type: recordedMimeType });
  const { blob, mimeType } = await prepareRecordedAudioForTranscription(
    recordedBlob,
    recordedMimeType,
  );
  const audioBase64 = await blobToBase64(blob);
  const payload = await fetchJson("/api/transcribe", {
    method: "POST",
    body: JSON.stringify({
      audioBase64,
      mimeType,
    }),
  });
  transcriptInput.value = payload.normalizedText;
  return "已在停止录音后完成转写，可以继续编辑后插入。";
}

async function startRecording() {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("当前浏览器不支持录音。");
  }

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  recordedChunks = [];
  liveFinalTranscript = "";
  liveInterimTranscript = "";
  transcriptInput.value = "";

  const preferredMimeType = pickRecorderMimeType();
  mediaRecorder = preferredMimeType
    ? new MediaRecorder(stream, { mimeType: preferredMimeType })
    : new MediaRecorder(stream);
  mediaRecorder.ondataavailable = (event) => {
    if (event.data?.size) {
      recordedChunks.push(event.data);
    }
  };

  mediaRecorder.onstop = async () => {
    try {
      setMessage("整理文本中...", "");
      const statusMessage = await finalizeTranscriptFromStop();
      setMessage(statusMessage, "success");
    } catch (error) {
      setMessage(error.message, "error");
    } finally {
      for (const track of stream.getTracks()) {
        track.stop();
      }
    }
  };

  mediaRecorder.start();

  if (!speechRecognition) {
    setupSpeechRecognition();
  }

  if (speechRecognition) {
    speechRecognitionEnabled = true;
    speechRecognition.start();
  }

  isRecording = true;
  recordButton.textContent = "停止录音";
  recordButton.classList.remove("idle");
  recordButton.classList.add("recording");
  setMessage(
    SpeechRecognitionCtor
      ? "录音中，实时预览已开启..."
      : "录音中，停止后会自动转写...",
    "",
  );
}

async function stopRecording() {
  if (!mediaRecorder || !isRecording) {
    return;
  }

  await stopSpeechRecognition();
  mediaRecorder.stop();
  isRecording = false;
  recordButton.textContent = "开始录音";
  recordButton.classList.remove("recording");
  recordButton.classList.add("idle");
}

recordButton.addEventListener("click", async () => {
  try {
    if (isRecording) {
      await stopRecording();
    } else {
      await startRecording();
    }
  } catch (error) {
    setMessage(error.message, "error");
  }
});

refreshTargetButton.addEventListener("click", refreshTarget);
refreshHistoryButton.addEventListener("click", refreshHistory);
refreshGlossaryButton.addEventListener("click", () => {
  refreshGlossary().catch((error) => setMessage(error.message, "error"));
});
addGlossaryRowButton.addEventListener("click", () => {
  addGlossaryRow();
});
saveGlossaryButton.addEventListener("click", () => {
  saveGlossary().catch((error) => setMessage(error.message, "error"));
});
glossaryList.addEventListener("input", () => {
  syncGlossaryStateFromDom();
});
glossaryList.addEventListener("click", (event) => {
  const removeButton = event.target.closest("[data-remove-index]");
  if (!removeButton) {
    return;
  }
  removeGlossaryRow(Number.parseInt(removeButton.dataset.removeIndex, 10));
});
pinTargetButton.addEventListener("click", () => {
  pinCurrentTargetApp().catch((error) => setMessage(error.message, "error"));
});
clearPinnedTargetButton.addEventListener("click", clearPinnedTarget);
installPwaButton.addEventListener("click", () => {
  installPwa().catch((error) => setMessage(error.message, "error"));
});
modeSelect.addEventListener("change", saveModePreference);
normalizeButton.addEventListener("click", () => {
  transcribeManualText().catch((error) => setMessage(error.message, "error"));
});
commitButton.addEventListener("click", () => {
  commitText().catch((error) => setMessage(error.message, "error"));
});

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstallPrompt = event;
  refreshInstallHint();
});

window.addEventListener("appinstalled", () => {
  deferredInstallPrompt = null;
  refreshInstallHint();
});

loadModePreference();
refreshTargetMode();
refreshPreviewMode();
refreshBrowserCompatibility();
registerPwaSupport();
refreshInstallHint();

Promise.all([refreshHealth(), refreshTarget(), refreshHistory(), refreshGlossary()]).catch((error) => {
  setMessage(error.message, "error");
});
