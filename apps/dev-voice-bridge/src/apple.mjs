import { execFile, spawn } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export const TERMINAL_APPS = new Set([
  "Terminal",
  "iTerm2",
  "Warp",
  "WezTerm",
  "Ghostty",
  "Alacritty",
]);

function assertMacOS() {
  if (process.platform !== "darwin") {
    throw new Error("This MVP currently supports macOS automation only.");
  }
}

export function isTerminalLikeApp(name) {
  return TERMINAL_APPS.has(String(name ?? ""));
}

export function buildPasteScript() {
  return [
    'tell application "System Events"',
    '  keystroke "v" using command down',
    "end tell",
  ].join("\n");
}

export async function runAppleScript(script) {
  assertMacOS();
  const { stdout } = await execFileAsync("/usr/bin/osascript", ["-e", script]);
  return stdout.trim();
}

export async function getFrontmostApp() {
  const script =
    'tell application "System Events" to get name of first application process whose frontmost is true';
  return runAppleScript(script);
}

export async function copyToClipboard(text) {
  assertMacOS();
  await new Promise((resolve, reject) => {
    const child = spawn("/usr/bin/pbcopy", []);

    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`pbcopy exited with code ${code}`));
    });

    child.stdin.write(String(text ?? ""));
    child.stdin.end();
  });
}

export async function activateApp(appName) {
  assertMacOS();
  if (!appName) {
    return;
  }

  const script = `tell application "${String(appName).replace(/"/g, '\\"')}" to activate`;
  await runAppleScript(script);
}

export async function pasteText({
  text,
  targetApp = null,
  dryRun = false,
} = {}) {
  if (!text) {
    throw new Error("Nothing to paste.");
  }

  const frontmostBefore = process.platform === "darwin" ? await getFrontmostApp() : "unknown";
  const effectiveTarget = targetApp || frontmostBefore;

  if (dryRun) {
    return {
      dryRun: true,
      targetApp: effectiveTarget,
      action: "insert_only",
      textLength: text.length,
    };
  }

  if (targetApp) {
    await activateApp(targetApp);
    await new Promise((resolve) => setTimeout(resolve, 120));
  }

  await copyToClipboard(text);
  await runAppleScript(buildPasteScript());

  return {
    dryRun: false,
    targetApp: effectiveTarget,
    action: "insert_only",
    textLength: text.length,
  };
}
