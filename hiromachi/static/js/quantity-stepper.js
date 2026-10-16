"use strict";

document.querySelectorAll("[data-quantity-stepper]").forEach((stepper) => {
  const input = stepper.querySelector('input[type="number"]');
  const decreaseButton = stepper.querySelector("[data-quantity-decrease]");
  const increaseButton = stepper.querySelector("[data-quantity-increase]");
  const status = stepper.querySelector("[data-quantity-status]");
  const step = Number(stepper.dataset.step);
  const minimum = Number(stepper.dataset.min);
  const maximum = Number(stepper.dataset.max);
  const initialValue = Number(stepper.dataset.initial);
  const unit = stepper.dataset.unit || "";

  if (
    !input ||
    !decreaseButton ||
    !increaseButton ||
    !Number.isFinite(step) ||
    !Number.isFinite(minimum) ||
    !Number.isFinite(maximum) ||
    !Number.isFinite(initialValue)
  ) {
    return;
  }

  const currentValue = () => {
    if (input.value.trim() === "") {
      return null;
    }
    const value = Number(input.value);
    return Number.isInteger(value) ? value : null;
  };

  const updateButtonStates = () => {
    const value = currentValue();
    decreaseButton.disabled = value === null || value <= minimum;
    increaseButton.disabled = value !== null && value >= maximum;
  };

  const announce = (value) => {
    if (status) {
      status.textContent = `${input.labels?.[0]?.textContent.trim() || "数量"} ${value}${unit}`;
    }
  };

  const changeValue = (direction) => {
    const value = currentValue();
    if (value === null && direction < 0) {
      return;
    }

    const candidate = value === null ? initialValue : value + direction * step;
    const nextValue = Math.min(maximum, Math.max(minimum, candidate));
    input.value = String(nextValue);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    announce(nextValue);
    updateButtonStates();
  };

  decreaseButton.addEventListener("click", () => changeValue(-1));
  increaseButton.addEventListener("click", () => changeValue(1));
  input.addEventListener("input", updateButtonStates);
  input.addEventListener("change", updateButtonStates);

  updateButtonStates();
  stepper.classList.add("is-enhanced");
});
