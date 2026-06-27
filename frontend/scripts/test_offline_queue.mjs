#!/usr/bin/env node
// File: frontend/scripts/test_offline_queue.mjs
// Purpose: Smoke test for the PWA offline mutation queue (item 9).
// Verifies:
//   1. /public/sw.js registers a `sync` handler for the agreed tag and
//      uses the same IndexedDB name / store as src/lib/offline-db.ts.
//   2. The client wrapper in src/lib/offline-db.ts exports the expected
//      queue API symbols (enqueueMutation, listPendingMutations,
//      deleteMutation, requestSync).
//   3. api-client.ts intercepts non-GET requests when offline.
//
// Strategy: text-level assertions so we stay zero-dependency and don't
// need a DOM / IndexedDB runtime. This catches the regressions we care
// about: renamed store, missing sync handler, accidental removal of the
// offline intercept branch.

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import assert from "node:assert/strict";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");

const SW = readFileSync(resolve(ROOT, "public/sw.js"), "utf8");
const DB = readFileSync(resolve(ROOT, "src/lib/offline-db.ts"), "utf8");
const API = readFileSync(resolve(ROOT, "src/lib/api-client.ts"), "utf8");

test("service worker registers the background sync handler", () => {
  assert.match(SW, /addEventListener\(['"]sync['"]/);
  assert.match(SW, /varuflow-mutations/);
});

test("service worker and client agree on the IndexedDB schema", () => {
  assert.match(SW, /_OFFLINE_DB\s*=\s*['"]varuflow['"]/);
  assert.match(SW, /_OFFLINE_STORE\s*=\s*['"]pendingMutations['"]/);
  assert.match(DB, /DB_NAME\s*=\s*['"]varuflow['"]/);
  assert.match(DB, /STORE\s*=\s*['"]pendingMutations['"]/);
});

test("offline-db exports the expected public API", () => {
  for (const symbol of [
    "export async function enqueueMutation",
    "export async function listPendingMutations",
    "export async function deleteMutation",
    "export async function requestSync",
    "export async function pendingCount",
  ]) {
    assert.ok(DB.includes(symbol), `missing export: ${symbol}`);
  }
});

test("api-client queues non-GET requests when navigator.onLine is false", () => {
  assert.match(API, /enqueueMutation/);
  assert.match(API, /navigator\.onLine\s*===\s*false/);
  assert.match(API, /requestSync\(\)/);
});

test("service worker falls back to a postMessage drain trigger", () => {
  assert.match(SW, /drain-mutations/);
});
