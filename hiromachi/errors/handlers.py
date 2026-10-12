"""HTML error handlers."""

from flask import render_template


def bad_request(_error):
    return render_template("errors/400.html"), 400


def not_found(_error):
    return render_template("errors/404.html"), 404


def request_too_large(_error):
    return render_template("errors/413.html"), 413


def internal_server_error(_error):
    return render_template("errors/500.html"), 500
