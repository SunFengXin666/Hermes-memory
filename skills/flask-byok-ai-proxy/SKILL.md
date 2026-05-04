---
name: flask-byok-ai-proxy
description: "Build a Flask-based AI chat proxy where each user brings their own API key, base URL, and model — the server relays requests and stores credentials per-user with a settings UI."
version: 1.1.0
author: Hermes Agent
---

# Flask Bring-Your- Own-Key (BYOK) AI Proxy

Build a Flask web app that acts as an AI chat proxy — each user configures their own LLM provider credentials (API key, base URL, model) through a settings page, and the server relays chat requests using the user's configured provider.

## When to Use

- User asks to build a chat interface where each user uses their own API key (no shared provider billing)
- Need a "proxy" pattern: app doesn't pay for API calls, users bring their own keys
- Multi-user Flask app with per-user LLM provider configuration
- Same pattern works for OpenAI-compatible APIs (DeepSeek, Groq, local Ollama, etc.)
- User wants to switch between multiple AI models inline from the chat UI

**Not for**: Single-provider chat apps (just hardcode the key), or server-side-only LLM proxies without a web UI.

## Architecture

```
User Settings → POST /api/chat/config → Server stores per-user {presets: [{name, api_key, base_url, model}, ...], active: N}
User taps chat header → POST /api/chat/config → switches active preset index
User Message → POST /api/chat/completion → creates OpenAI(api_key=active_preset.key, base_url=active_preset.url) → Returns reply
```

## Per-User Multi-Preset Config

Instead of a single config per user, store an array of presets with an active index:

```python
ai_configs: dict[str, dict] = {}  # user_id -> {'presets': [...], 'active': int}

@app.route('/api/chat/config', methods=['GET', 'POST'])
def chat_config():
    user_id = request.json.get('user_id', '') if request.method == 'POST' else request.args.get('user_id', '')
    if not user_id:
        return jsonify({'ok': False, 'error': '缺少user_id'}), 400
    if request.method == 'POST':
        data = request.json
        ai_configs[user_id] = {
            'presets': data.get('presets', []),   # [{name, api_key, base_url, model}, ...]
            'active': data.get('active', 0),       # index into presets
        }
        return jsonify({'ok': True})
    else:
        cfg = ai_configs.get(user_id, {'presets': [], 'active': 0})
        return jsonify({'ok': True, 'presets': cfg.get('presets', []), 'active': cfg.get('active', 0)})

def get_ai_config(user_id: str):
    """Return active preset's config, or default fallback."""
    cfg = ai_configs.get(user_id, {})
    presets = cfg.get('presets', [])
    idx = cfg.get('active', 0)
    if presets and idx < len(presets):
        p = presets[idx]
        return {'api_key': p.get('api_key', ''), 'base_url': p.get('base_url', ''), 'model': p.get('model', ''), 'name': p.get('name', 'AI')}
    return {'api_key': 'default-key', 'base_url': 'http://localhost:8642/v1', 'model': 'default-model', 'name': 'AI'}
```

## Chat Completion

Use the active preset to create a per-request OpenAI client:

```python
@app.route('/api/chat/completion', methods=['POST'])
def chat_completion():
    data = request.json
    user_id, text = data.get('user_id', ''), data.get('text', '').strip()
    cfg = get_ai_config(user_id)
    client = OpenAI(api_key=cfg['api_key'], base_url=cfg['base_url'])
    resp = client.chat.completions.create(model=cfg['model'], messages=messages, timeout=60)
    reply = resp.choices[0].message.content
    return jsonify({'ok': True, 'reply': reply})
```

Also push to SSE so any open WebView chat UI stays in sync:
```python
push_to_user(user_id, {'type': 'message', 'from': 'AI', 'text': reply})
```

### Frontend: In-Chat Model Switching

Two UX patterns are common. Choose based on user preference:

**Option A: Cycle through models** (tap header to rotate)

```html
<div class="chat-header" id="chat-header" onclick="switchAiModel()" style="cursor:pointer">
  💬 <span id="ai-name-display">友友</span> <span style="font-size:12px;color:#8e8e93">▾</span>
</div>
```

```javascript
let aiPresets = [];
let aiActiveIdx = 0;

function updateAiDisplay() {
  const name = (aiPresets.length > 0 && aiActiveIdx < aiPresets.length)
    ? aiPresets[aiActiveIdx].name : '友友';
  document.getElementById('ai-name-display').textContent = name;
}

async function switchAiModel() {
  if (aiPresets.length <= 1) { toast('只有1个模型，去设置添加更多'); return; }
  aiActiveIdx = (aiActiveIdx + 1) % aiPresets.length;
  updateAiDisplay();
  await fetch('/api/chat/config', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ user_id: userId, presets: aiPresets, active: aiActiveIdx }),
  });
  toast(`切换到 ${aiPresets[aiActiveIdx].name}`);
}
```

**Option B: List picker** (tap header → bottom drawer with all models, user picks one)

```javascript
async function switchAiModel() {
  if (aiPresets.length <= 1) { toast('只有1个模型'); return; }
  showAiModelList(); // instead of cycling
}

function showAiModelList() {
  const overlay = document.createElement('div');
  overlay.id = 'ai-model-picker';
  overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.4);z-index:200;display:flex;align-items:flex-end';
  overlay.addEventListener('click', function(e) { if (e.target === this) this.remove(); });
  const drawer = document.createElement('div');
  drawer.style.cssText = 'background:#fff;border-radius:14px 14px 0 0;padding:16px 0;max-height:50%;overflow-y:auto;width:100%';
  let html = '<div style="width:36px;height:4px;background:#d1d1d6;border-radius:2px;margin:0 auto 12px"></div>';
  html += '<div style="font-size:15px;font-weight:600;padding:0 16px 10px">切换模型</div>';
  aiPresets.forEach((p, i) => {
    const active = i === aiActiveIdx;
    html += `<div onclick="selectAiModel(${i})" style="padding:12px 16px;display:flex;align-items:center;gap:10px;border-bottom:1px solid #f2f2f2;cursor:pointer${active ? ';background:#f0f7ff' : ''}">
      <span style="font-size:14px;flex:1;color:${active ? '#007aff' : '#1d1d1f'};font-weight:${active ? '600' : '400'}">${p.name}</span>
      <span style="font-size:11px;color:#8e8e93">${p.model}</span>
      ${active ? '<span style="color:#007aff;font-size:16px">✓</span>' : ''}
    </div>`;
  });
  drawer.innerHTML = html;
  overlay.appendChild(drawer);
  document.body.appendChild(overlay);
}

async function selectAiModel(idx) {
  if (idx === aiActiveIdx) { document.getElementById('ai-model-picker')?.remove(); return; }
  aiActiveIdx = idx;
  updateAiDisplay();
  await fetch('/api/chat/config', { ... });
  // Load new model's history
  const resp = await fetch(`/api/chat/history?user_id=${userId}&model_idx=${aiActiveIdx}`);
  const result = await resp.json();
  const el = document.getElementById('chat-messages');
  el.innerHTML = '';
  if (result.ok && result.history.length) {
    result.history.forEach(msg => appendMessage(msg));
  }
  document.getElementById('ai-model-picker')?.remove();
  toast(`切换到 ${aiPresets[aiActiveIdx].name}`);
}
```

### Settings page: Dynamic preset list

**Pattern A — Inline on settings page** (simple):
```javascript
function renderAiConfigs() {
  const el = document.getElementById('ai-config-list');
  el.innerHTML = aiPresets.map((p, i) => `
    <div style="background:#f5f5f7;border-radius:10px;padding:12px;margin-bottom:8px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <input value="${p.name}" placeholder="名称" data-idx="${i}" data-field="name" oninput="updatePresetField(this)">
        <button onclick="removeAiConfig(${i})" style="border:none;color:#ff3b30;font-size:16px;cursor:pointer">✕</button>
      </div>
      <input value="${p.base_url}" placeholder="API 地址" data-idx="${i}" data-field="base_url" oninput="updatePresetField(this)">
      <input value="${p.api_key}" placeholder="API Key" type="password" data-idx="${i}" data-field="api_key" oninput="updatePresetField(this)">
      <input value="${p.model}" placeholder="模型名" data-idx="${i}" data-field="model" oninput="updatePresetField(this)">
    </div>
  `).join('');
}
```

**Pattern B — Hidden behind a button** (user requested: "not display settings so openly"):
Show only a "管理AI模型" (Manage AI Models) button in settings. The config editor opens as a modal overlay on tap.
```html
<!-- Settings page: just a button -->
<label>🤖 AI 模型</label>
<p>当前：<span id="setting-ai-name">友友</span></p>
<button onclick="showAiConfigEditor()">✎ 管理AI模型</button>

<!-- Modal overlay (hidden by default) -->
<div class="modal" id="ai-config-modal">
  <div class="modal-box" style="max-height:80vh;overflow-y:auto">
    <h3>🤖 AI 模型</h3>
    <div id="ai-config-list"></div>
    <button onclick="addAiConfig()">+ 添加模型</button>
    <div class="modal-actions">
      <button onclick="closeModal('ai-config-modal')">取消</button>
      <button onclick="saveAiConfigEditor()">保存</button>
    </div>
  </div>
</div>
```
```javascript
function showAiConfigEditor() {
  renderAiConfigs();
  document.getElementById('ai-config-modal').classList.add('show');
}

async function saveAiConfigEditor() {
  await fetch('/api/chat/config', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ user_id: userId, presets: aiPresets, active: aiActiveIdx }),
  });
  updateAiDisplay();
  closeModal('ai-config-modal');
  toast('AI 模型已保存');
}
```
This keeps the settings page clean — sensitive API keys and provider details are only visible when the user explicitly taps to edit.

## Per-User Persistent Memory (User-Written)

Each user can write personal notes ("about me") that get injected into the AI's system prompt. This survives server restarts.

### Server: File-based storage

```python
from pathlib import Path
import json, threading, time

MEMORY_DIR = Path('/tmp/im-app-memories')
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_LOCK = threading.Lock()

def save_user_memory(user_id: str, text: str):
    file_path = MEMORY_DIR / f'{user_id}.json'
    with MEMORY_LOCK:
        file_path.write_text(json.dumps(
            {'user_id': user_id, 'text': text, 'updated_at': time.time()},
            ensure_ascii=False), encoding='utf-8')

def load_user_memory(user_id: str) -> str:
    file_path = MEMORY_DIR / f'{user_id}.json'
    if not file_path.exists():
        return ''
    with MEMORY_LOCK:
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
            return data.get('text', '')
        except:
            return ''
```

### API Endpoint

```python
@app.route('/api/chat/memory', methods=['GET', 'POST'])
def chat_memory():
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
```

### System Prompt Injection

```python
def load_system_prompt(user_id: str = '') -> str:
    prompt = '你的名字叫友友...'
    # ... global memories ...
    if user_id:
        mem = load_user_memory(user_id)
        if mem:
            prompt += f'\n\n用户 {user_id} 的私人记忆：\n{mem}'
    return prompt
```

### Frontend: Textarea in Settings

```html
<textarea id="memory-text" style="width:100%;height:80px;..."
  placeholder="比如：我喜欢Python，养了一只猫叫咪咪..."></textarea>
```

Load on settings page entry, save alongside AI config:

```javascript
async function loadMemory() {
  const resp = await fetch(`/api/chat/memory?user_id=${encodeURIComponent(userId)}`);
  const result = await resp.json();
  if (result.ok) document.getElementById('memory-text').value = result.text || '';
}

// Call loadMemory() when switching to settings tab
// Call saveMemory() inside saveSettings()
```

## Conversation Context (Per-Model Message History)

Each model should have its **own** conversation history — switching models shows a different chat. Key by `user_id:model_idx`:

```python
ai_memories: dict[str, list] = {}       # key: "user_id:model_idx"
ai_locks: dict[str, threading.Lock] = {} # key: "user_id:model_idx"

active_idx = ai_configs.get(user_id, {}).get('active', 0)
mem_key = f"{user_id}:{active_idx}"
lock_key = f"{user_id}:{active_idx}"

if lock_key not in ai_locks:
    ai_locks[lock_key] = threading.Lock()
with ai_locks[lock_key]:
    if mem_key not in ai_memories:
        ai_memories[mem_key] = [{'role': 'system', 'content': system_prompt}]
    ai_memories[mem_key].append({'role': 'user', 'content': text})
    if len(ai_memories[mem_key]) > 21:
        ai_memories[mem_key] = [ai_memories[mem_key][0]] + ai_memories[mem_key][-20:]
    # ... call AI ...
    ai_memories[mem_key].append({'role': 'assistant', 'content': reply})
```

### Per-Model Chat History Persistence

Save each model's conversation history to separate files so switching models reloads the correct history:

```python
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
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(msg, ensure_ascii=False) + '\n')

def load_history(user_id: str, model_idx: int = 0) -> list[dict]:
    file_path = get_history_path(user_id, model_idx)
    if not file_path.exists():
        return []
    with CHAT_LOCK:
        lines = file_path.read_text(encoding='utf-8').strip().split('\n')
        return [json.loads(l) for l in lines if l.strip()]
```

### History API Endpoint

Needed so the frontend can fetch a specific model's history when switching:

```python
@app.route('/api/chat/history', methods=['GET'])
def chat_history():
    user_id = request.args.get('user_id', '')
    model_idx = int(request.args.get('model_idx', 0))
    history = load_history(user_id, model_idx)
    return jsonify({'ok': True, 'history': history})
```

Also return the active model index in the login response so the frontend knows which history to display initially:

```python
@app.route('/api/chat/login', methods=['POST'])
def chat_login():
    # ...
    active_idx = ai_configs.get(user_id, {}).get('active', 0)
    history = load_history(user_id, active_idx)
    return jsonify({'ok': True, 'history': history, 'active_idx': active_idx})
```

### SSE Events with Model Filtering

Include `model_idx` in SSE push events so the frontend can ignore events for non-active models:

```python
push_to_user(user_id, {
    'type': 'message', 'from': 'AI', 'text': reply,
    'time': '', 'isSelf': False, 'model_idx': active_idx,
})
save_message(user_id, {'from': 'AI', 'text': reply, 'isSelf': False}, active_idx)
```

### Frontend: Load History on Model Switch

```javascript
async function switchAiModel() {
  if (aiPresets.length <= 1) { toast('只有1个模型'); return; }
  aiActiveIdx = (aiActiveIdx + 1) % aiPresets.length;
  updateAiDisplay();
  await fetch('/api/chat/config', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ user_id: userId, presets: aiPresets, active: aiActiveIdx }),
  });
  // Load the new model's chat history
  const resp = await fetch(`/api/chat/history?user_id=${encodeURIComponent(userId)}&model_idx=${aiActiveIdx}`);
  const result = await resp.json();
  const el = document.getElementById('chat-messages');
  el.innerHTML = '';
  if (result.ok && result.history && result.history.length) {
    result.history.forEach(msg => appendMessage(msg));
  } else {
    el.innerHTML = '<div style="text-align:center;padding:40px 20px;color:#8e8e93;font-size:14px">发送消息开始聊天</div>';
  }
  toast(`切换到 ${aiPresets[aiActiveIdx].name}`);
}

// Filter SSE events by current model
function receiveMessage(data) {
  if (data.model_idx !== undefined && data.model_idx !== aiActiveIdx) return;
  appendMessage({from: data.from, text: data.text, time: data.time, isSelf: data.isSelf});
}
```

To keep the history display in sync on initial load, persist `active_idx` from the login response:

## Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| Config not persisting across server restarts | In-memory dict only | Save to file/DB on each `POST /api/chat/config` |
| "Incorrect API key" for user B after user A | Shared global `OpenAI()` client | Create new `OpenAI(...)` per request |
| SSE WebView shows stale data | SSE not receiving the API response | Push both user message + AI reply to SSE in the completion handler |
| User tries switching model with 0 presets | Empty presets array | Guard `aiPresets.length <= 1` before trying to cycle |
| Settings shows empty preset list on first visit | `renderAiConfigs()` called before data loaded | Call `loadAiConfigs()` on login + call `renderAiConfigs()` on settings page switch |
| API call hangs forever / no response | API URL uses public IP for co-located servers | When Flask proxy and AI API (Hermes/Ollama) are on the **same machine**, use `http://localhost:PORT` not the public IP — cloud security groups often block self-connections to public IPs, causing 30+ second timeouts |
| Model not found (400 error) | Provider model name has subtle differences from what user typed | Verify exact model name from provider's docs/screenshot — e.g. `MiMo-V2.5` not `MiMo-2.5` (missing `V`). Always match provider's exact casing and naming |
| Lock deadlock: subsequent requests blocked for the same user+model | A previous request (wrong URL, timeout, auth failure) enters the per-model `with ai_locks[lock_key]` block and the API call hangs for the full timeout period (60s). During that time, ALL requests for the same user+model block waiting for the lock | Set a low `timeout` on `client.chat.completions.create(timeout=30)` so failed requests release the lock quickly. Also restart the server to clear stuck locks. For production, use `threading.Lock.acquire(timeout=...)` with fallback |
| API Key lost / "Invalid API Key" for third-party provider | Most platforms (MiMo, etc.) only show the API key **once at creation time** | Tell user to regenerate a new key on the provider's platform. Never store keys in client-side code |
