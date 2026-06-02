import sqlite3
import hashlib
import os

# 数据库路径
DB_PATH = 'instance/course_work.db'

def init_db():
    """初始化数据库，创建所有表并插入测试数据"""
    
    # 确保 instance 文件夹存在
    os.makedirs('instance', exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. 创建用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('student', 'teacher', 'admin')),
            real_name TEXT NOT NULL,
            class_name TEXT
        )
    ''')
    
    # 2. 创建作业表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            teacher_id INTEGER NOT NULL,
            deadline TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (teacher_id) REFERENCES users (id)
        )
    ''')
    
    # 3. 创建提交记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            content TEXT,
            submit_time TEXT NOT NULL,
            score INTEGER DEFAULT NULL,
            feedback TEXT,
            status TEXT DEFAULT 'submitted',
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (student_id) REFERENCES users (id)
        )
    ''')
    
    # 4. 插入测试数据（如果数据库为空）
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        
        # 密码统一为 123456 的 MD5 值
        default_pwd = hashlib.md5('123456'.encode()).hexdigest()
        
        # 插入学生
        cursor.execute('''
            INSERT INTO users (username, password, role, real_name, class_name)
            VALUES (?, ?, ?, ?, ?)
        ''', ('student1', default_pwd, 'student', '张三', '计算机1班'))
        
        cursor.execute('''
            INSERT INTO users (username, password, role, real_name, class_name)
            VALUES (?, ?, ?, ?, ?)
        ''', ('student2', default_pwd, 'student', '李四', '计算机1班'))
        
        # 插入教师
        cursor.execute('''
            INSERT INTO users (username, password, role, real_name)
            VALUES (?, ?, ?, ?)
        ''', ('teacher1', default_pwd, 'teacher', '王老师'))
        
        # 插入管理员
        cursor.execute('''
            INSERT INTO users (username, password, role, real_name)
            VALUES (?, ?, ?, ?)
        ''', ('admin1', default_pwd, 'admin', '超级管理员'))
        
        # 获取教师ID
        teacher_id = cursor.lastrowid - 1  # teacher1 的 ID
        
        # 插入示例作业
        cursor.execute('''
            INSERT INTO assignments (title, description, teacher_id, deadline, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', ('第一次作业：Python基础', '请完成课后练习题1-10，提交代码和运行截图', 
              teacher_id, '2026-06-15 23:59:59', '2026-06-01 10:00:00'))
        
        cursor.execute('''
            INSERT INTO assignments (title, description, teacher_id, deadline, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', ('第二次作业：Web开发', '使用Flask搭建一个简单的博客系统', 
              teacher_id, '2026-06-22 23:59:59', '2026-06-08 10:00:00'))
    
    conn.commit()
    conn.close()
    print("数据库初始化完成！")

def get_db_connection():
    """获取数据库连接，返回支持字典式访问的连接对象"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 使返回结果支持 row['column_name']
    return conn

# 测试时可以直接运行此文件初始化数据库
if __name__ == '__main__':
    init_db()