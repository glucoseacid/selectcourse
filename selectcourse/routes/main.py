"""主页路由"""
from flask import Blueprint, render_template
from selectcourse.models.course import Course

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    courses = Course.query.order_by(Course.created_at.desc()).limit(6).all()
    return render_template("index.html", courses=courses)
