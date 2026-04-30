import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

const MAX_HISTORY = 50;

function ensureParentDir(filePath) {
  mkdirSync(dirname(filePath), { recursive: true });
}

export function readHistory(historyPath) {
  try {
    const raw = readFileSync(historyPath, "utf8");
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function appendHistory(historyPath, entry) {
  ensureParentDir(historyPath);
  const current = readHistory(historyPath);
  const next = [entry, ...current].slice(0, MAX_HISTORY);
  writeFileSync(historyPath, JSON.stringify(next, null, 2));
  return next;
}
