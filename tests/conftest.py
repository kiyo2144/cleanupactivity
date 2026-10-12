from __future__ import annotations

import pytest
from werkzeug.security import generate_password_hash

from hiromachi import create_app
from hiromachi.commands import init_database
from hiromachi.database import database_proxy
from hiromachi.models import INITIAL_MODELS, User


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE_PATH": str(tmp_path / "test.sqlite3"),
            "SESSION_DIR": str(tmp_path / "sessions"),
            "UPLOAD_DIR": str(tmp_path / "uploads"),
            "WTF_CSRF_ENABLED": False,
        }
    )
    init_database()

    yield application

    database = application.extensions["peewee_database"]
    with database.connection_context():
        database.drop_tables(reversed(INITIAL_MODELS), safe=True)
    if not database.is_closed():
        database.close()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


@pytest.fixture()
def user(app):
    with app.app_context(), database_proxy.connection_context():
        return User.create(
            username="sato_1",
            display_name="佐藤",
            password_hash=generate_password_hash("password123"),
        )


def login(client, username="sato_1", password="password123"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )
