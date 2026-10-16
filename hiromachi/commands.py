"""Application management commands."""

import re

import click
from flask import Flask

from .database import database_proxy
from .models import INITIAL_MODELS, INITIAL_WASTE_TYPES, WasteType


def _normalized_schema(sql: str) -> str:
    return re.sub(r'[\s"`\[\]]+', "", sql).upper()


def _upgrade_activity_route_point_count() -> tuple[bool, int]:
    row = database_proxy.execute_sql(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("activity_routes",),
    ).fetchone()
    if row is None or not row[0]:
        raise RuntimeError("activity_routesテーブルの定義を確認できません。")

    schema = _normalized_schema(row[0])
    old_constraint = "CHECK(POINT_COUNTBETWEEN2AND100)"
    new_constraint = "CHECK(POINT_COUNTBETWEEN1AND100)"
    route_count = database_proxy.execute_sql(
        "SELECT COUNT(*) FROM activity_routes"
    ).fetchone()[0]

    if new_constraint in schema:
        return False, route_count
    if old_constraint not in schema:
        raise RuntimeError(
            "activity_routes.point_countのDB制約が想定と異なるため、更新を中止しました。"
        )

    temporary_table = "activity_routes_point_count_upgrade"
    temporary_exists = database_proxy.execute_sql(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (temporary_table,),
    ).fetchone()
    if temporary_exists is not None:
        raise RuntimeError("清掃ルートのDB更新用一時テーブルが既に存在します。")

    with database_proxy.atomic():
        database_proxy.execute_sql(
            f'''
            CREATE TABLE "{temporary_table}" (
                "id" INTEGER NOT NULL PRIMARY KEY,
                "activity_id" INTEGER NOT NULL,
                "points_json" TEXT NOT NULL
                    CHECK (length(points_json) BETWEEN 5 AND 8192),
                "point_count" INTEGER NOT NULL
                    CHECK (point_count BETWEEN 1 AND 100),
                "created_at" DATETIME NOT NULL,
                "updated_at" DATETIME NOT NULL,
                FOREIGN KEY ("activity_id") REFERENCES "activities" ("id")
                    ON DELETE CASCADE
            )
            '''
        )
        database_proxy.execute_sql(
            f'''
            INSERT INTO "{temporary_table}"
                (id, activity_id, points_json, point_count, created_at, updated_at)
            SELECT id, activity_id, points_json, point_count, created_at, updated_at
            FROM activity_routes
            '''
        )
        copied_count = database_proxy.execute_sql(
            f'SELECT COUNT(*) FROM "{temporary_table}"'
        ).fetchone()[0]
        if copied_count != route_count:
            raise RuntimeError("清掃ルートのコピー件数が一致しないため、更新を中止しました。")

        database_proxy.execute_sql("DROP TABLE activity_routes")
        database_proxy.execute_sql(
            f'ALTER TABLE "{temporary_table}" RENAME TO "activity_routes"'
        )
        database_proxy.execute_sql(
            'CREATE UNIQUE INDEX "activityroute_activity_id" '
            'ON "activity_routes" ("activity_id")'
        )
        foreign_key_errors = database_proxy.execute_sql(
            "PRAGMA foreign_key_check"
        ).fetchall()
        if foreign_key_errors:
            raise RuntimeError(
                "外部キーの整合性を確認できないため、DB制約の更新を中止しました。"
            )

    return True, route_count


def init_database() -> tuple[bool, int]:
    with database_proxy.connection_context():
        database_proxy.create_tables(INITIAL_MODELS, safe=True)
        route_constraint_updated, route_count = _upgrade_activity_route_point_count()
        for waste_type in INITIAL_WASTE_TYPES:
            WasteType.insert(waste_type).on_conflict_ignore().execute()
    return route_constraint_updated, route_count


def register_commands(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Create initial tables and seed waste types without deleting data."""

        route_constraint_updated, route_count = init_database()
        if route_constraint_updated:
            click.echo(
                f"清掃ルートのDB制約を更新しました（既存{route_count}件を維持）。"
            )
        else:
            click.echo("清掃ルートのDB制約は更新不要です。")
        click.echo("データベースを初期化しました。")
