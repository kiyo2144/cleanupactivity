from hiromachi.database import database_proxy
from hiromachi.models import WasteType


def test_init_db_is_repeatable(runner):
    first = runner.invoke(args=["init-db"])
    second = runner.invoke(args=["init-db"])

    assert first.exit_code == 0
    assert second.exit_code == 0
    with database_proxy.connection_context():
        assert WasteType.select().count() == 4
        assert set(database_proxy.get_tables()) == {
            "activities",
            "activity_photos",
            "activity_waste_types",
            "users",
            "waste_types",
        }
