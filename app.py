from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, make_response, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from dotenv import load_dotenv
import os
import uuid
import xml.etree.ElementTree as ET
import sqlite3
import hashlib

# 加载环境变量
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'change-this-in-production')
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_FILE_SIZE', 16)) * 1024 * 1024
app.config['DATABASE'] = os.getenv('DATABASE_PATH', 'data/site.db')

# 确保目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)

# 数据库操作
def get_db():
    """获取数据库连接"""
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    return db

def init_db():
    """初始化数据库"""
    db = get_db()
    
    # 用户表
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user' CHECK(role IN ('admin', 'publisher', 'user')),
            created_at TEXT NOT NULL
        )
    ''')
    
    # 种子表
    db.execute('''
        CREATE TABLE IF NOT EXISTS torrents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT DEFAULT 'general',
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            publisher_id TEXT NOT NULL,
            publisher_name TEXT NOT NULL
        )
    ''')
    
    db.commit()
    
    # 创建默认管理员
    admin_exists = db.execute('SELECT 1 FROM users WHERE username = ?', ('admin',)).fetchone()
    if not admin_exists:
        db.execute('''
            INSERT INTO users (id, username, password, role, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()),
            'admin',
            generate_password_hash(os.getenv('ADMIN_PASSWORD', 'admin')),
            'admin',
            datetime.now().isoformat()
        ))
        db.commit()
    
    db.close()

# 初始化数据库
init_db()

# 权限装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'warning')
            return redirect(url_for('login'))
        user = get_user_by_id(session['user_id'])
        if not user or user['role'] != 'admin':
            flash('需要管理员权限', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def publisher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'warning')
            return redirect(url_for('login'))
        user = get_user_by_id(session['user_id'])
        if not user or user['role'] not in ['admin', 'publisher']:
            flash('需要发布员权限', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_by_id(user_id):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    db.close()
    return dict(user) if user else None

def get_user_by_username(username):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    db.close()
    return dict(user) if user else None

# 路由：首页（种子列表）
@app.route('/')
def index():
    db = get_db()
    torrents = db.execute('''
        SELECT * FROM torrents 
        ORDER BY created_at DESC
    ''').fetchall()
    db.close()
    return render_template('index.html', torrents=[dict(t) for t in torrents])

# 路由：注册
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if not username or not password:
            flash('用户名和密码不能为空', 'danger')
            return redirect(url_for('register'))
        
        if get_user_by_username(username):
            flash('用户名已存在', 'danger')
            return redirect(url_for('register'))
        
        db = get_db()
        db.execute('''
            INSERT INTO users (id, username, password, role, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()),
            username,
            generate_password_hash(password),
            'user',
            datetime.now().isoformat()
        ))
        db.commit()
        db.close()
        
        flash('注册成功，请登录', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# 路由：登录
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = get_user_by_username(username)
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f'欢迎回来，{username}！', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'danger')
            return redirect(url_for('login'))
    
    return render_template('login.html')

# 路由：登出
@app.route('/logout')
def logout():
    session.clear()
    flash('已退出登录', 'info')
    return redirect(url_for('index'))

# 路由：上传种子（仅发布员和管理员）
@app.route('/upload', methods=['GET', 'POST'])
@publisher_required
def upload():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description', '')
        category = request.form.get('category', 'general')
        
        if 'torrent' not in request.files:
            flash('没有选择文件', 'danger')
            return redirect(request.url)
        
        file = request.files['torrent']
        if file.filename == '':
            flash('没有选择文件', 'danger')
            return redirect(request.url)
        
        if not title:
            flash('标题不能为空', 'danger')
            return redirect(request.url)
        
        # 保存文件
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        # 保存种子信息到数据库
        db = get_db()
        db.execute('''
            INSERT INTO torrents (id, title, description, category, filename, 
                                original_filename, file_size, created_at, 
                                publisher_id, publisher_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()),
            title,
            description,
            category,
            unique_filename,
            filename,
            os.path.getsize(file_path),
            datetime.now().isoformat(),
            session['user_id'],
            session['username']
        ))
        db.commit()
        db.close()
        
        flash('种子发布成功！', 'success')
        return redirect(url_for('index'))
    
    return render_template('upload.html')

# 路由：下载种子
@app.route('/download/<torrent_id>')
def download(torrent_id):
    db = get_db()
    torrent = db.execute('SELECT * FROM torrents WHERE id = ?', (torrent_id,)).fetchone()
    db.close()
    
    if not torrent:
        flash('种子不存在', 'danger')
        return redirect(url_for('index'))
    
    torrent = dict(torrent)
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        torrent['filename'],
        as_attachment=True,
        download_name=torrent['original_filename']
    )

# 路由：RSS Feed
@app.route('/rss.xml')
def rss_feed():
    db = get_db()
    torrents = db.execute('''
        SELECT * FROM torrents 
        ORDER BY created_at DESC 
        LIMIT 50
    ''').fetchall()
    db.close()
    
    # 创建RSS XML
    rss = ET.Element('rss')
    rss.set('version', '2.0')
    rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')
    
    channel = ET.SubElement(rss, 'channel')
    
    # 频道信息
    ET.SubElement(channel, 'title').text = os.getenv('SITE_NAME', 'RSS种子站点')
    ET.SubElement(channel, 'link').text = request.url_root
    ET.SubElement(channel, 'description').text = '自动下载种子RSS源'
    ET.SubElement(channel, 'language').text = 'zh-CN'
    ET.SubElement(channel, 'lastBuildDate').text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0800')
    
    # 生成atom:link
    atom_link = ET.SubElement(channel, 'atom:link')
    atom_link.set('href', request.url)
    atom_link.set('rel', 'self')
    atom_link.set('type', 'application/rss+xml')
    
    # 添加种子条目
    for torrent in torrents:
        torrent = dict(torrent)
        item = ET.SubElement(channel, 'item')
        
        ET.SubElement(item, 'title').text = torrent['title']
        ET.SubElement(item, 'link').text = url_for('download', torrent_id=torrent['id'], _external=True)
        ET.SubElement(item, 'description').text = torrent['description'] or torrent['title']
        ET.SubElement(item, 'pubDate').text = datetime.fromisoformat(torrent['created_at']).strftime('%a, %d %b %Y %H:%M:%S +0800')
        ET.SubElement(item, 'guid').text = torrent['id']
        
        # enclosure标签（qBittorrent用它来识别种子文件）
        enclosure = ET.SubElement(item, 'enclosure')
        enclosure.set('url', url_for('download', torrent_id=torrent['id'], _external=True))
        enclosure.set('length', str(torrent['file_size']))
        enclosure.set('type', 'application/x-bittorrent')
        
        # 类别
        if torrent.get('category'):
            category = ET.SubElement(item, 'category')
            category.text = torrent['category']
    
    # 转换为字符串
    xml_string = ET.tostring(rss, encoding='unicode')
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    
    response = make_response(xml_declaration + xml_string)
    response.headers['Content-Type'] = 'application/rss+xml; charset=utf-8'
    return response

# 路由：管理后台
@app.route('/admin')
@admin_required
def admin():
    db = get_db()
    users = db.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    torrents = db.execute('SELECT * FROM torrents ORDER BY created_at DESC').fetchall()
    db.close()
    
    return render_template('admin.html', 
                         users=[dict(u) for u in users], 
                         torrents=[dict(t) for t in torrents])

# 路由：设置用户权限
@app.route('/admin/set_role/<user_id>/<role>')
@admin_required
def set_role(user_id, role):
    if role not in ['user', 'publisher', 'admin']:
        flash('无效的角色', 'danger')
        return redirect(url_for('admin'))
    
    user = get_user_by_id(user_id)
    if not user:
        flash('用户不存在', 'danger')
        return redirect(url_for('admin'))
    
    if user['username'] == 'admin' and role != 'admin':
        flash('不能修改默认管理员权限', 'danger')
        return redirect(url_for('admin'))
    
    db = get_db()
    db.execute('UPDATE users SET role = ? WHERE id = ?', (role, user_id))
    db.commit()
    db.close()
    
    flash(f'已将 {user["username"]} 设置为 {role}', 'success')
    return redirect(url_for('admin'))

# 路由：删除种子
@app.route('/admin/delete_torrent/<torrent_id>')
@admin_required
def delete_torrent(torrent_id):
    db = get_db()
    torrent = db.execute('SELECT * FROM torrents WHERE id = ?', (torrent_id,)).fetchone()
    
    if torrent:
        torrent = dict(torrent)
        # 删除文件
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], torrent['filename'])
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # 从数据库移除
        db.execute('DELETE FROM torrents WHERE id = ?', (torrent_id,))
        db.commit()
        flash('种子已删除', 'success')
    else:
        flash('种子不存在', 'danger')
    
    db.close()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
