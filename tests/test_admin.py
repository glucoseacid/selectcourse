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

    def test_create_course_with_category(self, login_admin, sample_category):
        """创建课程时选择分类"""
        response = login_admin.post("/admin/courses/create", data={
            "name": "分类课程",
            "code": "CAT101",
            "teacher": "赵教授",
            "credits": 2.0,
            "capacity": 50,
            "semester": "2026-秋季",
            "category_id": sample_category.id,
            "schedules_json": json.dumps([
                {"day_of_week": 1, "start_time": "08:00", "end_time": "09:40"},
            ]),
        }, follow_redirects=True)
        assert response.status_code == 200
        assert "创建成功" in response.get_data(as_text=True)

        from selectcourse.models.course import Course
        course = Course.query.filter_by(code="CAT101").first()
        assert course is not None
        assert course.category_id == sample_category.id


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
