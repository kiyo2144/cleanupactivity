"""Authentication forms."""

import re

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, ValidationError

from ..models import User

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


class RegistrationForm(FlaskForm):
    username = StringField(
        "ログインID",
        validators=[DataRequired(), Length(min=3, max=30)],
    )
    display_name = StringField(
        "お名前",
        validators=[DataRequired(), Length(min=1, max=50)],
    )
    password = PasswordField(
        "パスワード",
        validators=[DataRequired(), Length(min=8, max=128)],
    )
    password_confirm = PasswordField(
        "パスワード（確認）",
        validators=[DataRequired(), EqualTo("password", message="パスワードが一致しません。")],
    )
    submit = SubmitField("登録する")

    def validate_username(self, field: StringField) -> None:
        username = field.data.strip() if field.data else ""
        if not USERNAME_PATTERN.fullmatch(username):
            raise ValidationError("半角英数字とアンダースコアだけを使用してください。")
        if User.select().where(User.username == username).exists():
            raise ValidationError("このログインIDは使用できません。")


class LoginForm(FlaskForm):
    username = StringField("ログインID", validators=[DataRequired(), Length(max=30)])
    password = PasswordField("パスワード", validators=[DataRequired(), Length(max=128)])
    submit = SubmitField("ログインする")


class LogoutForm(FlaskForm):
    submit = SubmitField("ログアウト")
