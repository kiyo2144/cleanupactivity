"""Safe validation and storage helpers for one activity photo."""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener
from werkzeug.datastructures import FileStorage

register_heif_opener()


class PhotoValidationError(ValueError):
    """Raised when an uploaded file is not an accepted still image."""


@dataclass(frozen=True)
class ProcessedPhoto:
    data: bytes
    extension: str
    mime_type: str
    width: int
    height: int


_FORMAT_SETTINGS = {
    "JPEG": {
        "extensions": {".jpg", ".jpeg"},
        "extension": ".jpg",
        "mime_type": "image/jpeg",
    },
    "PNG": {
        "extensions": {".png"},
        "extension": ".png",
        "mime_type": "image/png",
    },
    "WEBP": {
        "extensions": {".webp"},
        "extension": ".webp",
        "mime_type": "image/webp",
    },
    "HEIF": {
        "extensions": {".heic", ".heif"},
    },
}


def process_photo(
    upload: FileStorage,
    *,
    max_bytes: int,
    max_dimension: int,
) -> ProcessedPhoto:
    """Validate, orient, resize, and re-encode an uploaded still image."""

    raw = upload.stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        max_megabytes = max_bytes // (1024 * 1024)
        raise PhotoValidationError(
            f"写真のファイルサイズは{max_megabytes}MB以内にしてください。"
        )
    if not raw:
        raise PhotoValidationError("写真ファイルを選択してください。")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                image_format = source.format
                if image_format not in _FORMAT_SETTINGS:
                    raise PhotoValidationError(
                        "写真はJPEG、PNG、WebP、HEIC、HEIFのいずれかを選択してください。"
                    )
                if image_format != "HEIF" and getattr(source, "n_frames", 1) != 1:
                    raise PhotoValidationError("アニメーション画像は登録できません。")

                suffix = Path(upload.filename or "").suffix.lower()
                settings = _FORMAT_SETTINGS[image_format]
                if suffix not in settings["extensions"]:
                    raise PhotoValidationError(
                        "ファイルの拡張子と画像形式が一致していません。"
                    )

                if image_format == "HEIF":
                    source.seek(0)
                source.load()
                oriented = ImageOps.exif_transpose(source)
                oriented.thumbnail(
                    (max_dimension, max_dimension),
                    Image.Resampling.LANCZOS,
                )
                image = oriented.copy()
                image.info.clear()
    except PhotoValidationError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as error:
        raise PhotoValidationError(
            "画像の内容を確認できませんでした。別の写真を選択してください。"
        ) from error

    output = BytesIO()
    output_format = image_format
    if image_format == "HEIF":
        has_transparency = image.mode in {"LA", "PA", "RGBA"} or (
            image.mode == "P" and "transparency" in image.info
        )
        output_format = "PNG" if has_transparency else "JPEG"
        settings = _FORMAT_SETTINGS[output_format]
    if output_format == "JPEG":
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        image.save(output, format="JPEG", quality=85, optimize=True)
    elif output_format == "PNG":
        image.save(output, format="PNG", optimize=True)
    else:
        image.save(output, format="WEBP", quality=85, method=6)

    return ProcessedPhoto(
        data=output.getvalue(),
        extension=settings["extension"],
        mime_type=settings["mime_type"],
        width=image.width,
        height=image.height,
    )


def store_photo(photo: ProcessedPhoto, upload_dir: Path) -> tuple[str, Path]:
    """Atomically store processed bytes under a random server-generated name."""

    storage_name = f"{uuid4().hex}{photo.extension}"
    final_path = upload_dir / storage_name
    temporary_path = upload_dir / f".{storage_name}.tmp"
    try:
        temporary_path.write_bytes(photo.data)
        os.replace(temporary_path, final_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return storage_name, final_path
