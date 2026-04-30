import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

function ensureParentDir(filePath) {
  mkdirSync(dirname(filePath), { recursive: true });
}

export function normalizeGlossaryEntries(entries = []) {
  return entries
    .filter((entry) => entry && entry.spoken && entry.written)
    .map((entry) => ({
      spoken: String(entry.spoken).trim(),
      written: String(entry.written).trim(),
    }))
    .filter((entry) => entry.spoken && entry.written);
}

export function readGlossaryFile(glossaryPath, fallback = []) {
  try {
    const raw = readFileSync(glossaryPath, "utf8");
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return fallback;
    }
    return normalizeGlossaryEntries(parsed);
  } catch {
    return fallback;
  }
}

export function writeGlossaryFile(glossaryPath, entries = []) {
  ensureParentDir(glossaryPath);
  const normalized = normalizeGlossaryEntries(entries);
  writeFileSync(glossaryPath, JSON.stringify(normalized, null, 2));
  return normalized;
}

export function mergeGlossaries(defaultEntries = [], userEntries = []) {
  const merged = new Map();

  for (const entry of normalizeGlossaryEntries(defaultEntries)) {
    merged.set(entry.spoken.toLowerCase(), entry);
  }

  for (const entry of normalizeGlossaryEntries(userEntries)) {
    merged.set(entry.spoken.toLowerCase(), entry);
  }

  return [...merged.values()];
}
