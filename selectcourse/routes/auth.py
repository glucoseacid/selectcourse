"""认证路由（登录 / 注册 / 登出）"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from selectcourse.extensions import db
from selectcourse.models.user import User
from selectcourse.forms import LoginForm, RegisterForm

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash("用户名或密码错误。", "danger")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=True)
        flash(f"欢迎回来，{user.username}！", "success")
        next_page = request.args.get("next")
        if next_page:
            return redirect(next_page)
        if user.is_admin:
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("course.list_courses"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        # 检查用户名和邮箱唯一性
        if User.query.filter_by(username=form.username.data).first():
            flash("该用户名已被使用。", "danger")
            return render_template("auth/register.html", form=form)
        if User.query.filter_by(email=form.email.data).first():
            flash("该邮箱已被注册。", "danger")
            return render_template("auth/register.html", form=form)

        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash("注册成功！请登录。", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("已安全退出。", "info")
    return redirect(url_for("main.index"))
