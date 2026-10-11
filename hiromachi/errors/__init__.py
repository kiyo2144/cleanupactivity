from flask import Flask
from flask_wtf.csrf import CSRFError

from .handlers import bad_request, internal_server_error, not_found


def register_error_handlers(app: Flask) -> None:
    app.register_error_handler(400, bad_request)
    app.register_error_handler(CSRFError, bad_request)
    app.register_error_handler(404, not_found)
    app.register_error_handler(500, internal_server_error)
