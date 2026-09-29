(() => {
  const button = document.getElementById("mfa_webauthn_add");
  const credential = document.getElementById("id_credential");
  const passwordless = document.getElementById("id_passwordless");
  const form = credential?.closest("form");

  if (!button || !credential || !passwordless || !form) return;

  const reportError = (exception) => {
    document.dispatchEvent(new CustomEvent("allauth.error", {
      cancelable: true,
      detail: { tags: ["mfa", "webauthn"], exception },
    }));
  };

  button.addEventListener("click", async (event) => {
    event.preventDefault();
    try {
      const csrfToken = form.querySelector("[name=csrfmiddlewaretoken]")?.value;
      const response = await fetch(form.dataset.webauthnOptionsUrl, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/x-www-form-urlencoded",
          "X-CSRFToken": csrfToken,
          "X-Requested-With": "XMLHttpRequest",
        },
        body: new URLSearchParams({ passwordless: passwordless.checked ? "true" : "false" }),
      });
      if (!response.ok) throw new Error("Unable to fetch passkey data from server.");
      const data = await response.json();
      const created = await window.webauthnJSON.create(data.creation_options);
      credential.value = JSON.stringify(created);
      form.submit();
    } catch (error) {
      reportError(error);
    }
  });
})();
