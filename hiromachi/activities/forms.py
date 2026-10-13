"""Activity form and validation."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import (
    BooleanField,
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
    photo = FileField("活動写真", validators=[Optional()])
    submit = SubmitField("記録する")

    def validate_activity_date(self, field: DateField) -> None:
        if field.data and field.data > today_in_japan():
            raise ValidationError("未来の日付は指定できません。")


class ActivityEditForm(ActivityForm):
    photo = FileField("新しい活動写真", validators=[Optional()])
    remove_photo = BooleanField("現在の写真を削除する")
    submit = SubmitField("更新する")

    def validate_photo(self, field: FileField) -> None:
        if self.remove_photo.data and field.data and field.data.filename:
            raise ValidationError(
                "新しい写真の選択と現在の写真の削除は同時に指定できません。"
            )
