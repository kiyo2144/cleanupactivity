from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from hiromachi.database import database_proxy
from hiromachi.models import Activity, ActivityWasteType, User, WasteType

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
    assert client.get("/activities/1/photo").status_code == 302
    assert client.get("/me").status_code == 302


def test_create_page_has_accessible_quantity_steppers(client, user):
    login(client)

    response = client.get("/activities/new")

    assert response.status_code == 200
    assert response.text.count('data-quantity-stepper') == 2
    assert 'data-step="5"' in response.text
    assert 'data-step="1"' in response.text
    assert 'data-initial="5"' in response.text
    assert 'data-initial="1"' in response.text
    assert 'aria-label="所要時間を5分減らす"' in response.text
    assert 'aria-label="所要時間を5分増やす"' in response.text
    assert 'aria-label="ゴミの袋数を1袋減らす"' in response.text
    assert 'aria-label="ゴミの袋数を1袋増やす"' in response.text
    assert 'inputmode="numeric"' in response.text
    assert 'id="duration_minutes"' in response.text
    assert 'id="bag_count"' in response.text
    assert 'value=""' in response.text
    assert "/static/js/quantity-stepper.js?v=20261017-1" in response.text


def test_quantity_stepper_script_is_served(client):
    script = client.get("/static/js/quantity-stepper.js?v=20261017-1")

    assert script.status_code == 200
    assert script.mimetype == "text/javascript"
    assert 'document.querySelectorAll("[data-quantity-stepper]")' in script.text
    assert "decreaseButton.disabled = value === null || value <= minimum" in script.text
    assert "increaseButton.disabled = value !== null && value >= maximum" in script.text
    assert "value === null ? initialValue" in script.text
    assert "Math.min(maximum, Math.max(minimum, candidate))" in script.text
    assert 'new Event("input", { bubbles: true })' in script.text


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
    assert 'name="duration_minutes"' in response.text
    assert 'value="30"' in response.text
    assert 'name="bag_count"' in response.text
    assert 'value="1"' in response.text
    with database_proxy.connection_context():
        assert Activity.select().count() == 0


def test_create_shows_linked_error_summary_for_all_invalid_fields(client, user):
    login(client)

    response = client.post(
        "/activities/new",
        data={
            "activity_date": "",
            "location": "",
            "route_points": "not-json",
            "duration_minutes": "",
            "bag_count": "",
            "waste_types": [],
            "comment": "",
        },
    )

    assert response.status_code == 200
    assert "投稿できませんでした" in response.text
    assert 'class="form-error-summary"' in response.text
    assert 'role="alert"' in response.text
    assert 'href="#field-activity-date"' in response.text
    assert 'href="#field-location"' in response.text
    assert 'href="#field-route-points"' in response.text
    assert 'href="#field-duration-minutes"' in response.text
    assert 'href="#field-bag-count"' in response.text
    assert 'href="#field-waste-types"' in response.text
    assert "活動日：入力してください。" in response.text
    assert "清掃ルート：清掃ルートの形式が正しくありません。" in response.text
    assert 'aria-invalid="true"' in response.text
    assert "field-has-error" in response.text
    assert "/static/js/activity-form-errors.js?v=20261017-1" in response.text
    with database_proxy.connection_context():
        assert Activity.select().count() == 0


def test_activity_form_error_script_is_served(client):
    script = client.get("/static/js/activity-form-errors.js?v=20261017-1")

    assert script.status_code == 200
    assert script.mimetype == "text/javascript"
    assert "summary.focus({ preventScroll: true })" in script.text
    assert "field.scrollIntoView" in script.text
    assert "focusTarget?.focus" in script.text


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


def test_activity_list_shows_zero_totals(client, user):
    login(client)

    response = client.get("/activities")

    assert response.status_code == 200
    assert 'data-metric="activity-count"><strong>0</strong>' in response.text
    assert 'data-metric="total-minutes"><strong>0</strong>' in response.text
    assert 'data-metric="total-bags"><strong>0</strong>' in response.text


def test_activity_list_totals_include_all_users_and_pages(client, user):
    with database_proxy.atomic():
        other_user = User.create(
            username="other_user",
            display_name="別の利用者",
            password_hash=generate_password_hash("password123"),
        )
        for number in range(11):
            Activity.create(
                user=user if number < 6 else other_user,
                activity_date=date.today(),
                location=f"場所{number}",
                duration_minutes=number + 1,
                bag_count=number % 3,
            )
    login(client)

    first_page = client.get("/activities")
    second_page = client.get("/activities?page=2")

    for response in (first_page, second_page):
        assert 'data-metric="activity-count"><strong>11</strong>' in response.text
        assert 'data-metric="total-minutes"><strong>66</strong>' in response.text
        assert 'data-metric="total-bags"><strong>10</strong>' in response.text


def test_activity_totals_follow_create_edit_and_delete(client, user):
    login(client)
    created = client.post("/activities/new", data=activity_data())
    activity_id = int(created.headers["Location"].rstrip("/").split("/")[-1])

    after_create = client.get("/activities")
    assert 'data-metric="activity-count"><strong>1</strong>' in after_create.text
    assert 'data-metric="total-minutes"><strong>30</strong>' in after_create.text
    assert 'data-metric="total-bags"><strong>1</strong>' in after_create.text

    edited = client.post(
        f"/activities/{activity_id}/edit",
        data=activity_data(duration_minutes="45", bag_count="3"),
    )
    assert edited.status_code == 303
    after_edit = client.get("/activities")
    assert 'data-metric="total-minutes"><strong>45</strong>' in after_edit.text
    assert 'data-metric="total-bags"><strong>3</strong>' in after_edit.text

    deleted = client.post(f"/activities/{activity_id}/delete")
    assert deleted.status_code == 303
    after_delete = client.get("/activities")
    assert 'data-metric="activity-count"><strong>0</strong>' in after_delete.text
    assert 'data-metric="total-minutes"><strong>0</strong>' in after_delete.text
    assert 'data-metric="total-bags"><strong>0</strong>' in after_delete.text


def test_missing_activity_is_404(client, user):
    login(client)
    assert client.get("/activities/999").status_code == 404
