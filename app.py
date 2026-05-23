from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, make_response, session, jsonify
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
import secrets

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
    
    # API Keys表
    db.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            key TEXT UNIQUE NOT NULL,
            name TEXT,
            created_at TEXT NOT NULL,
            last_used TEXT,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
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

# ==================== 认证装饰器 ====================

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

def api_auth_required(f):
    """API认证装饰器 - 通过API Key或Session"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 优先检查API Key
        api_key = None
        
        # 从Header获取
        if 'X-API-Key' in request.headers:
            api_key = request.headers['X-API-Key']
        # 从Query参数获取
        elif request.args.get('api_key'):
            api_key = request.args.get('api_key')
        # 从JSON body获取
        elif request.is_json and request.json and 'api_key' in request.json:
            api_key = request.json['api_key']
        
        if api_key:
            user = get_user_by_api_key(api_key)
            if user:
                # 更新最后使用时间
                update_api_key_last_used(api_key)
                request.current_user = user
                request.auth_type = 'api_key'
                return f(*args, **kwargs)
            else:
                return jsonify({'success': False, 'error': 'Invalid API key'}), 401
        
        # 如果没有API Key，检查Session（用于浏览器访问）
        if 'user_id' in session:
            user = get_user_by_id(session['user_id'])
            if user:
                request.current_user = user
                request.auth_type = 'session'
                return f(*args, **kwargs)
        
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    return decorated_function

def api_publisher_required(f):
    """API发布员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(request, 'current_user'):
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        user = request.current_user
        if user['role'] not in ['admin', 'publisher']:
            return jsonify({'success': False, 'error': 'Publisher or admin role required'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

# ==================== 用户和API Key辅助函数 ====================

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

def get_user_by_api_key(api_key):
    """通过API Key获取用户"""
    db = get_db()
    result = db.execute('''
        SELECT u.* FROM users u
        JOIN api_keys k ON u.id = k.user_id
        WHERE k.key = ? AND k.is_active = 1
    ''', (api_key,)).fetchone()
    db.close()
    return dict(result) if result else None

def update_api_key_last_used(api_key):
    """更新API Key最后使用时间"""
    db = get_db()
    db.execute('UPDATE api_keys SET last_used = ? WHERE key = ?', 
               (datetime.now().isoformat(), api_key))
    db.commit()
    db.close()

def generate_api_key():
    """生成安全的API Key"""
    return 'sgd_' + secrets.token_urlsafe(32)

def get_user_api_keys(user_id):
    """获取用户的所有API Keys"""
    db = get_db()
    keys = db.execute('''
        SELECT * FROM api_keys 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    ''', (user_id,)).fetchall()
    db.close()
    return [dict(k) for k in keys]

# ==================== 页面路由 ====================

@app.route('/')
def index():
    db = get_db()
    torrents = db.execute('''
        SELECT * FROM torrents 
        ORDER BY created_at DESC
    ''').fetchall()
    db.close()
    return render_template('index.html', torrents=[dict(t) for t in torrents])

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

@app.route('/logout')
def logout():
    session.clear()
    flash('已退出登录', 'info')
    return redirect(url_for('index'))

# ==================== 上传和下载 ====================

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

# ==================== RSS Feed ====================

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
        
        # enclosure标签
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

# ==================== 管理后台 ====================

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

# ==================== API Key 管理 ====================

@app.route('/api-keys')
@login_required
def api_keys():
    """API Key管理页面"""
    keys = get_user_api_keys(session['user_id'])
    return render_template('api_keys.html', api_keys=keys)

@app.route('/api-keys/create', methods=['POST'])
@login_required
def create_api_key():
    """创建新的API Key"""
    name = request.form.get('name', 'Default')
    
    db = get_db()
    api_key = generate_api_key()
    db.execute('''
        INSERT INTO api_keys (id, user_id, key, name, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        str(uuid.uuid4()),
        session['user_id'],
        api_key,
        name,
        datetime.now().isoformat()
    ))
    db.commit()
    db.close()
    
    flash(f'API Key 创建成功！请立即复制保存，这是唯一一次显示：{api_key}', 'success')
    return redirect(url_for('api_keys'))

@app.route('/api-keys/delete/<key_id>')
@login_required
def delete_api_key(key_id):
    """删除API Key"""
    db = get_db()
    # 确保只能删除自己的key
    db.execute('DELETE FROM api_keys WHERE id = ? AND user_id = ?', 
               (key_id, session['user_id']))
    db.commit()
    db.close()
    
    flash('API Key 已删除', 'info')
    return redirect(url_for('api_keys'))

# ==================== API 文档页面 ====================

@app.route('/api/docs')
def api_docs():
    """API文档页面"""
    base_url = request.url_root.rstrip('/')
    return render_template('api_docs.html', base_url=base_url)

# ==================== API 端点 ====================

@app.route('/api/v1/torrents', methods=['GET'])
@api_auth_required
def api_get_torrents():
    """获取种子列表"""
    try:
        # 分页参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        per_page = min(per_page, 100)  # 最大100条
        
        # 分类过滤
        category = request.args.get('category')
        
        # 搜索
        search = request.args.get('search')
        
        db = get_db()
        
        # 构建查询
        query = 'SELECT * FROM torrents WHERE 1=1'
        params = []
        
        if category:
            query += ' AND category = ?'
            params.append(category)
        
        if search:
            query += ' AND (title LIKE ? OR description LIKE ?)'
            params.extend([f'%{search}%', f'%{search}%'])
        
        # 获取总数
        count_query = query.replace('SELECT *', 'SELECT COUNT(*) as total')
        total = db.execute(count_query, params).fetchone()['total']
        
        # 获取分页数据
        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([per_page, (page - 1) * per_page])
        
        torrents = db.execute(query, params).fetchall()
        db.close()
        
        # 构建响应
        results = []
        for t in torrents:
            t = dict(t)
            results.append({
                'id': t['id'],
                'title': t['title'],
                'description': t['description'],
                'category': t['category'],
                'file_size': t['file_size'],
                'file_size_human': f"{t['file_size'] / 1024 / 1024:.2f} MB",
                'created_at': t['created_at'],
                'publisher_name': t['publisher_name'],
                'download_url': url_for('download', torrent_id=t['id'], _external=True)
            })
        
        return jsonify({
            'success': True,
            'data': {
                'torrents': results,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'total_pages': (total + per_page - 1) // per_page
                }
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/v1/torrents', methods=['POST'])
@api_auth_required
@api_publisher_required
def api_upload_torrent():
    """通过API上传种子"""
    try:
        # 获取数据
        if request.content_type and 'multipart/form-data' in request.content_type:
            # 表单上传
            title = request.form.get('title')
            description = request.form.get('description', '')
            category = request.form.get('category', 'general')
            
            if 'torrent' not in request.files:
                return jsonify({'success': False, 'error': 'No torrent file provided'}), 400
            
            file = request.files['torrent']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No torrent file selected'}), 400
        else:
            # JSON上传（需要提供URL或base64）
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            title = data.get('title')
            description = data.get('description', '')
            category = data.get('category', 'general')
            
            # 这里可以扩展支持URL下载或base64解码
            return jsonify({'success': False, 'error': 'Please use multipart/form-data to upload torrent files'}), 400
        
        if not title:
            return jsonify({'success': False, 'error': 'Title is required'}), 400
        
        # 保存文件
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        # 保存到数据库
        torrent_id = str(uuid.uuid4())
        db = get_db()
        db.execute('''
            INSERT INTO torrents (id, title, description, category, filename, 
                                original_filename, file_size, created_at, 
                                publisher_id, publisher_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            torrent_id,
            title,
            description,
            category,
            unique_filename,
            filename,
            os.path.getsize(file_path),
            datetime.now().isoformat(),
            request.current_user['id'],
            request.current_user['username']
        ))
        db.commit()
        db.close()
        
        return jsonify({
            'success': True,
            'data': {
                'id': torrent_id,
                'title': title,
                'download_url': url_for('download', torrent_id=torrent_id, _external=True),
                'message': 'Torrent uploaded successfully'
            }
        }), 201
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/v1/torrents/<torrent_id>', methods=['GET'])
@api_auth_required
def api_get_torrent(torrent_id):
    """获取单个种子详情"""
    try:
        db = get_db()
        torrent = db.execute('SELECT * FROM torrents WHERE id = ?', (torrent_id,)).fetchone()
        db.close()
        
        if not torrent:
            return jsonify({'success': False, 'error': 'Torrent not found'}), 404
        
        t = dict(torrent)
        return jsonify({
            'success': True,
            'data': {
                'id': t['id'],
                'title': t['title'],
                'description': t['description'],
                'category': t['category'],
                'file_size': t['file_size'],
                'file_size_human': f"{t['file_size'] / 1024 / 1024:.2f} MB",
                'created_at': t['created_at'],
                'publisher_name': t['publisher_name'],
                'download_url': url_for('download', torrent_id=t['id'], _external=True)
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/v1/categories', methods=['GET'])
def api_get_categories():
    """获取所有分类"""
    try:
        db = get_db()
        categories = db.execute('''
            SELECT category, COUNT(*) as count 
            FROM torrents 
            GROUP BY category 
            ORDER BY count DESC
        ''').fetchall()
        db.close()
        
        return jsonify({
            'success': True,
            'data': [dict(c) for c in categories]
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/v1/stats', methods=['GET'])
def api_get_stats():
    """获取站点统计信息"""
    try:
        db = get_db()
        
        total_torrents = db.execute('SELECT COUNT(*) as count FROM torrents').fetchone()['count']
        total_users = db.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
        total_size = db.execute('SELECT COALESCE(SUM(file_size), 0) as total FROM torrents').fetchone()['total']
        
        # 最近24小时上传数
        from datetime import timedelta
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        recent_torrents = db.execute(
            'SELECT COUNT(*) as count FROM torrents WHERE created_at > ?', 
            (yesterday,)
        ).fetchone()['count']
        
        db.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_torrents': total_torrents,
                'total_users': total_users,
                'total_size': total_size,
                'total_size_human': f"{total_size / 1024 / 1024 / 1024:.2f} GB",
                'recent_torrents_24h': recent_torrents,
                'site_name': os.getenv('SITE_NAME', 'RSS种子站点'),
                'rss_url': url_for('rss_feed', _external=True)
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/v1/user', methods=['GET'])
@api_auth_required
def api_get_user():
    """获取当前用户信息"""
    try:
        user = request.current_user
        return jsonify({
            'success': True,
            'data': {
                'id': user['id'],
                'username': user['username'],
                'role': user['role'],
                'auth_type': getattr(request, 'auth_type', 'unknown')
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Endpoint not found'}), 404
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_error(error):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
    return render_template('index.html'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
