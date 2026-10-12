"""Registration, login, and logout routes."""

from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user
from peewee import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import login_manager
from ..models import User
from . import blueprint
from .forms import LoginForm, LogoutForm, RegistrationForm


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    try:
        return User.get_by_id(int(user_id))
    except (TypeError, ValueError, User.DoesNotExist):
        return None


@blueprint.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("activities.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            User.create(
                username=form.username.data.strip(),
                display_name=form.display_name.data.strip(),
                password_hash=generate_password_hash(form.password.data),
            )
        except IntegrityError:
            form.username.errors.append("このユーザーIDは使用できません。")
        else:
            flash("ユーザー登録が完了しました。ログインしてください。", "success")
            return redirect(url_for("auth.login"), code=303)

    return render_template("auth/register.html", form=form)


@blueprint.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("activities.index"))

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        user = User.get_or_none(User.username == username)
        if user is not None and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            flash("ログインしました。", "success")
            return redirect(url_for("activities.index"), code=303)
        form.password.errors.append("ユーザーIDまたはパスワードが正しくありません。")

    return render_template("auth/login.html", form=form)


@blueprint.post("/logout")
@login_required
def logout():
    form = LogoutForm()
    if form.validate_on_submit():
        logout_user()
        flash("ログアウトしました。", "success")
        return redirect(url_for("auth.login"), code=303)
    return render_template("errors/400.html"), 400
