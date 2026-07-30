"""selectcourse 包初始化 —— App Factory 模式

数据库 schema 管理策略
---------------------
- 开发环境（默认 SQLite）：启动时自动执行 db.create_all()，并由
  _ensure_schema_upgrade() 补齐缺失列，零配置即可运行。
- 生产环境（MySQL/PostgreSQL）：应设置 AUTO_CREATE_TABLES=False，
  使用 Flask-Migrate / Alembic 管理所有 schema 变更：
    flask db upgrade    # 应用迁移
    flask db migrate -m "描述"  # 生成新迁移
"""
import logging
import sqlite3
from flask import Flask
from selectcourse.config import Config
from selectcourse.extensions import db, login_manager, migrate, csrf

logger = logging.getLogger(__name__)


def _ensure_schema_upgrade(app: Flask) -> None:
    """检测并自动添加 SQLite 数据库中缺失的列（简易 schema 迁移）。

    仅对 SQLite 生效；生产环境（MySQL/PostgreSQL）应使用 Flask-Migrate / Alembic。
    可通过设置 AUTO_CREATE_TABLES=False 完全跳过自动建表逻辑。
    """
    if not app.config.get("AUTO_CREATE_TABLES", True):
        return

    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not db_uri.startswith("sqlite:///"):
        return  # 非 SQLite 跳过，应使用 Alembic 迁移

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
                logger.info(
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

    # 初始化数据库
    with app.app_context():
        from selectcourse.models import user, course, selection  # noqa: F401

        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        db_type = "SQLite" if "sqlite" in db_uri else (
            "MySQL" if "mysql" in db_uri else (
                "PostgreSQL" if "postgresql" in db_uri else "Unknown"
            )
        )
        logger.info("Database type: %s | URI: %s", db_type,
                     db_uri[:80] + "..." if len(db_uri) > 80 else db_uri)

        if app.config.get("AUTO_CREATE_TABLES", True):
            db.create_all()
            _ensure_schema_upgrade(app)
            logger.info("Auto-created database tables (AUTO_CREATE_TABLES=True).")
        else:
            logger.info(
                "AUTO_CREATE_TABLES=False — skipping auto-create. "
                "Use 'flask db upgrade' to apply migrations."
            )

    return app
