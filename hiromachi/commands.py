"""Application management commands."""

import click
from flask import Flask

from .database import database_proxy
from .models import INITIAL_MODELS, INITIAL_WASTE_TYPES, WasteType


def init_database() -> None:
    with database_proxy.connection_context():
        database_proxy.create_tables(INITIAL_MODELS, safe=True)
        for waste_type in INITIAL_WASTE_TYPES:
            WasteType.insert(waste_type).on_conflict_ignore().execute()


def register_commands(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Create initial tables and seed waste types without deleting data."""

        init_database()
        click.echo("データベースを初期化しました。")
