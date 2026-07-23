"""创建管理员账户脚本"""
from selectcourse import create_app
from selectcourse.extensions import db
from selectcourse.models.user import User


def create_admin():
    app = create_app()
    with app.app_context():
        db.create_all()

        # 检查是否已存在管理员
        existing = User.query.filter_by(username="admin").first()
        if existing:
            print("管理员已存在。")
            return

        admin = User(
            username="admin",
            email="admin@selectcourse.edu",
            role="admin",
        )
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        print("管理员创建成功！")
        print("  用户名: admin")
        print("  密码:   admin123")


if __name__ == "__main__":
    create_admin()
