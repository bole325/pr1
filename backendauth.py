from functools import wraps
from flask import session, redirect, url_for, flash
import hashlib
from backend.database import get_db_connection

def login_required(role=None):
    """
    权限装饰器：要求用户登录，可选指定角色
    
    用法：
        @login_required                     # 任何登录用户都可访问
        @login_required(role='student')     # 仅学生可访问
        @login_required(role='teacher')     # 仅教师可访问
        @login_required(role='admin')       # 仅管理员可访问
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 检查是否已登录
            if 'user_id' not in session:
                flash('请先登录', 'warning')
                return redirect(url_for('login'))
            
            # 检查角色权限
            if role and session.get('role') != role:
                flash('无权访问此页面', 'danger')
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def check_login(username, password):
    """验证用户登录，返回用户信息（字典）或 None"""
    conn = get_db_connection()
    hashed_pwd = hashlib.md5(password.encode()).hexdigest()
    
    user = conn.execute(
        "SELECT id, username, role, real_name FROM users WHERE username = ? AND password = ?",
        (username, hashed_pwd)
    ).fetchone()
    
    conn.close()
    
    if user:
        return dict(user)  # 转换为普通字典
    return None

def get_user_by_id(user_id):
    """根据用户ID获取用户信息"""
    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, username, role, real_name FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    return dict(user) if user else None