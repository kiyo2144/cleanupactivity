"""Current user's profile route."""

from flask import render_template
from flask_login import current_user, login_required
from peewee import fn

from ..activities.routes import _activity_page
from ..activities.forms import today_in_japan
from ..models import Activity, User
from . import blueprint


@blueprint.get("/me")
@login_required
def me():
    month_start = today_in_japan().replace(day=1)
    next_month = month_start.replace(
        year=month_start.year + (month_start.month == 12),
        month=month_start.month % 12 + 1,
    )
    totals_query = (
        Activity.select(
            fn.COUNT(Activity.id).alias("activity_count"),
            fn.COALESCE(fn.SUM(Activity.duration_minutes), 0).alias("total_minutes"),
            fn.COALESCE(fn.SUM(Activity.bag_count), 0).alias("total_bags"),
        )
        .where(Activity.user == current_user.id)
        .dicts()
    )
    totals = totals_query.get()
    monthly_totals = totals_query.where(
        Activity.activity_date >= month_start,
        Activity.activity_date < next_month,
    ).get()
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
        monthly_totals=monthly_totals,
        month_label=f"{month_start.year}年{month_start.month}月",
        activities=activities,
        page=page,
        total_pages=total_pages,
    )
