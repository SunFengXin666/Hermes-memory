import os, json, threading, uuid, base64, queue, time, hashlib, secrets
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, session, make_response, Response
import paramiko
from openai import OpenAI

# ─── AI Chat ─────────────────────────────────
ai_memories: dict[str, list] = {}  # user_id -> message history
ai_locks: dict[str, threading.Lock] = {}
ai_configs: dict[str, dict] = {}  # user_id -> {api_key, base_url, model}

# Read Hermes memory files
def load_hermes_memories(user_id: str = '') -> str:
    system_info = '你的名字叫友友，是一个友善耐心的AI助手。用中文回答，简洁但友好。'
    try:
        user_md = Path('/root/.hermes/memories/USER.md').read_text(encoding='utf-8')
        memory_md = Path('/root/.hermes/memories/MEMORY.md').read_text(encoding='utf-8')
        user_info = user_md.replace('§', '\n').strip()
        sys_info = memory_md.replace('§', '\n').strip()
        system_info += f'\n\n关于用户的信息：\n{user_info}\n\n环境信息：\n{sys_info}'
    except Exception:
        pass
    if user_id:
        mem = load_user_memory(user_id)
        if mem:
            system_info += f'\n\n用户 {user_id} 的私人记忆：\n{mem}'
    return system_info

HERMES_SYSTEM_PROMPT = load_hermes_memories()

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
app.jinja_env.auto_reload = True

UPLOAD_DIR = Path('/tmp/im-app-uploads')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Public download directory (served statically)
DOWNLOAD_DIR = Path('/tmp/im-app-downloads')
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ─── Chat history persistence ─────────────────
CHAT_DIR = Path('/tmp/im-app-chat-history')
CHAT_DIR.mkdir(parents=True, exist_ok=True)
CHAT_LOCK = threading.Lock()

def get_history_path(user_id: str, model_idx: int = 0) -> Path:
    user_dir = CHAT_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / f'model_{model_idx}.jsonl'

def save_message(user_id: str, msg: dict, model_idx: int = 0):
    file_path = get_history_path(user_id, model_idx)
    with CHAT_LOCK:
        try:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(msg, ensure_ascii=False) + '\n')
        except Exception:
            pass

def load_history(user_id: str, model_idx: int = 0) -> list[dict]:
    file_path = get_history_path(user_id, model_idx)
    if not file_path.exists():
        return []
    with CHAT_LOCK:
        try:
            lines = file_path.read_text(encoding='utf-8').strip().split('\n')
            return [json.loads(l) for l in lines if l.strip()]
        except Exception:
            return []

# ─── Per-user memory persistence ─────────────────
MEMORY_DIR = Path('/tmp/im-app-memories')
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_LOCK = threading.Lock()

def save_user_memory(user_id: str, text: str):
    file_path = MEMORY_DIR / f'{user_id}.json'
    with MEMORY_LOCK:
        try:
            file_path.write_text(json.dumps({'user_id': user_id, 'text': text, 'updated_at': time.time()}, ensure_ascii=False), encoding='utf-8')
        except Exception:
            pass

def load_user_memory(user_id: str) -> str:
    file_path = MEMORY_DIR / f'{user_id}.json'
    if not file_path.exists():
        return ''
    with MEMORY_LOCK:
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
            return data.get('text', '')
        except Exception:
            return ''

# ─── User Profile (persistent storage) ────────────
USER_DIR = Path('/tmp/im-app-users')
USER_DIR.mkdir(parents=True, exist_ok=True)
USER_LOCK = threading.Lock()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def load_user_profile(username: str) -> dict:
    file_path = USER_DIR / f'{username}.json'
    if not file_path.exists():
        return None
    with USER_LOCK:
        try:
            return json.loads(file_path.read_text(encoding='utf-8'))
        except Exception:
            return None

def save_user_profile(username: str, profile: dict):
    file_path = USER_DIR / f'{username}.json'
    with USER_LOCK:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)

def profile_to_ai_config(profile: dict) -> dict:
    return {
        'presets': profile.get('ai_presets', []),
        'active': profile.get('ai_active', 0),
    }

@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({'ok': False, 'error': '用户名和密码不能为空'}), 400
    if len(username) < 2:
        return jsonify({'ok': False, 'error': '用户名至少2个字符'}), 400
    if len(password) < 4:
        return jsonify({'ok': False, 'error': '密码至少4个字符'}), 400
    if load_user_profile(username):
        return jsonify({'ok': False, 'error': '用户名已存在'}), 400
    profile = {
        'password_hash': hash_password(password),
        'ai_presets': [],
        'ai_active': 0,
        'servers': [],
        'memory': '',
        'created_at': time.time(),
    }
    save_user_profile(username, profile)
    return jsonify({'ok': True})

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({'ok': False, 'error': '用户名和密码不能为空'}), 400
    profile = load_user_profile(username)
    if not profile:
        return jsonify({'ok': False, 'error': '用户不存在'}), 400
    if profile.get('password_hash') != hash_password(password):
        return jsonify({'ok': False, 'error': '密码错误'}), 400
    # Generate session token
    token = secrets.token_hex(32)
    profile['token'] = token
    save_user_profile(username, profile)
    # Load profile into memory
    ai_configs[username] = profile_to_ai_config(profile)
    return jsonify({
        'ok': True,
        'token': token,
        'profile': {
            'ai_presets': profile.get('ai_presets', []),
            'ai_active': profile.get('ai_active', 0),
            'servers': profile.get('servers', []),
            'memory': profile.get('memory', ''),
        }
    })

@app.route('/api/auth/token_login', methods=['POST'])
def auth_token_login():
    data = request.json
    username = data.get('username', '').strip()
    token = data.get('token', '')
    if not username or not token:
        return jsonify({'ok': False, 'error': '参数不全'}), 400
    profile = load_user_profile(username)
    if not profile:
        return jsonify({'ok': False, 'error': '用户不存在'}), 400
    if profile.get('token') != token:
        return jsonify({'ok': False, 'error': 'token无效'}), 400
    ai_configs[username] = profile_to_ai_config(profile)
    return jsonify({
        'ok': True,
        'profile': {
            'ai_presets': profile.get('ai_presets', []),
            'ai_active': profile.get('ai_active', 0),
            'servers': profile.get('servers', []),
            'memory': profile.get('memory', ''),
        }
    })

# ─── Chat: SSE instead of WebSocket ─────────────────
# Each user has a list of per-SSE-connection queues
user_queues: dict[str, list[queue.Queue]] = {}
user_queues_lock = threading.Lock()
# Online users set
online_users: set[str] = set()
online_lock = threading.Lock()

def push_to_user(user_id: str, msg: dict):
    with user_queues_lock:
        qs = user_queues.get(user_id, [])
    payload = json.dumps(msg, ensure_ascii=False)
    for q in qs:
        q.put(payload)

@app.route('/')
def index():
    resp = make_response(render_template('index.html'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/api/chat/login', methods=['POST'])
def chat_login():
    data = request.json
    user_id = data.get('user_id', '').strip()
    if not user_id:
        return jsonify({'ok': False, 'error': '缺少用户ID'}), 400
    with online_lock:
        was_offline = user_id not in online_users
        online_users.add(user_id)
        users_snapshot = list(online_users)
    with user_queues_lock:
        user_queues.setdefault(user_id, [])
    if was_offline:
        notify_all({'type': 'user_online', 'user_id': user_id}, exclude=user_id)
    push_to_user(user_id, {'type': 'user_list', 'users': users_snapshot})
    active_idx = ai_configs.get(user_id, {}).get('active', 0)
    history = load_history(user_id, active_idx)
    return jsonify({'ok': True, 'users': users_snapshot, 'history': history, 'active_idx': active_idx})

@app.route('/api/chat/config', methods=['GET', 'POST'])
def chat_config():
    """GET → 获取当前用户的AI配置, POST → 设置AI配置"""
    user_id = request.json.get('user_id', '') if request.method == 'POST' else request.args.get('user_id', '')
    if not user_id:
        return jsonify({'ok': False, 'error': '缺少user_id'}), 400
    if request.method == 'POST':
        data = request.json
        # configs is an array of {name, api_key, base_url, model}
        ai_configs[user_id] = {
            'presets': data.get('presets', []),
            'active': data.get('active', 0),
        }
        # Persist to user profile
        profile = load_user_profile(user_id)
        if profile:
            profile['ai_presets'] = data.get('presets', [])
            profile['ai_active'] = data.get('active', 0)
            save_user_profile(user_id, profile)
        return jsonify({'ok': True})
    else:
        cfg = ai_configs.get(user_id, {'presets': [], 'active': 0})
        return jsonify({'ok': True, 'presets': cfg.get('presets', []), 'active': cfg.get('active', 0)})

@app.route('/api/chat/memory', methods=['GET', 'POST'])
def chat_memory():
    """GET → 获取用户的记忆, POST → 保存记忆"""
    user_id = request.json.get('user_id', '') if request.method == 'POST' else request.args.get('user_id', '')
    if not user_id:
        return jsonify({'ok': False, 'error': '缺少user_id'}), 400
    if request.method == 'POST':
        text = request.json.get('text', '')
        save_user_memory(user_id, text)
        return jsonify({'ok': True})
    else:
        text = load_user_memory(user_id)
        return jsonify({'ok': True, 'text': text})

@app.route('/api/chat/send', methods=['POST'])
def chat_send():
    data = request.json
    user_id = data.get('user_id', '')
    text = data.get('text', '').strip()
    if not user_id or not text:
        return jsonify({'ok': False, 'error': '参数不全'}), 400
    active_idx = ai_configs.get(user_id, {}).get('active', 0)
    push_to_user(user_id, {
        'type': 'message', 'from': user_id, 'text': text,
        'time': data.get('time', ''), 'isSelf': True, 'model_idx': active_idx,
    })
    save_message(user_id, {
        'from': user_id, 'text': text,
        'time': data.get('time', ''), 'isSelf': True,
    }, active_idx)
    threading.Thread(target=call_ai, args=(user_id, text), daemon=True).start()
    return jsonify({'ok': True})

def get_ai_config(user_id: str):
    """获取用户当前激活的AI配置，没有配置则用默认值"""
    cfg = ai_configs.get(user_id, {})
    presets = cfg.get('presets', [])
    active_idx = cfg.get('active', 0)
    if presets and active_idx < len(presets):
        p = presets[active_idx]
        return {
            'api_key': p.get('api_key', ''),
            'base_url': p.get('base_url', 'http://localhost:8642/v1'),
            'model': p.get('model', 'deepseek-v4-flash'),
            'name': p.get('name', 'AI'),
        }
    # Default fallback
    return {
        'api_key': '44c7cddf60761d694d6c2f424e4a4b4fe9220d26f7327ded',
        'base_url': 'http://localhost:8642/v1',
        'model': 'deepseek-v4-flash',
        'name': '友友',
    }

@app.route('/api/chat/completion', methods=['POST'])
def chat_completion():
    """同步AI接口：POST {"user_id":"xxx","text":"你好"} → {"ok":true,"reply":"..."}"""
    data = request.json
    user_id = data.get('user_id', '')
    text = data.get('text', '').strip()
    if not user_id or not text:
        return jsonify({'ok': False, 'error': '参数不全'}), 400
    try:
        active_idx = ai_configs.get(user_id, {}).get('active', 0)
        mem_key = f"{user_id}:{active_idx}"
        lock_key = f"{user_id}:{active_idx}"
        if lock_key not in ai_locks:
            ai_locks[lock_key] = threading.Lock()
        with ai_locks[lock_key]:
            if mem_key not in ai_memories:
                system_prompt = load_hermes_memories(user_id)
                ai_memories[mem_key] = [{'role': 'system', 'content': system_prompt}]
            ai_memories[mem_key].append({'role': 'user', 'content': text})
            if len(ai_memories[mem_key]) > 21:
                ai_memories[mem_key] = [ai_memories[mem_key][0]] + ai_memories[mem_key][-20:]
            cfg = get_ai_config(user_id)
            client = OpenAI(api_key=cfg['api_key'], base_url=cfg['base_url'])
            resp = client.chat.completions.create(
                model=cfg['model'],
                messages=ai_memories[mem_key],
                timeout=60,
            )
            reply = resp.choices[0].message.content
            ai_memories[mem_key].append({'role': 'assistant', 'content': reply})
        save_message(user_id, {'from': user_id, 'text': text, 'time': '', 'isSelf': True}, active_idx)
        save_message(user_id, {'from': 'AI', 'text': reply, 'time': '', 'isSelf': False}, active_idx)
        push_to_user(user_id, {'type': 'message', 'from': user_id, 'text': text, 'time': '', 'isSelf': True, 'model_idx': active_idx})
        push_to_user(user_id, {'type': 'message', 'from': 'AI', 'text': reply, 'time': '', 'isSelf': False, 'model_idx': active_idx})
        return jsonify({'ok': True, 'reply': reply})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ─── Cloud Disk Tools (for AI function calling) ─────
CLOUD_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出云盘目录下的文件和文件夹",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "目录路径，默认为云盘根目录",
                        "default": "/home/ubuntu/yunpan"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_text_file",
            "description": "读取云盘上的文本文件内容（支持txt、json、md、py、log等文本格式）",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件的完整路径"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_item",
            "description": "删除云盘上的文件或空目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "要删除的文件或目录路径"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "在云盘上创建新目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "要创建的目录路径"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_disk_usage",
            "description": "获取云盘的磁盘使用情况（总空间、已用、剩余）",
            "parameters": {"type": "object", "properties": {}}
        }
    },
]

def execute_cloud_tool(user_id: str, func_name: str, args: dict) -> dict:
    """Execute a cloud disk tool for the given user"""
    # Find the user's active connection
    conn_info = None
    for cid, conn in list(sftp_connections.items()):
        if conn['info'].get('user_id') == user_id:
            conn_info = conn['info']
            break
    if not conn_info:
        return {"error": "你没有连接的云盘服务器，请先在云盘页面连接服务器"}
    
    try:
        # Fresh connection for each operation
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(conn_info['host'], port=int(conn_info.get('port', 22)),
            username=conn_info['username'], password=conn_info.get('password', ''), timeout=15)
        sftp = client.open_sftp()
        
        result = {}
        if func_name == 'list_files':
            path = args.get('path', '/home/ubuntu/yunpan')
            items = sftp.listdir_attr(path)
            entries = []
            for item in items:
                entries.append({
                    'name': item.filename,
                    'size': item.st_size,
                    'mtime': item.st_mtime,
                    'is_dir': bool(item.st_mode & 0o40000),
                })
            entries.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
            result = {'files': entries, 'path': path, 'count': len(entries)}
        
        elif func_name == 'read_text_file':
            path = args['path']
            with sftp.open(path, 'r') as f:
                content = f.read()
            # Try to decode
            try:
                text = content.decode('utf-8')
            except:
                text = content.decode('utf-8', errors='replace')
            result = {'path': path, 'content': text, 'size': len(text)}
        
        elif func_name == 'delete_item':
            path = args['path']
            try:
                sftp.rmdir(path)
                result = {'deleted': path, 'type': 'directory'}
            except:
                sftp.remove(path)
                result = {'deleted': path, 'type': 'file'}
        
        elif func_name == 'create_directory':
            path = args['path']
            sftp.mkdir(path)
            result = {'created': path}
        
        elif func_name == 'get_disk_usage':
            QUOTA = 20 * 1024 * 1024 * 1024  # 20GB
            stdin, stdout, stderr = client.exec_command(f"du -sb {conn_info.get('base_path', '/home/ubuntu/yunpan')} | cut -f1")
            output = stdout.read().decode().strip()
            used = int(output) if output else 0
            free = max(0, QUOTA - used)
            result = {
                'total_bytes': QUOTA,
                'used_bytes': used,
                'free_bytes': free,
                'total_gb': 20.0,
                'used_gb': round(used / 1073741824, 2),
                'free_gb': round(free / 1073741824, 2),
                'used_percent': round(used / QUOTA * 100, 1) if QUOTA > 0 else 0,
            }
        elif func_name == 'get_disk_usage_error':
            result = {'error': '无法获取磁盘信息'}
        
        sftp.close()
        client.close()
        return result
    except Exception as e:
        return {'error': str(e)}

def call_ai(user_id: str, text: str):
    try:
        print(f"[AI] 收到消息 from {user_id}: {text[:50]}")
        active_idx = ai_configs.get(user_id, {}).get('active', 0)
        mem_key = f"{user_id}:{active_idx}"
        lock_key = f"{user_id}:{active_idx}"
        if lock_key not in ai_locks:
            ai_locks[lock_key] = threading.Lock()
        with ai_locks[lock_key]:
            if mem_key not in ai_memories:
                system_prompt = load_hermes_memories(user_id)
                system_prompt += '\n\n你具备云盘控制能力，可以列出文件、读取文本文件、删除文件、创建目录、查看磁盘空间。'
                ai_memories[mem_key] = [
                    {'role': 'system', 'content': system_prompt},
                ]
            ai_memories[mem_key].append({'role': 'user', 'content': text})
            if len(ai_memories[mem_key]) > 21:
                ai_memories[mem_key] = [ai_memories[mem_key][0]] + ai_memories[mem_key][-20:]
            cfg = get_ai_config(user_id)
            print(f"[AI] 调用API: {cfg['model']} @ {cfg['base_url']}")
            client = OpenAI(api_key=cfg['api_key'], base_url=cfg['base_url'])
            resp = client.chat.completions.create(
                model=cfg['model'],
                messages=ai_memories[mem_key],
                tools=CLOUD_TOOLS,
                tool_choice="auto",
                timeout=30,
            )
            # Handle tool calls loop
            tool_calls_used = False
            while resp.choices[0].finish_reason == "tool_calls":
                tool_calls_used = True
                msg = resp.choices[0].message
                ai_memories[mem_key].append({
                    'role': 'assistant',
                    'content': msg.content or '',
                    'tool_calls': [{
                        'id': tc.id,
                        'type': 'function',
                        'function': {'name': tc.function.name, 'arguments': tc.function.arguments}
                    } for tc in msg.tool_calls]
                })
                for tc in msg.tool_calls:
                    func_name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except:
                        args = {}
                    print(f"[AI] 执行云盘工具: {func_name}({args})")
                    result = execute_cloud_tool(user_id, func_name, args)
                    ai_memories[mem_key].append({
                        'role': 'tool',
                        'tool_call_id': tc.id,
                        'content': json.dumps(result, ensure_ascii=False)
                    })
                resp = client.chat.completions.create(
                    model=cfg['model'],
                    messages=ai_memories[mem_key],
                    tools=CLOUD_TOOLS,
                    tool_choice="auto",
                    timeout=30,
                )
            reply = resp.choices[0].message.content
            if not reply and tool_calls_used:
                reply = '✅ 操作已完成。'
            ai_memories[mem_key].append({'role': 'assistant', 'content': reply})
            print(f"[AI] 回复成功: {reply[:50]}...")
    except Exception as e:
        reply = f'⚠️ AI出错了: {str(e)}'
        print(f"[AI] 错误: {e}")
    push_to_user(user_id, {
        'type': 'message', 'from': 'AI', 'text': reply,
        'time': '', 'isSelf': False, 'model_idx': active_idx,
    })
    save_message(user_id, {
        'from': 'AI', 'text': reply,
        'time': '', 'isSelf': False,
    }, active_idx)
    print(f"[AI] 已推送到 {user_id}")

@app.route('/api/chat/events')
def chat_events():
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({'ok': False, 'error': '缺少user_id'}), 400
    q = queue.Queue()
    with user_queues_lock:
        user_queues.setdefault(user_id, []).append(q)
    def generate():
        try:
            while True:
                try:
                    msg = q.get(timeout=30)
                    yield f'data: {msg}\n\n'
                except queue.Empty:
                    yield ': keepalive\n\n'
        finally:
            with user_queues_lock:
                qs = user_queues.get(user_id, [])
                if q in qs:
                    qs.remove(q)
    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive',
                             'Access-Control-Allow-Origin': '*'})

@app.route('/api/chat/history', methods=['GET'])
def chat_history():
    user_id = request.args.get('user_id', '')
    model_idx = int(request.args.get('model_idx', 0))
    history = load_history(user_id, model_idx)
    return jsonify({'ok': True, 'history': history})

@app.route('/api/user/profile', methods=['POST'])
def user_profile():
    """Save user profile (servers, memory)"""
    data = request.json
    user_id = data.get('user_id', '')
    if not user_id:
        return jsonify({'ok': False, 'error': '缺少user_id'}), 400
    profile = load_user_profile(user_id)
    if not profile:
        return jsonify({'ok': False, 'error': '用户不存在'}), 400
    if 'servers' in data:
        profile['servers'] = data['servers']
    if 'memory' in data:
        profile['memory'] = data['memory']
    save_user_profile(user_id, profile)
    return jsonify({'ok': True})

def notify_all(msg: dict, exclude: str = None):
    payload = json.dumps(msg, ensure_ascii=False)
    with user_queues_lock:
        for uid, qs in user_queues.items():
            if uid != exclude:
                for q in qs:
                    q.put(payload)

@app.route('/api/chat/logout', methods=['POST'])
def chat_logout():
    user_id = request.json.get('user_id', '')
    if user_id:
        with online_lock:
            online_users.discard(user_id)
        with user_queues_lock:
            user_queues.pop(user_id, None)
        notify_all({'type': 'user_offline', 'user_id': user_id})
    return jsonify({'ok': True})

# ─── Cloud Disk: SFTP connections ────────────────────────────
sftp_connections: dict[str, dict] = {}

@app.route('/api/disks/connect', methods=['POST'])
def disk_connect():
    data = request.json
    host = data['host']
    port = int(data.get('port', 22))
    username = data['username']
    password = data.get('password', '')
    key_file = data.get('key_file', '')
    user_id = data.get('user_id', '')
    
    # Disconnect existing connection to same server/user
    for cid, conn in list(sftp_connections.items()):
        if conn['info'].get('host') == host and conn['info'].get('port') == port and conn['info'].get('username') == username:
            try: conn['sftp'].close()
            except: pass
            try: conn['client'].close()
            except: pass
            del sftp_connections[cid]
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        if key_file:
            key = paramiko.RSAKey.from_private_key_file(key_file)
            client.connect(host, port=port, username=username, pkey=key, timeout=10)
        else:
            client.connect(host, port=port, username=username, password=password, timeout=10)
        # Keepalive to prevent connection from being dropped
        client.get_transport().set_keepalive(15)
        sftp = client.open_sftp()
        conn_id = str(uuid.uuid4())[:8]
        data['user_id'] = user_id
        sftp_connections[conn_id] = {'client': client, 'sftp': sftp, 'info': data}
        return jsonify({'ok': True, 'conn_id': conn_id, 'host': host})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@app.route('/api/disks/<conn_id>/list', methods=['GET'])
def disk_list(conn_id):
    path = request.args.get('path', '/')
    conn = sftp_connections.get(conn_id)
    if not conn:
        return jsonify({'ok': False, 'error': '连接已断开'}), 404
    info = conn.get('info', {})
    try:
        # Fresh connection for each list
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(info['host'], port=int(info.get('port', 22)),
            username=info['username'], password=info.get('password', ''), timeout=15)
        sftp = client.open_sftp()
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
        sftp.close()
        client.close()
        return jsonify({'ok': True, 'entries': entries, 'path': path})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@app.route('/api/disks/<conn_id>/download', methods=['GET'])
def disk_download(conn_id):
    conn = sftp_connections.get(conn_id)
    if not conn:
        return jsonify({'ok': False, 'error': '连接已断开'}), 404
    path = request.args.get('path', '')
    info = conn.get('info', {})
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(info['host'], port=int(info.get('port', 22)),
            username=info['username'], password=info.get('password', ''), timeout=15)
        sftp = client.open_sftp()
        filename = os.path.basename(path)
        local_path = DOWNLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{filename}"
        sftp.get(path, str(local_path))
        sftp.close()
        client.close()
        download_url = f'/dl/{local_path.name}'
        return jsonify({'ok': True, 'url': download_url, 'filename': filename})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

# Serve downloaded files
@app.route('/dl/<path:filename>')
def serve_download(filename):
    return send_from_directory(str(DOWNLOAD_DIR), filename, as_attachment=True)

@app.route('/api/disks/<conn_id>/upload', methods=['POST'])
def disk_upload(conn_id):
    conn = sftp_connections.get(conn_id)
    if not conn:
        return jsonify({'ok': False, 'error': '连接已断开'}), 404
    dest_dir = request.form.get('path', '/')
    file = request.files.get('file')
    if not file:
        return jsonify({'ok': False, 'error': '没有文件'}), 400
    try:
        local_tmp = UPLOAD_DIR / f"ul_{uuid.uuid4().hex[:12]}_{file.filename}"
        file.save(str(local_tmp))
        print(f"[UPLOAD] Saved locally: {local_tmp}")
        # Fresh connection, synchronous upload
        info = conn.get('info', {})
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print(f"[UPLOAD] Connecting to {info.get('host')}...")
        client.connect(info['host'], port=int(info.get('port', 22)),
            username=info['username'], password=info.get('password', ''), timeout=30)
        sftp = client.open_sftp()
        remote_path = os.path.join(dest_dir, file.filename).replace('\\', '/')
        print(f"[UPLOAD] Putting {local_tmp} -> {remote_path}...")
        sftp.put(str(local_tmp), remote_path)
        sftp.close()
        client.close()
        local_tmp.unlink(missing_ok=True)
        print(f"[UPLOAD] Done: {file.filename}")
        return jsonify({'ok': True})
    except Exception as e:
        print(f"[UPLOAD] Error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 400

@app.route('/api/disks/<conn_id>/delete', methods=['POST'])
def disk_delete(conn_id):
    conn = sftp_connections.get(conn_id)
    if not conn:
        return jsonify({'ok': False, 'error': '连接已断开'}), 404
    path = request.json.get('path', '')
    info = conn.get('info', {})
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(info['host'], port=int(info.get('port', 22)),
            username=info['username'], password=info.get('password', ''), timeout=15)
        sftp = client.open_sftp()
        try:
            sftp.rmdir(path)
        except:
            sftp.remove(path)
        sftp.close()
        client.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@app.route('/api/disks/<conn_id>/mkdir', methods=['POST'])
def disk_mkdir(conn_id):
    conn = sftp_connections.get(conn_id)
    if not conn:
        return jsonify({'ok': False, 'error': '连接已断开'}), 404
    path = request.json.get('path', '')
    info = conn.get('info', {})
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(info['host'], port=int(info.get('port', 22)),
            username=info['username'], password=info.get('password', ''), timeout=15)
        sftp = client.open_sftp()
        sftp.mkdir(path)
        sftp.close()
        client.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@app.route('/api/disks/<conn_id>/usage', methods=['GET'])
def disk_usage(conn_id):
    QUOTA = 20 * 1024 * 1024 * 1024  # 20GB
    conn = sftp_connections.get(conn_id)
    if not conn:
        return jsonify({'ok': False, 'error': '连接已断开'}), 404
    info = conn.get('info', {})
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(info['host'], port=int(info.get('port', 22)),
            username=info['username'], password=info.get('password', ''), timeout=15)
        stdin, stdout, stderr = client.exec_command("du -sb /home/ubuntu/yunpan | cut -f1")
        output = stdout.read().decode().strip()
        client.close()
        used = int(output) if output else 0
        free = max(0, QUOTA - used)
        return jsonify({'ok': True, 'total': QUOTA, 'used': used, 'free': free})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@app.route('/api/disks/disconnect', methods=['POST'])
def disk_disconnect():
    conn_id = request.json.get('conn_id', '')
    conn = sftp_connections.pop(conn_id, None)
    if conn:
        try: conn['sftp'].close()
        except: pass
        try: conn['client'].close()
        except: pass
    return jsonify({'ok': True})

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='IM+Cloud Disk App')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=5000, help='监听端口')
    args = parser.parse_args()
    print(f"🚀 IM+Cloud Disk App 启动: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
