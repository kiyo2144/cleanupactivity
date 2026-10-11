"""Activity form and validation."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    IntegerField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
    widgets,
)
from wtforms.validators import InputRequired, Length, NumberRange, Optional, ValidationError


def today_in_japan() -> date:
    return datetime.now(ZoneInfo("Asia/Tokyo")).date()


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class ActivityForm(FlaskForm):
    activity_date = DateField(
        "活動日",
        default=today_in_japan,
        validators=[InputRequired()],
    )
    location = StringField(
        "活動場所",
        validators=[InputRequired(), Length(min=1, max=100)],
    )
    duration_minutes = IntegerField(
        "所要時間（分）",
        validators=[InputRequired(), NumberRange(min=1, max=1440)],
    )
    bag_count = IntegerField(
        "ゴミの袋数",
        validators=[InputRequired(), NumberRange(min=0, max=99)],
    )
    waste_types = MultiCheckboxField(
        "ゴミの種類",
        coerce=int,
        validators=[InputRequired(message="1つ以上選択してください。")],
    )
    comment = TextAreaField("コメント・感想", validators=[Optional(), Length(max=500)])
    submit = SubmitField("記録する")

    def validate_activity_date(self, field: DateField) -> None:
        if field.data and field.data > today_in_japan():
            raise ValidationError("未来の日付は指定できません。")
