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
  const removed = [];
  const cache = {
    addAll(requests) { saved.push(...requests); return Promise.resolve(); },
    match() { return Promise.resolve({ offline: true }); },
  };
  const caches = {
    open() { return Promise.resolve(cache); },
    keys() { return Promise.resolve(["acervo-static-v1", "unrelated-cache"]); },
    delete(key) { removed.push(key); return Promise.resolve(true); },
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

  let activation;
  handlers.activate({ waitUntil(promise) { activation = promise; } });
  await activation;
  assert.deepEqual(removed, ["acervo-static-v1"]);

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
  for (const id of ["start-scan", "stop-scan", "switch-camera", "scan-video", "scan-canvas", "scan-image", "scan-status"]) {
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

test("QR読取は画面側カメラを優先し、切替・失敗復旧・停止時に映像を解放する", async () => {
  const elements = new Map();
  for (const id of ["start-scan", "stop-scan", "switch-camera", "scan-video", "scan-canvas", "scan-image", "scan-status"]) {
    elements.set(id, { disabled: false, hidden: false, handlers: {}, addEventListener(name, handler) { this.handlers[name] = handler; } });
  }
  elements.get("scan-canvas").getContext = () => ({});
  const video = elements.get("scan-video");
  video.play = async () => {};
  const requests = [];
  const streams = [];
  let rejectBackCamera = false;
  const mediaDevices = {
    async getUserMedia({ video: constraints, audio }) {
      requests.push({ constraints, audio });
      const facing = constraints.facingMode.exact || constraints.facingMode.ideal;
      if (rejectBackCamera && facing === "environment") throw new Error("no back camera");
      const track = { facing, stopped: false, stop() { this.stopped = true; }, getSettings() { return { facingMode: this.facing }; } };
      const mediaStream = { getTracks() { return [track]; }, getVideoTracks() { return [track]; } };
      streams.push({ track, mediaStream });
      return mediaStream;
    },
  };
  const window = { isSecureContext: true, jsQR() {}, addEventListener() {} };
  const document = { hidden: false, getElementById(id) { return elements.get(id); }, addEventListener() {} };
  const code = fs.readFileSync(path.join(root, "static/js/qr-scan.js"), "utf8");
  vm.runInNewContext(code, {
    window, document, navigator: { mediaDevices }, URL,
    requestAnimationFrame: () => 1, cancelAnimationFrame() {},
  });

  await elements.get("start-scan").handlers.click();
  assert.equal(requests[0].constraints.facingMode.ideal, "user");
  assert.equal(requests[0].audio, false);
  assert.equal(video.srcObject, streams[0].mediaStream);
  assert.equal(elements.get("switch-camera").disabled, false);
  assert.equal(elements.get("switch-camera").textContent, "背面カメラに切り替え");

  await elements.get("switch-camera").handlers.click();
  assert.equal(requests[1].constraints.facingMode.exact, "environment");
  assert.equal(streams[0].track.stopped, true);
  assert.equal(video.srcObject, streams[1].mediaStream);
  assert.equal(elements.get("switch-camera").textContent, "画面側のカメラに切り替え");

  await elements.get("switch-camera").handlers.click();
  assert.equal(requests[2].constraints.facingMode.exact, "user");
  assert.equal(streams[1].track.stopped, true);
  assert.equal(video.srcObject, streams[2].mediaStream);

  rejectBackCamera = true;
  await elements.get("switch-camera").handlers.click();
  assert.equal(requests[3].constraints.facingMode.exact, "environment");
  assert.equal(requests[4].constraints.facingMode.ideal, "user");
  assert.equal(streams[2].track.stopped, true);
  assert.equal(video.srcObject, streams[3].mediaStream);
  assert.match(elements.get("scan-status").textContent, /切り替えられませんでした/);

  elements.get("stop-scan").handlers.click();
  assert.equal(streams[3].track.stopped, true);
  assert.equal(video.srcObject, null);
  assert.equal(elements.get("switch-camera").disabled, true);
  assert.equal(elements.get("start-scan").disabled, false);

  let resolvePending;
  mediaDevices.getUserMedia = () => new Promise((resolve) => { resolvePending = resolve; });
  const pending = elements.get("start-scan").handlers.click();
  elements.get("stop-scan").handlers.click();
  const lateTrack = { stopped: false, stop() { this.stopped = true; } };
  resolvePending({ getTracks() { return [lateTrack]; } });
  await pending;
  assert.equal(lateTrack.stopped, true);
  assert.equal(video.srcObject, null);
});
