"""课程分类模型"""
from datetime import datetime, timezone
from selectcourse.extensions import db


class CourseCategory(db.Model):
    """课程分类（管理员可增删）"""
    __tablename__ = "course_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # 关系：一个分类下有多门课程
    courses = db.relationship("Course", back_populates="category", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<CourseCategory {self.name}>"
