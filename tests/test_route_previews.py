import html
import json
import re
from datetime import date
from unittest.mock import patch

import pytest

from hiromachi.database import database_proxy
from hiromachi.models import Activity, ActivityRoute, User

from .conftest import login


def _activity(user, points=None):
    activity = Activity.create(
        user=user, activity_date=date(2026, 10, 1), location="公園 <入口>",
        duration_minutes=30, bag_count=1,
    )
    if points:
        ActivityRoute.create(
            activity=activity, points_json=json.dumps(points), point_count=len(points)
        )
    return activity


def _points(response):
    return [json.loads(html.unescape(value)) for value in re.findall(
        r"data-route-preview data-route-points='([^']*)'", response.text
    )]


@pytest.mark.parametrize("url", ["/activities", "/me"])
def test_previews_mix_single_route_and_no_route(client, user, url):
    single = [[35.123, 139.123]]
    route = [[35.2, 139.2], [35.3, 139.3]]
    with database_proxy.atomic():
        _activity(user)
        first = _activity(user, single)
        second = _activity(user, route)
    login(client)
    response = client.get(url)
    assert response.status_code == 200
    assert _points(response) == [route, single]
    assert 'aria-label="公園 &lt;入口&gt;の清掃地点・ルートを詳しく見る"' in response.text
    assert f'href="/activities/{first.id}"' in response.text
    assert f'href="/activities/{second.id}"' in response.text
    assert response.text.count("activity-route-previews.js") == 1
    assert response.text.count("vendor/leaflet/leaflet.js") == 1
    assert response.text.count("詳しく見る</span>") == 3


@pytest.mark.parametrize("url", ["/activities", "/me"])
def test_previews_only_contain_current_page_routes(client, user, url):
    hidden = [[34.111, 138.111]]
    visible = [[35.222, 139.222]]
    with database_proxy.atomic():
        _activity(user, hidden)
        for _ in range(10):
            _activity(user, visible)
    login(client)
    assert _points(client.get(url)) == [visible] * 10
    assert _points(client.get(f"{url}?page=2")) == [hidden]


def test_my_page_previews_never_include_other_users(client, user):
    with database_proxy.atomic():
        other = User.create(username="other", display_name="別の人", password_hash="unused")
        _activity(other, [[36.333, 140.333]])
        _activity(user, [[35.222, 139.222]])
    login(client)
    assert _points(client.get("/me")) == [[[35.222, 139.222]]]
    assert len(_points(client.get("/activities"))) == 2


@pytest.mark.parametrize("url", ["/activities", "/me"])
def test_no_routes_does_not_load_map_assets(client, user, url):
    with database_proxy.atomic():
        _activity(user)
    login(client)
    response = client.get(url)
    assert _points(response) == []
    assert "activity-route-previews.js" not in response.text
    assert "vendor/leaflet/leaflet" not in response.text


@pytest.mark.parametrize("url", ["/activities", "/me"])
def test_route_previews_use_one_query_for_entire_page(client, app, user, url):
    with database_proxy.atomic():
        _activity(user, [[35.222, 139.222]])
    login(client)
    database = app.extensions["peewee_database"]
    with patch.object(database, "execute_sql", wraps=database.execute_sql) as sql:
        assert client.get(url).status_code == 200
        initial_count = sql.call_count
    with database_proxy.atomic():
        for _ in range(9):
            _activity(user, [[35.333, 139.333]])
    with patch.object(database, "execute_sql", wraps=database.execute_sql) as sql:
        assert client.get(url).status_code == 200
        assert sql.call_count == initial_count
        route_queries = [call.args[0] for call in sql.call_args_list
                         if 'FROM "activity_routes"' in call.args[0]]
        assert len(route_queries) == 1


@pytest.mark.parametrize("url", ["/activities", "/me"])
def test_route_previews_remain_login_required(client, url):
    response = client.get(url)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
