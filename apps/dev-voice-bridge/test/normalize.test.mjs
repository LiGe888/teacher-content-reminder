import test from "node:test";
import assert from "node:assert/strict";

import { normalizeDeveloperText } from "../src/normalize.mjs";

test("normalizes glossary replacements", () => {
  const glossary = [
    { spoken: "claude code", written: "Claude Code" },
    { spoken: "fast api", written: "FastAPI" },
  ];

  const result = normalizeDeveloperText(
    "please ask claude code to update fast api config",
    glossary,
  );

  assert.equal(result, "please ask Claude Code to update FastAPI config");
});

test("normalizes dot filenames and newline markers", () => {
  const result = normalizeDeveloperText("open main dot py new line add tests");
  assert.equal(result, "open main.py\nadd tests");
});

test("removes extra spaces before punctuation", () => {
  const result = normalizeDeveloperText("hello , world !");
  assert.equal(result, "hello, world!");
});

test("normalizes compact letter sequences before glossary matching", () => {
  const glossary = [
    { spoken: "q q", written: "QQ" },
    { spoken: "c o d e x", written: "Codex" },
  ];

  const result = normalizeDeveloperText("please ping q q and open c o d e x", glossary);
  assert.equal(result, "please ping QQ and open Codex");
});

test("normalizes chinese aliases for developer tools", () => {
  const glossary = [
    { spoken: "扣扣", written: "QQ" },
    { spoken: "寇德克斯", written: "Codex" },
    { spoken: "克劳德 code", written: "Claude Code" },
  ];

  const result = normalizeDeveloperText("把扣扣和寇德克斯还有克劳德 code 都打开", glossary);
  assert.equal(result, "把QQ和Codex还有Claude Code 都打开");
});

test("normalizes codex from colloquial chinese homophone phrases", () => {
  const glossary = [
    { spoken: "口袋装C片", written: "Codex" },
    { spoken: "口袋装西片", written: "Codex" },
  ];

  const result = normalizeDeveloperText(
    "我就是用口袋装C片开发一款新的 app 再看看口袋装西片能不能识别",
    glossary,
  );

  assert.equal(result, "我就是用Codex开发一款新的 app 再看看Codex能不能识别");
});

test("normalizes cloud-code style aliases and common dev terms", () => {
  const glossary = [
    { spoken: "cloud code", written: "Claude Code" },
    { spoken: "api key", written: "API key" },
    { spoken: "vs code", written: "VS Code" },
  ];

  const result = normalizeDeveloperText(
    "please ask cloud code to check the api key in vs code",
    glossary,
  );

  assert.equal(result, "please ask Claude Code to check the API key in VS Code");
});
