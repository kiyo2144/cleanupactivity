import re
from datetime import date, datetime, timezone

import pytest

from hiromachi.database import database_proxy
from hiromachi.models import Activity, User
from hiromachi.activities import forms
from hiromachi.users import routes

from .conftest import login


def test_my_page_shows_only_current_user_totals(client, user):
    with database_proxy.atomic():
        Activity.create(
            user=user,
            activity_date=date.today(),
            location="駅前",
            duration_minutes=20,
            bag_count=1,
        )
        Activity.create(
            user=user,
            activity_date=date.today(),
            location="公園",
            duration_minutes=40,
            bag_count=2,
        )

    login(client)
    response = client.get("/me")

    assert response.status_code == 200
    assert "活動回数" in response.text
    assert "累計時間（分）" in response.text
    assert ">60<" in response.text
    assert ">3<" in response.text


def _summary(response, heading):
    section = re.search(
        rf'<section class="summary" aria-labelledby="{heading}">(.*?)</section>',
        response.text,
        re.S,
    )
    assert section is not None
    return [int(value) for value in re.findall(r'<strong>(\d+)</strong>', section[1])]


@pytest.mark.parametrize("today,previous,last,next_month", [
    (date(2026, 10, 17), date(2026, 9, 30), date(2026, 10, 31), date(2026, 11, 1)),
    (date(2026, 12, 31), date(2026, 11, 30), date(2026, 12, 31), date(2027, 1, 1)),
    (date(2028, 2, 1), date(2028, 1, 31), date(2028, 2, 29), date(2028, 3, 1)),
])
def test_monthly_totals_use_activity_dates_and_current_user(
    client, user, monkeypatch, today, previous, last, next_month
):
    monkeypatch.setattr(routes, "today_in_japan", lambda: today)
    with database_proxy.atomic():
        other = User.create(username="other", display_name="別の人", password_hash="unused")
        for owner, activity_date, minutes, bags in [
            (user, previous, 5, 1),
            (user, today.replace(day=1), 20, 2),
            (user, last, 30, 3),
            (user, next_month, 10, 4),
            (other, today, 100, 10),
        ]:
            Activity.create(user=owner, activity_date=activity_date, location="公園",
                            duration_minutes=minutes, bag_count=bags,
                            created_at=datetime(2026, 10, 17))
    login(client)
    response = client.get("/me")
    assert response.status_code == 200
    assert f"{today.year}年{today.month}月" in response.text
    assert _summary(response, "monthly-summary-heading") == [2, 50, 5]
    assert _summary(response, "all-time-summary-heading") == [4, 65, 10]
    assert "今月の記録はまだありません" not in response.text


@pytest.mark.parametrize("has_previous_activity", [False, True])
def test_monthly_zero_totals_and_message(client, user, monkeypatch, has_previous_activity):
    monkeypatch.setattr(routes, "today_in_japan", lambda: date(2026, 10, 17))
    if has_previous_activity:
        with database_proxy.atomic():
            Activity.create(user=user, activity_date=date(2026, 9, 30), location="公園",
                            duration_minutes=20, bag_count=1)
    login(client)
    response = client.get("/me")
    assert response.status_code == 200
    assert _summary(response, "monthly-summary-heading") == [0, 0, 0]
    assert "今月の記録はまだありません。自分のペースで記録しましょう。" in response.text
    assert ("まだ活動記録がありません。" in response.text) is not has_previous_activity


def test_monthly_totals_follow_changes_and_ignore_pagination(client, user, monkeypatch):
    monkeypatch.setattr(routes, "today_in_japan", lambda: date(2026, 10, 17))
    with database_proxy.atomic():
        for _ in range(11):
            activity = Activity.create(user=user, activity_date=date(2026, 10, 1),
                                       location="公園", duration_minutes=20, bag_count=1)
    login(client)
    assert _summary(client.get("/me?page=2"), "monthly-summary-heading") == [11, 220, 11]
    with database_proxy.atomic():
        activity.duration_minutes = 30
        activity.bag_count = 3
        activity.save()
    assert _summary(client.get("/me"), "monthly-summary-heading") == [11, 230, 13]
    with database_proxy.atomic():
        activity.activity_date = date(2026, 9, 30)
        activity.save()
    assert _summary(client.get("/me"), "monthly-summary-heading") == [10, 200, 10]
    with database_proxy.atomic():
        Activity.get(Activity.id != activity.id).delete_instance()
    assert _summary(client.get("/me"), "monthly-summary-heading") == [9, 180, 9]


@pytest.mark.parametrize("utc_hour,expected", [(14, "2026年12月"), (15, "2027年1月")])
def test_monthly_period_changes_at_japan_midnight(client, user, monkeypatch, utc_hour, expected):
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 12, 31, utc_hour, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(forms, "datetime", FrozenDatetime)
    login(client)
    assert expected in client.get("/me").text


def test_monthly_summary_requires_login(client):
    response = client.get("/me")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
