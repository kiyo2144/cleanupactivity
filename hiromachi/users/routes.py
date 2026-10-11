"""Current user's profile route."""

from flask import render_template
from flask_login import current_user, login_required
from peewee import fn

from ..activities.routes import _activity_page
from ..models import Activity, User
from . import blueprint


@blueprint.get("/me")
@login_required
def me():
    totals = (
        Activity.select(
            fn.COUNT(Activity.id).alias("activity_count"),
            fn.COALESCE(fn.SUM(Activity.duration_minutes), 0).alias("total_minutes"),
            fn.COALESCE(fn.SUM(Activity.bag_count), 0).alias("total_bags"),
        )
        .where(Activity.user == current_user.id)
        .dicts()
        .get()
    )
    query = (
        Activity.select(Activity, User)
        .join(User)
        .where(Activity.user == current_user.id)
        .order_by(Activity.created_at.desc(), Activity.id.desc())
    )
    activities, page, total_pages = _activity_page(query)
    return render_template(
        "users/me.html",
        totals=totals,
        activities=activities,
        page=page,
        total_pages=total_pages,
    )
