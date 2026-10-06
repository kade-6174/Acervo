"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "../..");

test("Service Workerは静的資産とオフライン案内だけを保存する", async () => {
  const handlers = {};
  const saved = [];
  const cache = {
    addAll(requests) { saved.push(...requests); return Promise.resolve(); },
    match() { return Promise.resolve({ offline: true }); },
  };
  const caches = {
    open() { return Promise.resolve(cache); },
    keys() { return Promise.resolve([]); },
    match() { return Promise.resolve(null); },
  };
  const self = {
    location: { origin: "https://acervo.test" },
    addEventListener(name, handler) { handlers[name] = handler; },
    skipWaiting() {},
    clients: { claim() { return Promise.resolve(); } },
  };
  class Request {
    constructor(url, options) { this.url = url; this.credentials = options.credentials; }
  }
  const code = fs.readFileSync(path.join(root, "static/js/service-worker.js"), "utf8");
  vm.runInNewContext(code, { self, caches, Request, URL, fetch: () => Promise.reject(new Error("offline")) });

  let installation;
  handlers.install({ waitUntil(promise) { installation = promise; } });
  await installation;
  assert.ok(saved.length > 0);
  assert.ok(saved.every((request) => request.url.startsWith("/static/") && request.credentials === "omit"));

  for (const pathname of ["/specimens/", "/specimens/abc/photos/1/", "/management/", "/management/specimens/export.csv", "/api/private/"]) {
    let responded = false;
    handlers.fetch({
      request: { url: `https://acervo.test${pathname}`, method: "GET", mode: "same-origin" },
      respondWith() { responded = true; },
    });
    assert.equal(responded, false, pathname);
  }

  let offlinePage;
  handlers.fetch({
    request: { url: "https://acervo.test/specimens/", method: "GET", mode: "navigate" },
    respondWith(promise) { offlinePage = promise; },
  });
  assert.deepEqual(await offlinePage, { offline: true });
});

test("QR読取は同一オリジンのUUIDv4経路だけへ進む", async () => {
  const elements = new Map();
  for (const id of ["start-scan", "stop-scan", "scan-video", "scan-canvas", "scan-image", "scan-status"]) {
    elements.set(id, { handlers: {}, addEventListener(name, handler) { this.handlers[name] = handler; } });
  }
  const canvas = elements.get("scan-canvas");
  canvas.getContext = () => ({
    drawImage() {},
    getImageData() { return { data: new Uint8ClampedArray(4) }; },
  });
  const imageInput = elements.get("scan-image");
  const visited = [];
  let decoded = "";
  const window = {
    location: { origin: "https://acervo.test", assign(pathname) { visited.push(pathname); } },
    jsQR() { return { data: decoded }; },
    createImageBitmap: async () => ({ width: 10, height: 10, close() {} }),
    addEventListener() {},
  };
  const document = {
    getElementById(id) { return elements.get(id); },
    addEventListener() {},
  };
  const code = fs.readFileSync(path.join(root, "static/js/qr-scan.js"), "utf8");
  vm.runInNewContext(code, {
    window, document, URL, Uint8ClampedArray,
    createImageBitmap: async () => ({ width: 10, height: 10, close() {} }),
  });

  const token = "12345678-1234-4123-8123-123456789abc";
  for (const value of [
    `https://evil.test/q/${token}/`,
    `https://acervo.test/q/${token}/?next=evil`,
    "https://acervo.test/q/12345678-1234-1123-8123-123456789abc/",
    `https://acervo.test/q/${token}/#fragment`,
  ]) {
    decoded = value;
    imageInput.files = [{ type: "image/png", size: 100 }];
    await imageInput.handlers.change();
  }
  assert.equal(visited.length, 0);

  decoded = `https://acervo.test/q/${token}/`;
  imageInput.files = [{ type: "image/png", size: 100 }];
  await imageInput.handlers.change();
  assert.deepEqual(visited, [`/q/${token}/`]);
});
