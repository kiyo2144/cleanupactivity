"use strict";

(() => {
  const summary = document.querySelector("[data-form-error-summary]");
  if (!summary) {
    return;
  }

  summary.focus({ preventScroll: true });

  summary.querySelectorAll("[data-error-link]").forEach((link) => {
    link.addEventListener("click", (event) => {
      const targetId = link.getAttribute("href")?.slice(1);
      const field = targetId ? document.getElementById(targetId) : null;
      if (!field) {
        return;
      }

      event.preventDefault();
      field.scrollIntoView({ block: "center" });
      const focusId = field.dataset.errorFocus;
      const focusTarget = focusId ? document.getElementById(focusId) : null;
      focusTarget?.focus({ preventScroll: true });
    });
  });
})();
