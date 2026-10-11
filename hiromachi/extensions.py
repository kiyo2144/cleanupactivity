"""Flask extensions shared by the application factory."""

from flask_login import LoginManager
from flask_session import Session
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()
login_manager = LoginManager()
session_manager = Session()

login_manager.login_view = "auth.login"
login_manager.login_message = "ログインしてください。"
login_manager.login_message_category = "warning"
