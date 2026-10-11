from datetime import date, timedelta

from hiromachi.database import database_proxy
from hiromachi.models import Activity, ActivityWasteType, WasteType

from .conftest import login


def activity_data(**overrides):
    with database_proxy.connection_context():
        waste_type_id = WasteType.get(WasteType.code == "burnable").id
    data = {
        "activity_date": date.today().isoformat(),
        "location": "フットパス北側",
        "duration_minutes": "30",
        "bag_count": "1",
        "waste_types": [str(waste_type_id)],
        "comment": "道路脇を清掃しました。",
    }
    data.update(overrides)
    return data


def test_activity_routes_require_login(client):
    assert client.get("/activities").status_code == 302
    assert client.get("/activities/new").status_code == 302
    assert client.get("/activities/1").status_code == 302
    assert client.get("/me").status_code == 302


def test_create_activity_and_show_detail(client, user):
    login(client)
    response = client.post("/activities/new", data=activity_data())

    assert response.status_code == 303
    assert "/activities/" in response.headers["Location"]
    with database_proxy.connection_context():
        activity = Activity.get()
        assert activity.location == "フットパス北側"
        assert ActivityWasteType.select().count() == 1

    detail = client.get(response.headers["Location"])
    assert detail.status_code == 200
    assert "道路脇を清掃しました" in detail.text
    assert "燃えるごみ" in detail.text


def test_create_rejects_future_date(client, user):
    login(client)
    future = (date.today() + timedelta(days=1)).isoformat()

    response = client.post(
        "/activities/new", data=activity_data(activity_date=future)
    )

    assert response.status_code == 200
    assert "未来の日付は指定できません" in response.text
    with database_proxy.connection_context():
        assert Activity.select().count() == 0


def test_activity_list_is_paginated(client, user):
    with database_proxy.atomic():
        for number in range(11):
            Activity.create(
                user=user,
                activity_date=date.today(),
                location=f"場所{number}",
                duration_minutes=10,
                bag_count=0,
            )
    login(client)

    first_page = client.get("/activities")
    second_page = client.get("/activities?page=2")

    assert first_page.status_code == 200
    assert first_page.text.count("activity-card") == 10
    assert second_page.status_code == 200
    assert second_page.text.count("activity-card") == 1
    assert client.get("/activities?page=3").status_code == 404


def test_missing_activity_is_404(client, user):
    login(client)
    assert client.get("/activities/999").status_code == 404
