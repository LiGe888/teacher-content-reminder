function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function buildFlexiblePhrasePattern(spoken) {
  return spoken
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => escapeRegExp(part))
    .join("[\\s._-]*");
}

function replaceAsciiPhrase(source, spoken, written) {
  const pattern = buildFlexiblePhrasePattern(spoken);
  const matcher = new RegExp(`(^|[^A-Za-z0-9])(${pattern})(?=$|[^A-Za-z0-9])`, "giu");
  return source.replace(matcher, (_, prefix) => `${prefix}${written}`);
}

function replaceLiteralPhrase(source, spoken, written) {
  const pattern = buildFlexiblePhrasePattern(spoken);
  const matcher = new RegExp(pattern, "gu");
  return source.replace(matcher, written);
}

function replaceGlossaryEntry(source, spoken, written) {
  if (/[A-Za-z0-9]/.test(spoken)) {
    return replaceAsciiPhrase(source, spoken, written);
  }

  return replaceLiteralPhrase(source, spoken, written);
}

function normalizeWhitespace(text) {
  return text
    .replace(/\r\n/g, "\n")
    .replace(/\n[ \t]+/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}

function normalizeDeveloperPatterns(text) {
  return text
    .replace(/\b((?:[A-Za-z]\s+){1,}[A-Za-z])\b/g, (_, value) => value.replace(/\s+/g, ""))
    .replace(/\b(new line|newline)\b/gi, "\n")
    .replace(/\b([A-Za-z0-9_-]+)\s+dot\s+([A-Za-z0-9_-]+)\b/g, "$1.$2")
    .replace(/\s+([,.;:!?])/g, "$1")
    .replace(/([({[])\s+/g, "$1")
    .replace(/\s+([)\]}])/g, "$1");
}

export function normalizeDeveloperText(text, glossary = []) {
  let result = String(text ?? "");

  result = normalizeDeveloperPatterns(result);

  const sortedGlossary = [...glossary].sort(
    (left, right) => right.spoken.length - left.spoken.length,
  );

  for (const entry of sortedGlossary) {
    result = replaceGlossaryEntry(result, entry.spoken, entry.written);
  }

  return normalizeWhitespace(result);
}
