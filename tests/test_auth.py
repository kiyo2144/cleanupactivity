from pathlib import Path

from werkzeug.security import check_password_hash

from hiromachi.database import database_proxy
from hiromachi.models import User

from .conftest import login


def test_register_hashes_password_and_redirects(client):
    response = client.post(
        "/register",
        data={
            "username": "New_User",
            "display_name": "新しい利用者",
            "password": "long-password",
            "password_confirm": "long-password",
        },
    )

    assert response.status_code == 303
    assert response.headers["Location"].endswith("/login")
    with database_proxy.connection_context():
        created = User.get(User.username == "new_user")
        assert created.password_hash != "long-password"
        assert check_password_hash(created.password_hash, "long-password")


def test_registration_rejects_case_insensitive_duplicate(client, user):
    response = client.post(
        "/register",
        data={
            "username": "SATO_1",
            "display_name": "別の佐藤",
            "password": "password123",
            "password_confirm": "password123",
        },
    )

    assert response.status_code == 200
    assert "このユーザー名は使用できません" in response.text


def test_login_creates_server_side_session_and_logout_clears_auth(client, app, user):
    response = login(client)

    assert response.status_code == 303
    assert response.headers["Location"].endswith("/activities")
    cookie = response.headers["Set-Cookie"]
    assert "_user_id" not in cookie
    assert any(Path(app.config["SESSION_DIR"]).iterdir())
    assert client.get("/activities").status_code == 200

    response = client.post("/logout")
    assert response.status_code == 303
    assert client.get("/activities").status_code == 302


def test_login_uses_generic_error(client, user):
    response = login(client, password="wrong-password")

    assert response.status_code == 200
    assert "ユーザー名またはパスワードが正しくありません" in response.text
