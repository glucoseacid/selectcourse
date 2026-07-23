"""管理员路由"""
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from selectcourse.extensions import db
from selectcourse.models.user import User
from selectcourse.models.course import Course, CourseSchedule
from selectcourse.models.selection import Selection
from selectcourse.forms import CourseForm

admin_bp = Blueprint("admin", __name__)


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
    if form.validate_on_submit():
        course = Course(
            name=form.name.data,
            code=form.code.data,
            teacher=form.teacher.data,
            credits=form.credits.data,
            capacity=form.capacity.data,
            semester=form.semester.data,
            location=form.location.data or "",
            description=form.description.data or "",
        )
        db.session.add(course)
        db.session.flush()  # 获取 course.id

        # 添加排课记录
        if form.day_of_week.data is not None and form.start_time.data and form.end_time.data:
            schedule = CourseSchedule(
                course_id=course.id,
                day_of_week=form.day_of_week.data,
                start_time=form.start_time.data,
                end_time=form.end_time.data,
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
    # 预填排课信息
    if course.schedules:
        s = course.schedules[0]
        form.day_of_week.data = s.day_of_week
        form.start_time.data = s.start_time
        form.end_time.data = s.end_time

    if form.validate_on_submit():
        form.populate_obj(course)
        course.location = course.location or ""
        course.description = course.description or ""

        # 更新排课
        CourseSchedule.query.filter_by(course_id=course.id).delete()
        if form.day_of_week.data is not None and form.start_time.data and form.end_time.data:
            schedule = CourseSchedule(
                course_id=course.id,
                day_of_week=form.day_of_week.data,
                start_time=form.start_time.data,
                end_time=form.end_time.data,
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
