"""课程路由（浏览 / 详情 / 选课 / 退课 / 课表）"""
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from selectcourse.extensions import db
from selectcourse.models.course import Course, CourseSchedule
from selectcourse.models.category import CourseCategory
from selectcourse.models.selection import Selection

# 北京时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))

course_bp = Blueprint("course", __name__)

# 课表配色（17 种颜色循环使用）
TIMETABLE_COLORS = [
    "#E74C3C", "#3498DB", "#2ECC71", "#9B59B6", "#F39C12",
    "#1ABC9C", "#E67E22", "#2980B9", "#27AE60", "#8E44AD",
    "#D35400", "#16A085", "#C0392B", "#2C3E50", "#7F8C8D",
    "#F1C40F", "#00B894",
]


@course_bp.route("/")
@login_required
def list_courses():
    page = request.args.get("page", 1, type=int)
    semester = request.args.get("semester", "")
    search = request.args.get("search", "")
    category = request.args.get("category", "")

    query = Course.query
    if semester:
        query = query.filter(Course.semester == semester)
    if category:
        query = query.filter(Course.category_id == int(category))
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

    # 获取所有课程分类
    all_categories = CourseCategory.query.order_by(
        CourseCategory.display_order, CourseCategory.id
    ).all()

    return render_template(
        "course/list.html",
        courses=courses,
        pagination=pagination,
        enrolled_ids=enrolled_ids,
        semesters=semesters,
        categories=all_categories,
        current_semester=semester,
        current_category=category,
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


@course_bp.route("/<int:course_id>/info")
@login_required
def course_info(course_id: int):
    """返回课程详细信息的 JSON API（用于弹窗）。"""
    from flask import jsonify

    course = db.session.get(Course, course_id)
    if course is None:
        return jsonify({"error": "课程不存在"}), 404

    days_label = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    return jsonify({
        "id": course.id,
        "name": course.name,
        "code": course.code,
        "teacher": course.teacher,
        "credits": course.credits,
        "capacity": course.capacity,
        "enrolled_count": course.enrolled_count,
        "available_slots": course.available_slots,
        "semester": course.semester,
        "location": course.location or "",
        "description": course.description or "",
        "category": course.category.name if course.category else "",
        "schedules": [
            {
                "day_of_week": s.day_of_week,
                "day_label": days_label[s.day_of_week],
                "start_time": s.start_time,
                "end_time": s.end_time,
            }
            for s in (course.schedules or [])
        ],
        "is_full": course.is_full,
    })


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

    # 检查是否已选（不含已退选的）
    existing = Selection.query.filter_by(
        student_id=current_user.id, course_id=course_id
    ).first()
    if existing and existing.status == "enrolled":
        flash("你已选择该课程。", "warning")
        return redirect(url_for("course.detail", course_id=course_id))

    # 检查容量（退课重选不占新名额）
    if (not existing or existing.status != "enrolled") and course.is_full:
        flash("课程名额已满，无法选课。", "danger")
        return redirect(url_for("course.detail", course_id=course_id))

    # 检查时间冲突
    if Selection.has_time_conflict(current_user.id, course_id):
        flash("与已选课程存在时间冲突，无法选课。", "danger")
        return redirect(url_for("course.detail", course_id=course_id))

    # 执行选课：已有退课记录则复用，否则新建
    if existing:
        existing.status = "enrolled"
        existing.enrolled_at = datetime.now(BEIJING_TZ)
    else:
        existing = Selection(student_id=current_user.id, course_id=course_id)
        db.session.add(existing)
    course.enrolled_count += 1
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


def _build_timetable_grid(selections: list[Selection]) -> dict:
    """将选课记录构建为课表网格数据。

    Returns:
        dict with keys:
          - grid: dict[day_of_week][period_num] = list of course blocks
          - colors: dict[course_id] = color hex string
          - course_count: int
    """
    days = 7   # 0=周一 … 6=周日
    periods = 12

    # 初始化空白网格
    grid: dict[int, dict[int, list[dict]]] = {
        d: {p: [] for p in range(1, periods + 1)} for d in range(days)
    }

    colors: dict[int, str] = {}
    course_names: dict[int, str] = {}
    color_idx = 0

    for selection in selections:
        course = selection.course
        # 分配颜色与名称
        if course.id not in colors:
            colors[course.id] = TIMETABLE_COLORS[color_idx % len(TIMETABLE_COLORS)]
            course_names[course.id] = course.name
            color_idx += 1

        for schedule in course.schedules:
            start_p, end_p = CourseSchedule.period_range(
                schedule.start_time, schedule.end_time
            )
            day = schedule.day_of_week
            rowspan = end_p - start_p + 1

            block = {
                "course_id": course.id,
                "course_name": course.name,
                "course_code": course.code,
                "teacher": course.teacher,
                "location": course.location or "",
                "semester": course.semester,
                "start_period": start_p,
                "end_period": end_p,
                "rowspan": rowspan,
                "start_time": schedule.start_time,
                "end_time": schedule.end_time,
                "color": colors[course.id],
            }
            grid[day][start_p].append(block)

    return {
        "grid": grid,
        "colors": colors,
        "course_names": course_names,
        "course_count": len(selections),
    }


@course_bp.route("/timetable")
@login_required
def timetable():
    """学生课表视图（表格模式）。"""
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))

    semester = request.args.get("semester", "")

    # 获取学生已选课程
    query = (
        Selection.query
        .filter_by(student_id=current_user.id, status="enrolled")
        .join(Course)
    )
    if semester:
        query = query.filter(Course.semester == semester)
    selections = query.order_by(Selection.enrolled_at.desc()).all()

    # 获取可选学期列表
    semesters = [
        row[0]
        for row in db.session.query(Course.semester)
        .join(Selection, Selection.course_id == Course.id)
        .filter(Selection.student_id == current_user.id, Selection.status == "enrolled")
        .distinct()
        .order_by(Course.semester)
        .all()
    ]

    # 如果未指定学期，默认使用第一个可用学期
    if not semester and semesters:
        semester = semesters[0]
        query = (
            Selection.query
            .filter_by(student_id=current_user.id, status="enrolled")
            .join(Course)
            .filter(Course.semester == semester)
        )
        selections = query.order_by(Selection.enrolled_at.desc()).all()

    timetable_data = _build_timetable_grid(selections)
    total_credits = sum(s.course.credits for s in selections)

    return render_template(
        "course/timetable.html",
        timetable=timetable_data,
        semesters=semesters,
        current_semester=semester,
        total_credits=total_credits,
        course_count=timetable_data["course_count"],
        days_label=["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
        periods=list(range(1, 13)),
    )
