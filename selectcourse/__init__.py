"""selectcourse 包初始化 —— App Factory 模式"""
from flask import Flask
from selectcourse.config import Config
from selectcourse.extensions import db, login_manager, migrate, csrf


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "请先登录后再访问该页面。"
    login_manager.login_message_category = "warning"

    # 注册蓝图
    from selectcourse.routes.auth import auth_bp
    from selectcourse.routes.course import course_bp
    from selectcourse.routes.admin import admin_bp
    from selectcourse.routes.main import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(course_bp, url_prefix="/course")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # 创建数据库表
    with app.app_context():
        from selectcourse.models import user, course, selection  # noqa: F401
        db.create_all()

    return app
