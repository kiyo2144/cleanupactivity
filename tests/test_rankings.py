import re
from datetime import date, datetime, UTC

import pytest

from hiromachi.activities import routes, forms
from hiromachi.database import database_proxy
from hiromachi.models import Activity, User
from .conftest import login


def record(user, day=date(2026, 10, 1), minutes=30, bags=1):
    return Activity.create(user=user, activity_date=day, location="公園",
                           duration_minutes=minutes, bag_count=bags)


@pytest.fixture()
def month(monkeypatch):
    monkeypatch.setattr(routes, "today_in_japan", lambda: date(2026, 10, 17))


def rows(response):
    return re.findall(r'<li value="(\d+)" class="ranking-entry">\s*'
                      r'<span class="ranking-position">\d+位</span>\s*'
                      r'<span class="ranking-name">(.*?)さん</span>\s*'
                      r'<strong class="ranking-time">(\d+)分</strong>', response.text)


def metric(response, name):
    return int(re.search(rf'data-metric="{name}"><strong>(\d+)</strong>', response.text)[1])


def test_ranking_requires_login_and_is_read_only(client):
    assert '/login' in client.get('/activities/ranking').location
    assert client.post('/activities/ranking').status_code == 405


@pytest.mark.parametrize('today,previous,last,next_month', [
    (date(2026, 10, 17), date(2026, 9, 30), date(2026, 10, 31), date(2026, 11, 1)),
    (date(2026, 12, 31), date(2026, 11, 30), date(2026, 12, 31), date(2027, 1, 1)),
    (date(2027, 1, 1), date(2026, 12, 31), date(2027, 1, 31), date(2027, 2, 1)),
    (date(2028, 2, 29), date(2028, 1, 31), date(2028, 2, 29), date(2028, 3, 1)),
])
def test_month_boundaries_and_all_users(client, user, monkeypatch, today, previous, last, next_month):
    monkeypatch.setattr(routes, 'today_in_japan', lambda: today)
    with database_proxy.atomic():
        other = User.create(username='other_user', display_name='別の人', password_hash='unused')
        record(user, previous, 100, 9)
        record(user, today.replace(day=1), 20, 2)
        record(user, last, 30, 3)
        record(user, next_month, 100, 9)
        record(other, last, 70, 4)
    login(client)
    response = client.get('/activities')
    assert [metric(response, 'monthly-'+key) for key in ['activity-count', 'total-minutes', 'total-bags']] == [3, 120, 9]
    assert metric(response, 'total-minutes') == 320
    ranking = client.get('/activities/ranking')
    assert f'{today.year}年{today.month}月' in ranking.text
    assert rows(ranking) == [('1', '別の人', '70'), ('2', '佐藤', '50')]
    assert 'other_user' not in ranking.text


def test_competition_ranks_include_boundary_ties_and_not_inactive_users(client, user, month):
    with database_proxy.atomic():
        for index, minutes in enumerate([100, 100, 90, 80, 70, 60, 50, 40, 30, 20, 20, 10]):
            owner = User.create(username=f'person_{index}', display_name=f'参加者{index}', password_hash='unused')
            record(owner, minutes=minutes)
    login(client)
    result = rows(client.get('/activities/ranking'))
    assert [int(row[0]) for row in result] == [1, 1, 3, 4, 5, 6, 7, 8, 9, 10, 10]
    assert [row[1] for row in result[:2]] == ['参加者0', '参加者1']
    assert all(row[1] != '佐藤' for row in result)


def test_duplicate_display_names_and_escaping(client, user, month):
    with database_proxy.atomic():
        user.display_name = '<script>alert(1)</script>'
        user.save()
        other = User.create(username='same_name', display_name=user.display_name, password_hash='unused')
        record(user)
        record(other)
    login(client)
    response = client.get('/activities/ranking')
    assert len(rows(response)) == 2
    assert '<script>alert(1)</script>' not in response.text
    assert '&lt;script&gt;' in response.text


def test_empty_month_with_and_without_past_records(client, user, month):
    login(client)
    for past in [False, True]:
        if past:
            with database_proxy.atomic():
                record(user, date(2026, 9, 30))
        response = client.get('/activities')
        assert metric(response, 'monthly-activity-count') == 0
        assert metric(response, 'monthly-total-minutes') == 0
        assert metric(response, 'monthly-total-bags') == 0
        ranking = client.get('/activities/ranking')
        assert ranking.status_code == 200
        assert '今月の活動記録はまだありません。' in ranking.text
        assert rows(ranking) == []


def test_recalculation_and_pagination(client, user, month):
    with database_proxy.atomic():
        for _ in range(11):
            activity = record(user, minutes=10)
    login(client)
    assert metric(client.get('/activities?page=2'), 'monthly-total-minutes') == 110
    assert rows(client.get('/activities/ranking?page=2')) == [('1', '佐藤', '110')]
    with database_proxy.atomic():
        activity.duration_minutes = 20
        activity.bag_count = 3
        activity.save()
    assert rows(client.get('/activities/ranking')) == [('1', '佐藤', '120')]
    assert metric(client.get('/activities'), 'monthly-total-bags') == 13
    with database_proxy.atomic():
        activity.activity_date = date(2026, 9, 30)
        activity.save()
    assert rows(client.get('/activities/ranking')) == [('1', '佐藤', '100')]
    with database_proxy.atomic():
        Activity.delete().where(Activity.user == user).execute()
    assert rows(client.get('/activities/ranking')) == []


def test_japan_month_boundary(client, user, monkeypatch):
    class Clock:
        @classmethod
        def now(cls, tz):
            return datetime(2026, 9, 30, 15, 0, tzinfo=UTC).astimezone(tz)
    monkeypatch.setattr(forms, 'datetime', Clock)
    with database_proxy.atomic():
        record(user, date(2026, 9, 30), 50)
        record(user, date(2026, 10, 1), 20)
    login(client)
    assert rows(client.get('/activities/ranking')) == [('1', '佐藤', '20')]
    assert metric(client.get('/activities'), 'monthly-total-minutes') == 20


def test_ranking_query_count_does_not_grow_per_user(client, user, month, monkeypatch):
    with database_proxy.atomic():
        record(user)
    login(client)
    database = database_proxy.obj
    original = database.execute_sql
    queries = []

    def execute(sql, *args, **kwargs):
        if sql.lstrip().upper().startswith('SELECT'):
            queries.append(sql)
        return original(sql, *args, **kwargs)

    monkeypatch.setattr(database, 'execute_sql', execute)
    client.get('/activities/ranking')
    initial_count = len(queries)
    with database_proxy.atomic():
        for index in range(15):
            owner = User.create(username=f'query_{index}', display_name='参加者', password_hash='unused')
            record(owner)
    queries.clear()
    response = client.get('/activities/ranking')
    assert len(rows(response)) == 16
    assert len(queries) == initial_count
