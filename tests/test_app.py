import pytest

from hiromachi import create_app


def test_root_redirects_anonymous_user_to_login(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


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
