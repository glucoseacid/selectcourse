"""管理员路由"""
import json
import logging
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from selectcourse.extensions import db
from selectcourse.models.user import User
from selectcourse.models.course import Course, CourseSchedule
from selectcourse.models.category import CourseCategory
from selectcourse.models.selection import Selection
from selectcourse.forms import (
    CourseForm, CategoryForm, CourseImportForm,
    parse_import_file, _normalize_row, _validate_row,
)

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__)

# 默认课程分类
DEFAULT_CATEGORIES = ["通识课程", "必修课程", "体育分项", "其他"]


def admin_required(f):
    """装饰器：要求管理员权限"""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash("需要管理员权限。", "danger")
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/")
@admin_required
def dashboard():
    total_students = User.query.filter_by(role="student").count()
    total_courses = Course.query.count()
    total_selections = Selection.query.filter_by(status="enrolled").count()
    return render_template(
        "admin/dashboard.html",
        total_students=total_students,
        total_courses=total_courses,
        total_selections=total_selections,
    )


@admin_bp.route("/courses")
@admin_required
def manage_courses():
    page = request.args.get("page", 1, type=int)
    pagination = Course.query.order_by(Course.code).paginate(
        page=page, per_page=15, error_out=False
    )
    return render_template(
        "admin/courses.html", courses=pagination.items, pagination=pagination
    )


@admin_bp.route("/courses/create", methods=["GET", "POST"])
@admin_required
def create_course():
    form = CourseForm()
    categories = CourseCategory.query.order_by(CourseCategory.display_order, CourseCategory.id).all()
    form.set_category_choices(categories)
    if form.validate_on_submit():
        # 检查课程编号唯一性
        existing = Course.query.filter_by(code=form.code.data).first()
        if existing:
            flash(f"课程编号「{form.code.data}」已存在。", "danger")
            return render_template("admin/create_course.html", form=form)

        # 解析并验证时间段
        schedules_data = form.parse_schedules()
        if schedules_data:
            has_overlap, error_msg = CourseSchedule.has_overlap(schedules_data)
            if has_overlap:
                flash(f"上课时间段冲突：{error_msg}", "danger")
                return render_template("admin/create_course.html", form=form)

        course = Course(
            name=form.name.data,
            code=form.code.data,
            teacher=form.teacher.data,
            credits=form.credits.data,
            capacity=form.capacity.data,
            semester=form.semester.data,
            category_id=form.category_id.data if form.category_id.data != 0 else None,
            location=form.location.data or "",
            description=form.description.data or "",
        )
        db.session.add(course)
        db.session.flush()  # 获取 course.id

        # 添加多条排课记录
        for s in schedules_data:
            schedule = CourseSchedule(
                course_id=course.id,
                day_of_week=s["day_of_week"],
                start_time=s["start_time"],
                end_time=s["end_time"],
            )
            db.session.add(schedule)

        db.session.commit()
        flash(f"课程「{course.name}」创建成功！", "success")
        return redirect(url_for("admin.manage_courses"))

    return render_template("admin/create_course.html", form=form)


@admin_bp.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_course(course_id: int):
    course = db.session.get(Course, course_id)
    if course is None:
        flash("课程不存在。", "danger")
        return redirect(url_for("admin.manage_courses"))

    form = CourseForm(obj=course)
    categories = CourseCategory.query.order_by(CourseCategory.display_order, CourseCategory.id).all()
    form.set_category_choices(categories)
    if course.category_id is None:
        form.category_id.data = 0  # 映射 — 不分类 —

    if form.validate_on_submit():
        # 检查课程编号唯一性（排除自身）
        existing = Course.query.filter(
            Course.code == form.code.data, Course.id != course.id
        ).first()
        if existing:
            flash(f"课程编号「{form.code.data}」已被其他课程使用。", "danger")
            return render_template("admin/edit_course.html", form=form, course=course)

        # 解析并验证时间段
        schedules_data = form.parse_schedules()
        if schedules_data:
            has_overlap, error_msg = CourseSchedule.has_overlap(schedules_data)
            if has_overlap:
                flash(f"上课时间段冲突：{error_msg}", "danger")
                return render_template("admin/edit_course.html", form=form, course=course)

        form.populate_obj(course)
        course.category_id = form.category_id.data if form.category_id.data != 0 else None
        course.location = course.location or ""
        course.description = course.description or ""

        # 更新排课：先清空再重建
        CourseSchedule.query.filter_by(course_id=course.id).delete()
        for s in schedules_data:
            schedule = CourseSchedule(
                course_id=course.id,
                day_of_week=s["day_of_week"],
                start_time=s["start_time"],
                end_time=s["end_time"],
            )
            db.session.add(schedule)

        db.session.commit()
        flash(f"课程「{course.name}」更新成功！", "success")
        return redirect(url_for("admin.manage_courses"))

    return render_template("admin/edit_course.html", form=form, course=course)


@admin_bp.route("/courses/<int:course_id>/delete", methods=["POST"])
@admin_required
def delete_course(course_id: int):
    course = db.session.get(Course, course_id)
    if course is None:
        flash("课程不存在。", "danger")
        return redirect(url_for("admin.manage_courses"))

    name = course.name
    db.session.delete(course)
    db.session.commit()
    flash(f"课程「{name}」已删除。", "info")
    return redirect(url_for("admin.manage_courses"))


@admin_bp.route("/courses/import", methods=["GET", "POST"])
@admin_required
def import_courses():
    """批量导入课程：支持 CSV / JSON / Excel (.xlsx)"""
    form = CourseImportForm()
    if form.validate_on_submit():
        file = form.file.data
        filename = (file.filename or "").lower()

        # 推断格式
        if filename.endswith(".csv"):
            fmt = "csv"
        elif filename.endswith(".json"):
            fmt = "json"
        elif filename.endswith(".xlsx"):
            fmt = "xlsx"
        else:
            flash("不支持的文件格式，请上传 CSV、JSON 或 Excel 文件。", "danger")
            return render_template("admin/import_courses.html", form=form)

        rows, parse_error = parse_import_file(file, fmt)
        if parse_error:
            flash(parse_error, "danger")
            return render_template("admin/import_courses.html", form=form)

        if not rows:
            flash("文件中没有数据行。", "warning")
            return render_template("admin/import_courses.html", form=form)

        success_count = 0
        skip_count = 0
        errors = []
        new_courses = []

        for i, raw_row in enumerate(rows, start=2):  # 从第 2 行开始（第 1 行是表头）
            row = _normalize_row(raw_row)
            row_errors = _validate_row(row, i)
            if row_errors:
                errors.extend(row_errors)
                skip_count += 1
                continue

            # 检查课程编号是否已存在
            existing = Course.query.filter_by(code=row["code"]).first()
            if existing:
                errors.append(f"第 {i} 行课程编号「{row['code']}」已存在，跳过。")
                skip_count += 1
                continue

            # 解析分类名称 -> category_id
            category_id = None
            category_name = row.get("category_name", "").strip()
            if category_name:
                cat = CourseCategory.query.filter_by(name=category_name).first()
                if cat:
                    category_id = cat.id

            try:
                course = Course(
                    name=row["name"],
                    code=row["code"],
                    teacher=row["teacher"],
                    credits=row["credits"],
                    capacity=row["capacity"],
                    semester=row["semester"],
                    category_id=category_id,
                    location=row.get("location", ""),
                    description=row.get("description", ""),
                )
                db.session.add(course)
                db.session.flush()

                # 解析多时间段：优先使用 schedules JSON，否则回退到单字段
                schedules_created = False
                schedules_raw = row.get("schedules", "").strip()
                if schedules_raw:
                    try:
                        schedules_data = json.loads(schedules_raw)
                        if isinstance(schedules_data, list):
                            for s in schedules_data:
                                sd = CourseSchedule(
                                    course_id=course.id,
                                    day_of_week=int(s["day_of_week"]),
                                    start_time=str(s.get("start_time", "")).strip(),
                                    end_time=str(s.get("end_time", "")).strip(),
                                )
                                db.session.add(sd)
                            schedules_created = True
                    except (json.JSONDecodeError, ValueError, TypeError, KeyError):
                        pass  # 已在 _validate_row 中校验过，不应发生

                if not schedules_created:
                    # 回退：单时间段字段
                    day = row.get("day_of_week")
                    start_t = row.get("start_time")
                    end_t = row.get("end_time")
                    if day is not None and start_t and end_t:
                        schedule = CourseSchedule(
                            course_id=course.id,
                            day_of_week=day,
                            start_time=start_t,
                            end_time=end_t,
                        )
                        db.session.add(schedule)

                new_courses.append(course)
                success_count += 1
            except Exception as e:
                db.session.rollback()
                errors.append(f"第 {i} 行导入失败: {e}")
                skip_count += 1

        if new_courses:
            db.session.commit()
            flash(f"成功导入 {success_count} 门课程！", "success")
        if skip_count:
            flash(f"跳过 {skip_count} 行（详见下方错误信息）。", "warning")

        return render_template(
            "admin/import_courses.html",
            form=form,
            success_count=success_count,
            skip_count=skip_count,
            errors=errors,
            total_rows=len(rows),
        )

    return render_template("admin/import_courses.html", form=form)


@admin_bp.route("/students")
@admin_required
def manage_students():
    page = request.args.get("page", 1, type=int)
    pagination = User.query.filter_by(role="student").order_by(User.username).paginate(
        page=page, per_page=15, error_out=False
    )
    return render_template(
        "admin/students.html", students=pagination.items, pagination=pagination
    )


# ---- 课程分类管理 ----


@admin_bp.route("/categories")
@admin_required
def manage_categories():
    """管理课程分类页面。"""
    categories = CourseCategory.query.order_by(
        CourseCategory.display_order, CourseCategory.id
    ).all()
    form = CategoryForm()
    return render_template(
        "admin/categories.html", categories=categories, form=form
    )


@admin_bp.route("/categories/create", methods=["POST"])
@admin_required
def create_category():
    """添加课程分类。"""
    form = CategoryForm()
    if form.validate_on_submit():
        name = form.name.data.strip()
        existing = CourseCategory.query.filter_by(name=name).first()
        if existing:
            flash(f"分类「{name}」已存在。", "danger")
        else:
            category = CourseCategory(name=name)
            db.session.add(category)
            db.session.commit()
            flash(f"分类「{name}」已添加。", "success")
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                flash(err, "danger")
    return redirect(url_for("admin.manage_categories"))


@admin_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def delete_category(category_id: int):
    """删除课程分类（同时将关联课程置为无分类）。"""
    category = db.session.get(CourseCategory, category_id)
    if category is None:
        flash("分类不存在。", "danger")
        return redirect(url_for("admin.manage_categories"))

    name = category.name
    # 将关联课程的 category_id 置空
    Course.query.filter_by(category_id=category_id).update(
        {Course.category_id: None}
    )
    db.session.delete(category)
    db.session.commit()
    flash(f"分类「{name}」已删除，关联课程已取消分类。", "info")
    return redirect(url_for("admin.manage_categories"))


# ---- 初始化默认分类 ----


def init_default_categories() -> None:
    """在应用启动时初始化默认课程分类（幂等）。"""
    for cat_name in DEFAULT_CATEGORIES:
        if not CourseCategory.query.filter_by(name=cat_name).first():
            db.session.add(CourseCategory(name=cat_name))
    db.session.commit()
