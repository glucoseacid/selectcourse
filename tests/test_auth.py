"""认证模块测试"""
import pytest
from selectcourse.models.user import User


class TestRegistration:
    """用户注册测试"""

    def test_register_page_loads(self, client):
        response = client.get("/auth/register")
        assert response.status_code == 200
        assert "注册" in response.get_data(as_text=True)

    def test_register_success(self, client, db):
        response = client.post("/auth/register", data={
            "username": "newstudent",
            "email": "new@test.edu",
            "password": "testpass123",
            "confirm_password": "testpass123",
        }, follow_redirects=True)
        assert response.status_code == 200
        assert "注册成功" in response.get_data(as_text=True)

        user = User.query.filter_by(username="newstudent").first()
        assert user is not None
        assert user.email == "new@test.edu"
        assert user.role == "student"

    def test_register_duplicate_username(self, client, student_user):
        response = client.post("/auth/register", data={
            "username": "teststudent",
            "email": "another@test.edu",
            "password": "testpass123",
            "confirm_password": "testpass123",
        })
        assert "已被使用" in response.get_data(as_text=True)

    def test_register_duplicate_email(self, client, student_user):
        response = client.post("/auth/register", data={
            "username": "another",
            "email": "student@test.edu",
            "password": "testpass123",
            "confirm_password": "testpass123",
        })
        assert "已被注册" in response.get_data(as_text=True)

    def test_register_password_mismatch(self, client):
        response = client.post("/auth/register", data={
            "username": "newstudent",
            "email": "new@test.edu",
            "password": "testpass123",
            "confirm_password": "wrongpass",
        })
        assert response.status_code == 200
        assert "不一致" in response.get_data(as_text=True)

    def test_register_short_password(self, client):
        response = client.post("/auth/register", data={
            "username": "newstudent",
            "email": "new@test.edu",
            "password": "12345",
            "confirm_password": "12345",
        })
        assert "至少 6 位" in response.get_data(as_text=True)


class TestLogin:
    """用户登录测试"""

    def test_login_page_loads(self, client):
        response = client.get("/auth/login")
        assert response.status_code == 200
        assert "登录" in response.get_data(as_text=True)

    def test_login_success_student(self, client, student_user):
        response = client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        }, follow_redirects=True)
        assert response.status_code == 200
        # 学生应重定向到课程列表
        assert "课程列表" in response.get_data(as_text=True)

    def test_login_success_admin(self, client, admin_user):
        response = client.post("/auth/login", data={
            "username": "admin",
            "password": "admin123",
        }, follow_redirects=True)
        assert response.status_code == 200
        # 管理员应重定向到后台
        assert "管理后台" in response.get_data(as_text=True)

    def test_login_wrong_password(self, client, student_user):
        response = client.post("/auth/login", data={
            "username": "teststudent",
            "password": "wrongpassword",
        }, follow_redirects=True)
        assert "用户名或密码错误" in response.get_data(as_text=True)

    def test_login_nonexistent_user(self, client):
        response = client.post("/auth/login", data={
            "username": "nobody",
            "password": "whatever",
        }, follow_redirects=True)
        assert "用户名或密码错误" in response.get_data(as_text=True)


class TestLogout:
    """登出测试"""

    def test_logout(self, client, student_user):
        # 先登录
        client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        })
        response = client.get("/auth/logout", follow_redirects=True)
        assert "已安全退出" in response.get_data(as_text=True)


class TestAccessControl:
    """访问控制测试"""

    def test_unauthenticated_redirect(self, client):
        """未登录用户访问受保护页面应重定向"""
        response = client.get("/course/", follow_redirects=True)
        assert "请先登录" in response.get_data(as_text=True)

    def test_student_cannot_access_admin(self, client, student_user):
        """学生无法访问管理后台"""
        client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        })
        response = client.get("/admin/", follow_redirects=True)
        assert "需要管理员权限" in response.get_data(as_text=True)
