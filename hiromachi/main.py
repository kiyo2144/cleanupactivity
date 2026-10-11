"""Application entry route."""

from flask import Blueprint, redirect, url_for
from flask_login import current_user

blueprint = Blueprint("main", __name__)


@blueprint.get("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("activities.index"))
    return redirect(url_for("auth.login"))
