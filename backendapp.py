from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
import hashlib
import os
import json

from backend.database import init_db, get_db_connection
from backend.auth import login_required, check_login

# 创建 Flask 应用
app = Flask(__name__, 
            template_folder='../frontend',  # HTML模板目录
            static_folder='../frontend')    # 静态文件目录
app.secret_key = 'your-secret-key-here-change-in-production'

# 初始化数据库
init_db()

# ==================== 公共路由 ====================

@app.route('/')
def index():
    """首页，重定向到登录页"""
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    # 如果已登录，直接跳转到仪表板
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = check_login(username, password)
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['real_name'] = user['real_name']
            flash(f'欢迎回来，{user["real_name"]}！', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """退出登录"""
    session.clear()
    flash('已退出登录', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required()
def dashboard():
    """根据用户角色跳转到对应主页"""
    role = session.get('role')
    if role == 'student':
        return redirect(url_for('student_dashboard'))
    elif role == 'teacher':
        return redirect(url_for('teacher_dashboard'))
    elif role == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))

# ==================== 学生功能（3个） ====================

@app.route('/student')
@login_required(role='student')
def student_dashboard():
    """功能1：学生主页 - 查看所有作业"""
    conn = get_db_connection()
    assignments = conn.execute('''
        SELECT 
            a.*, 
            u.real_name as teacher_name,
            (SELECT status FROM submissions WHERE assignment_id = a.id AND student_id = ?) as submit_status,
            (SELECT score FROM submissions WHERE assignment_id = a.id AND student_id = ?) as score,
            (SELECT feedback FROM submissions WHERE assignment_id = a.id AND student_id = ?) as feedback
        FROM assignments a
        JOIN users u ON a.teacher_id = u.id
        ORDER BY a.deadline ASC
    ''', (session['user_id'], session['user_id'], session['user_id'])).fetchall()
    conn.close()
    return render_template('student.html', assignments=assignments)

@app.route('/submit_assignment/<int:assignment_id>', methods=['POST'])
@login_required(role='student')
def submit_assignment(assignment_id):
    """功能2：提交/修改作业"""
    content = request.form.get('content', '').strip()
    
    if not content:
        flash('请输入作业内容', 'danger')
        return redirect(url_for('student_dashboard'))
    
    conn = get_db_connection()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 检查是否已有提交记录
    existing = conn.execute(
        "SELECT id FROM submissions WHERE assignment_id = ? AND student_id = ?",
        (assignment_id, session['user_id'])
    ).fetchone()
    
    if existing:
        # 更新已有提交
        conn.execute(
            "UPDATE submissions SET content = ?, submit_time = ?, status = 'resubmitted' WHERE id = ?",
            (content, now, existing['id'])
        )
        flash('作业已更新', 'info')
    else:
        # 新增提交
        conn.execute(
            "INSERT INTO submissions (assignment_id, student_id, content, submit_time, status) VALUES (?, ?, ?, ?, ?)",
            (assignment_id, session['user_id'], content, now, 'submitted')
        )
        flash('作业提交成功', 'success')
    
    conn.commit()
    conn.close()
    return redirect(url_for('student_dashboard'))

@app.route('/my_submissions')
@login_required(role='student')
def my_submissions():
    """功能3：查看我的作业成绩"""
    conn = get_db_connection()
    submissions = conn.execute('''
        SELECT 
            s.*, 
            a.title as assignment_title, 
            a.deadline,
            u.real_name as teacher_name
        FROM submissions s
        JOIN assignments a ON s.assignment_id = a.id
        JOIN users u ON a.teacher_id = u.id
        WHERE s.student_id = ?
        ORDER BY s.submit_time DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('my_submissions.html', submissions=submissions)

# ==================== 教师功能（3个） ====================

@app.route('/teacher')
@login_required(role='teacher')
def teacher_dashboard():
    """功能1：教师主页 - 管理作业"""
    conn = get_db_connection()
    assignments = conn.execute('''
        SELECT 
            a.*, 
            (SELECT COUNT(*) FROM submissions WHERE assignment_id = a.id) as submit_count,
            (SELECT COUNT(*) FROM submissions WHERE assignment_id = a.id AND score IS NULL) as ungraded_count
        FROM assignments a
        WHERE a.teacher_id = ?
        ORDER BY a.created_at DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('teacher.html', assignments=assignments)

@app.route('/create_assignment', methods=['POST'])
@login_required(role='teacher')
def create_assignment():
    """功能2：发布新作业"""
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    deadline = request.form.get('deadline')
    
    if not title:
        flash('作业标题不能为空', 'danger')
        return redirect(url_for('teacher_dashboard'))
    
    if not deadline:
        flash('请设置截止时间', 'danger')
        return redirect(url_for('teacher_dashboard'))
    
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO assignments (title, description, teacher_id, deadline, created_at) VALUES (?, ?, ?, ?, ?)",
        (title, description, session['user_id'], deadline, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    )
    conn.commit()
    conn.close()
    flash('作业发布成功', 'success')
    return redirect(url_for('teacher_dashboard'))

@app.route('/grade_assignment/<int:assignment_id>')
@login_required(role='teacher')
def grade_assignment(assignment_id):
    """功能3a：查看某作业的所有学生提交"""
    conn = get_db_connection()
    
    # 获取作业信息
    assignment = conn.execute(
        "SELECT * FROM assignments WHERE id = ? AND teacher_id = ?",
        (assignment_id, session['user_id'])
    ).fetchone()
    
    if not assignment:
        flash('作业不存在或无权访问', 'danger')
        return redirect(url_for('teacher_dashboard'))
    
    # 获取所有提交
    submissions = conn.execute('''
        SELECT 
            s.*, 
            u.real_name as student_name, 
            u.username,
            u.class_name
        FROM submissions s
        JOIN users u ON s.student_id = u.id
        WHERE s.assignment_id = ?
        ORDER BY s.submit_time
    ''', (assignment_id,)).fetchall()
    
    conn.close()
    return render_template('grade.html', submissions=submissions, assignment=assignment)

@app.route('/save_score', methods=['POST'])
@login_required(role='teacher')
def save_score():
    """功能3b：保存成绩和评语"""
    submission_id = request.form.get('submission_id')
    score = request.form.get('score')
    feedback = request.form.get('feedback', '').strip()
    
    if not score or not score.isdigit():
        flash('请输入有效的分数（0-100）', 'danger')
        return redirect(request.referrer or url_for('teacher_dashboard'))
    
    score_int = int(score)
    if score_int < 0 or score_int > 100:
        flash('分数必须在0-100之间', 'danger')
        return redirect(request.referrer or url_for('teacher_dashboard'))
    
    conn = get_db_connection()
    conn.execute(
        "UPDATE submissions SET score = ?, feedback = ?, status = 'graded' WHERE id = ?",
        (score_int, feedback, submission_id)
    )
    conn.commit()
    conn.close()
    flash('成绩已保存', 'success')
    return redirect(request.referrer or url_for('teacher_dashboard'))

# ==================== 管理员功能（3个 + 加分项） ====================

@app.route('/admin')
@login_required(role='admin')
def admin_dashboard():
    """功能1：管理员主页 - 查看统计和用户列表"""
    conn = get_db_connection()
    
    # 统计数据
    stats = {
        'student_count': conn.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
        'teacher_count': conn.execute("SELECT COUNT(*) FROM users WHERE role='teacher'").fetchone()[0],
        'admin_count': conn.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0],
        'assignment_count': conn.execute("SELECT COUNT(*) FROM assignments").fetchone()[0],
        'submission_count': conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
    }
    
    # 用户列表
    users = conn.execute("SELECT * FROM users ORDER BY role, id").fetchall()
    conn.close()
    
    return render_template('admin.html', stats=stats, users=users)

@app.route('/add_user', methods=['POST'])
@login_required(role='admin')
def add_user():
    """功能2：添加用户"""
    username = request.form.get('username', '').strip()
    real_name = request.form.get('real_name', '').strip()
    role = request.form.get('role')
    class_name = request.form.get('class_name', '')
    
    if not username or not real_name:
        flash('用户名和真实姓名不能为空', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # 默认密码 123456
    default_pwd = hashlib.md5('123456'.encode()).hexdigest()
    
    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO users (username, password, role, real_name, class_name) VALUES (?, ?, ?, ?, ?)",
            (username, default_pwd, role, real_name, class_name if class_name else None)
        )
        conn.commit()
        conn.close()
        flash(f'用户 {username} 添加成功，默认密码：123456', 'success')
    except sqlite3.IntegrityError:
        flash(f'用户名 {username} 已存在', 'danger')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/delete_user/<int:user_id>')
@login_required(role='admin')
def delete_user(user_id):
    """功能3：删除用户"""
    if user_id == session['user_id']:
        flash('不能删除自己的账号', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash('用户已删除', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/export_data')
@login_required(role='admin')
def export_data():
    """加分项：导出所有数据为 JSON"""
    conn = get_db_connection()
    
    users = conn.execute("SELECT id, username, real_name, role, class_name FROM users").fetchall()
    assignments = conn.execute("SELECT * FROM assignments").fetchall()
    submissions = conn.execute("SELECT * FROM submissions").fetchall()
    
    # 转换为可序列化的字典列表
    data = {
        'export_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'users': [dict(row) for row in users],
        'assignments': [dict(row) for row in assignments],
        'submissions': [dict(row) for row in submissions]
    }
    conn.close()
    
    # 返回 JSON 下载
    response = jsonify(data)
    response.headers['Content-Disposition'] = 'attachment; filename=export_data.json'
    return response

# ==================== 启动应用 ====================

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)