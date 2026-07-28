"""管理员功能测试"""
import io
import json
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
            "schedules_json": json.dumps([
                {"day_of_week": 3, "start_time": "10:00", "end_time": "11:40"},
            ]),
        }, follow_redirects=True)
        assert response.status_code == 200
        assert "创建成功" in response.get_data(as_text=True)

        from selectcourse.models.course import Course
        course = Course.query.filter_by(code="NEW101").first()
        assert course is not None
        assert len(course.schedules) == 1

    def test_create_course_multi_schedule(self, login_admin):
        """创建包含多个时间段的课程"""
        response = login_admin.post("/admin/courses/create", data={
            "name": "多时间段课程",
            "code": "MULTI101",
            "teacher": "李教授",
            "credits": 3.0,
            "capacity": 60,
            "semester": "2026-秋季",
            "location": "教学楼E-101",
            "schedules_json": json.dumps([
                {"day_of_week": 0, "start_time": "08:00", "end_time": "09:40"},
                {"day_of_week": 2, "start_time": "10:00", "end_time": "11:40"},
            ]),
        }, follow_redirects=True)
        assert response.status_code == 200
        assert "创建成功" in response.get_data(as_text=True)

        from selectcourse.models.course import Course
        course = Course.query.filter_by(code="MULTI101").first()
        assert course is not None
        assert len(course.schedules) == 2

    def test_create_course_schedule_overlap(self, login_admin):
        """创建课程时时间段重合应被拒绝"""
        response = login_admin.post("/admin/courses/create", data={
            "name": "冲突课程",
            "code": "CONFLICT",
            "teacher": "张教授",
            "credits": 2.0,
            "capacity": 50,
            "semester": "2026-秋季",
            "schedules_json": json.dumps([
                {"day_of_week": 1, "start_time": "08:00", "end_time": "10:00"},
                {"day_of_week": 1, "start_time": "09:00", "end_time": "11:00"},
            ]),
        }, follow_redirects=True)
        assert response.status_code == 200
        assert "时间段冲突" in response.get_data(as_text=True)

        from selectcourse.models.course import Course
        assert Course.query.filter_by(code="CONFLICT").first() is None

    def test_create_course_invalid_schedule_time(self, login_admin):
        """创建课程时结束时间不晚于开始时间应被拒绝"""
        response = login_admin.post("/admin/courses/create", data={
            "name": "错误时间课程",
            "code": "BADTIME",
            "teacher": "王教授",
            "credits": 2.0,
            "capacity": 50,
            "semester": "2026-秋季",
            "schedules_json": json.dumps([
                {"day_of_week": 1, "start_time": "10:00", "end_time": "08:00"},
            ]),
        }, follow_redirects=True)
        assert response.status_code == 200
        assert "时间段冲突" in response.get_data(as_text=True)

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
            "schedules_json": json.dumps([
                {"day_of_week": 1, "start_time": "08:00", "end_time": "09:40"},
            ]),
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

    def test_manage_students_page_has_action_buttons(self, login_admin, student_user):
        """学生列表页面包含操作按钮"""
        response = login_admin.get("/admin/students")
        html = response.get_data(as_text=True)
        assert "查看详情" in html or "📋" in html
        assert "编辑信息" in html or "✏️" in html
        assert "修改密码" in html or "🔑" in html

    # ---- 学生详情 ----

    def test_student_detail_page(self, login_admin, student_user):
        """查看学生详情页面"""
        response = login_admin.get(f"/admin/students/{student_user.id}")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "teststudent" in html
        assert "student@test.edu" in html

    def test_student_detail_shows_selections(self, login_admin, enrolled_student, sample_course):
        """学生详情页显示选课记录"""
        response = login_admin.get(f"/admin/students/{enrolled_student.id}")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert sample_course.name in html

    def test_student_detail_not_found(self, login_admin):
        """查看不存在的学生返回列表"""
        response = login_admin.get("/admin/students/99999", follow_redirects=True)
        assert response.status_code == 200
        assert "不存在" in response.get_data(as_text=True)

    def test_student_detail_not_student_role(self, login_admin, admin_user):
        """查看管理员角色的用户应重定向"""
        response = login_admin.get(f"/admin/students/{admin_user.id}", follow_redirects=True)
        assert response.status_code == 200
        assert "不存在" in response.get_data(as_text=True)

    def test_student_detail_unauthorized(self, client, student_user):
        """非管理员无法查看学生详情"""
        client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        })
        response = client.get(f"/admin/students/{student_user.id}", follow_redirects=True)
        assert "需要管理员权限" in response.get_data(as_text=True)

    # ---- 编辑学生信息 ----

    def test_edit_student_page(self, login_admin, student_user):
        """编辑学生信息页面"""
        response = login_admin.get(f"/admin/students/{student_user.id}/edit")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "teststudent" in html
        assert "student@test.edu" in html

    def test_edit_student_success(self, login_admin, student_user):
        """成功修改学生信息"""
        response = login_admin.post(
            f"/admin/students/{student_user.id}/edit",
            data={
                "username": "updatedstudent",
                "email": "updated@test.edu",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "已更新" in response.get_data(as_text=True)

        from selectcourse.models.user import User
        u = User.query.get(student_user.id)
        assert u.username == "updatedstudent"
        assert u.email == "updated@test.edu"

    def test_edit_student_duplicate_username(self, login_admin, student_user, db):
        """修改为已存在的用户名应报错"""
        # 创建第二个学生
        other = User(username="otherstudent", email="other@test.edu", role="student")
        other.set_password("pass123")
        db.session.add(other)
        db.session.commit()

        response = login_admin.post(
            f"/admin/students/{student_user.id}/edit",
            data={
                "username": "otherstudent",
                "email": "student@test.edu",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "已被使用" in response.get_data(as_text=True)

    def test_edit_student_duplicate_email(self, login_admin, student_user, db):
        """修改为已存在的邮箱应报错"""
        other = User(username="otherstudent", email="other@test.edu", role="student")
        other.set_password("pass123")
        db.session.add(other)
        db.session.commit()

        response = login_admin.post(
            f"/admin/students/{student_user.id}/edit",
            data={
                "username": "teststudent",
                "email": "other@test.edu",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "已被使用" in response.get_data(as_text=True)

    def test_edit_student_not_found(self, login_admin):
        """编辑不存在学生"""
        response = login_admin.get("/admin/students/99999/edit", follow_redirects=True)
        assert response.status_code == 200
        assert "不存在" in response.get_data(as_text=True)

    # ---- 修改学生密码 ----

    def test_change_password_page(self, login_admin, student_user):
        """修改密码页面"""
        response = login_admin.get(f"/admin/students/{student_user.id}/change-password")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "修改密码" in html or "新密码" in html

    def test_change_password_success(self, login_admin, student_user, client):
        """成功修改学生密码"""
        response = login_admin.post(
            f"/admin/students/{student_user.id}/change-password",
            data={
                "new_password": "newpass123",
                "confirm_password": "newpass123",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "密码已修改" in response.get_data(as_text=True)

        # 验证新密码可登录
        client.get("/auth/logout")
        login_resp = client.post("/auth/login", data={
            "username": "teststudent",
            "password": "newpass123",
        }, follow_redirects=True)
        assert "teststudent" in login_resp.get_data(as_text=True)

    def test_change_password_mismatch(self, login_admin, student_user):
        """两次密码不一致应报错"""
        response = login_admin.post(
            f"/admin/students/{student_user.id}/change-password",
            data={
                "new_password": "newpass123",
                "confirm_password": "different456",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "不一致" in response.get_data(as_text=True) or "错误" in response.get_data(as_text=True)

    def test_change_password_too_short(self, login_admin, student_user):
        """密码太短应报错"""
        response = login_admin.post(
            f"/admin/students/{student_user.id}/change-password",
            data={
                "new_password": "12345",
                "confirm_password": "12345",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "6" in response.get_data(as_text=True) or "错误" in response.get_data(as_text=True)

    # ---- 删除学生 ----

    def test_delete_student_success(self, login_admin, student_user):
        """成功删除学生"""
        response = login_admin.post(
            f"/admin/students/{student_user.id}/delete",
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "已删除" in response.get_data(as_text=True)

        from selectcourse.models.user import User
        assert User.query.get(student_user.id) is None

    def test_delete_student_clears_selections(self, login_admin, enrolled_student, sample_course):
        """删除学生同时清除其选课记录并恢复课程容量"""
        sid = enrolled_student.id
        assert sample_course.enrolled_count == 1

        response = login_admin.post(
            f"/admin/students/{sid}/delete",
            follow_redirects=True,
        )
        assert response.status_code == 200

        from selectcourse.models.user import User
        from selectcourse.models.selection import Selection
        from selectcourse.models.course import Course

        assert User.query.get(sid) is None
        assert Selection.query.filter_by(student_id=sid).count() == 0
        course = Course.query.get(sample_course.id)
        assert course.enrolled_count == 0

    def test_delete_student_not_found(self, login_admin):
        """删除不存在学生"""
        response = login_admin.post(
            "/admin/students/99999/delete",
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "不存在" in response.get_data(as_text=True)

    def test_delete_student_unauthorized(self, client, student_user):
        """非管理员不能删除学生"""
        client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        })
        response = client.post(
            f"/admin/students/{student_user.id}/delete",
            follow_redirects=True,
        )
        assert "需要管理员权限" in response.get_data(as_text=True)


class TestAdminCourseImport:
    """管理员批量导入课程测试"""

    def test_import_page_access(self, login_admin):
        """导入页面可访问"""
        response = login_admin.get("/admin/courses/import")
        assert response.status_code == 200
        assert "批量导入课程" in response.get_data(as_text=True)
        assert "CSV" in response.get_data(as_text=True)

    def test_import_unauthorized(self, client, student_user):
        """非管理员无法访问导入页"""
        client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        })
        response = client.get("/admin/courses/import", follow_redirects=True)
        assert "需要管理员权限" in response.get_data(as_text=True)

    def test_import_csv_success(self, login_admin, client):
        """CSV 导入成功"""
        csv_content = (
            "课程名称,课程编号,授课教师,学分,容量,学期,上课地点,上课日,开始时间,结束时间\n"
            "高等数学,MATH201,赵教授,4.0,80,2026-秋季,教学楼D-201,0,08:00,09:40\n"
            "线性代数,MATH202,钱教授,3.0,60,2026-秋季,教学楼D-301,2,10:00,11:40\n"
        )
        data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "courses.csv")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        text = response.get_data(as_text=True)
        assert "成功导入" in text
        assert "2" in text  # 成功导入 2 门

        from selectcourse.models.course import Course
        assert Course.query.filter_by(code="MATH201").first() is not None
        assert Course.query.filter_by(code="MATH202").first() is not None

    def test_import_csv_chinese_headers(self, login_admin):
        """CSV 中文表头导入"""
        csv_content = (
            "课程名称,课程编号,授课教师,学分,容量,学期\n"
            "大学物理,PHY101,孙教授,3.5,50,2026-秋季\n"
        )
        data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "courses.csv")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "成功导入 1" in response.get_data(as_text=True)

        from selectcourse.models.course import Course
        c = Course.query.filter_by(code="PHY101").first()
        assert c is not None
        assert c.name == "大学物理"

    def test_import_json_success(self, login_admin):
        """JSON 导入成功"""
        json_content = json.dumps([
            {
                "name": "数据结构",
                "code": "CS201",
                "teacher": "周教授",
                "credits": 3.0,
                "capacity": 70,
                "semester": "2026-秋季",
                "description": "数据结构与算法",
                "day_of_week": 3,
                "start_time": "14:00",
                "end_time": "15:40",
            },
        ])
        data = {"file": (io.BytesIO(json_content.encode("utf-8")), "courses.json")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "成功导入 1" in response.get_data(as_text=True)

        from selectcourse.models.course import Course
        c = Course.query.filter_by(code="CS201").first()
        assert c is not None
        assert c.description == "数据结构与算法"
        assert len(c.schedules) == 1

    def test_import_json_wrapped(self, login_admin):
        """JSON courses 包裹格式导入"""
        json_content = json.dumps({
            "courses": [
                {
                    "name": "操作系统",
                    "code": "CS301",
                    "teacher": "吴教授",
                    "credits": 3.0,
                    "capacity": 55,
                    "semester": "2026-秋季",
                },
            ]
        })
        data = {"file": (io.BytesIO(json_content.encode("utf-8")), "courses.json")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "成功导入 1" in response.get_data(as_text=True)

    def test_import_excel_success(self, login_admin):
        """Excel 导入成功"""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["课程名称", "课程编号", "授课教师", "学分", "容量", "学期", "上课地点"])
        ws.append(["编译原理", "CS401", "郑教授", 3.0, 40, "2026-秋季", "教学楼E-101"])
        ws.append(["计算机网络", "CS402", "冯教授", 3.5, 45, "2026-秋季", "教学楼E-201"])

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        data = {"file": (buf, "courses.xlsx")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "成功导入 2" in response.get_data(as_text=True)

        from selectcourse.models.course import Course
        assert Course.query.filter_by(code="CS401").first() is not None
        assert Course.query.filter_by(code="CS402").first() is not None

    def test_import_duplicate_code(self, login_admin, sample_course):
        """重复编号跳过"""
        csv_content = (
            "课程名称,课程编号,授课教师,学分,容量,学期\n"
            "Python 程序设计,CS101,张教授,3.0,60,2026-秋季\n"  # CS101 已存在
        )
        data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "courses.csv")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        text = response.get_data(as_text=True)
        assert "已存在" in text or "跳过" in text

    def test_import_missing_required_field(self, login_admin):
        """缺少必填字段报错"""
        csv_content = (
            "课程名称,课程编号,授课教师,学分,学期\n"  # 缺 capacity
            "测试课,TEST01,教师A,2.0,2026-秋季\n"
        )
        data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "courses.csv")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        text = response.get_data(as_text=True)
        assert "缺少必填字段" in text or "跳过" in text

    def test_import_invalid_credits(self, login_admin):
        """无效学分报错"""
        csv_content = (
            "课程名称,课程编号,授课教师,学分,容量,学期\n"
            "测试课,TEST02,教师B,abc,60,2026-秋季\n"
        )
        data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "courses.csv")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        text = response.get_data(as_text=True)
        assert "学分格式无效" in text or "跳过" in text

    def test_import_invalid_day_of_week(self, login_admin):
        """无效上课日报错"""
        csv_content = (
            "课程名称,课程编号,授课教师,学分,容量,学期,上课日\n"
            "测试课,TEST03,教师C,3.0,60,2026-秋季,9\n"
        )
        data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "courses.csv")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        text = response.get_data(as_text=True)
        assert "上课日" in text or "跳过" in text

    def test_import_no_file(self, login_admin):
        """未选择文件报错"""
        data = {"file": (io.BytesIO(b"dummy"), "")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        # 表单验证应报错
        text = response.get_data(as_text=True)
        assert "请选择" in text or "错误" in text

    def test_import_empty_csv(self, login_admin):
        """空文件提示"""
        csv_content = "课程名称,课程编号,授课教师,学分,容量,学期\n"  # 仅表头
        data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "courses.csv")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        text = response.get_data(as_text=True)
        assert "没有数据" in text

    def test_import_json_multi_schedule(self, login_admin):
        """JSON 导入多时间段课程"""
        schedules = [
            {"day_of_week": 0, "start_time": "08:00", "end_time": "09:40"},
            {"day_of_week": 2, "start_time": "10:00", "end_time": "11:40"},
        ]
        json_content = json.dumps([
            {
                "name": "多段课程",
                "code": "MULTI200",
                "teacher": "陈教授",
                "credits": 3.0,
                "capacity": 50,
                "semester": "2026-秋季",
                "schedules": json.dumps(schedules),
            },
        ])
        data = {"file": (io.BytesIO(json_content.encode("utf-8")), "courses.json")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "成功导入 1" in response.get_data(as_text=True)

        from selectcourse.models.course import Course
        c = Course.query.filter_by(code="MULTI200").first()
        assert c is not None
        assert len(c.schedules) == 2

    def test_import_csv_multi_schedule(self, login_admin):
        """CSV 导入多时间段课程"""
        import csv
        schedules = json.dumps([
            {"day_of_week": 1, "start_time": "08:00", "end_time": "09:40"},
            {"day_of_week": 3, "start_time": "14:00", "end_time": "15:40"},
        ])
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["课程名称", "课程编号", "授课教师", "学分", "容量", "学期", "时间段"])
        writer.writerow(["英语听说", "ENG201", "李教授", "2.0", "40", "2026-秋季", schedules])
        buf.seek(0)
        data = {"file": (io.BytesIO(buf.getvalue().encode("utf-8")), "courses.csv")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "成功导入 1" in response.get_data(as_text=True)

        from selectcourse.models.course import Course
        c = Course.query.filter_by(code="ENG201").first()
        assert c is not None
        assert len(c.schedules) == 2

    def test_import_schedules_conflict(self, login_admin):
        """导入时多时间段冲突应被拒绝"""
        import csv
        schedules = json.dumps([
            {"day_of_week": 1, "start_time": "08:00", "end_time": "10:00"},
            {"day_of_week": 1, "start_time": "09:00", "end_time": "11:00"},
        ])
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["课程名称", "课程编号", "授课教师", "学分", "容量", "学期", "时间段"])
        writer.writerow(["冲突课程", "CONF01", "王教授", "3.0", "60", "2026-秋季", schedules])
        buf.seek(0)
        data = {"file": (io.BytesIO(buf.getvalue().encode("utf-8")), "courses.csv")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        text = response.get_data(as_text=True)
        assert "时间段冲突" in text or "跳过" in text
        # 确认未导入
        from selectcourse.models.course import Course
        assert Course.query.filter_by(code="CONF01").first() is None

    def test_import_csv_with_category(self, login_admin, sample_category):
        """CSV 导入时包含课程分类"""
        csv_content = (
            "课程名称,课程编号,授课教师,学分,容量,学期,课程分类\n"
            "马克思主义原理,MARX101,周教授,3.0,80,2026-秋季,必修课程\n"
        )
        data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "courses.csv")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "成功导入 1" in response.get_data(as_text=True)

        from selectcourse.models.course import Course
        c = Course.query.filter_by(code="MARX101").first()
        assert c is not None
        assert c.category_id is not None
        assert c.category.name == "必修课程"

    def test_import_json_with_category(self, login_admin, sample_category):
        """JSON 导入时包含课程分类"""
        json_content = json.dumps([
            {
                "name": "体育健康",
                "code": "PE101",
                "teacher": "吴教授",
                "credits": 1.0,
                "capacity": 40,
                "semester": "2026-秋季",
                "category_name": "体育分项",
            },
        ])
        data = {"file": (io.BytesIO(json_content.encode("utf-8")), "courses.json")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "成功导入 1" in response.get_data(as_text=True)

        from selectcourse.models.course import Course
        c = Course.query.filter_by(code="PE101").first()
        assert c is not None
        assert c.category is not None
        assert c.category.name == "体育分项"

    def test_import_unknown_category_warns(self, login_admin):
        """导入时使用系统中不存在的分类应警告但不阻断"""
        csv_content = (
            "课程名称,课程编号,授课教师,学分,容量,学期,课程分类\n"
            "测试课程,TEST_CAT,王教授,2.0,50,2026-秋季,不存在的分类XYZ\n"
        )
        data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "courses.csv")}
        response = login_admin.post(
            "/admin/courses/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        text = response.get_data(as_text=True)
        # 应提示分类不存在
        assert "不存在" in text or "不存在的分类XYZ" in text
        # 课程仍然成功导入（无分类）
        assert "成功导入 1" in text

        from selectcourse.models.course import Course
        c = Course.query.filter_by(code="TEST_CAT").first()
        assert c is not None
        assert c.category_id is None


class TestAdminCategoryManagement:
    """管理员课程分类管理测试"""

    def test_categories_page_access(self, login_admin):
        """分类管理页面可访问"""
        response = login_admin.get("/admin/categories")
        assert response.status_code == 200
        assert "课程分类管理" in response.get_data(as_text=True)
        # 默认分类应存在
        assert "通识课程" in response.get_data(as_text=True)

    def test_categories_page_requires_admin(self, client, student_user):
        """非管理员无法访问分类管理页"""
        client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        })
        response = client.get("/admin/categories", follow_redirects=True)
        assert "需要管理员权限" in response.get_data(as_text=True)

    def test_create_category(self, login_admin):
        """添加新分类"""
        response = login_admin.post("/admin/categories/create", data={
            "name": "实验课程",
        }, follow_redirects=True)
        assert response.status_code == 200
        assert "已添加" in response.get_data(as_text=True)
        assert "实验课程" in response.get_data(as_text=True)

        from selectcourse.models.category import CourseCategory
        cat = CourseCategory.query.filter_by(name="实验课程").first()
        assert cat is not None

    def test_create_duplicate_category(self, login_admin):
        """添加重复分类"""
        login_admin.post("/admin/categories/create", data={
            "name": "实验课程",
        }, follow_redirects=True)
        response = login_admin.post("/admin/categories/create", data={
            "name": "实验课程",
        }, follow_redirects=True)
        assert "已存在" in response.get_data(as_text=True)

    def test_delete_category(self, login_admin, sample_category):
        """删除分类"""
        response = login_admin.post(
            f"/admin/categories/{sample_category.id}/delete",
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "已删除" in response.get_data(as_text=True)

        from selectcourse.models.category import CourseCategory
        assert CourseCategory.query.get(sample_category.id) is None

    def test_delete_category_clears_course(self, login_admin, sample_category, sample_course):
        """删除分类后关联课程变为无分类"""
        # 先将课程关联到分类
        sample_course.category_id = sample_category.id
        from selectcourse.extensions import db as _db
        _db.session.commit()

        response = login_admin.post(
            f"/admin/categories/{sample_category.id}/delete",
            follow_redirects=True,
        )
        assert response.status_code == 200

        # 课程应变为无分类
        from selectcourse.models.course import Course
        c = _db.session.get(Course, sample_course.id)
        assert c.category_id is None

    def test_edit_course_change_category(self, login_admin, sample_course, sample_category):
        """编辑课程时修改分类应持久化"""
        from selectcourse.models.category import CourseCategory

        # 先确保课程开始时无分类
        sample_course.category_id = None
        from selectcourse.extensions import db as _db
        _db.session.commit()

        # 获取另一个分类（与 sample_category 不同）
        other_cat = CourseCategory.query.filter(
            CourseCategory.id != sample_category.id
        ).first()
        if other_cat is None:
            # 如果没有其他分类，创建一个
            other_cat = CourseCategory(name="测试分类_X")
            _db.session.add(other_cat)
            _db.session.commit()

        # 编辑课程，设置分类为 sample_category
        response = login_admin.post(
            f"/admin/courses/{sample_course.id}/edit",
            data={
                "name": sample_course.name,
                "code": sample_course.code,
                "teacher": sample_course.teacher,
                "credits": sample_course.credits,
                "capacity": sample_course.capacity,
                "semester": sample_course.semester,
                "category_id": sample_category.id,
                "schedules_json": json.dumps([
                    {"day_of_week": 1, "start_time": "08:00", "end_time": "09:40"},
                ]),
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "更新成功" in response.get_data(as_text=True)

        # 验证分类已更新
        from selectcourse.models.course import Course
        c = _db.session.get(Course, sample_course.id)
        assert c.category_id == sample_category.id

        # 编辑课程，切换为另一分类
        response = login_admin.post(
            f"/admin/courses/{sample_course.id}/edit",
            data={
                "name": sample_course.name,
                "code": sample_course.code,
                "teacher": sample_course.teacher,
                "credits": sample_course.credits,
                "capacity": sample_course.capacity,
                "semester": sample_course.semester,
                "category_id": other_cat.id,
                "schedules_json": json.dumps([
                    {"day_of_week": 1, "start_time": "08:00", "end_time": "09:40"},
                ]),
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        c = _db.session.get(Course, sample_course.id)
        assert c.category_id == other_cat.id

        # 编辑课程，取消分类（选择 — 不分类 —）
        response = login_admin.post(
            f"/admin/courses/{sample_course.id}/edit",
            data={
                "name": sample_course.name,
                "code": sample_course.code,
                "teacher": sample_course.teacher,
                "credits": sample_course.credits,
                "capacity": sample_course.capacity,
                "semester": sample_course.semester,
                "category_id": 0,  # — 不分类 —
                "schedules_json": json.dumps([
                    {"day_of_week": 1, "start_time": "08:00", "end_time": "09:40"},
                ]),
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        c = _db.session.get(Course, sample_course.id)
        assert c.category_id is None


class TestAdminCourseCategoryFilter:
    """学生端课程分类筛选测试"""

    def test_list_filter_by_category(self, login_student, sample_course, sample_category):
        """按分类筛选课程"""
        # 将示例课程关联到分类
        from selectcourse.extensions import db as _db
        sample_course.category_id = sample_category.id
        _db.session.commit()

        response = login_student.get(f"/course/?category={sample_category.id}")
        assert response.status_code == 200
        assert "Python 程序设计" in response.get_data(as_text=True)

    def test_list_no_category_courses(self, login_student, sample_course):
        """查看无分类课程"""
        response = login_student.get("/course/")
        assert response.status_code == 200
        assert "全部课程分类" in response.get_data(as_text=True)


class TestAdminSelectionManagement:
    """管理员选课记录管理测试"""

    def test_selections_page_access(self, login_admin):
        """选课记录页面可访问"""
        response = login_admin.get("/admin/selections")
        assert response.status_code == 200
        assert "选课记录管理" in response.get_data(as_text=True)

    def test_selections_page_empty(self, login_admin):
        """暂无选课记录时提示"""
        response = login_admin.get("/admin/selections")
        assert "暂无选课记录" in response.get_data(as_text=True)

    def test_selections_show_enrollments(self, login_admin, enrolled_student, sample_course):
        """选课记录页面显示已选课记录"""
        response = login_admin.get("/admin/selections")
        assert response.status_code == 200
        text = response.get_data(as_text=True)
        assert "teststudent" in text
        assert "Python 程序设计" in text
        assert "CS101" in text
        assert "张教授" in text
        assert "已选" in text

    def test_selections_unauthorized(self, client, student_user):
        """非管理员无法访问选课记录"""
        client.post("/auth/login", data={
            "username": "teststudent",
            "password": "password123",
        })
        response = client.get("/admin/selections", follow_redirects=True)
        assert "需要管理员权限" in response.get_data(as_text=True)

    # --- 搜索功能测试 ---

    def test_search_by_course_fuzzy(self, login_admin, enrolled_student, sample_course):
        """模糊搜索：按课程名称"""
        response = login_admin.get(
            "/admin/selections?keyword=Python&search_type=course&search_mode=fuzzy"
        )
        assert response.status_code == 200
        assert "teststudent" in response.get_data(as_text=True)

    def test_search_by_course_exact(self, login_admin, enrolled_student, sample_course):
        """精确搜索：按课程名称"""
        response = login_admin.get(
            "/admin/selections?keyword=Python+程序设计&search_type=course&search_mode=exact"
        )
        assert response.status_code == 200
        assert "teststudent" in response.get_data(as_text=True)

    def test_search_by_course_exact_no_match(self, login_admin, enrolled_student):
        """精确搜索：课程名不匹配"""
        response = login_admin.get(
            "/admin/selections?keyword=Python&search_type=course&search_mode=exact"
        )
        assert response.status_code == 200
        assert "未找到" in response.get_data(as_text=True)

    def test_search_by_teacher_fuzzy(self, login_admin, enrolled_student, sample_course):
        """模糊搜索：按教师名"""
        response = login_admin.get(
            "/admin/selections?keyword=张&search_type=teacher&search_mode=fuzzy"
        )
        assert response.status_code == 200
        assert "teststudent" in response.get_data(as_text=True)

    def test_search_by_teacher_exact(self, login_admin, enrolled_student, sample_course):
        """精确搜索：按教师名"""
        response = login_admin.get(
            "/admin/selections?keyword=张教授&search_type=teacher&search_mode=exact"
        )
        assert response.status_code == 200
        assert "teststudent" in response.get_data(as_text=True)

    def test_search_by_student_fuzzy(self, login_admin, enrolled_student, sample_course):
        """模糊搜索：按学生用户名"""
        response = login_admin.get(
            "/admin/selections?keyword=test&search_type=student&search_mode=fuzzy"
        )
        assert response.status_code == 200
        assert "teststudent" in response.get_data(as_text=True)

    def test_search_by_student_exact(self, login_admin, enrolled_student, sample_course):
        """精确搜索：按学生用户名"""
        response = login_admin.get(
            "/admin/selections?keyword=teststudent&search_type=student&search_mode=exact"
        )
        assert response.status_code == 200
        assert "Python 程序设计" in response.get_data(as_text=True)

    def test_search_all_fields_fuzzy(self, login_admin, enrolled_student, sample_course):
        """模糊搜索：全部字段"""
        response = login_admin.get(
            "/admin/selections?keyword=Pyt&search_type=all&search_mode=fuzzy"
        )
        assert response.status_code == 200
        assert "teststudent" in response.get_data(as_text=True)

    def test_search_no_results(self, login_admin, enrolled_student):
        """搜索无结果"""
        response = login_admin.get(
            "/admin/selections?keyword=不存在xyz&search_type=all&search_mode=fuzzy"
        )
        assert response.status_code == 200
        assert "未找到" in response.get_data(as_text=True)

    def test_search_clear_reset(self, login_admin, enrolled_student, sample_course):
        """搜索后清除显示全部"""
        response = login_admin.get(
            "/admin/selections?keyword=Python&search_type=course&search_mode=fuzzy"
        )
        assert "Python 程序设计" in response.get_data(as_text=True)
        # 清除搜索
        response = login_admin.get("/admin/selections")
        assert "Python 程序设计" in response.get_data(as_text=True)

    def test_search_multiple_results(self, login_admin, db, student_user, sample_course, another_course):
        """多门课程选课时搜索教师返回多条结果"""
        # 再选一门课
        from selectcourse.models.selection import Selection
        sel = Selection(
            student_id=student_user.id,
            course_id=another_course.id,
            status="enrolled",
        )
        another_course.enrolled_count = 1
        db.session.add(sel)
        db.session.commit()

        # 搜索教师"李"（another_course 的教师）
        response = login_admin.get(
            "/admin/selections?keyword=李&search_type=teacher&search_mode=fuzzy"
        )
        assert response.status_code == 200
        text = response.get_data(as_text=True)
        assert "Java 程序设计" in text

    # --- 删除选课记录测试 ---

    def test_delete_selection(self, login_admin, enrolled_student, sample_course):
        """删除选课记录"""
        from selectcourse.models.selection import Selection
        from selectcourse.models.course import Course

        sel = Selection.query.filter_by(
            student_id=enrolled_student.id, course_id=sample_course.id
        ).first()
        assert sel is not None

        course = Course.query.get(sample_course.id)
        old_count = course.enrolled_count

        response = login_admin.post(
            f"/admin/selections/{sel.id}/delete",
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "已删除" in response.get_data(as_text=True)

        # 确认记录已删除
        assert Selection.query.get(sel.id) is None
        # 确认 enrolled_count 已减少
        assert Course.query.get(sample_course.id).enrolled_count == old_count - 1

    def test_delete_nonexistent_selection(self, login_admin):
        """删除不存在的选课记录"""
        response = login_admin.post(
            "/admin/selections/99999/delete",
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "不存在" in response.get_data(as_text=True)

    def test_delete_dropped_selection(self, login_admin, db, student_user, sample_course):
        """删除已退选记录不减少 enrolled_count"""
        from selectcourse.models.selection import Selection
        from selectcourse.models.course import Course

        sel = Selection(
            student_id=student_user.id,
            course_id=sample_course.id,
            status="dropped",
        )
        db.session.add(sel)
        db.session.commit()

        course = Course.query.get(sample_course.id)
        old_count = course.enrolled_count

        response = login_admin.post(
            f"/admin/selections/{sel.id}/delete",
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "已删除" in response.get_data(as_text=True)
        # 已退选不应减少 enrolled_count
        assert Course.query.get(sample_course.id).enrolled_count == old_count

    def test_selections_pagination(self, login_admin, db, student_user, sample_course):
        """选课记录分页测试"""
        from selectcourse.models.selection import Selection
        from selectcourse.models.course import Course

        # 创建多个学生 + 多门课程来生成足够的选课记录
        from selectcourse.models.user import User
        students = []
        for i in range(5):
            u = User(
                username=f"pagination_student_{i}",
                email=f"pagination_{i}@test.edu",
                role="student",
            )
            u.set_password("password123")
            db.session.add(u)
            db.session.flush()
            students.append(u)

        courses = [sample_course]
        for i in range(5):
            c = Course(
                name=f"分页测试课程_{i}",
                code=f"PAGE{i:03d}",
                teacher=f"教师_{i}",
                credits=2.0,
                capacity=100,
                semester="2026-秋季",
            )
            db.session.add(c)
            db.session.flush()
            courses.append(c)

        # 为每个学生选不同的课程组合
        for si, student in enumerate(students):
            for ci, course in enumerate(courses):
                if (si + ci) % 3 == 0:
                    continue  # 跳过一些以模拟真实情况
                sel = Selection(
                    student_id=student.id,
                    course_id=course.id,
                    status="enrolled",
                )
                db.session.add(sel)
        db.session.commit()

        # 第 1 页应有 20 条（per_page=20）
        response = login_admin.get("/admin/selections?page=1")
        assert response.status_code == 200
        text = response.get_data(as_text=True)
        assert "第 1 /" in text or "第 1 " in text
