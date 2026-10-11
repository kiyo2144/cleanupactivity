from flask import Blueprint

blueprint = Blueprint("activities", __name__)

from . import routes  # noqa: E402, F401
