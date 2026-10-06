"use strict";

if ("serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js", { scope: "/" }).catch(() => {
      // PWA登録が使えなくても、通常のオンライン画面はそのまま利用できる。
    });
  });
}
