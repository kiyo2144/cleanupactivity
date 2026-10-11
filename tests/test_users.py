from datetime import date

from hiromachi.database import database_proxy
from hiromachi.models import Activity

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
