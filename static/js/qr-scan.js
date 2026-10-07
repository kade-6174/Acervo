"use strict";

(() => {
  const startButton = document.getElementById("start-scan");
  if (!startButton) return;
  const stopButton = document.getElementById("stop-scan");
  const switchButton = document.getElementById("switch-camera");
  const video = document.getElementById("scan-video");
  const canvas = document.getElementById("scan-canvas");
  const imageInput = document.getElementById("scan-image");
  const status = document.getElementById("scan-status");
  const context = canvas.getContext("2d", { willReadFrequently: true });
  const qrPath = /^\/q\/[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\/$/i;
  let stream = null;
  let frame = null;
  let lastScan = 0;
  let requestId = 0;
  let currentFacing = "user";

  function releaseCamera() {
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
    video.hidden = true;
  }

  function stopCamera() {
    requestId += 1;
    releaseCamera();
    currentFacing = "user";
    startButton.disabled = false;
    stopButton.disabled = true;
    switchButton.disabled = true;
    switchButton.textContent = "カメラを切り替え";
  }

  async function openCamera(facing, exact = false) {
    const thisRequest = ++requestId;
    // 同時に二つのカメラを開けない端末があるため、先に現在の映像を解放する。
    releaseCamera();
    startButton.disabled = true;
    stopButton.disabled = false;
    switchButton.disabled = true;
    status.textContent = "カメラを起動しています。";
    try {
      const nextStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { [exact ? "exact" : "ideal"]: facing } }, audio: false,
      });
      if (thisRequest !== requestId || document.hidden) {
        nextStream.getTracks().forEach((track) => track.stop());
        if (thisRequest === requestId) stopCamera();
        return "cancelled";
      }
      stream = nextStream;
      video.srcObject = stream;
      video.hidden = false;
      await video.play();
      if (thisRequest !== requestId) {
        nextStream.getTracks().forEach((track) => track.stop());
        return "cancelled";
      }
      if (document.hidden) {
        stopCamera();
        return "cancelled";
      }
      const actualFacing = stream.getVideoTracks()[0]?.getSettings?.().facingMode;
      currentFacing = actualFacing === "user" || actualFacing === "environment" ? actualFacing : facing;
      switchButton.textContent = currentFacing === "user"
        ? "背面カメラに切り替え" : "画面側のカメラに切り替え";
      stopButton.disabled = false;
      switchButton.disabled = false;
      status.textContent = "QRラベルをカメラに向けてください。";
      frame = requestAnimationFrame(scanFrame);
      return "started";
    } catch {
      if (thisRequest !== requestId) return "cancelled";
      stopCamera();
      return "failed";
    }
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

  function decode(width, height, inversionAttempts = "dontInvert") {
    const pixels = context.getImageData(0, 0, width, height);
    return window.jsQR(pixels.data, width, height, { inversionAttempts });
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
      status.textContent = "このサイトで使えるQRコードではありません。別のQRコードをお試しください。";
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
    if (await openCamera("user") === "failed") {
      status.textContent = "カメラを起動できませんでした。権限を確認するか、QRの写真を選択してください。";
    }
  });

  switchButton.addEventListener("click", async () => {
    if (!stream) return;
    const previousFacing = currentFacing;
    const nextFacing = previousFacing === "user" ? "environment" : "user";
    if (await openCamera(nextFacing, true) === "failed") {
      if (await openCamera(previousFacing) === "started") {
        status.textContent = "カメラを切り替えられませんでした。元のカメラで続けます。";
      } else {
        status.textContent = "カメラを起動できませんでした。権限を確認してください。";
      }
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
      let result = null;
      let previousSize = "";
      try {
        for (const maxSide of [1200, 2400]) {
          const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
          const width = Math.max(1, Math.round(bitmap.width * scale));
          const height = Math.max(1, Math.round(bitmap.height * scale));
          const size = `${width}x${height}`;
          if (size === previousSize) continue;
          previousSize = size;
          canvas.width = width;
          canvas.height = height;
          context.drawImage(bitmap, 0, 0, width, height);
          result = decode(width, height, "attemptBoth");
          if (result) break;
        }
      } finally {
        if (bitmap.close) bitmap.close();
      }
      if (!result) {
        status.textContent = "QRコードが見つかりませんでした。別の写真を選択してください。";
      } else {
        handleResult(result);
      }
    } catch {
      status.textContent = "写真を読み取れませんでした。別の写真を選択してください。";
    }
    imageInput.value = "";
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopCamera();
  });
  window.addEventListener("pagehide", stopCamera);
})();
