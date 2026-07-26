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

    @staticmethod
    def _time_to_minutes(time_str: str) -> int:
        """将 HH:MM 字符串转换为分钟数"""
        parts = time_str.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])

    @classmethod
    def has_overlap(cls, schedules: list[dict]) -> tuple[bool, str | None]:
        """检查多个时间段是否存在重合。
        
        Args:
            schedules: 时间段列表，每项含 day_of_week, start_time, end_time
        
        Returns:
            (has_overlap, error_message) — 无重合时返回 (False, None)
        """
        for i, s1 in enumerate(schedules):
            d1 = int(s1["day_of_week"])
            t1_start = cls._time_to_minutes(s1["start_time"])
            t1_end = cls._time_to_minutes(s1["end_time"])
            if t1_end <= t1_start:
                days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                return True, f"{days[d1]} {s1['start_time']}-{s1['end_time']} 结束时间必须晚于开始时间"
            for j in range(i + 1, len(schedules)):
                s2 = schedules[j]
                d2 = int(s2["day_of_week"])
                if d1 != d2:
                    continue
                t2_start = cls._time_to_minutes(s2["start_time"])
                t2_end = cls._time_to_minutes(s2["end_time"])
                # 时间段重叠检测：不重合的条件是 A结束<=B开始 或 B结束<=A开始
                if t1_start < t2_end and t2_start < t1_end:
                    days_label = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                    return True, (
                        f"{days_label[d1]} {s1['start_time']}-{s1['end_time']} "
                        f"与 {s2['start_time']}-{s2['end_time']} 时间段重合"
                    )
        return False, None

    def __repr__(self) -> str:
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return f"<Schedule {days[self.day_of_week]} {self.start_time}-{self.end_time}>"
