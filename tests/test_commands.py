from datetime import date

from werkzeug.security import generate_password_hash

from hiromachi.database import database_proxy
from hiromachi.models import Activity, ActivityPhoto, ActivityRoute, Reaction, User, WasteType


def _install_legacy_route_table() -> tuple[int, tuple]:
    owner = User.create(
        username="migration_owner",
        display_name="移行前の投稿者",
        password_hash=generate_password_hash("password123"),
    )
    actor = User.create(
        username="migration_actor",
        display_name="移行前の応援者",
        password_hash=generate_password_hash("password123"),
    )
    activity = Activity.create(
        user=owner,
        activity_date=date.today(),
        location="移行前の活動",
        duration_minutes=30,
        bag_count=1,
    )
    route = ActivityRoute.create(
        activity=activity,
        points_json="[[35.123,139.123],[35.456,139.456]]",
        point_count=2,
    )
    ActivityPhoto.create(
        activity=activity,
        storage_name="migration-test.jpg",
        mime_type="image/jpeg",
        width=100,
        height=100,
    )
    Reaction.create(user=actor, activity=activity)
    original_route = (
        route.id,
        route.activity_id,
        route.points_json,
        route.point_count,
        route.created_at,
        route.updated_at,
    )

    with database_proxy.atomic():
        database_proxy.execute_sql(
            "ALTER TABLE activity_routes RENAME TO activity_routes_new_schema"
        )
        database_proxy.execute_sql(
            """
            CREATE TABLE activity_routes (
                id INTEGER NOT NULL PRIMARY KEY,
                activity_id INTEGER NOT NULL,
                points_json TEXT NOT NULL
                    CHECK (length(points_json) BETWEEN 5 AND 8192),
                point_count INTEGER NOT NULL
                    CHECK (point_count BETWEEN 2 AND 100),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY (activity_id) REFERENCES activities(id)
                    ON DELETE CASCADE
            )
            """
        )
        database_proxy.execute_sql(
            "INSERT INTO activity_routes SELECT * FROM activity_routes_new_schema"
        )
        database_proxy.execute_sql("DROP TABLE activity_routes_new_schema")
        database_proxy.execute_sql(
            "CREATE UNIQUE INDEX activityroute_activity_id "
            "ON activity_routes (activity_id)"
        )

    return activity.id, original_route


def test_init_db_is_repeatable(runner):
    first = runner.invoke(args=["init-db"])
    second = runner.invoke(args=["init-db"])

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "清掃ルートのDB制約は更新不要です" in second.output
    with database_proxy.connection_context():
        assert WasteType.select().count() == 4
        assert set(database_proxy.get_tables()) == {
            "activities",
            "activity_photos",
            "activity_routes",
            "activity_waste_types",
            "reactions",
            "users",
            "waste_types",
        }


def test_init_db_migrates_legacy_route_constraint_without_data_loss(runner):
    with database_proxy.connection_context():
        activity_id, original_route = _install_legacy_route_table()

    result = runner.invoke(args=["init-db"])

    assert result.exit_code == 0
    assert "清掃ルートのDB制約を更新しました（既存1件を維持）" in result.output
    with database_proxy.connection_context():
        migrated = ActivityRoute.get()
        migrated_route = (
            migrated.id,
            migrated.activity_id,
            migrated.points_json,
            migrated.point_count,
            migrated.created_at,
            migrated.updated_at,
        )
        assert migrated_route == original_route
        assert Activity.get_by_id(activity_id).location == "移行前の活動"
        assert ActivityPhoto.select().count() == 1
        assert Reaction.select().count() == 1
        assert database_proxy.execute_sql("PRAGMA foreign_key_check").fetchall() == []
        schema = database_proxy.execute_sql(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name = 'activity_routes'"
        ).fetchone()[0]
        assert "point_count BETWEEN 1 AND 100" in schema

        second_activity = Activity.create(
            user=User.get_by_id(Activity.get_by_id(activity_id).user_id),
            activity_date=date.today(),
            location="1地点の活動",
            duration_minutes=10,
            bag_count=0,
        )
        ActivityRoute.create(
            activity=second_activity,
            points_json="[[35.123,139.123]]",
            point_count=1,
        )
        second_activity.delete_instance()
        assert (
            ActivityRoute.select()
            .where(ActivityRoute.activity == second_activity.id)
            .count()
            == 0
        )

    repeated = runner.invoke(args=["init-db"])
    assert repeated.exit_code == 0
    assert "清掃ルートのDB制約は更新不要です" in repeated.output


def test_route_constraint_migration_rolls_back_on_failure(runner, app, monkeypatch):
    with database_proxy.connection_context():
        _activity_id, original_route = _install_legacy_route_table()

    database = app.extensions["peewee_database"]
    original_execute_sql = database.execute_sql

    def fail_after_table_swap(sql, *args, **kwargs):
        if sql.strip().startswith(
            'CREATE UNIQUE INDEX "activityroute_activity_id"'
        ):
            raise RuntimeError("simulated migration failure")
        return original_execute_sql(sql, *args, **kwargs)

    monkeypatch.setattr(database, "execute_sql", fail_after_table_swap)
    result = runner.invoke(args=["init-db"])
    monkeypatch.undo()

    assert result.exit_code == 1
    assert isinstance(result.exception, RuntimeError)
    assert "simulated migration failure" in str(result.exception)
    with database_proxy.connection_context():
        route = ActivityRoute.get()
        assert (
            route.id,
            route.activity_id,
            route.points_json,
            route.point_count,
            route.created_at,
            route.updated_at,
        ) == original_route
        schema = database_proxy.execute_sql(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name = 'activity_routes'"
        ).fetchone()[0]
        assert "point_count BETWEEN 2 AND 100" in schema
        assert "activity_routes_point_count_upgrade" not in database_proxy.get_tables()
