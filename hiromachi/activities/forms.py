"""Activity form and validation."""

import json
import math
from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import (
    BooleanField,
    DateField,
    HiddenField,
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
    route_points = HiddenField("清掃ルート", validators=[Optional(), Length(max=8192)])
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

    def validate_route_points(self, field: HiddenField) -> None:
        if not field.data or not field.data.strip():
            field.data = None
            return

        try:
            raw_points = json.loads(field.data)
        except (TypeError, ValueError) as error:
            raise ValidationError("清掃ルートの形式が正しくありません。") from error

        if not isinstance(raw_points, list) or not 2 <= len(raw_points) <= 100:
            raise ValidationError("清掃ルートは2～100地点で指定してください。")

        points: list[list[float]] = []
        for raw_point in raw_points:
            if not isinstance(raw_point, list) or len(raw_point) != 2:
                raise ValidationError("清掃ルートの座標が正しくありません。")
            latitude, longitude = raw_point
            if (
                isinstance(latitude, bool)
                or isinstance(longitude, bool)
                or not isinstance(latitude, (int, float))
                or not isinstance(longitude, (int, float))
                or not math.isfinite(latitude)
                or not math.isfinite(longitude)
                or not -90 <= latitude <= 90
                or not -180 <= longitude <= 180
            ):
                raise ValidationError("清掃ルートの座標が正しくありません。")
            points.append([round(float(latitude), 6), round(float(longitude), 6)])

        # Do not retain precise start/end positions, which may reveal a home address.
        points[0] = [round(points[0][0], 3), round(points[0][1], 3)]
        points[-1] = [round(points[-1][0], 3), round(points[-1][1], 3)]
        if len({tuple(point) for point in points}) < 2:
            raise ValidationError("清掃ルートには異なる地点を2つ以上指定してください。")

        field.data = json.dumps(points, ensure_ascii=True, separators=(",", ":"))


class ActivityEditForm(ActivityForm):
    photo = FileField("新しい活動写真", validators=[Optional()])
    remove_photo = BooleanField("現在の写真を削除する")
    submit = SubmitField("更新する")

    def validate_photo(self, field: FileField) -> None:
        if self.remove_photo.data and field.data and field.data.filename:
            raise ValidationError(
                "新しい写真の選択と現在の写真の削除は同時に指定できません。"
            )


class ActivityDeleteForm(FlaskForm):
    submit = SubmitField("削除する")


class ThankForm(FlaskForm):
    submit = SubmitField("ありがとうを送る")
