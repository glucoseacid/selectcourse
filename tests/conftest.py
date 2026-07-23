"""pytest 配置与公共 fixtures"""
import pytest
from selectcourse import create_app
from selectcourse.config import TestingConfig
from selectcourse.extensions import db as _db
from selectcourse.models.user import User
from selectcourse.models.course import Course, CourseSchedule
from selectcourse.models.selection import Selection


@pytest.fixture
def app():
    """创建测试 Flask 应用"""
    app = create_app(TestingConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    """测试客户端"""
    return app.test_client()


@pytest.fixture
def db(app):
    """数据库会话"""
    return _db


@pytest.fixture
def runner(app):
    """CLI runner"""
    return app.test_cli_runner()


@pytest.fixture
def student_user(db):
    """创建测试学生"""
    user = User(username="teststudent", email="student@test.edu", role="student")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def admin_user(db):
    """创建测试管理员"""
    user = User(username="admin", email="admin@test.edu", role="admin")
    user.set_password("admin123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def sample_course(db):
    """创建示例课程"""
    course = Course(
        name="Python 程序设计",
        code="CS101",
        teacher="张教授",
        credits=3.0,
        capacity=2,
        semester="2026-秋季",
        location="教学楼A-301",
        description="Python 编程入门课程",
    )
    db.session.add(course)
    db.session.flush()

    schedule = CourseSchedule(
        course_id=course.id,
        day_of_week=1,  # 周二
        start_time="08:00",
        end_time="09:40",
    )
    db.session.add(schedule)
    db.session.commit()
    return course


@pytest.fixture
def another_course(db):
    """创建另一门课程（时间冲突）"""
    course = Course(
        name="Java 程序设计",
        code="CS102",
        teacher="李教授",
        credits=3.0,
        capacity=60,
        semester="2026-秋季",
        location="教学楼B-201",
    )
    db.session.add(course)
    db.session.flush()

    schedule = CourseSchedule(
        course_id=course.id,
        day_of_week=1,  # 周二（与 CS101 同天）
        start_time="08:30",
        end_time="10:00",  # 与 CS101 时间重叠
    )
    db.session.add(schedule)
    db.session.commit()
    return course


@pytest.fixture
def enrolled_student(db, student_user, sample_course):
    """已选课的学生"""
    selection = Selection(
        student_id=student_user.id,
        course_id=sample_course.id,
        status="enrolled",
    )
    sample_course.enrolled_count = 1
    db.session.add(selection)
    db.session.commit()
    return student_user


@pytest.fixture
def login_student(client, student_user):
    """已登录学生客户端"""
    client.post("/auth/login", data={
        "username": "teststudent",
        "password": "password123",
    }, follow_redirects=True)
    return client


@pytest.fixture
def login_admin(client, admin_user):
    """已登录管理员客户端"""
    client.post("/auth/login", data={
        "username": "admin",
        "password": "admin123",
    }, follow_redirects=True)
    return client
