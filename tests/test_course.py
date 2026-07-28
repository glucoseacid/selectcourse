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

    def test_re_enroll_after_drop(self, client, enrolled_student, sample_course):
        """退课后重新选课"""
        # 先退课
        client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        })
        client.post(f"/course/{sample_course.id}/drop", follow_redirects=True)

        # 重新选课
        response = client.post(
            f"/course/{sample_course.id}/enroll",
            follow_redirects=True,
        )
        assert "成功选择" in response.get_data(as_text=True)

        # 验证复用同一条记录，状态变回 enrolled
        from selectcourse.extensions import db as _db
        selections = Selection.query.filter_by(
            student_id=enrolled_student.id, course_id=sample_course.id
        ).all()
        assert len(selections) == 1  # 只有一条记录，没有重复插入
        assert selections[0].status == "enrolled"

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


class TestTimetable:
    """课表视图测试"""

    def test_timetable_page_requires_login(self, client):
        """课表页面需要登录"""
        response = client.get("/course/timetable", follow_redirects=True)
        assert "请先登录" in response.get_data(as_text=True)

    def test_timetable_shows_enrolled_courses(self, client, enrolled_student, sample_course):
        """课表页显示已选课程"""
        client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        })
        response = client.get("/course/timetable")
        assert response.status_code == 200
        content = response.get_data(as_text=True)
        assert "Python 程序设计" in content
        assert "CS101" in content

    def test_timetable_semester_filter(self, client, enrolled_student, sample_course, db):
        """课表学期筛选"""
        # 创建另一学期的课程
        course2 = Course(
            name="高等数学", code="MATH101", teacher="陈教授",
            credits=4.0, capacity=60, semester="2027-春季",
        )
        db.session.add(course2)
        db.session.flush()
        schedule2 = CourseSchedule(
            course_id=course2.id, day_of_week=2, start_time="10:00", end_time="11:40",
        )
        db.session.add(schedule2)

        sel2 = Selection(
            student_id=enrolled_student.id, course_id=course2.id, status="enrolled",
        )
        db.session.add(sel2)
        db.session.commit()

        client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        })

        # 默认学期筛选
        response = client.get("/course/timetable")
        content = response.get_data(as_text=True)
        # 应有学期选择器
        assert '<select id="semester-select"' in content

        # 按学期筛选
        response2 = client.get("/course/timetable?semester=2027-春季")
        content2 = response2.get_data(as_text=True)
        assert "高等数学" in content2

    def test_timetable_empty_no_courses(self, login_student):
        """无选课时课表页仍可访问"""
        response = login_student.get("/course/timetable")
        assert response.status_code == 200
        assert "暂无已选课程" in response.get_data(as_text=True)

    def test_admin_redirected_from_timetable(self, login_admin):
        """管理员访问课表被重定向"""
        response = login_admin.get("/course/timetable", follow_redirects=False)
        assert response.status_code == 302


class TestPeriodMapping:
    """节次映射测试"""

    def test_period_for_time_morning(self):
        """上午时间映射"""
        assert CourseSchedule.period_for_time("08:00") == 1
        assert CourseSchedule.period_for_time("08:30") == 1
        assert CourseSchedule.period_for_time("08:50") == 2
        assert CourseSchedule.period_for_time("09:20") == 2
        assert CourseSchedule.period_for_time("10:30") == 3

    def test_period_for_time_afternoon(self):
        """下午时间映射"""
        assert CourseSchedule.period_for_time("14:00") == 5
        assert CourseSchedule.period_for_time("15:20") == 6
        assert CourseSchedule.period_for_time("16:30") == 7

    def test_period_for_time_evening(self):
        """晚上时间映射"""
        assert CourseSchedule.period_for_time("19:00") == 9
        assert CourseSchedule.period_for_time("20:20") == 10
        assert CourseSchedule.period_for_time("21:50") == 12

    def test_period_range_two_periods(self):
        """两节课的时间段"""
        start, end = CourseSchedule.period_range("08:00", "09:40")
        assert start == 1
        # 09:40 处于 09:35~10:00 的间隙，应在第2节
        assert end == 2

    def test_period_range_single_period(self):
        """单节课的时间段"""
        start, end = CourseSchedule.period_range("10:00", "10:45")
        assert start == 3
        assert end == 3

    def test_period_range_three_periods(self):
        """三节课的时间段"""
        start, end = CourseSchedule.period_range("14:00", "16:45")
        assert start == 5
        assert end == 7


# 辅助函数
def db_session_get(course_id):
    from selectcourse.extensions import db
    from selectcourse.models.course import Course
    return db.session.get(Course, course_id)
