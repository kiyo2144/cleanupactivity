"""Hiromachi Flask application factory."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any, Mapping

from cachelib.file import FileSystemCache
from flask import Flask

from . import database
from .commands import register_commands
from .config import load_config
from .extensions import csrf, login_manager, session_manager


def create_app(config_override: Mapping[str, Any] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.from_mapping(load_config(app.instance_path))

    if config_override:
        app.config.update(config_override)

    session_dir = Path(app.config["SESSION_DIR"])
    session_dir.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)
    app.config["SESSION_CACHELIB"] = FileSystemCache(
        cache_dir=str(session_dir),
        threshold=500,
    )
    app.permanent_session_lifetime = timedelta(
        days=int(app.config["SESSION_LIFETIME_DAYS"])
    )

    database.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    session_manager.init_app(app)
    register_commands(app)

    from .activities import blueprint as activities_blueprint
    from .auth import blueprint as auth_blueprint
    from .errors import register_error_handlers
    from .main import blueprint as main_blueprint
    from .users import blueprint as users_blueprint

    app.register_blueprint(main_blueprint)
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(activities_blueprint)
    app.register_blueprint(users_blueprint)
    register_error_handlers(app)

    return app
