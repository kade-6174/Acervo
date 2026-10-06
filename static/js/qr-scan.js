"use strict";

(() => {
  const startButton = document.getElementById("start-scan");
  if (!startButton) return;
  const stopButton = document.getElementById("stop-scan");
  const video = document.getElementById("scan-video");
  const canvas = document.getElementById("scan-canvas");
  const imageInput = document.getElementById("scan-image");
  const status = document.getElementById("scan-status");
  const context = canvas.getContext("2d", { willReadFrequently: true });
  const qrPath = /^\/q\/[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\/$/i;
  let stream = null;
  let frame = null;
  let lastScan = 0;

  function stopCamera() {
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
    video.hidden = true;
    startButton.disabled = false;
    stopButton.disabled = true;
  }

  function acceptedPath(value) {
    try {
      const url = new URL(value);
      if (url.origin !== window.location.origin || url.username || url.password ||
          url.search || url.hash || !qrPath.test(url.pathname)) return null;
      return url.pathname;
    } catch {
      return null;
    }
  }

  function decode(width, height) {
    const pixels = context.getImageData(0, 0, width, height);
    return window.jsQR(pixels.data, width, height, { inversionAttempts: "dontInvert" });
  }

  async function imageFromFile(file) {
    if (window.createImageBitmap) return createImageBitmap(file);
    const objectUrl = URL.createObjectURL(file);
    try {
      return await new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = reject;
        image.src = objectUrl;
      });
    } finally {
      URL.revokeObjectURL(objectUrl);
    }
  }

  function handleResult(result) {
    if (!result) return false;
    const path = acceptedPath(result.data);
    if (!path) {
      status.textContent = "AcervoのQRラベルではありません。別のラベルを読み取ってください。";
      return false;
    }
    stopCamera();
    status.textContent = "QRコードを確認しました。移動します。";
    window.location.assign(path);
    return true;
  }

  function scanFrame(now) {
    if (!stream) return;
    if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA &&
        video.videoWidth > 0 && video.videoHeight > 0 && now - lastScan >= 120) {
      lastScan = now;
      const scale = Math.min(1, 800 / video.videoWidth);
      const width = Math.max(1, Math.round(video.videoWidth * scale));
      const height = Math.max(1, Math.round(video.videoHeight * scale));
      canvas.width = width;
      canvas.height = height;
      context.drawImage(video, 0, 0, width, height);
      if (handleResult(decode(width, height))) return;
    }
    frame = requestAnimationFrame(scanFrame);
  }

  startButton.addEventListener("click", async () => {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.jsQR || !context) {
      status.textContent = "この環境ではカメラを利用できません。HTTPSで開くか、QRの写真を選択してください。";
      return;
    }
    startButton.disabled = true;
    status.textContent = "カメラを起動しています。";
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } }, audio: false,
      });
      if (document.hidden) {
        stopCamera();
        return;
      }
      video.srcObject = stream;
      video.hidden = false;
      await video.play();
      stopButton.disabled = false;
      status.textContent = "QRラベルをカメラに向けてください。";
      frame = requestAnimationFrame(scanFrame);
    } catch {
      stopCamera();
      status.textContent = "カメラを起動できませんでした。権限を確認するか、QRの写真を選択してください。";
    }
  });

  stopButton.addEventListener("click", () => {
    stopCamera();
    status.textContent = "カメラを停止しました。";
  });

  imageInput.addEventListener("change", async () => {
    const file = imageInput.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/") || file.size > 10 * 1024 * 1024 || !window.jsQR || !context) {
      status.textContent = "10MB以下の画像を選択してください。";
      return;
    }
    try {
      const bitmap = await imageFromFile(file);
      const scale = Math.min(1, 1200 / Math.max(bitmap.width, bitmap.height));
      const width = Math.max(1, Math.round(bitmap.width * scale));
      const height = Math.max(1, Math.round(bitmap.height * scale));
      canvas.width = width;
      canvas.height = height;
      context.drawImage(bitmap, 0, 0, width, height);
      if (bitmap.close) bitmap.close();
      if (!handleResult(decode(width, height))) {
        status.textContent = "QRコードが見つかりませんでした。別の写真を選択してください。";
      }
    } catch {
      status.textContent = "写真を読み取れませんでした。別の写真を選択してください。";
    }
    imageInput.value = "";
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden && stream) stopCamera();
  });
  window.addEventListener("pagehide", stopCamera);
})();
