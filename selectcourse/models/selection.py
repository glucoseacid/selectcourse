"""选课记录模型"""
from datetime import datetime, timedelta, timezone
from selectcourse.extensions import db

# 北京时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))


class Selection(db.Model):
    """学生选课记录（多对多关联表）"""
    __tablename__ = "selections"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    status = db.Column(
        db.String(16), nullable=False, default="enrolled"
    )  # enrolled | dropped
    enrolled_at = db.Column(db.DateTime, default=lambda: datetime.now(BEIJING_TZ))

    student = db.relationship("User", back_populates="selections")
    course = db.relationship("Course", back_populates="selections")

    __table_args__ = (
        db.UniqueConstraint(
            "student_id", "course_id", name="uq_student_course"
        ),
    )

    @staticmethod
    def has_time_conflict(student_id: int, course_id: int) -> bool:
        """检查学生在所选课程之间是否存在时间冲突"""
        from selectcourse.models.course import Course, CourseSchedule

        # 获取目标课程的时间安排
        target_schedules = (
            db.session.query(CourseSchedule)
            .filter(CourseSchedule.course_id == course_id)
            .all()
        )
        if not target_schedules:
            return False  # 无时间安排的课程不产生冲突

        # 获取学生已选课程的时间安排
        enrolled_schedules = (
            db.session.query(CourseSchedule)
            .join(Course)
            .join(Selection, Selection.course_id == Course.id)
            .filter(
                Selection.student_id == student_id,
                Selection.status == "enrolled",
            )
            .all()
        )

        for target in target_schedules:
            for enrolled in enrolled_schedules:
                if target.day_of_week == enrolled.day_of_week:
                    # 时间段重叠检测
                    if target.start_time < enrolled.end_time and target.end_time > enrolled.start_time:
                        return True
        return False

    def __repr__(self) -> str:
        return f"<Selection student={self.student_id} course={self.course_id} [{self.status}]>"
