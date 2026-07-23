"""课程与排课模型"""
from datetime import datetime, timezone
from selectcourse.extensions import db


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default="")
    teacher = db.Column(db.String(64), nullable=False)
    credits = db.Column(db.Float, nullable=False, default=2.0)
    capacity = db.Column(db.Integer, nullable=False, default=60)
    enrolled_count = db.Column(db.Integer, nullable=False, default=0)
    semester = db.Column(db.String(16), nullable=False, default="2026-秋季")
    location = db.Column(db.String(128), default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # 关系
    schedules = db.relationship(
        "CourseSchedule", back_populates="course", cascade="all, delete-orphan"
    )
    selections = db.relationship("Selection", back_populates="course", lazy="dynamic")

    @property
    def available_slots(self) -> int:
        """剩余可选名额"""
        return max(0, self.capacity - self.enrolled_count)

    @property
    def is_full(self) -> bool:
        return self.enrolled_count >= self.capacity

    def has_time_conflict_with(self, other_course_id: int) -> bool:
        """检查与另一门课程是否有时间冲突（由 Selection 模型在选课时调用）"""
        from selectcourse.models.selection import Selection

        # 该方法在 Selection 模型中使用 SQL 查询来实现
        return False  # 占位，实际逻辑在 Selection 中

    def __repr__(self) -> str:
        return f"<Course {self.code} {self.name}>"


class CourseSchedule(db.Model):
    """课程时间安排"""
    __tablename__ = "course_schedules"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=周一 … 6=周日
    start_time = db.Column(db.String(8), nullable=False)  # "08:00"
    end_time = db.Column(db.String(8), nullable=False)  # "09:40"

    course = db.relationship("Course", back_populates="schedules")

    def __repr__(self) -> str:
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return f"<Schedule {days[self.day_of_week]} {self.start_time}-{self.end_time}>"
