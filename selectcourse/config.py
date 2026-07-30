"""应用配置

数据库切换指南
--------------
当前默认使用 SQLite（零配置，适合开发和小规模部署）。
要切换到 MySQL 或 PostgreSQL，只需设置环境变量 DATABASE_URL：

  MySQL:      set DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/selectcourse
  PostgreSQL: set DATABASE_URL=postgresql://user:pass@localhost:5432/selectcourse

并安装对应的数据库驱动（参见 requirements.txt 中的注释说明）。
切换后建议设置 AUTO_CREATE_TABLES=False，改用 Flask-Migrate 管理 schema：
  flask db init       # 首次使用
  flask db migrate -m "init"
  flask db upgrade
"""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _build_default_uri() -> str:
    """根据 DB_DRIVER 环境变量构建默认数据库 URI。

    支持的 DB_DRIVER 值：
      - 不设置 / sqlite  → SQLite（默认，文件存储在项目目录下）
      - mysql             → MySQL（需同时设置 DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME）
      - postgresql        → PostgreSQL（环境变量同上）

    也可以通过 DATABASE_URL 直接指定完整 URI（优先级最高）。
    """
    driver = os.environ.get("DB_DRIVER", "sqlite").lower()

    if driver == "mysql":
        user = os.environ.get("DB_USER", "root")
        password = os.environ.get("DB_PASS", "")
        host = os.environ.get("DB_HOST", "localhost")
        port = os.environ.get("DB_PORT", "3306")
        name = os.environ.get("DB_NAME", "selectcourse")
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"

    elif driver == "postgresql":
        user = os.environ.get("DB_USER", "postgres")
        password = os.environ.get("DB_PASS", "")
        host = os.environ.get("DB_HOST", "localhost")
        port = os.environ.get("DB_PORT", "5432")
        name = os.environ.get("DB_NAME", "selectcourse")
        return f"postgresql://{user}:{password}@{host}:{port}/{name}"

    else:
        # 默认 SQLite
        return f"sqlite:///{os.path.join(BASE_DIR, 'selectcourse.db')}"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

    # 数据库 URI：优先使用 DATABASE_URL 环境变量，否则根据 DB_DRIVER 构建
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or _build_default_uri()

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 连接池配置（SQLite 忽略此配置；MySQL/PostgreSQL 生产环境建议开启）
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": int(os.environ.get("DB_POOL_SIZE", "5")),
        "pool_recycle": int(os.environ.get("DB_POOL_RECYCLE", "3600")),
        "pool_pre_ping": True,  # 每次使用前检测连接是否有效
    }

    # 是否在启动时自动建表（仅 SQLite 开发环境推荐 True；生产 SQL 数据库应设为 False）
    AUTO_CREATE_TABLES = os.environ.get("AUTO_CREATE_TABLES", "true").lower() == "true"

    WTF_CSRF_ENABLED = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    AUTO_CREATE_TABLES = True  # 测试时自动建表
