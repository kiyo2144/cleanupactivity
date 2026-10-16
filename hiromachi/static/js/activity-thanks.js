"use strict";

(() => {
  const form = document.querySelector("[data-thank-form]");
  if (!form) {
    return;
  }

  const section = form.closest(".activity-thanks");
  const heading = document.getElementById("activity-thanks-heading");
  const count = section?.querySelector(".thank-count");
  const button = form.querySelector("[data-thank-button]");
  const buttonLabel = form.querySelector("[data-thank-button-label]");
  const status = form.querySelector("[data-thank-status]");

  if (!section || !heading || !count || !button || !buttonLabel || !status) {
    return;
  }

  let isSubmitting = false;

  const restartAnimation = (className) => {
    section.classList.remove("is-thank-sent", "is-thank-removed");
    void section.offsetWidth;
    section.classList.add(className);
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    isSubmitting = true;
    button.disabled = true;
    form.setAttribute("aria-busy", "true");
    status.hidden = true;
    status.classList.remove("is-error");

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });

      if (response.redirected) {
        window.location.assign(response.url);
        return;
      }

      const contentType = response.headers.get("content-type") || "";
      if (!response.ok || !contentType.includes("application/json")) {
        throw new Error("Unexpected response");
      }

      const result = await response.json();
      const hasThanked = result.has_thanked === true;
      const nextCount = Number(result.thank_count);
      if (!Number.isInteger(nextCount) || nextCount < 0) {
        throw new Error("Invalid response");
      }

      count.textContent = String(nextCount);
      heading.setAttribute("aria-label", `ありがとう ${nextCount}件`);
      button.setAttribute("aria-pressed", String(hasThanked));
      buttonLabel.textContent = hasThanked ? "ありがとうを取り消す" : "ありがとうを送る";
      status.textContent = result.message;
      status.hidden = false;
      restartAnimation(hasThanked ? "is-thank-sent" : "is-thank-removed");
    } catch (error) {
      status.textContent = "状態を確認できませんでした。ページを再読み込みして確認してください。";
      status.classList.add("is-error");
      status.hidden = false;
    } finally {
      isSubmitting = false;
      button.disabled = false;
      form.removeAttribute("aria-busy");
    }
  });
})();
