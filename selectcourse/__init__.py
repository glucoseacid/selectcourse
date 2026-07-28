"""selectcourse 包初始化 —— App Factory 模式"""
import sqlite3
from flask import Flask
from selectcourse.config import Config
from selectcourse.extensions import db, login_manager, migrate, csrf


def _ensure_schema_upgrade(app: Flask) -> None:
    """检测并自动添加 SQLite 数据库中缺失的列（简易 schema 迁移）。

    仅对 SQLite 生效；生产环境应使用 Flask-Migrate / Alembic。
    每个迁移以 (table_name, column_def_sql) 元组定义。
    """
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not db_uri.startswith("sqlite:///"):
        return  # 非 SQLite 跳过

    # 提取数据库文件路径
    db_path = db_uri.replace("sqlite:///", "", 1)
    if not db_path:
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # ---- 迁移列表（按添加顺序） ----
        # 格式: (表名, 列名, 列定义 SQL)
        migrations = [
            ("courses", "category_id", "ALTER TABLE courses ADD COLUMN category_id INTEGER REFERENCES course_categories(id)"),
        ]

        for table, col_name, alter_sql in migrations:
            # 检查列是否已存在
            cursor.execute(f"PRAGMA table_info({table})")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if col_name not in existing_cols:
                cursor.execute(alter_sql)
                conn.commit()
                import logging
                logging.getLogger(__name__).info(
                    "Schema migration: added column '%s' to table '%s'.", col_name, table
                )

        conn.close()
    except Exception:
        # 迁移失败不应阻止应用启动（可能表还不存在，create_all 会处理）
        pass


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
