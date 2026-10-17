from __future__ import annotations

import json
import re
from datetime import date

import pytest
from peewee import IntegrityError
from werkzeug.security import generate_password_hash

from hiromachi.database import database_proxy
from hiromachi.models import Activity, ActivityRoute, User

from .conftest import login
from .test_activities import activity_data


ROUTE_POINTS = [
    [35.123456, 139.123456],
    [35.234567, 139.234567],
    [35.345678, 139.345678],
]
SINGLE_ROUTE_POINT = [[35.123456, 139.123456]]


def _create_with_route(client) -> int:
    response = client.post(
        "/activities/new",
        data=activity_data(route_points=json.dumps(ROUTE_POINTS)),
    )
    assert response.status_code == 303
    return int(response.headers["Location"].rstrip("/").split("/")[-1])


def test_create_page_has_optional_route_map(client, user):
    login(client)

    response = client.get("/activities/new")

    assert response.status_code == 200
    assert 'id="activity-route-map"' in response.text
    assert response.text.count('name="route_points"') == 1
    location_button = re.search(
        r'<button[^>]*id="route-current-location"[^>]*>', response.text
    )
    assert location_button is not None
    assert "hidden" not in location_button.group(0)
    assert 'id="route-location-status"' in response.text
    assert "/static/vendor/leaflet/leaflet.css?v=20261017-4" in response.text
    assert "/static/vendor/leaflet/leaflet.js?v=20261017-4" in response.text
    assert "/static/js/activity-route-map.js?v=20261017-4" in response.text
    assert "/static/js/activity-form-errors.js?v=20261017-4" in response.text
    assert "data-form-error-summary" not in response.text


def test_create_without_route_remains_supported(client, user):
    login(client)

    response = client.post("/activities/new", data=activity_data())

    assert response.status_code == 303
    with database_proxy.connection_context():
        assert Activity.select().count() == 1
        assert ActivityRoute.select().count() == 0


def test_create_single_point_rounds_and_shows_marker(client, user):
    login(client)

    response = client.post(
        "/activities/new",
        data=activity_data(route_points=json.dumps(SINGLE_ROUTE_POINT)),
    )

    assert response.status_code == 303
    with database_proxy.connection_context():
        route = ActivityRoute.get()
        assert route.point_count == 1
        assert json.loads(route.points_json) == [[35.123, 139.123]]

    detail = client.get(response.headers["Location"])
    assert detail.status_code == 200
    assert "清掃地点" in detail.text
    assert 'aria-label="登録された清掃地点の地図"' in detail.text


def test_create_route_rounds_endpoints_and_shows_logged_in_users(client, user):
    login(client)
    activity_id = _create_with_route(client)

    with database_proxy.connection_context():
        activity_route = ActivityRoute.get()
        assert activity_route.activity_id == activity_id
        assert activity_route.point_count == 3
        assert json.loads(activity_route.points_json) == [
            [35.123, 139.123],
            [35.234567, 139.234567],
            [35.346, 139.346],
        ]
        User.create(
            username="other_user",
            display_name="別の利用者",
            password_hash=generate_password_hash("password123"),
        )

    client.post("/logout")
    login(client, username="other_user")
    detail = client.get(f"/activities/{activity_id}")

    assert detail.status_code == 200
    assert "清掃ルート" in detail.text
    assert 'data-route-mode="view"' in detail.text
    assert "/static/js/activity-route-map.js?v=20261017-4" in detail.text


@pytest.mark.parametrize(
    ("route_points", "message"),
    [
        ("not-json", "清掃ルートの形式が正しくありません"),
        (
            json.dumps([[35.0, 139.0 + (index * 0.001)] for index in range(101)]),
            "清掃ルートは1～100地点",
        ),
        (
            json.dumps([[91.0, 139.0], [35.0, 139.0]]),
            "清掃ルートの座標が正しくありません",
        ),
        (
            json.dumps([[35.0001, 139.0001], [35.0002, 139.0002]]),
            "異なる地点を2つ以上",
        ),
    ],
)
def test_create_rejects_invalid_route(client, user, route_points, message):
    login(client)

    response = client.post(
        "/activities/new",
        data=activity_data(route_points=route_points),
    )

    assert response.status_code == 200
    assert message in response.text
    assert "投稿できませんでした" in response.text
    assert 'href="#field-route-points"' in response.text
    assert 'id="field-route-points"' in response.text
    assert 'aria-invalid="true"' in response.text
    with database_proxy.connection_context():
        assert Activity.select().count() == 0
        assert ActivityRoute.select().count() == 0


def test_edit_prefills_updates_and_clears_route(client, user):
    login(client)
    activity_id = _create_with_route(client)

    edit_page = client.get(f"/activities/{activity_id}/edit")
    assert edit_page.status_code == 200
    assert "35.234567" in edit_page.text
    location_button = re.search(
        r'<button[^>]*id="route-current-location"[^>]*>', edit_page.text
    )
    assert location_button is not None
    assert "hidden" in location_button.group(0)

    updated_points = [[34.111111, 135.111111], [34.222222, 135.222222]]
    updated = client.post(
        f"/activities/{activity_id}/edit",
        data=activity_data(route_points=json.dumps(updated_points)),
    )
    assert updated.status_code == 303
    with database_proxy.connection_context():
        activity_route = ActivityRoute.get()
        assert json.loads(activity_route.points_json) == [
            [34.111, 135.111],
            [34.222, 135.222],
        ]

    cleared = client.post(
        f"/activities/{activity_id}/edit",
        data=activity_data(route_points=""),
    )
    assert cleared.status_code == 303
    with database_proxy.connection_context():
        assert ActivityRoute.select().count() == 0


def test_edit_can_change_route_to_single_point(client, user):
    login(client)
    activity_id = _create_with_route(client)

    response = client.post(
        f"/activities/{activity_id}/edit",
        data=activity_data(route_points=json.dumps(SINGLE_ROUTE_POINT)),
    )

    assert response.status_code == 303
    with database_proxy.connection_context():
        route = ActivityRoute.get()
        assert route.point_count == 1
        assert json.loads(route.points_json) == [[35.123, 139.123]]


def test_route_database_failure_rolls_back_activity(client, user, monkeypatch):
    login(client)

    def fail_to_create(*args, **kwargs):
        raise RuntimeError("simulated route database failure")

    monkeypatch.setattr(ActivityRoute, "create", staticmethod(fail_to_create))

    with pytest.raises(RuntimeError, match="simulated route database failure"):
        client.post(
            "/activities/new",
            data=activity_data(route_points=json.dumps(ROUTE_POINTS)),
        )

    with database_proxy.connection_context():
        assert Activity.select().count() == 0
        assert ActivityRoute.select().count() == 0


def test_delete_activity_cascades_to_route(client, user):
    login(client)
    activity_id = _create_with_route(client)

    response = client.post(f"/activities/{activity_id}/delete")

    assert response.status_code == 303
    with database_proxy.connection_context():
        assert Activity.select().count() == 0
        assert ActivityRoute.select().count() == 0


def test_map_static_files_are_served(client):
    script = client.get("/static/js/activity-route-map.js?v=20261017-4")
    assert script.status_code == 200
    assert "navigator.geolocation.getCurrentPosition" in script.text
    assert "enableHighAccuracy: true" in script.text
    assert "timeout: 10000" in script.text
    assert "maximumAge: 0" in script.text
    assert "draggable: isEditable" in script.text
    assert 'classList.add("route-point-added")' in script.text
    assert "points.length === 1" in script.text
    assert 'title: isEditable ? "始点（ドラッグして修正）" : "清掃地点"' in script.text
    assert "このまま投稿できます" in script.text
    assert "現在地の利用が許可されませんでした" in script.text
    assert (
        client.get("/static/vendor/leaflet/leaflet.css?v=20261017-4").status_code
        == 200
    )
    assert (
        client.get("/static/vendor/leaflet/leaflet.js?v=20261017-4").status_code
        == 200
    )


@pytest.mark.parametrize("point_count", [0, 101])
def test_route_database_rejects_out_of_range_point_count(user, point_count):
    with database_proxy.connection_context():
        activity = Activity.create(
            user=user,
            activity_date=date.today(),
            location="DB制約確認",
            duration_minutes=10,
            bag_count=0,
        )
        with pytest.raises(IntegrityError):
            with database_proxy.atomic():
                ActivityRoute.create(
                    activity=activity,
                    points_json="[[35.0,139.0]]",
                    point_count=point_count,
                )
