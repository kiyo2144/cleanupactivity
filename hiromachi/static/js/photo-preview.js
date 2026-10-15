"use strict";

(() => {
  const input = document.getElementById("photo");
  const preview = document.getElementById("photo-preview");
  const image = document.getElementById("photo-preview-image");
  const removeButton = document.getElementById("photo-preview-remove");
  const previewNote = document.getElementById("photo-preview-note");
  const errorMessage = document.getElementById("photo-preview-error");

  if (!input || !preview || !image || !removeButton || !previewNote || !errorMessage) {
    return;
  }

  const allowedTypes = new Set([
    "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif",
    "image/heic-sequence", "image/heif-sequence",
  ]);
  const allowedExtensions = new Set(["jpg", "jpeg", "png", "webp", "heic", "heif"]);
  const heifExtensions = new Set(["heic", "heif"]);
  const maxBytes = Number(preview.dataset.maxBytes);
  let objectUrl = null;

  const releaseObjectUrl = () => {
    if (objectUrl !== null) {
      URL.revokeObjectURL(objectUrl);
      objectUrl = null;
    }
  };

  const hidePreview = () => {
    image.onload = null;
    image.onerror = null;
    image.removeAttribute("src");
    preview.classList.remove("is-visible");
    preview.hidden = true;
    releaseObjectUrl();
  };

  const clearError = () => {
    errorMessage.textContent = "";
    errorMessage.hidden = true;
  };

  const clearNote = () => {
    previewNote.textContent = "";
    previewNote.hidden = true;
  };

  const rejectFile = (message) => {
    hidePreview();
    input.value = "";
    errorMessage.textContent = message;
    errorMessage.hidden = false;
    input.focus();
  };

  input.addEventListener("change", () => {
    hidePreview();
    clearError();
    clearNote();

    const file = input.files[0];
    if (!file) {
      return;
    }

    const extension = file.name.includes(".")
      ? file.name.split(".").pop().toLowerCase()
      : "";
    const typeIsInvalid = file.type && !allowedTypes.has(file.type);

    if (!allowedExtensions.has(extension) || typeIsInvalid) {
      rejectFile("JPEG、PNG、WebP、HEIC、HEIFのいずれかの写真を選んでください。");
      return;
    }

    if (Number.isFinite(maxBytes) && file.size > maxBytes) {
      rejectFile("写真のファイルサイズは10MB以内にしてください。");
      return;
    }

    if (heifExtensions.has(extension)) {
      previewNote.textContent = "HEIC・HEIFは投稿後に変換して表示されます。";
      previewNote.hidden = false;
      return;
    }

    objectUrl = URL.createObjectURL(file);
    image.onload = () => {
      preview.hidden = false;
      preview.classList.remove("is-visible");
      void preview.offsetWidth;
      preview.classList.add("is-visible");
    };
    image.onerror = () => {
      rejectFile("画像を読み込めませんでした。別の写真を選んでください。");
    };
    image.src = objectUrl;
  });

  removeButton.addEventListener("click", () => {
    hidePreview();
    clearError();
    clearNote();
    input.value = "";
    input.focus();
  });

  window.addEventListener("pagehide", releaseObjectUrl);
})();
