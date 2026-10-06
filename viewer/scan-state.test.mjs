import test from "node:test";
import assert from "node:assert/strict";
import { anyActive, formatBytes, isFinal, reductionText, statusLabel, statusMessage } from "./scan-state.js";

test("only ready and failed are final", () => {
  for (const status of ["uploaded", "validating", "processing"]) assert.equal(isFinal(status), false);
  for (const status of ["ready", "failed"]) assert.equal(isFinal(status), true);
});

test("polling continues while any scan is unfinished", () => {
  assert.equal(anyActive([]), false);
  assert.equal(anyActive([{ status: "ready" }, { status: "failed" }]), false);
  assert.equal(anyActive([{ status: "ready" }, { status: "processing" }]), true);
});

test("labels are friendly, and unknown statuses pass through", () => {
  assert.equal(statusLabel("uploaded"), "Queued");
  assert.equal(statusLabel("mystery"), "mystery");
});

test("byte sizes read naturally", () => {
  assert.equal(formatBytes(null), "-");
  assert.equal(formatBytes(512), "512 B");
  assert.equal(formatBytes(1536), "1.5 KB");
  assert.equal(formatBytes(9474205), "9.0 MB");
  assert.equal(formatBytes(150 * 1024 * 1024), "150 MB");
});

test("reduction handles shrinking, growing and missing values", () => {
  assert.equal(reductionText({ reduction_pct: 89.6 }), "89.6% smaller");
  assert.equal(reductionText({ reduction_pct: -3 }), "3.0% larger");
  assert.equal(reductionText({ reduction_pct: null }), "");
});

test("a failed scan shows its own reason", () => {
  assert.equal(statusMessage({ status: "failed", error_message: "Bad file." }), "Bad file.");
  assert.equal(statusMessage({ status: "failed", error_message: null }), "Processing failed.");
  assert.equal(statusMessage({ status: "ready" }), "");
});
