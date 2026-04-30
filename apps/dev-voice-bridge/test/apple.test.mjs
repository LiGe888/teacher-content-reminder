import test from "node:test";
import assert from "node:assert/strict";

import { buildPasteScript, isTerminalLikeApp } from "../src/apple.mjs";

test("builds paste-only script", () => {
  const script = buildPasteScript();
  assert.match(script, /keystroke "v" using command down/);
  assert.doesNotMatch(script, /key code 36/);
});

test("recognizes terminal-like apps", () => {
  assert.equal(isTerminalLikeApp("Warp"), true);
  assert.equal(isTerminalLikeApp("Claude"), false);
});
