from pathlib import Path

from werkzeug.security import check_password_hash

from hiromachi.database import database_proxy
from hiromachi.models import User

from .conftest import login


def test_auth_forms_use_user_facing_terms_and_required_marks(client):
    register_page = client.get("/register")
    login_page = client.get("/login")

    assert register_page.status_code == 200
    assert "ログインIDはログインに、お名前は活動の投稿者名として表示されます。" in register_page.text
    assert "は必須項目です。" in register_page.text
    assert register_page.text.count('class="required-mark"') == 5
    assert "ログインID" in register_page.text
    assert "お名前" in register_page.text
    assert register_page.text.index('id="display_name"') < register_page.text.index(
        'id="username"'
    )
    assert login_page.status_code == 200
    assert "ログインID" in login_page.text
    assert 'class="button primary auth-submit"' in login_page.text
    assert 'class="button primary auth-submit"' in register_page.text


def test_auth_submit_uses_brand_color_without_changing_other_buttons(client):
    stylesheet = client.get("/static/css/style.css?v=20261017-4")

    assert stylesheet.status_code == 200
    assert "input.button.primary.auth-submit" in stylesheet.text
    assert "background: var(--primary)" in stylesheet.text
    assert "color: #fff" in stylesheet.text


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
    assert "このログインIDは使用できません" in response.text


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
    assert "ログインIDまたはパスワードが正しくありません" in response.text
