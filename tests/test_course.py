"""课程与选课测试"""
import pytest
from selectcourse.models.course import Course, CourseSchedule
from selectcourse.models.selection import Selection


class TestCourseList:
    """课程列表测试"""

    def test_list_page_requires_login(self, client):
        response = client.get("/course/", follow_redirects=True)
        assert "请先登录" in response.get_data(as_text=True)

    def test_list_shows_courses(self, login_student, sample_course):
        response = login_student.get("/course/")
        assert response.status_code == 200
        assert "Python 程序设计" in response.get_data(as_text=True)

    def test_list_search(self, login_student, sample_course, another_course):
        response = login_student.get("/course/?search=Python")
        assert "Python 程序设计" in response.get_data(as_text=True)
        assert "Java 程序设计" not in response.get_data(as_text=True)

    def test_list_semester_filter(self, login_student, sample_course):
        response = login_student.get("/course/?semester=2026-秋季")
        assert "Python 程序设计" in response.get_data(as_text=True)


class TestCourseDetail:
    """课程详情测试"""

    def test_detail_page(self, login_student, sample_course):
        response = login_student.get(f"/course/{sample_course.id}")
        assert response.status_code == 200
        assert "Python 程序设计" in response.get_data(as_text=True)
        assert "CS101" in response.get_data(as_text=True)

    def test_detail_not_found(self, login_student):
        response = login_student.get("/course/9999", follow_redirects=True)
        assert "课程不存在" in response.get_data(as_text=True)


class TestEnrollment:
    """选课功能测试"""

    def test_enroll_success(self, client, student_user, sample_course):
        """正常选课"""
        client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        })
        response = client.post(
            f"/course/{sample_course.id}/enroll",
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "成功选择" in response.get_data(as_text=True)

        # 验证选课记录
        selection = Selection.query.filter_by(
            student_id=student_user.id, course_id=sample_course.id
        ).first()
        assert selection is not None
        assert selection.status == "enrolled"

        # 验证 enrolled_count 增加
        course = db_session_get(sample_course.id)
        assert course.enrolled_count == 1

    def test_enroll_duplicate(self, client, enrolled_student, sample_course):
        """重复选课"""
        client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        })
        response = client.post(
            f"/course/{sample_course.id}/enroll",
            follow_redirects=True,
        )
        assert "已选择该课程" in response.get_data(as_text=True)

    def test_enroll_full_course(self, client, student_user, db):
        """选课时课程已满"""
        # 创建一个容量为 1 且已满的课程
        course = Course(
            name="满员课程", code="CS999", teacher="王教授",
            credits=2.0, capacity=1, enrolled_count=1, semester="2026-秋季"
        )
        db.session.add(course)
        db.session.commit()

        client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        })
        response = client.post(
            f"/course/{course.id}/enroll",
            follow_redirects=True,
        )
        assert "名额已满" in response.get_data(as_text=True)

    def test_admin_cannot_enroll(self, login_admin, sample_course):
        """管理员不能选课"""
        response = login_admin.post(
            f"/course/{sample_course.id}/enroll",
            follow_redirects=True,
        )
        assert "管理员不能选课" in response.get_data(as_text=True)


class TestDrop:
    """退课功能测试"""

    def test_drop_success(self, client, enrolled_student, sample_course):
        """正常退课"""
        client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        })
        response = client.post(
            f"/course/{sample_course.id}/drop",
            follow_redirects=True,
        )
        assert "已退选" in response.get_data(as_text=True)

        selection = Selection.query.filter_by(
            student_id=enrolled_student.id, course_id=sample_course.id
        ).first()
        assert selection.status == "dropped"

    def test_drop_not_enrolled(self, login_student, sample_course):
        """退选未选的课程"""
        response = login_student.post(
            f"/course/{sample_course.id}/drop",
            follow_redirects=True,
        )
        assert "未选择该课程" in response.get_data(as_text=True)


class TestTimeConflict:
    """时间冲突检测测试"""

    def test_detect_conflict(self, db, student_user, sample_course, another_course):
        """检测时间冲突"""
        # 先选 CS101 (周二 08:00-09:40)
        selection = Selection(
            student_id=student_user.id,
            course_id=sample_course.id,
            status="enrolled",
        )
        sample_course.enrolled_count = 1
        db.session.add(selection)
        db.session.commit()

        # CS102 (周二 08:30-10:00) 应冲突
        assert Selection.has_time_conflict(student_user.id, another_course.id) is True

    def test_no_conflict_different_days(self, db, student_user, sample_course):
        """不同天不应该冲突"""
        # 创建周三的课程
        course = Course(
            name="数据结构", code="CS201", teacher="赵教授",
            credits=3.0, capacity=60, semester="2026-秋季"
        )
        db.session.add(course)
        db.session.flush()
        from selectcourse.models.course import CourseSchedule
        schedule = CourseSchedule(
            course_id=course.id,
            day_of_week=2,  # 周三
            start_time="08:00",
            end_time="09:40",
        )
        db.session.add(schedule)

        selection = Selection(
            student_id=student_user.id,
            course_id=sample_course.id,
            status="enrolled",
        )
        sample_course.enrolled_count = 1
        db.session.add(selection)
        db.session.commit()

        assert Selection.has_time_conflict(student_user.id, course.id) is False


class TestScheduleOverlap:
    """时间段重合检测测试"""

    def test_no_overlap_different_days(self):
        """不同天不重合"""
        has_overlap, msg = CourseSchedule.has_overlap([
            {"day_of_week": 0, "start_time": "08:00", "end_time": "09:40"},
            {"day_of_week": 2, "start_time": "08:00", "end_time": "09:40"},
        ])
        assert has_overlap is False
        assert msg is None

    def test_no_overlap_same_day_non_overlapping(self):
        """同天不重合时间段"""
        has_overlap, msg = CourseSchedule.has_overlap([
            {"day_of_week": 1, "start_time": "08:00", "end_time": "09:40"},
            {"day_of_week": 1, "start_time": "10:00", "end_time": "11:40"},
        ])
        assert has_overlap is False

    def test_no_overlap_adjacent(self):
        """同天紧邻时间段（不重合）"""
        has_overlap, msg = CourseSchedule.has_overlap([
            {"day_of_week": 1, "start_time": "08:00", "end_time": "09:40"},
            {"day_of_week": 1, "start_time": "09:40", "end_time": "11:20"},
        ])
        assert has_overlap is False

    def test_overlap_same_day_partial(self):
        """同天部分重合"""
        has_overlap, msg = CourseSchedule.has_overlap([
            {"day_of_week": 1, "start_time": "08:00", "end_time": "10:00"},
            {"day_of_week": 1, "start_time": "09:00", "end_time": "11:00"},
        ])
        assert has_overlap is True
        assert "重合" in msg

    def test_overlap_same_day_contained(self):
        """同天完全包含"""
        has_overlap, msg = CourseSchedule.has_overlap([
            {"day_of_week": 1, "start_time": "08:00", "end_time": "12:00"},
            {"day_of_week": 1, "start_time": "09:00", "end_time": "10:00"},
        ])
        assert has_overlap is True

    def test_invalid_end_before_start(self):
        """结束时间早于开始时间"""
        has_overlap, msg = CourseSchedule.has_overlap([
            {"day_of_week": 1, "start_time": "10:00", "end_time": "08:00"},
        ])
        assert has_overlap is True
        assert "结束时间必须晚于开始时间" in msg

    def test_multiple_schedules_no_overlap(self):
        """三个时间段无重合"""
        has_overlap, msg = CourseSchedule.has_overlap([
            {"day_of_week": 0, "start_time": "08:00", "end_time": "09:40"},
            {"day_of_week": 2, "start_time": "10:00", "end_time": "11:40"},
            {"day_of_week": 4, "start_time": "14:00", "end_time": "15:40"},
        ])
        assert has_overlap is False

    def test_empty_schedules(self):
        """空列表不报错"""
        has_overlap, msg = CourseSchedule.has_overlap([])
        assert has_overlap is False
        assert msg is None


class TestMyCourses:
    """我的选课测试"""

    def test_my_courses_page(self, client, enrolled_student, sample_course):
        client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        })
        response = client.get("/course/my-courses")
        assert response.status_code == 200
        assert "Python 程序设计" in response.get_data(as_text=True)


# 辅助函数
def db_session_get(course_id):
    from selectcourse.extensions import db
    from selectcourse.models.course import Course
    return db.session.get(Course, course_id)
