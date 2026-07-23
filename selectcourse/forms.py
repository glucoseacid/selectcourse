"""表单定义"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, FloatField, IntegerField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange, Optional


class LoginForm(FlaskForm):
    username = StringField("用户名", validators=[DataRequired(message="请输入用户名")])
    password = PasswordField("密码", validators=[DataRequired(message="请输入密码")])
    submit = SubmitField("登录")


class RegisterForm(FlaskForm):
    username = StringField(
        "用户名",
        validators=[
            DataRequired(message="请输入用户名"),
            Length(min=2, max=64, message="用户名长度须在 2~64 之间"),
        ],
    )
    email = StringField(
        "邮箱",
        validators=[
            DataRequired(message="请输入邮箱"),
            Email(message="邮箱格式不正确"),
        ],
    )
    password = PasswordField(
        "密码",
        validators=[
            DataRequired(message="请输入密码"),
            Length(min=6, max=128, message="密码至少 6 位"),
        ],
    )
    confirm_password = PasswordField(
        "确认密码",
        validators=[
            DataRequired(message="请再次输入密码"),
            EqualTo("password", message="两次密码输入不一致"),
        ],
    )
    submit = SubmitField("注册")


class CourseForm(FlaskForm):
    name = StringField("课程名称", validators=[DataRequired(message="请输入课程名称")])
    code = StringField("课程编号", validators=[DataRequired(message="请输入课程编号")])
    teacher = StringField("授课教师", validators=[DataRequired(message="请输入授课教师")])
    credits = FloatField("学分", validators=[NumberRange(min=0.5, max=10, message="学分范围 0.5~10")])
    capacity = IntegerField("容量", validators=[NumberRange(min=1, max=999, message="容量范围 1~999")])
    semester = StringField("学期", validators=[DataRequired(message="请输入学期")])
    location = StringField("上课地点", validators=[Optional()])
    description = TextAreaField("课程描述", validators=[Optional()])

    # 排课字段（简化为每日一条）
    day_of_week = SelectField(
        "上课日",
        choices=[
            (0, "周一"), (1, "周二"), (2, "周三"),
            (3, "周四"), (4, "周五"), (5, "周六"), (6, "周日"),
        ],
        coerce=int,
        validators=[Optional()],
    )
    start_time = StringField("开始时间 (HH:MM)", validators=[Optional()])
    end_time = StringField("结束时间 (HH:MM)", validators=[Optional()])
    submit = SubmitField("保存")
