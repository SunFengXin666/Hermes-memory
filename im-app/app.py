from flask import Flask, request, jsonify, send_from_directory, redirect, Response, stream_with_context
from pathlib import Path
import requests
import json
import os
import uuid
import paramiko
import threading
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__, static_folder='static')

APP_VERSION = '1.7.4'
APK_VERSION = '1.7.4'  # 有新APK时改这个，页面会提示"新版本可下载"
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

DAILY_TOKEN_LIMIT = 5_000_000

def _is_deepseek(provider):
    return provider.get('id') == 'deepseek' or provider.get('name', '').lower() == 'deepseek'

def _check_token_limit(user_id):
    path = _user_dir(user_id) / 'token_usage.json'
    today = datetime.now().strftime('%Y-%m-%d')
    used = 0
    if path.exists():
        data = json.loads(path.read_text())
        if data.get('date') == today:
            used = data.get('deepseek_tokens', 0)
    return used < DAILY_TOKEN_LIMIT, used

def _record_tokens(user_id, provider, count):
    if not _is_deepseek(provider) or count <= 0:
        return
    path = _user_dir(user_id) / 'token_usage.json'
    today = datetime.now().strftime('%Y-%m-%d')
    old = {}
    if path.exists():
        old = json.loads(path.read_text())
    data = {'date': today, 'deepseek_tokens': count}
    if old.get('date') == today:
        data['deepseek_tokens'] = old.get('deepseek_tokens', 0) + count
    path.write_text(json.dumps(data))

HERMES_API = 'http://100.107.11.26:8642/v1'
HERMES_KEY = '44c7cddf60761d694d6c2f424e4a4b4fe9220d26f7327ded'
MEMORIES_DIR = os.path.expanduser('~/daily-memories')
UPLOAD_DIR = Path('/tmp/webui-uploads')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_DIR = Path('/tmp/webui-downloads')
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
BASE_DIR = Path('/root/webui')
DATA_DIR = BASE_DIR / 'data'

# ─── Database ───
DB_PATH = BASE_DIR / 'users.db'

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS auth_tokens (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    ''')
    conn.commit()
    conn.close()

init_db()

# ─── Auth Helpers ───
def hash_password(password):
    salt = 'hermes_webui_salt_2026'
    return hashlib.sha256((password + salt).encode()).hexdigest()

def generate_token():
    return secrets.token_hex(32)

def get_user_by_token(token):
    if not token:
        return None
    conn = get_db()
    row = conn.execute(
        'SELECT u.id, u.username FROM auth_tokens t JOIN users u ON t.user_id = u.id WHERE t.token = ?',
        [token]
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = get_user_by_token(token)
        if not user:
            return jsonify({'error': '未登录'}), 401
        return f(user, *args, **kwargs)
    return decorated

def _user_dir(user_id):
    # Get username from DB for folder name
    conn = get_db()
    row = conn.execute('SELECT username FROM users WHERE id = ?', [user_id]).fetchone()
    conn.close()
    username = row['username'] if row else user_id
    d = DATA_DIR / username
    d.mkdir(parents=True, exist_ok=True)
    return d

# ─── Per-User Provider Storage ───
def _load_providers(user_id):
    path = _user_dir(user_id) / 'providers.json'
    if not path.exists():
        # Seed defaults for new user
        defaults = [
            {'id': 'deepseek', 'name': 'DeepSeek', 'base_url': 'https://api.deepseek.com/v1', 'api_key': 'sk-1935b91149a345a1b1fbcb8bf7f2c614', 'models': ['deepseek-chat', 'deepseek-v4-flash']},
        ]
        _save_providers(user_id, defaults)
        return defaults
    return json.loads(path.read_text())

def _save_providers(user_id, providers):
    path = _user_dir(user_id) / 'providers.json'
    path.write_text(json.dumps(providers, ensure_ascii=False, indent=2))

# ─── Auth API ───
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    if len(username) < 2 or len(password) < 4:
        return jsonify({'ok': False, 'error': '用户名至少2个字符，密码至少4个字符'}), 400
    conn = get_db()
    existing = conn.execute('SELECT id FROM users WHERE username = ?', [username]).fetchone()
    if existing:
        conn.close()
        return jsonify({'ok': False, 'error': '用户名已被注册'}), 400
    user_id = uuid.uuid4().hex[:8]
    conn.execute('INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)',
                 [user_id, username, hash_password(password)])
    conn.commit()
    conn.close()
    # 新用户自动创建远程目录
    try:
        remote_user = 'ubuntu'
        remote_pass = 'SunFengXin521?'
        remote_host = '81.70.229.222'
        remote_port = 22
        remote_base = '/home/ubuntu/113646'
        remote_dir = f'{remote_base}/{username}'
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(remote_host, port=remote_port, username=remote_user, password=remote_pass, timeout=15, banner_timeout=8, auth_timeout=10)
        sftp = client.open_sftp()
        try:
            sftp.stat(remote_dir)
        except:
            sftp.mkdir(remote_dir)
        sftp.close()
        client.close()
        # 保存 dysk 配置
        disk_cfg = {
            'host': remote_host,
            'port': remote_port,
            'username': remote_user,
            'password': remote_pass,
            'root_path': remote_dir
        }
        d = _user_dir(user_id)
        (d / 'disk_config.json').write_text(json.dumps(disk_cfg, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f'[register] 创建用户目录失败: {e}')
    return jsonify({'ok': True, 'message': '注册成功'})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    conn = get_db()
    user = conn.execute('SELECT id, username FROM users WHERE username = ? AND password_hash = ?',
                        [username, hash_password(password)]).fetchone()
    if not user:
        conn.close()
        return jsonify({'ok': False, 'error': '用户名或密码错误'}), 401
    token = generate_token()
    conn.execute('INSERT INTO auth_tokens (token, user_id) VALUES (?, ?)', [token, user['id']])
    # Clean old tokens (>30 days)
    conn.execute("DELETE FROM auth_tokens WHERE created_at < datetime('now', '-30 days')")
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'token': token, 'username': user['username']})

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout(user):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    conn = get_db()
    conn.execute('DELETE FROM auth_tokens WHERE token = ?', [token])
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/auth/check', methods=['GET'])
def auth_check():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = get_user_by_token(token)
    if user:
        return jsonify({'ok': True, 'username': user['username']})
    return jsonify({'ok': False}), 401

# ─── Providers API (per-user) ───
@app.route('/api/providers', methods=['GET'])
@require_auth
def list_providers(user):
    return jsonify(_load_providers(user['id']))

@app.route('/api/providers', methods=['POST'])
@require_auth
def add_provider(user):
    data = request.json
    if not data.get('name') or not data.get('base_url') or not data.get('api_key'):
        return jsonify({'ok': False, 'error': '名称、接口地址、API Key 不能为空'}), 400
    providers = _load_providers(user['id'])
    new_id = uuid.uuid4().hex[:8]
    entry = {
        'id': new_id,
        'name': data['name'],
        'base_url': data['base_url'].rstrip('/'),
        'api_key': data['api_key'],
        'models': data.get('models', [data.get('name')]),
    }
    providers.append(entry)
    _save_providers(user['id'], providers)
    return jsonify({'ok': True, 'provider': entry})

@app.route('/api/providers/<provider_id>', methods=['DELETE'])
@require_auth
def delete_provider(user, provider_id):
    providers = _load_providers(user['id'])
    providers = [p for p in providers if p['id'] != provider_id]
    _save_providers(user['id'], providers)
    return jsonify({'ok': True})

@app.route('/api/providers/<provider_id>', methods=['PUT'])
@require_auth
def update_provider(user, provider_id):
    data = request.json
    providers = _load_providers(user['id'])
    for p in providers:
        if p['id'] == provider_id:
            if 'name' in data: p['name'] = data['name']
            if 'base_url' in data: p['base_url'] = data['base_url'].rstrip('/')
            if 'api_key' in data: p['api_key'] = data['api_key']
            if 'models' in data: p['models'] = data['models']
            _save_providers(user['id'], providers)
            return jsonify({'ok': True, 'provider': p})
    return jsonify({'ok': False, 'error': '未找到'}), 404

# ─── Chat API (per-user) ───
def _find_model_provider(providers, model_name):
    for p in providers:
        if model_name in p.get('models', []):
            return p, model_name
        if model_name.startswith(p.get('name', '').lower()):
            return p, model_name
    return None, None

@app.route('/api/chat', methods=['POST'])
@require_auth
def chat(user):
    data = request.json
    model = data.get('model', 'hermes-agent')
    stream = data.get('stream', False)
    providers = _load_providers(user['id'])
    provider, actual_model = _find_model_provider(providers, model)
    if not provider:
        return jsonify({'error': f'未找到模型 {model} 的提供商，请先在模型页配置 API Key', 'ok': False}), 400
    if not provider.get('api_key'):
        return jsonify({'error': f'提供商 "{provider["name"]}" 未配置 API Key，请先在模型页配置', 'ok': False}), 400

    # ─── Daily token limit (DeepSeek only) ───
    if _is_deepseek(provider):
        allowed, used = _check_token_limit(user['id'])
        if not allowed:
            return jsonify({
                'error': f'今日 DeepSeek 额度已用尽（{used:,}/{DAILY_TOKEN_LIMIT:,} tokens），明天再试',
                'ok': False
            }), 429

    try:
        def sanitize_msgs(msgs):
            out = []
            for m in msgs:
                if isinstance(m.get('content'), list):
                    texts = [p.get('text','') for p in m['content'] if p.get('type') == 'text']
                    out.append({**m, 'content': texts[0] if texts else '[图片]'})
                else:
                    out.append(m)
            return out
        
        raw = data.get('messages', [])
        
        if stream:
            # Streaming mode — strip images proactively (can't retry mid-stream)
            clean = sanitize_msgs(raw)
            prov_resp = requests.post(f"{provider['base_url']}/chat/completions",
                json={'model': actual_model or model, 'messages': clean, 'stream': True},
                headers={'Authorization': 'Bearer ' + provider['api_key'], 'Content-Type': 'application/json'},
                stream=True, timeout=120)
            
            if prov_resp.status_code >= 400:
                result = prov_resp.json()
                err_body = result.get('error', result)
                err_msg = err_body.get('message', str(err_body)) if isinstance(err_body, dict) else str(err_body)
                if isinstance(err_body, dict) and err_body.get('metadata', {}).get('raw'):
                    err_msg += ' (' + err_body['metadata']['raw'] + ')'
                return jsonify({'error': err_msg, 'ok': False}), prov_resp.status_code
            
            def generate():
                content_chars = 0
                for line in prov_resp.iter_lines():
                    if line:
                        decoded = line.decode('utf-8') if isinstance(line, bytes) else line
                        if decoded.startswith('data: ') and decoded != 'data: [DONE]':
                            try:
                                chunk = json.loads(decoded[6:])
                                for c in chunk.get('choices', []):
                                    content = c.get('delta', {}).get('content', '')
                                    content_chars += len(content)
                            except:
                                pass
                        yield decoded + '\n'
                if _is_deepseek(provider) and content_chars > 0:
                    _record_tokens(user['id'], provider, max(content_chars // 2, 1))
            return Response(stream_with_context(generate()),
                          mimetype='text/event-stream',
                          headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
        
        # Non-streaming mode
        resp = requests.post(f"{provider['base_url']}/chat/completions", json={
                'model': actual_model or model,
                'messages': raw,
                'stream': False
            }, headers={'Authorization': 'Bearer ' + provider['api_key'], 'Content-Type': 'application/json'}, timeout=120)
        result = resp.json()
        # If it failed due to content format (image_url not supported), retry text-only
        if resp.status_code >= 400:
            err_msg = ''
            err_body = result.get('error', result)
            if isinstance(err_body, dict):
                err_msg = err_body.get('message', str(err_body))
            else:
                err_msg = str(err_body)
            if 'image_url' in err_msg.lower() or 'variant' in err_msg.lower() or 'deserialize' in err_msg.lower() or 'image' in err_msg.lower() or 'vision' in err_msg.lower():
                resp = requests.post(f"{provider['base_url']}/chat/completions", json={
                    'model': actual_model or model,
                    'messages': sanitize_msgs(raw),
                    'stream': False
                }, headers={'Authorization': 'Bearer ' + provider['api_key'], 'Content-Type': 'application/json'}, timeout=120)
                result = resp.json()
        if resp.status_code >= 400:
            err_body = result.get('error', result)
            err_msg = err_body.get('message', str(err_body)) if isinstance(err_body, dict) else str(err_body)
            # 如果有更详细的原始错误信息，追加到提示中
            if isinstance(err_body, dict) and err_body.get('metadata', {}).get('raw'):
                err_msg += ' (' + err_body['metadata']['raw'] + ')'
            return jsonify({'error': err_msg, 'ok': False}), resp.status_code
        # Record tokens for non-streaming
        if _is_deepseek(provider):
            usage = result.get('usage', {})
            total = usage.get('total_tokens', 0) or usage.get('completion_tokens', 0)
            if total:
                _record_tokens(user['id'], provider, total)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/models', methods=['GET'])
@require_auth
def models(user):
    all_models = []
    try:
        resp = requests.get(f'{HERMES_API}/models', headers={'Authorization': f'Bearer {HERMES_KEY}'}, timeout=10)
        all_models = resp.json().get('data', [])
    except:
        pass
    providers = _load_providers(user['id'])
    existing_ids = {m['id'] for m in all_models}
    for p in providers:
        for m in p.get('models', []):
            if m not in existing_ids:
                all_models.append({'id': m, 'object': 'model', 'owned_by': p['name']})
                existing_ids.add(m)
    return jsonify({'data': all_models, 'object': 'list'})

# ─── Per-User Chat Storage ───
@app.route('/api/chats', methods=['GET'])
@require_auth
def get_chats(user):
    path = _user_dir(user['id']) / 'chats.json'
    if not path.exists():
        return jsonify([])
    return jsonify(json.loads(path.read_text()))

@app.route('/api/chats', methods=['PUT'])
@require_auth
def save_chats(user):
    path = _user_dir(user['id']) / 'chats.json'
    path.write_text(json.dumps(request.json, ensure_ascii=False, indent=2))
    return jsonify({'ok': True})

# ─── Per-User Sync to GitHub ───
@app.route('/api/sync', methods=['POST'])
@require_auth
def sync_user_data(user):
    """Push this user's data to GitHub"""
    import subprocess
    try:
        sync_dir = os.path.expanduser('/root/hermes-memory-backup/users')
        user_dir = os.path.join(sync_dir, user['username'])
        os.makedirs(user_dir, exist_ok=True)
        # Copy user files
        for f in [f'chats_{user["id"]}.json', f'providers_{user["id"]}.json']:
            src = BASE_DIR / f
            if src.exists():
                dest = os.path.join(user_dir, f.replace(f'_{user["id"]}', ''))
                import shutil
                shutil.copy2(str(src), dest)
        # Git commit & push
        result = subprocess.run(
            ['bash', '/root/hermes-memory-backup/sync.sh'],
            capture_output=True, text=True, timeout=60
        )
        return jsonify({'ok': True, 'output': result.stdout[-500:]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ─── SFTP Connection Pool ───
sftp_connections: dict[str, dict] = {}
sftp_lock = threading.Lock()

def _get_conn(conn_id):
    with sftp_lock:
        return sftp_connections.get(conn_id)

def _fresh_sftp(conn_id):
    conn = _get_conn(conn_id)
    if not conn:
        return None, None, '连接已断开'
    # Try existing connection first
    try:
        client = conn['client']
        transport = client.get_transport()
        if transport and transport.is_active():
            sftp = conn['sftp']
            sftp.stat('/')  # Quick liveness check
            return client, sftp, None
    except:
        pass
    # Reconnect
    info = conn['info']
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(info['host'], port=int(info.get('port', 22)),
            username=info['username'], password=info.get('password', ''),
            timeout=15, banner_timeout=8, auth_timeout=10)
        client.get_transport().set_keepalive(15)
        sftp = client.open_sftp()
        # Update connection
        conn['client'] = client
        conn['sftp'] = sftp
        return client, sftp, None
    except Exception as e:
        return None, None, str(e)

@app.route('/api/disk/connect', methods=['POST'])
@require_auth
def disk_connect(user):
    data = request.json
    host = data.get('host', '')
    port = int(data.get('port', 22))
    username = data.get('username', '')
    password = data.get('password', '')
    root_path = data.get('root_path', '').strip()
    if not host or not username:
        return jsonify({'ok': False, 'error': '缺少主机地址或用户名'}), 400
    if root_path:
        root_path = '/' + root_path.lstrip('/').rstrip('/')
    with sftp_lock:
        for cid, conn in list(sftp_connections.items()):
            info = conn.get('info', {})
            if info.get('host') == host and info.get('username') == username:
                try: conn['sftp'].close()
                except: pass
                try: conn['client'].close()
                except: pass
                del sftp_connections[cid]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(host, port=port, username=username, password=password, timeout=15, banner_timeout=8, auth_timeout=10)
        client.get_transport().set_keepalive(15)
        sftp = client.open_sftp()
        if root_path:
            parts = root_path.strip('/').split('/')
            cur = ''
            for p in parts:
                cur += '/' + p
                try: sftp.stat(cur)
                except: sftp.mkdir(cur)
        conn_id = uuid.uuid4().hex[:8]
        with sftp_lock:
            sftp_connections[conn_id] = {
                'client': client, 'sftp': sftp,
                'info': {'host': host, 'port': port, 'username': username, 'password': password, 'root_path': root_path}
            }
        return jsonify({'ok': True, 'conn_id': conn_id, 'host': host, 'username': username, 'root_path': root_path})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@app.route('/api/disk/<conn_id>/list', methods=['GET'])
def disk_list(conn_id):
    path = request.args.get('path', '/')
    client, sftp, err = _fresh_sftp(conn_id)
    if err:
        return jsonify({'ok': False, 'error': err}), 404
    try:
        items = sftp.listdir_attr(path)
        entries = []
        for item in items:
            entries.append({
                'name': item.filename,
                'size': item.st_size,
                'mtime': item.st_mtime,
                'is_dir': item.st_mode is not None and (item.st_mode & 0o40000) != 0,
            })
        entries.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        return jsonify({'ok': True, 'entries': entries, 'path': path})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    finally:
        try: sftp.close()
        except: pass
        try: client.close()
        except: pass

@app.route('/api/disk/<conn_id>/upload', methods=['POST'])
def disk_upload(conn_id):
    dest_dir = request.form.get('path', '/')
    file = request.files.get('file')
    if not file:
        return jsonify({'ok': False, 'error': '没有文件'}), 400
    conn = _get_conn(conn_id)
    if not conn:
        return jsonify({'ok': False, 'error': '连接已断开'}), 404
    info = conn['info']
    local_tmp = UPLOAD_DIR / f'ul_{uuid.uuid4().hex[:12]}_{file.filename}'
    file.save(str(local_tmp))
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(info['host'], port=int(info.get('port', 22)),
            username=info['username'], password=info.get('password', ''), timeout=30)
        sftp = client.open_sftp()
        remote_path = os.path.join(dest_dir, file.filename).replace('\\', '/')
        sftp.put(str(local_tmp), remote_path)
        sftp.close()
        client.close()
        local_tmp.unlink(missing_ok=True)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@app.route('/api/disk/<conn_id>/download', methods=['GET'])
def disk_download(conn_id):
    path = request.args.get('path', '')
    conn = _get_conn(conn_id)
    if not conn:
        return jsonify({'ok': False, 'error': '连接已断开'}), 404
    info = conn['info']
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(info['host'], port=int(info.get('port', 22)),
            username=info['username'], password=info.get('password', ''),
            timeout=15, banner_timeout=8, auth_timeout=10)
        sftp = client.open_sftp()
        filename = os.path.basename(path)
        local_path = DOWNLOAD_DIR / f'{uuid.uuid4().hex[:8]}_{filename}'
        sftp.get(path, str(local_path))
        sftp.close()
        client.close()
        return jsonify({'ok': True, 'url': f'/dl/{local_path.name}', 'filename': filename})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@app.route('/dl/<path:filename>')
def serve_download(filename):
    return send_from_directory(str(DOWNLOAD_DIR), filename, as_attachment=True)

@app.route('/api/disk/<conn_id>/delete', methods=['POST'])
def disk_delete(conn_id):
    path = request.json.get('path', '')
    conn = _get_conn(conn_id)
    if not conn:
        return jsonify({'ok': False, 'error': '连接已断开'}), 404
    info = conn['info']
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(info['host'], port=int(info.get('port', 22)),
            username=info['username'], password=info.get('password', ''),
            timeout=15, banner_timeout=8, auth_timeout=10)
        sftp = client.open_sftp()
        try: sftp.rmdir(path)
        except: sftp.remove(path)
        sftp.close()
        client.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@app.route('/api/disk/<conn_id>/mkdir', methods=['POST'])
def disk_mkdir(conn_id):
    path = request.json.get('path', '')
    conn = _get_conn(conn_id)
    if not conn:
        return jsonify({'ok': False, 'error': '连接已断开'}), 404
    info = conn['info']
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(info['host'], port=int(info.get('port', 22)),
            username=info['username'], password=info.get('password', ''),
            timeout=15, banner_timeout=8, auth_timeout=10)
        sftp = client.open_sftp()
        sftp.mkdir(path)
        sftp.close()
        client.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@app.route('/api/disk/<conn_id>/disconnect', methods=['POST'])
def disk_disconnect(conn_id):
    with sftp_lock:
        conn = sftp_connections.pop(conn_id, None)
    if conn:
        try: conn['sftp'].close()
        except: pass
        try: conn['client'].close()
        except: pass

@app.route('/api/disk/config', methods=['GET'])
@require_auth
def disk_config(user):
    path = _user_dir(user['id']) / 'disk_config.json'
    if path.exists():
        return jsonify(json.loads(path.read_text()))
    return jsonify({})

    return jsonify({'ok': True})

# ─── 每日记忆 API ───
@app.route('/api/memories', methods=['GET'])
@require_auth
def list_memories(user):
    Path(MEMORIES_DIR).mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(Path(MEMORIES_DIR).glob('*.md'), reverse=True):
        try:
            dt = datetime.strptime(f.stem, '%Y-%m-%d')
            title = f'{dt.year}年{dt.month}月{dt.day}日'
        except:
            title = f.stem
        files.append({'date': f.stem, 'title': title, 'size': f.stat().st_size})
    return jsonify(files)

@app.route('/api/memories/<date>', methods=['GET'])
@require_auth
def get_memory(user, date):
    path = Path(MEMORIES_DIR) / f'{date}.md'
    if not path.exists():
        return jsonify({'error': 'not found'}), 404
    return jsonify({'date': date, 'content': path.read_text(encoding='utf-8')})

@app.route('/api/memories/today', methods=['GET'])
@require_auth
def today_memory(user):
    today = datetime.now().strftime('%Y-%m-%d')
    path = Path(MEMORIES_DIR) / f'{today}.md'
    exists = path.exists()
    return jsonify({'date': today, 'exists': exists, 'content': path.read_text(encoding='utf-8') if exists else ''})

# ─── 页面路由 ───
def serve_page(page):
    path = BASE_DIR / 'templates' / page
    with open(str(path), 'r', encoding='utf-8') as f:
        content = f.read()
    resp = Response(content, mimetype='text/html; charset=utf-8')
    mtime = path.stat().st_mtime
    resp.headers['Last-Modified'] = datetime.utcfromtimestamp(mtime).strftime('%a, %d %b %Y %H:%M:%S GMT')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp

@app.route('/')
def chat_page():
    return serve_page('chat.html')

@app.route('/disk')
def disk_page():
    return serve_page('disk.html')

@app.route('/memories')
def memories_page():
    return serve_page('memories.html')

@app.route('/models')
def models_page():
    return serve_page('models.html')

@app.route('/settings')
def settings_page():
    return serve_page('settings.html')

@app.route('/login')
def login_page():
    return send_from_directory('templates', 'login.html')

@app.route('/api/version')
def api_version():
    return jsonify({'version': APP_VERSION, 'latest_version': APK_VERSION, 'apk_url': '/api/download-apk'})

@app.route('/api/download-apk')
def download_apk():
    return send_from_directory('static', 'qingyun.apk', mimetype='application/vnd.android.package-archive', as_attachment=True, download_name='qingyun.apk')

@app.route('/api/token/usage', methods=['GET'])
@require_auth
def token_usage(user):
    _, used = _check_token_limit(user['id'])
    return jsonify({'date': datetime.now().strftime('%Y-%m-%d'), 'used': used, 'limit': DAILY_TOKEN_LIMIT})

if __name__ == '__main__':
    try:
        from waitress import serve
        serve(app, host='0.0.0.0', port=8080, threads=8, send_bytes=65536)
    except ImportError:
        app.run(host='0.0.0.0', port=8080, debug=True)
