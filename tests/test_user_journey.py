from datetime import date
from html.parser import HTMLParser

from hiromachi.database import database_proxy
from hiromachi.models import Activity, WasteType


class _CsrfTokenParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.token: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "input":
            return
        values = dict(attrs)
        if values.get("name") == "csrf_token":
            self.token = values.get("value")


def _csrf_token(response) -> str:
    parser = _CsrfTokenParser()
    parser.feed(response.get_data(as_text=True))
    assert parser.token is not None
    return parser.token


def test_complete_mvp_journey_with_csrf_enabled(app):
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()

    register_page = client.get("/register")
    response = client.post(
        "/register",
        data={
            "csrf_token": _csrf_token(register_page),
            "username": "mvp_user",
            "display_name": "MVP利用者",
            "password": "password123",
            "password_confirm": "password123",
        },
    )
    assert response.status_code == 303
    assert response.headers["Location"].endswith("/login")

    login_page = client.get("/login")
    response = client.post(
        "/login",
        data={
            "csrf_token": _csrf_token(login_page),
            "username": "mvp_user",
            "password": "password123",
        },
    )
    assert response.status_code == 303
    assert response.headers["Location"].endswith("/activities")

    with database_proxy.connection_context():
        waste_type_id = WasteType.get(WasteType.code == "burnable").id

    create_page = client.get("/activities/new")
    response = client.post(
        "/activities/new",
        data={
            "csrf_token": _csrf_token(create_page),
            "activity_date": date.today().isoformat(),
            "location": "フットパス北側",
            "duration_minutes": "30",
            "bag_count": "1",
            "waste_types": [str(waste_type_id)],
            "comment": "MVPの動作確認",
        },
    )
    assert response.status_code == 303
    assert "/activities/" in response.headers["Location"]

    detail = client.get(response.headers["Location"])
    assert detail.status_code == 200
    assert "MVPの動作確認" in detail.text
    assert "燃えるごみ" in detail.text

    activity_id = int(response.headers["Location"].rstrip("/").split("/")[-1])
    edit_page = client.get(f"/activities/{activity_id}/edit")
    response = client.post(
        f"/activities/{activity_id}/edit",
        data={
            "csrf_token": _csrf_token(edit_page),
            "activity_date": date.today().isoformat(),
            "location": "フットパス南側",
            "duration_minutes": "45",
            "bag_count": "2",
            "waste_types": [str(waste_type_id)],
            "comment": "編集後の動作確認",
        },
    )
    assert response.status_code == 303
    assert response.headers["Location"].endswith(f"/activities/{activity_id}")

    activity_list = client.get("/activities")
    my_page = client.get("/me")
    assert activity_list.status_code == 200
    assert "フットパス南側" in activity_list.text
    assert my_page.status_code == 200
    assert "MVP利用者" in my_page.text
    assert "フットパス南側" in my_page.text

    with database_proxy.connection_context():
        assert Activity.select().count() == 1

    response = client.post(
        "/logout",
        data={"csrf_token": _csrf_token(my_page)},
    )
    assert response.status_code == 303
    assert response.headers["Location"].endswith("/login")
    assert client.get("/activities").status_code == 302
