(() => {
  const status = document.getElementById("webauthn-status");
  const message = (text) => { if (status) { status.textContent = text; status.classList.remove("d-none"); status.classList.add("alert-danger"); } };
  if (!window.PublicKeyCredential || !navigator.credentials) message("このブラウザはパスキーまたはセキュリティキーに対応していません。");
  document.addEventListener("allauth.error", (event) => { event.preventDefault(); message("パスキーまたはセキュリティキーを利用できませんでした。中止した場合は、もう一度お試しください。"); });
  document.addEventListener("click", (event) => { const button = event.target.closest("#mfa_webauthn_add, #mfa_webauthn_reauthenticate, #passkey_login"); if (button && !button.disabled) { button.disabled = true; setTimeout(() => { button.disabled = false; }, 15000); } });
  document.querySelectorAll("form[data-webauthn-submit]").forEach((form) => form.addEventListener("submit", () => { const button = form.querySelector("button[type=submit]"); if (button) { button.disabled = true; button.textContent = "処理しています"; } }, { once: true }));
})();
