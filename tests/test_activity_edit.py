from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

from hiromachi.database import database_proxy
from hiromachi.models import (
    Activity,
    ActivityPhoto,
    ActivityWasteType,
    User,
    WasteType,
)

from .conftest import login
from .test_activities import activity_data
from .test_activity_photos import heif_upload, image_upload


class _InputParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.inputs: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "input":
            self.inputs.append(dict(attrs))


def _create_activity(client, *, photo=None) -> int:
    data = activity_data()
    if photo is not None:
        data["photo"] = photo
    response = client.post("/activities/new", data=data)
    assert response.status_code == 303
    return int(response.headers["Location"].rstrip("/").split("/")[-1])


def test_edit_requires_login_and_owner(client, user):
    login(client)
    activity_id = _create_activity(client)
    client.post("/logout")

    assert client.get(f"/activities/{activity_id}/edit").status_code == 302

    with database_proxy.connection_context():
        User.create(
            username="other_user",
            display_name="別の利用者",
            password_hash=generate_password_hash("password123"),
        )
    login(client, username="other_user")

    detail = client.get(f"/activities/{activity_id}")
    assert f'/activities/{activity_id}/edit' not in detail.text
    assert client.get(f"/activities/{activity_id}/edit").status_code == 404
    assert (
        client.post(f"/activities/{activity_id}/edit", data=activity_data()).status_code
        == 404
    )


def test_edit_page_prefills_activity_and_owner_link(client, user):
    login(client)
    activity_id = _create_activity(client)

    detail = client.get(f"/activities/{activity_id}")
    edit_page = client.get(f"/activities/{activity_id}/edit")

    assert detail.status_code == 200
    assert f'/activities/{activity_id}/edit' in detail.text
    assert edit_page.status_code == 200
    assert 'value="フットパス北側"' in edit_page.text
    assert "道路脇を清掃しました。" in edit_page.text
    parser = _InputParser()
    parser.feed(edit_page.text)
    with database_proxy.connection_context():
        burnable_id = str(WasteType.get(WasteType.code == "burnable").id)
    selected = next(
        item
        for item in parser.inputs
        if item.get("name") == "waste_types" and item.get("value") == burnable_id
    )
    assert "checked" in selected


def test_edit_can_replace_photo_with_heif(client, app, user):
    login(client)
    activity_id = _create_activity(client, photo=image_upload())
    with database_proxy.connection_context():
        original_name = ActivityPhoto.get().storage_name

    response = client.post(
        f"/activities/{activity_id}/edit",
        data=activity_data(photo=heif_upload()),
    )

    assert response.status_code == 303
    with database_proxy.connection_context():
        photo = ActivityPhoto.get()
        assert photo.mime_type == "image/jpeg"
        assert photo.storage_name.endswith(".jpg")
        assert photo.storage_name != original_name
    upload_dir = Path(app.config["UPLOAD_DIR"])
    assert not (upload_dir / original_name).exists()
    assert (upload_dir / photo.storage_name).is_file()


def test_edit_updates_activity_waste_types_and_timestamp(client, user, monkeypatch):
    login(client)
    activity_id = _create_activity(client)
    changed_at = datetime(2026, 10, 13, 3, 0, tzinfo=UTC).replace(tzinfo=None)
    monkeypatch.setattr("hiromachi.activities.routes.utc_now", lambda: changed_at)
    with database_proxy.connection_context():
        other_id = WasteType.get(WasteType.code == "other").id

    response = client.post(
        f"/activities/{activity_id}/edit",
        data=activity_data(
            location="公園の南側",
            duration_minutes="45",
            bag_count="2",
            waste_types=[str(other_id)],
            comment="編集後のコメント",
        ),
    )

    assert response.status_code == 303
    assert response.headers["Location"].endswith(f"/activities/{activity_id}")
    with database_proxy.connection_context():
        activity = Activity.get_by_id(activity_id)
        links = list(
            ActivityWasteType.select().where(
                ActivityWasteType.activity == activity_id
            )
        )
        assert activity.location == "公園の南側"
        assert activity.duration_minutes == 45
        assert activity.bag_count == 2
        assert activity.comment == "編集後のコメント"
        assert activity.updated_at == changed_at
        assert [link.waste_type_id for link in links] == [other_id]


def test_edit_validation_error_does_not_change_activity(client, user):
    login(client)
    activity_id = _create_activity(client)
    future = (date.today() + timedelta(days=1)).isoformat()

    response = client.post(
        f"/activities/{activity_id}/edit",
        data=activity_data(activity_date=future, location="変更されない場所"),
    )

    assert response.status_code == 200
    assert "未来の日付は指定できません" in response.text
    assert "更新できませんでした" in response.text
    assert 'class="form-error-summary"' in response.text
    assert 'href="#field-activity-date"' in response.text
    assert 'aria-invalid="true"' in response.text
    with database_proxy.connection_context():
        assert Activity.get_by_id(activity_id).location == "フットパス北側"


def test_edit_without_photo_change_keeps_existing_photo(client, app, user):
    login(client)
    activity_id = _create_activity(client, photo=image_upload())
    with database_proxy.connection_context():
        original_name = ActivityPhoto.get().storage_name

    response = client.post(
        f"/activities/{activity_id}/edit",
        data=activity_data(location="写真を維持する場所"),
    )

    assert response.status_code == 303
    with database_proxy.connection_context():
        assert ActivityPhoto.get().storage_name == original_name
    assert (Path(app.config["UPLOAD_DIR"]) / original_name).is_file()


def test_edit_replaces_existing_photo(client, app, user):
    login(client)
    activity_id = _create_activity(client, photo=image_upload())
    with database_proxy.connection_context():
        original_name = ActivityPhoto.get().storage_name

    response = client.post(
        f"/activities/{activity_id}/edit",
        data=activity_data(photo=image_upload("PNG")),
    )

    assert response.status_code == 303
    with database_proxy.connection_context():
        photo = ActivityPhoto.get()
        new_name = photo.storage_name
        assert photo.mime_type == "image/png"
        assert new_name != original_name
    upload_dir = Path(app.config["UPLOAD_DIR"])
    assert not (upload_dir / original_name).exists()
    assert (upload_dir / new_name).is_file()


def test_edit_removes_existing_photo(client, app, user):
    login(client)
    activity_id = _create_activity(client, photo=image_upload())
    with database_proxy.connection_context():
        original_name = ActivityPhoto.get().storage_name

    response = client.post(
        f"/activities/{activity_id}/edit",
        data=activity_data(remove_photo="y"),
    )

    assert response.status_code == 303
    with database_proxy.connection_context():
        assert ActivityPhoto.select().count() == 0
    assert not (Path(app.config["UPLOAD_DIR"]) / original_name).exists()


def test_edit_rejects_photo_and_removal_together(client, app, user):
    login(client)
    activity_id = _create_activity(client, photo=image_upload())
    with database_proxy.connection_context():
        original_name = ActivityPhoto.get().storage_name

    response = client.post(
        f"/activities/{activity_id}/edit",
        data=activity_data(remove_photo="y", photo=image_upload("PNG")),
    )

    assert response.status_code == 200
    assert "同時に指定できません" in response.text
    with database_proxy.connection_context():
        assert ActivityPhoto.get().storage_name == original_name
    assert [path.name for path in Path(app.config["UPLOAD_DIR"]).iterdir()] == [
        original_name
    ]


def test_edit_invalid_photo_does_not_change_activity(client, app, user):
    login(client)
    activity_id = _create_activity(client, photo=image_upload())
    with database_proxy.connection_context():
        original_name = ActivityPhoto.get().storage_name

    response = client.post(
        f"/activities/{activity_id}/edit",
        data=activity_data(
            location="変更されない場所",
            photo=(image_upload()[0], "broken.png"),
        ),
    )

    assert response.status_code == 200
    with database_proxy.connection_context():
        assert Activity.get_by_id(activity_id).location == "フットパス北側"
        assert ActivityPhoto.get().storage_name == original_name
    assert [path.name for path in Path(app.config["UPLOAD_DIR"]).iterdir()] == [
        original_name
    ]


def test_edit_database_failure_removes_new_file_and_keeps_old_photo(
    client, app, user, monkeypatch
):
    login(client)
    activity_id = _create_activity(client, photo=image_upload())
    with database_proxy.connection_context():
        original_name = ActivityPhoto.get().storage_name

    def fail_to_save(self, *args, **kwargs):
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(ActivityPhoto, "save", fail_to_save)

    with pytest.raises(RuntimeError, match="simulated database failure"):
        client.post(
            f"/activities/{activity_id}/edit",
            data=activity_data(
                location="ロールバック対象",
                photo=image_upload("PNG"),
            ),
        )

    with database_proxy.connection_context():
        assert Activity.get_by_id(activity_id).location == "フットパス北側"
        assert ActivityPhoto.get().storage_name == original_name
    assert [path.name for path in Path(app.config["UPLOAD_DIR"]).iterdir()] == [
        original_name
    ]
