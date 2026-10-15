import pytest

from hiromachi import create_app


def test_root_redirects_anonymous_user_to_login(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_pages_use_versioned_main_stylesheet(client):
    response = client.get("/login")

    assert response.status_code == 200
    assert '/static/css/style.css?v=20261016-2' in response.text


def test_branding_and_ui_assets_are_served(client):
    login_page = client.get("/login")
    full_logo = client.get("/static/images/brand/hiromachi-logo.png?v=20261016-2")
    brand_mark = client.get("/static/images/brand/hiromachi-mark.png?v=20261016-2")
    icon_sprite = client.get("/static/images/icons/ui.svg?v=20261016-2")
    stylesheet = client.get("/static/css/style.css?v=20261016-2")

    assert login_page.status_code == 200
    assert "/static/images/brand/hiromachi-logo.png?v=20261016-2" in login_page.text
    assert "/static/images/brand/hiromachi-mark.png?v=20261016-2" in login_page.text
    assert full_logo.status_code == 200
    assert full_logo.mimetype == "image/png"
    assert brand_mark.status_code == 200
    assert brand_mark.mimetype == "image/png"
    assert icon_sprite.status_code == 200
    assert icon_sprite.mimetype == "image/svg+xml"
    assert 'id="icon-sparkles"' in icon_sprite.text
    assert stylesheet.status_code == 200
    assert 'input[type="date"]' in stylesheet.text
    assert "min-inline-size: 0" in stylesheet.text
    assert "@media (prefers-reduced-motion: reduce)" in stylesheet.text


def test_success_feedback_is_only_rendered_for_one_redirect(client, user):
    from .conftest import login

    response = login(client)
    first_page = client.get(response.headers["Location"])
    refreshed_page = client.get(response.headers["Location"])

    assert 'data-feedback="success-celebrate"' in first_page.text
    assert 'class="flash flash-success-celebrate"' in first_page.text
    assert 'data-feedback="success-celebrate"' not in refreshed_page.text


def test_production_requires_secret_key(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(
            {
                "DATABASE_PATH": str(tmp_path / "db.sqlite3"),
                "SESSION_DIR": str(tmp_path / "sessions"),
            }
        )
