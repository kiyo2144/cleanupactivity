from __future__ import annotations

import logging
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

from hiromachi.database import database_proxy
from hiromachi.models import Activity, ActivityPhoto, ActivityWasteType, User

from .conftest import login
from .test_activities import activity_data
from .test_activity_photos import image_upload


def _create_activity(client, *, photo=None) -> int:
    data = activity_data()
    if photo is not None:
        data["photo"] = photo
    response = client.post("/activities/new", data=data)
    assert response.status_code == 303
    return int(response.headers["Location"].rstrip("/").split("/")[-1])


def test_delete_requires_login_and_owner(client, user):
    login(client)
    activity_id = _create_activity(client)
    client.post("/logout")

    assert client.get(f"/activities/{activity_id}/delete").status_code == 302
    assert client.post(f"/activities/{activity_id}/delete").status_code == 302

    with database_proxy.connection_context():
        User.create(
            username="other_user",
            display_name="別の利用者",
            password_hash=generate_password_hash("password123"),
        )
    login(client, username="other_user")

    detail = client.get(f"/activities/{activity_id}")
    assert f'/activities/{activity_id}/delete' not in detail.text
    assert client.get(f"/activities/{activity_id}/delete").status_code == 404
    assert client.post(f"/activities/{activity_id}/delete").status_code == 404
    assert client.get("/activities/99999/delete").status_code == 404


def test_delete_confirmation_does_not_delete_on_get(client, user):
    login(client)
    activity_id = _create_activity(client, photo=image_upload())

    detail = client.get(f"/activities/{activity_id}")
    response = client.get(f"/activities/{activity_id}/delete")

    assert f'/activities/{activity_id}/delete' in detail.text
    assert response.status_code == 200
    assert "この操作は元に戻せません" in response.text
    assert "フットパス北側" in response.text
    assert "あり" in response.text
    assert f'/activities/{activity_id}' in response.text
    with database_proxy.connection_context():
        assert Activity.get_by_id(activity_id)


def test_delete_activity_and_related_data(client, app, user):
    login(client)
    activity_id = _create_activity(client, photo=image_upload())
    with database_proxy.connection_context():
        storage_name = ActivityPhoto.get().storage_name
    photo_path = Path(app.config["UPLOAD_DIR"]) / storage_name

    response = client.post(f"/activities/{activity_id}/delete")

    assert response.status_code == 303
    assert response.headers["Location"].endswith("/me")
    assert not photo_path.exists()
    with database_proxy.connection_context():
        assert Activity.select().count() == 0
        assert ActivityWasteType.select().count() == 0
        assert ActivityPhoto.select().count() == 0
    page = client.get(response.headers["Location"])
    assert "活動を削除しました" in page.text
    assert 'data-feedback="success-neutral"' in page.text
    assert 'class="flash flash-success-neutral"' in page.text


def test_delete_activity_without_photo(client, user):
    login(client)
    activity_id = _create_activity(client)

    confirmation = client.get(f"/activities/{activity_id}/delete")
    response = client.post(f"/activities/{activity_id}/delete")

    assert "なし" in confirmation.text
    assert response.status_code == 303
    with database_proxy.connection_context():
        assert Activity.select().count() == 0


def test_delete_rejects_post_without_csrf(client, app, user):
    login(client)
    activity_id = _create_activity(client)
    app.config["WTF_CSRF_ENABLED"] = True

    response = client.post(f"/activities/{activity_id}/delete")

    assert response.status_code == 400
    with database_proxy.connection_context():
        assert Activity.get_by_id(activity_id)


def test_delete_database_failure_rolls_back_and_keeps_photo(
    client, app, user, monkeypatch
):
    login(client)
    activity_id = _create_activity(client, photo=image_upload())
    with database_proxy.connection_context():
        storage_name = ActivityPhoto.get().storage_name
    photo_path = Path(app.config["UPLOAD_DIR"]) / storage_name
    original_delete = Activity.delete_instance

    def delete_then_fail(activity, *args, **kwargs):
        original_delete(activity, *args, **kwargs)
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(Activity, "delete_instance", delete_then_fail)

    with pytest.raises(RuntimeError, match="simulated database failure"):
        client.post(f"/activities/{activity_id}/delete")

    assert photo_path.is_file()
    with database_proxy.connection_context():
        assert Activity.get_by_id(activity_id)
        assert ActivityWasteType.select().count() == 1
        assert ActivityPhoto.select().count() == 1


def test_photo_delete_failure_is_logged_without_filename(
    client, app, user, monkeypatch, caplog
):
    login(client)
    activity_id = _create_activity(client, photo=image_upload())
    with database_proxy.connection_context():
        storage_name = ActivityPhoto.get().storage_name
    photo_path = Path(app.config["UPLOAD_DIR"]) / storage_name
    original_unlink = Path.unlink

    def fail_for_activity_photo(path, *args, **kwargs):
        if path == photo_path:
            raise OSError("simulated file failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_for_activity_photo)

    with caplog.at_level(logging.ERROR):
        response = client.post(f"/activities/{activity_id}/delete")

    assert response.status_code == 303
    assert photo_path.is_file()
    assert "Failed to remove deleted activity photo" in caplog.text
    assert storage_name not in caplog.text
    with database_proxy.connection_context():
        assert Activity.select().count() == 0
        assert ActivityPhoto.select().count() == 0
