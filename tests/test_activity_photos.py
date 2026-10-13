from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from pillow_heif import from_pillow

from hiromachi.database import database_proxy
from hiromachi.models import Activity, ActivityPhoto

from .conftest import login
from .test_activities import activity_data


def image_upload(
    image_format: str = "JPEG",
    *,
    filename: str | None = None,
    size: tuple[int, int] = (120, 80),
    exif: Image.Exif | None = None,
):
    stream = BytesIO()
    image = Image.new("RGB", size, "#4f7354")
    save_options = {"exif": exif} if exif is not None else {}
    image.save(stream, format=image_format, **save_options)
    stream.seek(0)
    extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[image_format]
    return stream, filename or f"activity.{extension}"


def heif_upload(
    *,
    filename: str = "activity.heic",
    mode: str = "RGB",
    size: tuple[int, int] = (120, 80),
    multiple: bool = False,
):
    stream = BytesIO()
    color = (79, 115, 84, 128) if mode == "RGBA" else "#4f7354"
    heif = from_pillow(Image.new(mode, size, color))
    if multiple:
        heif.add_from_pillow(Image.new("RGB", (40, 30), "#ffffff"))
    heif.save(stream)
    stream.seek(0)
    return stream, filename


def test_create_page_includes_photo_preview(client, user):
    login(client)

    response = client.get("/activities/new")

    assert response.status_code == 200
    assert 'id="photo-preview"' in response.text
    assert 'data-max-bytes="10485760"' in response.text
    assert 'aria-describedby="photo-help photo-privacy photo-preview-note photo-preview-error"' in response.text
    assert 'id="photo-preview-image"' in response.text
    assert 'id="photo-preview-remove"' in response.text
    assert 'id="photo-preview-note"' in response.text
    assert "選択を取り消す" in response.text
    assert ".heic,.heif" in response.text
    assert "/static/js/photo-preview.js" in response.text

    script = client.get("/static/js/photo-preview.js")
    assert script.status_code == 200
    assert "URL.createObjectURL" in script.text
    assert "URL.revokeObjectURL" in script.text
    assert "HEIC・HEIFは投稿後に変換して表示されます" in script.text


@pytest.mark.parametrize(
    ("image_format", "expected_mime"),
    [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")],
)
def test_create_activity_with_supported_photo(
    client, app, user, image_format, expected_mime
):
    login(client)
    data = activity_data(photo=image_upload(image_format))

    response = client.post("/activities/new", data=data)

    assert response.status_code == 303
    with database_proxy.connection_context():
        photo = ActivityPhoto.get()
        storage_name = photo.storage_name
        assert photo.mime_type == expected_mime
        assert photo.width == 120
        assert photo.height == 80
    assert (Path(app.config["UPLOAD_DIR"]) / storage_name).is_file()


def test_photo_is_resized_oriented_and_metadata_is_removed(client, app, user):
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private metadata"
    login(client)
    data = activity_data(
        photo=image_upload("JPEG", size=(3000, 1500), exif=exif)
    )

    response = client.post("/activities/new", data=data)

    assert response.status_code == 303
    with database_proxy.connection_context():
        photo = ActivityPhoto.get()
        stored_path = Path(app.config["UPLOAD_DIR"]) / photo.storage_name
        assert (photo.width, photo.height) == (1000, 2000)
    with Image.open(stored_path) as stored:
        assert stored.size == (1000, 2000)
        assert len(stored.getexif()) == 0


@pytest.mark.parametrize(
    "photo",
    [
        (BytesIO(b"not an image"), "broken.jpg"),
        image_upload("PNG", filename="wrong.jpg"),
    ],
)
def test_invalid_photo_does_not_create_activity(client, app, user, photo):
    login(client)

    response = client.post(
        "/activities/new", data=activity_data(photo=photo)
    )

    assert response.status_code == 200
    with database_proxy.connection_context():
        assert Activity.select().count() == 0
        assert ActivityPhoto.select().count() == 0
    assert list(Path(app.config["UPLOAD_DIR"]).iterdir()) == []


def test_photo_over_ten_megabytes_is_rejected(client, app, user):
    login(client)
    oversized = BytesIO(b"x" * (10 * 1024 * 1024 + 1))

    response = client.post(
        "/activities/new",
        data=activity_data(photo=(oversized, "large.jpg")),
    )

    assert response.status_code == 200
    assert "10MB以内" in response.text
    with database_proxy.connection_context():
        assert Activity.select().count() == 0
    assert list(Path(app.config["UPLOAD_DIR"]).iterdir()) == []


@pytest.mark.parametrize("extension", ["heic", "heif"])
def test_heif_is_converted_to_jpeg(client, app, user, extension):
    login(client)

    response = client.post(
        "/activities/new",
        data=activity_data(photo=heif_upload(filename=f"activity.{extension}")),
    )

    assert response.status_code == 303
    with database_proxy.connection_context():
        photo = ActivityPhoto.get()
        stored_path = Path(app.config["UPLOAD_DIR"]) / photo.storage_name
        assert photo.mime_type == "image/jpeg"
        assert photo.storage_name.endswith(".jpg")
        assert (photo.width, photo.height) == (120, 80)
    with Image.open(stored_path) as stored:
        assert stored.format == "JPEG"
        assert len(stored.getexif()) == 0
    assert not any(
        path.suffix.lower() in {".heic", ".heif"}
        for path in Path(app.config["UPLOAD_DIR"]).iterdir()
    )


def test_heif_with_transparency_is_converted_to_png(client, app, user):
    login(client)

    response = client.post(
        "/activities/new",
        data=activity_data(photo=heif_upload(mode="RGBA")),
    )

    assert response.status_code == 303
    with database_proxy.connection_context():
        photo = ActivityPhoto.get()
        stored_path = Path(app.config["UPLOAD_DIR"]) / photo.storage_name
        assert photo.mime_type == "image/png"
        assert photo.storage_name.endswith(".png")
    with Image.open(stored_path) as stored:
        assert stored.format == "PNG"


def test_multi_image_heif_uses_first_image(client, app, user):
    login(client)

    response = client.post(
        "/activities/new",
        data=activity_data(photo=heif_upload(multiple=True)),
    )

    assert response.status_code == 303
    with database_proxy.connection_context():
        photo = ActivityPhoto.get()
        assert (photo.width, photo.height) == (120, 80)


@pytest.mark.parametrize(
    "photo",
    [
        (BytesIO(b"not a heif image"), "broken.heic"),
        heif_upload(filename="wrong.jpg"),
    ],
)
def test_invalid_heif_does_not_create_activity(client, app, user, photo):
    login(client)

    response = client.post("/activities/new", data=activity_data(photo=photo))

    assert response.status_code == 200
    with database_proxy.connection_context():
        assert Activity.select().count() == 0
        assert ActivityPhoto.select().count() == 0
    assert list(Path(app.config["UPLOAD_DIR"]).iterdir()) == []


def test_photo_route_requires_login_and_serves_stored_photo(client, user):
    login(client)
    response = client.post(
        "/activities/new", data=activity_data(photo=image_upload())
    )
    activity_id = int(response.headers["Location"].rstrip("/").split("/")[-1])

    detail = client.get(f"/activities/{activity_id}")
    assert f'/activities/{activity_id}/photo' in detail.text

    photo_response = client.get(f"/activities/{activity_id}/photo")
    assert photo_response.status_code == 200
    assert photo_response.content_type == "image/jpeg"
    assert photo_response.data.startswith(b"\xff\xd8")

    client.post("/logout")
    assert client.get(f"/activities/{activity_id}/photo").status_code == 302


def test_missing_photo_is_404(client, user):
    login(client)
    response = client.post("/activities/new", data=activity_data())
    activity_id = int(response.headers["Location"].rstrip("/").split("/")[-1])

    assert client.get(f"/activities/{activity_id}/photo").status_code == 404


def test_database_failure_removes_file_and_rolls_back_activity(
    client, app, user, monkeypatch
):
    def fail_to_create(**kwargs):
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(ActivityPhoto, "create", staticmethod(fail_to_create))
    login(client)

    with pytest.raises(RuntimeError, match="simulated database failure"):
        client.post(
            "/activities/new", data=activity_data(photo=image_upload())
        )

    with database_proxy.connection_context():
        assert Activity.select().count() == 0
        assert ActivityPhoto.select().count() == 0
    assert list(Path(app.config["UPLOAD_DIR"]).iterdir()) == []
