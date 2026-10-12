"""Peewee models for the initial Hiromachi schema."""

from __future__ import annotations

from datetime import UTC, datetime

from flask_login import UserMixin
from peewee import (
    AutoField,
    CharField,
    Check,
    CompositeKey,
    DateField,
    DateTimeField,
    ForeignKeyField,
    IntegerField,
    Model,
    TextField,
)

from .database import database_proxy


def utc_now() -> datetime:
    """Return naive UTC, the database-wide timestamp representation."""

    return datetime.now(UTC).replace(tzinfo=None)


class BaseModel(Model):
    class Meta:
        database = database_proxy


class User(UserMixin, BaseModel):
    id = AutoField()
    username = CharField(
        max_length=30,
        unique=True,
        collation="NOCASE",
        constraints=[
            Check("length(username) BETWEEN 3 AND 30"),
            Check("username NOT GLOB '*[^A-Za-z0-9_]*'"),
        ],
    )
    display_name = CharField(
        max_length=50,
        constraints=[Check("length(trim(display_name)) BETWEEN 1 AND 50")],
    )
    password_hash = CharField(
        max_length=255,
        constraints=[Check("length(password_hash) > 0")],
    )
    created_at = DateTimeField(default=utc_now)

    class Meta:
        table_name = "users"


class Activity(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="activities", on_delete="RESTRICT")
    activity_date = DateField()
    location = CharField(
        max_length=100,
        constraints=[Check("length(trim(location)) BETWEEN 1 AND 100")],
    )
    duration_minutes = IntegerField(
        constraints=[Check("duration_minutes BETWEEN 1 AND 1440")]
    )
    bag_count = IntegerField(constraints=[Check("bag_count BETWEEN 0 AND 99")])
    comment = TextField(
        null=True,
        constraints=[Check("comment IS NULL OR length(comment) <= 500")],
    )
    created_at = DateTimeField(default=utc_now)
    updated_at = DateTimeField(default=utc_now)

    class Meta:
        table_name = "activities"
        indexes = (
            (("created_at", "id"), False),
            (("user", "created_at", "id"), False),
        )


class WasteType(BaseModel):
    id = AutoField()
    code = CharField(
        max_length=30,
        unique=True,
        constraints=[Check("length(code) BETWEEN 1 AND 30")],
    )
    name = CharField(
        max_length=50,
        unique=True,
        constraints=[Check("length(trim(name)) BETWEEN 1 AND 50")],
    )
    sort_order = IntegerField(unique=True, constraints=[Check("sort_order > 0")])

    class Meta:
        table_name = "waste_types"


class ActivityWasteType(BaseModel):
    activity = ForeignKeyField(
        Activity,
        backref="waste_type_links",
        on_delete="CASCADE",
    )
    waste_type = ForeignKeyField(
        WasteType,
        backref="activity_links",
        on_delete="RESTRICT",
        index=True,
    )

    class Meta:
        table_name = "activity_waste_types"
        primary_key = CompositeKey("activity", "waste_type")


class ActivityPhoto(BaseModel):
    id = AutoField()
    activity = ForeignKeyField(
        Activity,
        backref="photo_records",
        on_delete="CASCADE",
        unique=True,
    )
    storage_name = CharField(max_length=64, unique=True)
    mime_type = CharField(
        max_length=20,
        constraints=[
            Check("mime_type IN ('image/jpeg', 'image/png', 'image/webp')")
        ],
    )
    width = IntegerField(constraints=[Check("width > 0")])
    height = IntegerField(constraints=[Check("height > 0")])
    created_at = DateTimeField(default=utc_now)

    class Meta:
        table_name = "activity_photos"


INITIAL_WASTE_TYPES = (
    {"code": "burnable", "name": "燃えるごみ", "sort_order": 1},
    {
        "code": "plastic_bottle",
        "name": "プラスチック・ペットボトル",
        "sort_order": 2,
    },
    {"code": "cans_bottles", "name": "缶・びん", "sort_order": 3},
    {"code": "other", "name": "その他", "sort_order": 4},
)

INITIAL_MODELS = (User, WasteType, Activity, ActivityWasteType, ActivityPhoto)
