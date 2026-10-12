"""Activity list, creation, and detail routes."""

from math import ceil
from pathlib import Path

from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from peewee import prefetch

from ..database import database_proxy
from ..models import Activity, ActivityPhoto, ActivityWasteType, User, WasteType
from . import blueprint
from .forms import ActivityForm
from .images import PhotoValidationError, process_photo, store_photo

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
        processed_photo = None
        if len(selected) != len(set(form.waste_types.data)):
            form.waste_types.errors.append("選択されたゴミの種類が正しくありません。")
        if form.photo.data and form.photo.data.filename:
            try:
                processed_photo = process_photo(
                    form.photo.data,
                    max_bytes=current_app.config["PHOTO_MAX_BYTES"],
                    max_dimension=current_app.config["PHOTO_MAX_DIMENSION"],
                )
            except PhotoValidationError as error:
                form.photo.errors.append(str(error))

        if not form.waste_types.errors and not form.photo.errors:
            comment = form.comment.data.strip() if form.comment.data else None
            stored_path = None
            try:
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
                            {
                                "activity": activity.id,
                                "waste_type": waste_type.id,
                            }
                            for waste_type in selected
                        ]
                    ).execute()
                    if processed_photo is not None:
                        storage_name, stored_path = store_photo(
                            processed_photo,
                            Path(current_app.config["UPLOAD_DIR"]),
                        )
                        ActivityPhoto.create(
                            activity=activity,
                            storage_name=storage_name,
                            mime_type=processed_photo.mime_type,
                            width=processed_photo.width,
                            height=processed_photo.height,
                        )
            except Exception:
                if stored_path is not None:
                    stored_path.unlink(missing_ok=True)
                raise
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
    activity = activities[0]
    photo = ActivityPhoto.get_or_none(ActivityPhoto.activity == activity.id)
    return render_template("activities/detail.html", activity=activity, photo=photo)


@blueprint.get("/activities/<int:activity_id>/photo")
@login_required
def photo(activity_id: int):
    activity_photo = ActivityPhoto.get_or_none(
        ActivityPhoto.activity == activity_id
    )
    if activity_photo is None:
        abort(404)
    return send_from_directory(
        current_app.config["UPLOAD_DIR"],
        activity_photo.storage_name,
        mimetype=activity_photo.mime_type,
        conditional=True,
        max_age=0,
    )
