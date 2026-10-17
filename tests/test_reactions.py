from __future__ import annotations

from datetime import date

import pytest
from peewee import IntegrityError
from werkzeug.security import generate_password_hash

from hiromachi.database import database_proxy
from hiromachi.models import Activity, Reaction, User

from .conftest import login


def _create_user(username: str, display_name: str) -> User:
    with database_proxy.connection_context():
        return User.create(
            username=username,
            display_name=display_name,
            password_hash=generate_password_hash("password123"),
        )


def _create_activity(owner: User, location: str = "フットパス北側") -> Activity:
    with database_proxy.connection_context():
        return Activity.create(
            user=owner,
            activity_date=date.today(),
            location=location,
            duration_minutes=30,
            bag_count=1,
        )


def test_thank_requires_login_and_post(client, user):
    activity = _create_activity(user)

    assert client.post(f"/activities/{activity.id}/thanks").status_code == 302
    assert client.get(f"/activities/{activity.id}/thanks").status_code == 405
    with database_proxy.connection_context():
        assert Reaction.select().count() == 0


def test_thank_can_be_sent_and_cancelled(client, user):
    activity = _create_activity(user)
    actor = _create_user("actor_user", "応援する人")
    login(client, username=actor.username)

    before = client.get(f"/activities/{activity.id}")
    sent = client.post(f"/activities/{activity.id}/thanks")

    assert "ありがとう 0件" in before.text
    assert "ありがとうを送る" in before.text
    assert sent.status_code == 303
    assert sent.headers["Location"].endswith(f"/activities/{activity.id}")
    after_send = client.get(sent.headers["Location"])
    assert "ありがとうを送りました" in after_send.text
    assert 'data-feedback="success-thanks"' in after_send.text
    assert 'class="flash flash-success-thanks"' in after_send.text
    assert "ありがとう 1件" in after_send.text
    assert "ありがとうを取り消す" in after_send.text
    with database_proxy.connection_context():
        assert Reaction.select().count() == 1

    cancelled = client.post(f"/activities/{activity.id}/thanks")

    assert cancelled.status_code == 303
    after_cancel = client.get(cancelled.headers["Location"])
    assert "ありがとうを取り消しました" in after_cancel.text
    assert "ありがとう 0件" in after_cancel.text
    assert "ありがとうを送る" in after_cancel.text
    with database_proxy.connection_context():
        assert Reaction.select().count() == 0


def test_thank_json_updates_in_place_without_flash(client, user):
    activity = _create_activity(user)
    actor = _create_user("json_actor", "画面内で応援する人")
    login(client, username=actor.username)
    client.get("/activities")  # Consume the login success flash.

    detail = client.get(f"/activities/{activity.id}")
    sent = client.post(
        f"/activities/{activity.id}/thanks",
        headers={"Accept": "application/json"},
    )

    assert 'data-thank-form' in detail.text
    assert 'aria-pressed="false"' in detail.text
    assert "/static/js/activity-thanks.js?v=20261017-4" in detail.text
    assert sent.status_code == 200
    assert sent.json == {
        "has_thanked": True,
        "message": "ありがとうを送りました。",
        "thank_count": 1,
    }

    refreshed = client.get(f"/activities/{activity.id}")
    assert 'aria-pressed="true"' in refreshed.text
    assert 'class="flash flash-success-thanks"' not in refreshed.text

    cancelled = client.post(
        f"/activities/{activity.id}/thanks",
        headers={"Accept": "application/json"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json == {
        "has_thanked": False,
        "message": "ありがとうを取り消しました。",
        "thank_count": 0,
    }
    with database_proxy.connection_context():
        assert Reaction.select().count() == 0


def test_thank_in_place_script_is_served(client):
    script = client.get("/static/js/activity-thanks.js?v=20261017-4")

    assert script.status_code == 200
    assert script.mimetype == "text/javascript"
    assert 'headers: { Accept: "application/json" }' in script.text
    assert 'button.disabled = true' in script.text
    assert 'window.location.assign(response.url)' in script.text


def test_detail_shows_count_without_actor_names(client, user):
    activity = _create_activity(user)
    first_actor = _create_user("first_actor", "一人目の応援者")
    second_actor = _create_user("second_actor", "二人目の応援者")
    with database_proxy.atomic():
        Reaction.create(user=first_actor, activity=activity)
        Reaction.create(user=second_actor, activity=activity)
    login(client, username=first_actor.username)

    response = client.get(f"/activities/{activity.id}")

    assert response.status_code == 200
    assert "ありがとう 2件" in response.text
    assert "一人目の応援者" not in response.text
    assert "二人目の応援者" not in response.text


def test_owner_can_only_see_count(client, user):
    activity = _create_activity(user)
    login(client)

    detail = client.get(f"/activities/{activity.id}")
    response = client.post(f"/activities/{activity.id}/thanks")

    assert "ありがとう 0件" in detail.text
    assert "ありがとうを送る" not in detail.text
    assert "ありがとうを取り消す" not in detail.text
    assert response.status_code == 400
    with database_proxy.connection_context():
        assert Reaction.select().count() == 0


def test_thank_rejects_missing_activity(client, user):
    actor = _create_user("actor_user", "応援する人")
    login(client, username=actor.username)

    response = client.post("/activities/99999/thanks")

    assert response.status_code == 404
    with database_proxy.connection_context():
        assert Reaction.select().count() == 0


def test_thank_rejects_post_without_csrf(client, app, user):
    activity = _create_activity(user)
    actor = _create_user("actor_user", "応援する人")
    login(client, username=actor.username)
    app.config["WTF_CSRF_ENABLED"] = True

    response = client.post(f"/activities/{activity.id}/thanks")

    assert response.status_code == 400
    with database_proxy.connection_context():
        assert Reaction.select().count() == 0


def test_reaction_composite_key_prevents_duplicates(app, user):
    activity = _create_activity(user)
    actor = _create_user("actor_user", "応援する人")
    with database_proxy.connection_context():
        Reaction.create(user=actor, activity=activity)

        with pytest.raises(IntegrityError):
            Reaction.create(user=actor, activity=activity)

        assert Reaction.select().count() == 1


def test_activity_delete_cascades_only_related_reactions(client, user):
    deleted_activity = _create_activity(user, "削除する場所")
    kept_activity = _create_activity(user, "残す場所")
    actor = _create_user("actor_user", "応援する人")
    with database_proxy.atomic():
        Reaction.create(user=actor, activity=deleted_activity)
        Reaction.create(user=actor, activity=kept_activity)
    login(client)

    response = client.post(f"/activities/{deleted_activity.id}/delete")

    assert response.status_code == 303
    with database_proxy.connection_context():
        assert Reaction.select().count() == 1
        assert Reaction.get().activity_id == kept_activity.id
