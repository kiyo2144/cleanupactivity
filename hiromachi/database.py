"""Peewee database lifecycle integration for Flask."""

from __future__ import annotations

from pathlib import Path

from flask import Flask
from peewee import DatabaseProxy, SqliteDatabase

database_proxy = DatabaseProxy()


def init_app(app: Flask) -> None:
    database_path = Path(app.config["DATABASE_PATH"])
    database_path.parent.mkdir(parents=True, exist_ok=True)

    database = SqliteDatabase(
        database_path,
        pragmas={"foreign_keys": 1},
    )
    database_proxy.initialize(database)
    app.extensions["peewee_database"] = database

    @app.before_request
    def connect_database() -> None:
        if database.is_closed():
            database.connect(reuse_if_open=True)

    @app.teardown_request
    def close_database(_exception: BaseException | None) -> None:
        if not database.is_closed():
            database.close()
