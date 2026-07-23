"""管理员功能测试"""
import pytest
from selectcourse.models.user import User


class TestAdminDashboard:
    """管理后台测试"""

    def test_dashboard_access(self, login_admin):
        response = login_admin.get("/admin/")
        assert response.status_code == 200
        assert "管理后台" in response.get_data(as_text=True)

    def test_unauthorized_access(self, client, student_user):
        client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        })
        response = client.get("/admin/", follow_redirects=True)
        assert "需要管理员权限" in response.get_data(as_text=True)


class TestAdminCourseManagement:
    """管理员课程管理测试"""

    def test_manage_courses_page(self, login_admin, sample_course):
        response = login_admin.get("/admin/courses")
        assert response.status_code == 200
        assert "Python 程序设计" in response.get_data(as_text=True)

    def test_create_course(self, login_admin):
        response = login_admin.post("/admin/courses/create", data={
            "name": "新课程",
            "code": "NEW101",
            "teacher": "陈教授",
            "credits": 2.0,
            "capacity": 50,
            "semester": "2026-秋季",
            "location": "教学楼C-101",
            "description": "测试课程",
            "day_of_week": 3,
            "start_time": "10:00",
            "end_time": "11:40",
        }, follow_redirects=True)
        assert response.status_code == 200
        assert "创建成功" in response.get_data(as_text=True)

        from selectcourse.models.course import Course
        course = Course.query.filter_by(code="NEW101").first()
        assert course is not None
        assert len(course.schedules) == 1

    def test_edit_course(self, login_admin, sample_course):
        response = login_admin.post(f"/admin/courses/{sample_course.id}/edit", data={
            "name": "Python 高级编程",
            "code": "CS101",
            "teacher": "张教授",
            "credits": 4.0,
            "capacity": 60,
            "semester": "2026-秋季",
            "location": "教学楼A-301",
            "description": "更新后的描述",
            "day_of_week": 1,
            "start_time": "08:00",
            "end_time": "09:40",
        }, follow_redirects=True)
        assert response.status_code == 200
        assert "更新成功" in response.get_data(as_text=True)

    def test_delete_course(self, login_admin, sample_course):
        response = login_admin.post(
            f"/admin/courses/{sample_course.id}/delete",
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "已删除" in response.get_data(as_text=True)

        from selectcourse.models.course import Course
        assert Course.query.get(sample_course.id) is None


class TestAdminStudentManagement:
    """管理员学生管理测试"""

    def test_manage_students_page(self, login_admin, student_user):
        response = login_admin.get("/admin/students")
        assert response.status_code == 200
        assert "teststudent" in response.get_data(as_text=True)
