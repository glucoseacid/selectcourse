"""课程路由（浏览 / 详情 / 选课 / 退课）"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from selectcourse.extensions import db
from selectcourse.models.course import Course
from selectcourse.models.selection import Selection

course_bp = Blueprint("course", __name__)


@course_bp.route("/")
@login_required
def list_courses():
    page = request.args.get("page", 1, type=int)
    semester = request.args.get("semester", "")
    search = request.args.get("search", "")

    query = Course.query
    if semester:
        query = query.filter(Course.semester == semester)
    if search:
        query = query.filter(
            db.or_(
                Course.name.contains(search),
                Course.code.contains(search),
                Course.teacher.contains(search),
            )
        )

    pagination = query.order_by(Course.code).paginate(
        page=page, per_page=12, error_out=False
    )
    courses = pagination.items

    # 获取当前学生已选课程 ID 集合
    enrolled_ids: set[int] = set()
    if not current_user.is_admin:
        enrolled_ids = {
            s.course_id
            for s in Selection.query.filter_by(
                student_id=current_user.id, status="enrolled"
            ).all()
        }

    # 获取可选学期列表
    semesters = [
        row[0]
        for row in db.session.query(Course.semester).distinct().order_by(Course.semester).all()
    ]

    return render_template(
        "course/list.html",
        courses=courses,
        pagination=pagination,
        enrolled_ids=enrolled_ids,
        semesters=semesters,
        current_semester=semester,
        current_search=search,
    )


@course_bp.route("/<int:course_id>")
@login_required
def detail(course_id: int):
    course = db.session.get(Course, course_id)
    if course is None:
        flash("课程不存在。", "danger")
        return redirect(url_for("course.list_courses"))

    enrolled = False
    if not current_user.is_admin:
        enrolled = Selection.query.filter_by(
            student_id=current_user.id, course_id=course_id, status="enrolled"
        ).first() is not None

    return render_template("course/detail.html", course=course, enrolled=enrolled)


@course_bp.route("/<int:course_id>/enroll", methods=["POST"])
@login_required
def enroll(course_id: int):
    if current_user.is_admin:
        flash("管理员不能选课。", "warning")
        return redirect(url_for("course.list_courses"))

    course = db.session.get(Course, course_id)
    if course is None:
        flash("课程不存在。", "danger")
        return redirect(url_for("course.list_courses"))

    # 检查是否已选
    existing = Selection.query.filter_by(
        student_id=current_user.id, course_id=course_id, status="enrolled"
    ).first()
    if existing:
        flash("你已选择该课程。", "warning")
        return redirect(url_for("course.detail", course_id=course_id))

    # 检查容量
    if course.is_full:
        flash("课程名额已满，无法选课。", "danger")
        return redirect(url_for("course.detail", course_id=course_id))

    # 检查时间冲突
    if Selection.has_time_conflict(current_user.id, course_id):
        flash("与已选课程存在时间冲突，无法选课。", "danger")
        return redirect(url_for("course.detail", course_id=course_id))

    # 执行选课
    selection = Selection(student_id=current_user.id, course_id=course_id)
    course.enrolled_count += 1
    db.session.add(selection)
    db.session.commit()

    flash(f"成功选择课程「{course.name}」！", "success")
    return redirect(url_for("course.detail", course_id=course_id))


@course_bp.route("/<int:course_id>/drop", methods=["POST"])
@login_required
def drop(course_id: int):
    if current_user.is_admin:
        flash("管理员不能退课。", "warning")
        return redirect(url_for("course.list_courses"))

    selection = Selection.query.filter_by(
        student_id=current_user.id, course_id=course_id, status="enrolled"
    ).first()
    if selection is None:
        flash("你未选择该课程。", "warning")
        return redirect(url_for("course.detail", course_id=course_id))

    course = db.session.get(Course, course_id)
    selection.status = "dropped"
    if course:
        course.enrolled_count = max(0, course.enrolled_count - 1)
    db.session.commit()

    flash(f"已退选课程「{course.name}」。", "info")
    return redirect(url_for("course.list_courses"))


@course_bp.route("/my-courses")
@login_required
def my_courses():
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))

    selections = (
        Selection.query.filter_by(student_id=current_user.id, status="enrolled")
        .order_by(Selection.enrolled_at.desc())
        .all()
    )
    return render_template("course/my_courses.html", selections=selections)
