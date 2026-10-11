"""Activity list, creation, and detail routes."""

from math import ceil

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from peewee import prefetch

from ..database import database_proxy
from ..models import Activity, ActivityWasteType, User, WasteType
from . import blueprint
from .forms import ActivityForm

PAGE_SIZE = 10


def _page_number(total_items: int) -> tuple[int, int]:
    raw_page = request.args.get("page", "1")
    try:
        page = int(raw_page)
    except (TypeError, ValueError):
        abort(404)
    total_pages = max(1, ceil(total_items / PAGE_SIZE))
    if page < 1 or page > total_pages:
        abort(404)
    return page, total_pages


def _activity_page(query):
    total_items = query.count()
    page, total_pages = _page_number(total_items)
    page_query = query.paginate(page, PAGE_SIZE)
    activities = list(prefetch(page_query, ActivityWasteType, WasteType))
    return activities, page, total_pages


@blueprint.get("/activities")
@login_required
def index():
    query = (
        Activity.select(Activity, User)
        .join(User)
        .order_by(Activity.created_at.desc(), Activity.id.desc())
    )
    activities, page, total_pages = _activity_page(query)
    return render_template(
        "activities/index.html",
        activities=activities,
        page=page,
        total_pages=total_pages,
    )


@blueprint.route("/activities/new", methods=["GET", "POST"])
@login_required
def create():
    form = ActivityForm()
    waste_types = list(WasteType.select().order_by(WasteType.sort_order))
    form.waste_types.choices = [(item.id, item.name) for item in waste_types]

    if form.validate_on_submit():
        selected = [item for item in waste_types if item.id in form.waste_types.data]
        if len(selected) != len(set(form.waste_types.data)):
            form.waste_types.errors.append("選択されたゴミの種類が正しくありません。")
        else:
            comment = form.comment.data.strip() if form.comment.data else None
            with database_proxy.atomic():
                activity = Activity.create(
                    user=current_user.id,
                    activity_date=form.activity_date.data,
                    location=form.location.data.strip(),
                    duration_minutes=form.duration_minutes.data,
                    bag_count=form.bag_count.data,
                    comment=comment or None,
                )
                ActivityWasteType.insert_many(
                    [
                        {"activity": activity.id, "waste_type": waste_type.id}
                        for waste_type in selected
                    ]
                ).execute()
            flash("活動を記録しました。", "success")
            return redirect(
                url_for("activities.detail", activity_id=activity.id), code=303
            )

    return render_template("activities/create.html", form=form)


@blueprint.get("/activities/<int:activity_id>")
@login_required
def detail(activity_id: int):
    query = (
        Activity.select(Activity, User)
        .join(User)
        .where(Activity.id == activity_id)
    )
    activities = list(prefetch(query, ActivityWasteType, WasteType))
    if not activities:
        abort(404)
    return render_template("activities/detail.html", activity=activities[0])
