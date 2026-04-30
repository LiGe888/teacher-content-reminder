import { access } from "node:fs/promises";
import { platform, version as osVersion } from "node:os";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

async function checkBinary(path, args = []) {
  try {
    const { stdout, stderr } = await execFileAsync(path, args);
    return {
      ok: true,
      output: (stdout || stderr || "").trim(),
    };
  } catch (error) {
    return {
      ok: false,
      output: error.message,
    };
  }
}

async function checkPathReadable(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

function printResult(label, ok, detail) {
  const prefix = ok ? "[ok]" : "[warn]";
  console.log(`${prefix} ${label}`);
  if (detail) {
    console.log(`       ${detail}`);
  }
}

async function main() {
  console.log("Dev Voice Bridge doctor\n");

  const isMac = platform() === "darwin";
  printResult("Running on macOS", isMac, `${platform()} ${osVersion()}`);

  const nodeMajor = Number.parseInt(process.versions.node.split(".")[0], 10);
  printResult("Node.js version", nodeMajor >= 20, process.versions.node);

  const activeProvider = process.env.VOICE_CODER_TRANSCRIBE_PROVIDER || "auto";
  const hasXFYunKey = Boolean(
    process.env.VOICE_CODER_XFYUN_APP_ID &&
      process.env.VOICE_CODER_XFYUN_API_KEY &&
      process.env.VOICE_CODER_XFYUN_API_SECRET,
  );
  const hasDoubaoKey = Boolean(
    process.env.VOICE_CODER_DOUBAO_API_KEY || process.env.VOICE_CODER_DOUBAO_APP_KEY,
  );
  const hasOpenAIKey = Boolean(process.env.OPENAI_API_KEY);
  const hasDashScopeKey = Boolean(process.env.DASHSCOPE_API_KEY);
  const hasFunASRURL = Boolean(process.env.VOICE_CODER_FUNASR_URL);
  const hasAnyProvider =
    hasXFYunKey || hasDoubaoKey || hasOpenAIKey || hasDashScopeKey || hasFunASRURL;
  printResult(
    "Transcription provider configured",
    hasAnyProvider,
    [
      `active=${activeProvider}`,
      `xfyun=${hasXFYunKey ? "yes" : "no"}`,
      `doubao=${hasDoubaoKey ? "yes" : "no"}`,
      `openai=${hasOpenAIKey ? "yes" : "no"}`,
      `dashscope=${hasDashScopeKey ? "yes" : "no"}`,
      `funasr=${hasFunASRURL ? "yes" : "no"}`,
    ].join(" · "),
  );

  const pbcopyCheck = await checkBinary("/usr/bin/pbcopy", ["-help"]);
  printResult("pbcopy available", pbcopyCheck.ok, pbcopyCheck.output || "Clipboard bridge");

  const osascriptCheck = await checkBinary("/usr/bin/osascript", ["-e", 'return "ok"']);
  printResult("osascript available", osascriptCheck.ok, osascriptCheck.output || "AppleScript bridge");

  const glossaryExists = await checkPathReadable("./config/default-glossary.json");
  printResult("Default glossary present", glossaryExists, "./config/default-glossary.json");

  const userGlossaryExists = await checkPathReadable("./data/user-glossary.json");
  printResult(
    "User glossary file",
    true,
    userGlossaryExists
      ? "./data/user-glossary.json"
      : "Not created yet. It will appear after you save custom glossary entries in the UI.",
  );

  const publicIndexExists = await checkPathReadable("./public/index.html");
  printResult("Web control page present", publicIndexExists, "./public/index.html");

  console.log("\nNotes:");
  console.log("- First real paste requires macOS Accessibility permission for the terminal app running the service.");
  console.log("- Android Chrome currently gives the best real-time preview experience.");
  console.log("- iPhone Chrome usually falls back to stop-then-transcribe due to WebKit limitations.");
  console.log("- You can switch between XFYun, Doubao, OpenAI, DashScope, or a local FunASR adapter through VOICE_CODER_TRANSCRIBE_PROVIDER.");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
