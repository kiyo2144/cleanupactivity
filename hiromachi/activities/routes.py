"""Activity list, creation, and detail routes."""

import json
from math import ceil
from pathlib import Path

from flask import (
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from peewee import fn, prefetch

from ..database import database_proxy
from ..models import (
    Activity,
    ActivityPhoto,
    ActivityRoute,
    ActivityWasteType,
    Reaction,
    User,
    WasteType,
    utc_now,
)
from . import blueprint
from .forms import ActivityDeleteForm, ActivityEditForm, ActivityForm, ThankForm
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


def _activity_route_previews(activities) -> dict[int, list]:
    """Load saved route coordinates only for the activities on this page."""
    activity_ids = [activity.id for activity in activities]
    if not activity_ids:
        return {}
    return {
        route.activity_id: json.loads(route.points_json)
        for route in ActivityRoute.select(
            ActivityRoute.activity, ActivityRoute.points_json
        ).where(ActivityRoute.activity.in_(activity_ids))
    }


def _waste_types_for_form(form):
    waste_types = list(WasteType.select().order_by(WasteType.sort_order))
    form.waste_types.choices = [(item.id, item.name) for item in waste_types]
    return waste_types


def _selected_waste_types(form, waste_types):
    selected = [item for item in waste_types if item.id in form.waste_types.data]
    if len(selected) != len(set(form.waste_types.data)):
        form.waste_types.errors.append("選択されたゴミの種類が正しくありません。")
    return selected


def _processed_photo(form):
    if not form.photo.data or not form.photo.data.filename:
        return None
    try:
        return process_photo(
            form.photo.data,
            max_bytes=current_app.config["PHOTO_MAX_BYTES"],
            max_dimension=current_app.config["PHOTO_MAX_DIMENSION"],
        )
    except PhotoValidationError as error:
        form.photo.errors.append(str(error))
        return None


def _activity_values(form):
    comment = form.comment.data.strip() if form.comment.data else None
    return {
        "activity_date": form.activity_date.data,
        "location": form.location.data.strip(),
        "duration_minutes": form.duration_minutes.data,
        "bag_count": form.bag_count.data,
        "comment": comment or None,
    }


def _route_points(points_json: str | None):
    if not points_json:
        return None
    return json.loads(points_json)


def _save_activity_route(activity: Activity, points_json: str | None) -> None:
    existing_route = ActivityRoute.get_or_none(ActivityRoute.activity == activity.id)
    if not points_json:
        if existing_route is not None:
            existing_route.delete_instance()
        return

    point_count = len(json.loads(points_json))
    if existing_route is None:
        ActivityRoute.create(
            activity=activity,
            points_json=points_json,
            point_count=point_count,
        )
        return

    existing_route.points_json = points_json
    existing_route.point_count = point_count
    existing_route.updated_at = utc_now()
    existing_route.save()


def _remove_replaced_photo(path: Path | None, activity_id: int) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        current_app.logger.exception(
            "Failed to remove replaced activity photo",
            extra={"activity_id": activity_id},
        )


def _remove_deleted_photo(path: Path | None, activity_id: int) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        current_app.logger.exception(
            "Failed to remove deleted activity photo",
            extra={"activity_id": activity_id},
        )


@blueprint.get("/activities")
@login_required
def index():
    totals = (
        Activity.select(
            fn.COUNT(Activity.id).alias("activity_count"),
            fn.COALESCE(fn.SUM(Activity.duration_minutes), 0).alias(
                "total_minutes"
            ),
            fn.COALESCE(fn.SUM(Activity.bag_count), 0).alias("total_bags"),
        )
        .dicts()
        .get()
    )
    query = (
        Activity.select(Activity, User)
        .join(User)
        .order_by(Activity.created_at.desc(), Activity.id.desc())
    )
    activities, page, total_pages = _activity_page(query)
    return render_template(
        "activities/index.html",
        totals=totals,
        activities=activities,
        route_previews=_activity_route_previews(activities),
        page=page,
        total_pages=total_pages,
    )


@blueprint.route("/activities/new", methods=["GET", "POST"])
@login_required
def create():
    form = ActivityForm()
    waste_types = _waste_types_for_form(form)

    if form.validate_on_submit():
        selected = _selected_waste_types(form, waste_types)
        processed_photo = _processed_photo(form)

        if not form.waste_types.errors and not form.photo.errors:
            stored_path = None
            try:
                with database_proxy.atomic():
                    activity = Activity.create(
                        user=current_user.id,
                        **_activity_values(form),
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
                    _save_activity_route(activity, form.route_points.data)
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
            flash("活動を記録しました。", "success-celebrate")
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
    activity_route = ActivityRoute.get_or_none(ActivityRoute.activity == activity.id)
    thank_count = Reaction.select().where(Reaction.activity == activity.id).count()
    has_thanked = (
        activity.user_id != current_user.id
        and Reaction.get_or_none(
            (Reaction.activity == activity.id) & (Reaction.user == current_user.id)
        )
        is not None
    )
    return render_template(
        "activities/detail.html",
        activity=activity,
        photo=photo,
        thank_count=thank_count,
        has_thanked=has_thanked,
        thank_form=ThankForm(),
        route_points=_route_points(
            activity_route.points_json if activity_route is not None else None
        ),
    )


@blueprint.post("/activities/<int:activity_id>/thanks")
@login_required
def toggle_thank(activity_id: int):
    form = ThankForm()
    if not form.validate_on_submit():
        abort(400)

    activity = Activity.get_or_none(Activity.id == activity_id)
    if activity is None:
        abort(404)
    if activity.user_id == current_user.id:
        abort(400)

    with database_proxy.atomic():
        reaction = Reaction.get_or_none(
            (Reaction.activity == activity.id) & (Reaction.user == current_user.id)
        )
        if reaction is None:
            Reaction.create(user=current_user.id, activity=activity.id)
            message = "ありがとうを送りました。"
            has_thanked = True
        else:
            reaction.delete_instance()
            message = "ありがとうを取り消しました。"
            has_thanked = False

    if request.accept_mimetypes.best == "application/json":
        thank_count = Reaction.select().where(Reaction.activity == activity.id).count()
        return jsonify(
            {
                "has_thanked": has_thanked,
                "message": message,
                "thank_count": thank_count,
            }
        )

    flash(message, "success-thanks")
    return redirect(
        url_for("activities.detail", activity_id=activity.id), code=303
    )


@blueprint.route("/activities/<int:activity_id>/edit", methods=["GET", "POST"])
@login_required
def edit(activity_id: int):
    activity = Activity.get_or_none(
        (Activity.id == activity_id) & (Activity.user == current_user.id)
    )
    if activity is None:
        abort(404)

    existing_photo = ActivityPhoto.get_or_none(
        ActivityPhoto.activity == activity.id
    )
    existing_route = ActivityRoute.get_or_none(ActivityRoute.activity == activity.id)
    form = ActivityEditForm(obj=activity)
    waste_types = _waste_types_for_form(form)
    if request.method == "GET":
        form.waste_types.data = [
            link.waste_type_id
            for link in ActivityWasteType.select().where(
                ActivityWasteType.activity == activity.id
            )
        ]
        form.route_points.data = (
            existing_route.points_json if existing_route is not None else None
        )

    if form.validate_on_submit():
        selected = _selected_waste_types(form, waste_types)
        processed_photo = _processed_photo(form)

        if not form.waste_types.errors and not form.photo.errors:
            new_stored_path = None
            old_stored_path = None
            try:
                with database_proxy.atomic():
                    for field_name, value in _activity_values(form).items():
                        setattr(activity, field_name, value)
                    activity.updated_at = utc_now()
                    activity.save()

                    ActivityWasteType.delete().where(
                        ActivityWasteType.activity == activity.id
                    ).execute()
                    ActivityWasteType.insert_many(
                        [
                            {
                                "activity": activity.id,
                                "waste_type": waste_type.id,
                            }
                            for waste_type in selected
                        ]
                    ).execute()
                    _save_activity_route(activity, form.route_points.data)

                    if processed_photo is not None:
                        storage_name, new_stored_path = store_photo(
                            processed_photo,
                            Path(current_app.config["UPLOAD_DIR"]),
                        )
                        if existing_photo is None:
                            ActivityPhoto.create(
                                activity=activity,
                                storage_name=storage_name,
                                mime_type=processed_photo.mime_type,
                                width=processed_photo.width,
                                height=processed_photo.height,
                            )
                        else:
                            old_stored_path = Path(
                                current_app.config["UPLOAD_DIR"]
                            ) / existing_photo.storage_name
                            existing_photo.storage_name = storage_name
                            existing_photo.mime_type = processed_photo.mime_type
                            existing_photo.width = processed_photo.width
                            existing_photo.height = processed_photo.height
                            existing_photo.save()
                    elif form.remove_photo.data and existing_photo is not None:
                        old_stored_path = Path(
                            current_app.config["UPLOAD_DIR"]
                        ) / existing_photo.storage_name
                        existing_photo.delete_instance()
            except Exception:
                if new_stored_path is not None:
                    new_stored_path.unlink(missing_ok=True)
                raise

            _remove_replaced_photo(old_stored_path, activity.id)
            flash("活動を更新しました。", "success-celebrate")
            return redirect(
                url_for("activities.detail", activity_id=activity.id), code=303
            )

    return render_template(
        "activities/edit.html",
        form=form,
        activity=activity,
        photo=existing_photo,
    )


@blueprint.route("/activities/<int:activity_id>/delete", methods=["GET", "POST"])
@login_required
def delete(activity_id: int):
    activity = Activity.get_or_none(
        (Activity.id == activity_id) & (Activity.user == current_user.id)
    )
    if activity is None:
        abort(404)

    photo = ActivityPhoto.get_or_none(ActivityPhoto.activity == activity.id)
    photo_path = None
    if photo is not None:
        photo_path = Path(current_app.config["UPLOAD_DIR"]) / photo.storage_name

    form = ActivityDeleteForm()
    if form.validate_on_submit():
        with database_proxy.atomic():
            activity.delete_instance()

        _remove_deleted_photo(photo_path, activity_id)
        flash("活動を削除しました。", "success-neutral")
        return redirect(url_for("users.me"), code=303)

    return render_template(
        "activities/delete.html",
        form=form,
        activity=activity,
        has_photo=photo is not None,
    )


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
