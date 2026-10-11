from flask import Blueprint

blueprint = Blueprint("users", __name__)

from . import routes  # noqa: E402, F401
