"""表单定义"""
import io
import csv
import json
import logging
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, PasswordField, SelectField, FloatField, IntegerField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange, Optional

logger = logging.getLogger(__name__)


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


class CourseImportForm(FlaskForm):
    """批量导入课程表单"""
    file = FileField(
        "选择文件",
        validators=[
            FileRequired(message="请选择要上传的文件"),
            FileAllowed(
                ["csv", "json", "xlsx"],
                "仅支持 CSV、JSON、Excel (.xlsx) 格式",
            ),
        ],
    )
    submit = SubmitField("导入课程")


# ---- 导入解析器 ----

# 列名映射：支持中英文表头
COLUMN_MAP = {
    "name": "name", "课程名称": "name", "名称": "name",
    "code": "code", "课程编号": "code", "编号": "code",
    "teacher": "teacher", "授课教师": "teacher", "教师": "teacher",
    "credits": "credits", "学分": "credits",
    "capacity": "capacity", "容量": "capacity", "人数上限": "capacity",
    "semester": "semester", "学期": "semester",
    "description": "description", "课程描述": "description", "描述": "description",
    "location": "location", "上课地点": "location", "地点": "location", "教室": "location",
    "day_of_week": "day_of_week", "上课日": "day_of_week",
    "start_time": "start_time", "开始时间": "start_time",
    "end_time": "end_time", "结束时间": "end_time",
}

REQUIRED_FIELDS = ["name", "code", "teacher", "credits", "capacity", "semester"]


def _normalize_row(raw: dict) -> dict:
    """将中文/英文表头统一映射到标准字段名。"""
    result = {}
    for key, value in raw.items():
        key_clean = key.strip()
        mapped = COLUMN_MAP.get(key_clean, COLUMN_MAP.get(key_clean.lower(), None))
        if mapped:
            result[mapped] = str(value).strip() if value is not None else ""
    return result


def _validate_row(row: dict, row_index: int) -> list[str]:
    """验证单行数据，返回错误列表。"""
    errors = []
    for field in REQUIRED_FIELDS:
        if not row.get(field):
            errors.append(f"第 {row_index} 行缺少必填字段「{field}」")
            return errors  # 缺少必填字段直接返回

    row["credits"] = row.get("credits", "2.0")
    row["capacity"] = row.get("capacity", "60")

    try:
        credits_val = float(row["credits"])
        if credits_val < 0.5 or credits_val > 10:
            errors.append(f"第 {row_index} 行学分不在 0.5~10 范围内")
        row["credits"] = credits_val
    except (ValueError, TypeError):
        errors.append(f"第 {row_index} 行学分格式无效: {row['credits']}")

    try:
        cap_val = int(row["capacity"])
        if cap_val < 1 or cap_val > 999:
            errors.append(f"第 {row_index} 行容量不在 1~999 范围内")
        row["capacity"] = cap_val
    except (ValueError, TypeError):
        errors.append(f"第 {row_index} 行容量格式无效: {row['capacity']}")

    day = row.get("day_of_week")
    if day:
        try:
            day_val = int(day)
            if day_val < 0 or day_val > 6:
                errors.append(f"第 {row_index} 行上课日必须在 0~6 之间")
            row["day_of_week"] = day_val
        except (ValueError, TypeError):
            errors.append(f"第 {row_index} 行上课日格式无效: {day}")

    start_t = row.get("start_time", "")
    end_t = row.get("end_time", "")
    if start_t and not end_t:
        errors.append(f"第 {row_index} 行有开始时间但缺少结束时间")
    if end_t and not start_t:
        errors.append(f"第 {row_index} 行有结束时间但缺少开始时间")

    return errors


def parse_csv(file_stream) -> list[dict]:
    """解析 CSV 文件，返回行列表。"""
    # 尝试检测 BOM 和编码
    raw_bytes = file_stream.read()
    # 处理 BOM
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        text = raw_bytes.decode("utf-8-sig")
    else:
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = raw_bytes.decode("gbk", errors="replace")

    reader = csv.DictReader(io.StringIO(text))
    return [row for row in reader]


def parse_json(file_stream) -> list[dict]:
    """解析 JSON 文件，返回行列表。"""
    raw = file_stream.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="replace")
    data = json.loads(text)
    if isinstance(data, dict):
        # 支持 {"courses": [...]} 或直接 {"name":...} 单条
        data = data.get("courses", [data])
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("JSON 格式错误：期望数组或包含 courses 键的对象")
    return data


def parse_excel(file_stream) -> list[dict]:
    """解析 Excel 文件，返回行列表。"""
    import openpyxl
    wb = openpyxl.load_workbook(file_stream, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h).strip() if h else "" for h in rows[0]]
    result = []
    for row_values in rows[1:]:
        row_dict = {}
        for i, header in enumerate(headers):
            if header and i < len(row_values):
                row_dict[header] = row_values[i]
        result.append(row_dict)
    wb.close()
    return result


def parse_import_file(file_storage, format_hint: str) -> tuple[list[dict], str | None]:
    """
    根据文件扩展名解析上传文件。
    返回 (行列表, 错误信息)。
    """
    filename = (file_storage.filename or "").lower()
    if format_hint == "csv" or filename.endswith(".csv"):
        try:
            return parse_csv(file_storage), None
        except Exception as e:
            return [], f"CSV 解析失败: {e}"
    elif format_hint == "json" or filename.endswith(".json"):
        try:
            return parse_json(file_storage), None
        except Exception as e:
            return [], f"JSON 解析失败: {e}"
    elif format_hint == "xlsx" or filename.endswith(".xlsx"):
        try:
            return parse_excel(file_storage), None
        except Exception as e:
            return [], f"Excel 解析失败: {e}"
    else:
        return [], f"不支持的文件格式: {filename}"
