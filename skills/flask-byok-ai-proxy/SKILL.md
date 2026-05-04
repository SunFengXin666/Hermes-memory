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

### Typing Indicator (AI is thinking)

Add a visual "AI 正在输入 ● ● ●" indicator while the AI is generating a reply. This improves UX by giving the user feedback that their message was received and the AI is working.

**Pattern**: Show the indicator when the user's own message appears via SSE (meaning the server is now processing). Hide it when the AI's reply arrives via SSE.

**CSS**:
```css
/* Typing indicator with bouncing dots */
.typing-indicator{padding:12px 16px;display:flex;align-items:center;gap:8px;font-size:13px;color:#8e8e93}
.typing-dots{display:flex;gap:3px}
.typing-dots span{width:6px;height:6px;border-radius:50%;background:#c7c7cc;animation:typingBounce 1.4s ease-in-out infinite}
.typing-dots span:nth-child(1){animation-delay:0s}
.typing-dots span:nth-child(2){animation-delay:.2s}
.typing-dots span:nth-child(3){animation-delay:.4s}
@keyframes typingBounce{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-5px)}}
```

**JavaScript (added to `receiveMessage`)**:
```javascript
function receiveMessage(data) {
  if (data.model_idx !== undefined && data.model_idx !== aiActiveIdx) return;
  // Remove typing indicator when AI replies
  if (!data.isSelf && data.from === 'AI') {
    removeTypingIndicator();
  }
  appendMessage({from: data.from, text: data.text, time: data.time, isSelf: data.isSelf});
  // Show typing indicator when user's own message appears (AI is thinking)
  if (data.isSelf && !data.text.startsWith('📷 [')) {  // skip for image messages (has own loading)
    showTypingIndicator();
  }
}

function showTypingIndicator() {
  removeTypingIndicator();
  const el = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'typing-indicator';
  div.id = 'typing-indicator';
  div.innerHTML = '<span>AI 正在输入</span><div class="typing-dots"><span></span><span></span><span></span></div>';
  el.appendChild(div);
  el.scrollTop = el.scrollHeight;
}

function removeTypingIndicator() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}
```

**Important**: Do NOT show the typing indicator for vision/image messages — they already have their own loading indicator ("🔄 正在识别图片..."). The check `!data.text.startsWith('📷 [')` prevents this conflict.

Also remove the typing indicator when loading a new model's history in `selectAiModel` / `switchAiModel`, so old "AI is thinking" remnants don't persist after switching.

## Adding Vision / Image Recognition to the Chat

When a user uploads an image in chat and wants AI to analyze it, you need a dedicated vision endpoint that calls a vision-capable model. This is separate from the text chat flow because most LLM providers separate vision and text capabilities into different models.

### Architecture

```
User taps 🖼 → picks image → POST /api/chat/vision (multipart: image + user_id)
  → Server saves to temp → base64 encodes → calls vision model (e.g. MiMo, GPT-4o-mini-vision)
  → Saves user+AI messages to chat history → Pushes via SSE
  → Frontend receives AI reply with analysis
```

### Key Design Decisions

1. **Use a dedicated vision model** — Don't rely on the user's active text model to support vision (most don't). Hardcode a specific vision-capable model and API key on the server side.
2. **Server-side vision call** — The image is uploaded to the Flask server, which converts it to base64 and sends to the vision API. Never send raw images client-side to the LLM.
3. **Save to chat history** — Both the user's image message and the AI's analysis result should be saved so they persist across sessions.
4. **Push via SSE** — The result arrives asynchronously (not as the HTTP response to the upload). The frontend shows a loading state, then the AI reply arrives through the SSE stream.

### Backend Endpoint

```python
# Hardcoded vision credentials (keep server-side, never expose to client)
VISION_API_KEY = 'your-vision-api-key'
VISION_BASE_URL = 'https://vision-provider.com/v1'
VISION_MODEL = 'vision-model-name'

@app.route('/api/chat/vision', methods=['POST'])
def chat_vision():
    user_id = request.form.get('user_id', '')
    file = request.files.get('image')
    if not user_id or not file:
        return jsonify({'ok': False, 'error': '参数不全'}), 400

    img_path = UPLOAD_DIR / f"vision_{uuid.uuid4().hex[:12]}_{file.filename}"
    file.save(str(img_path))
    try:
        with open(img_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()
        ext = os.path.splitext(file.filename)[1].lower() or '.png'
        mime = 'image/jpeg' if ext in ('.jpg', '.jpeg') else 'image/png'
        data_url = f'data:{mime};base64,{b64}'

        client = OpenAI(api_key=VISION_API_KEY, base_url=VISION_BASE_URL)
        resp = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': '请详细描述这张图片的内容'},
                    {'type': 'image_url', 'image_url': {'url': data_url}},
                ]
            }],
            max_tokens=500,
            timeout=30,
        )
        reply = resp.choices[0].message.content or '（无法识别）'

        # Save to chat history + push via SSE
        active_idx = ai_configs.get(user_id, {}).get('active', 0)
        save_message(user_id, {'from': user_id, 'text': f'📷 [图片] {file.filename}', ...}, active_idx)
        save_message(user_id, {'from': 'AI', 'text': f'🖼 图片分析结果：\n{reply}', ...}, active_idx)
        push_to_user(user_id, {'type': 'message', 'from': 'AI', 'text': f'🖼 图片分析结果：\n{reply}', ...})
        
        img_path.unlink(missing_ok=True)
        return jsonify({'ok': True, 'reply': reply})
    except Exception as e:
        img_path.unlink(missing_ok=True)
        return jsonify({'ok': False, 'error': f'图片识别失败: {str(e)}'}), 500
```

### Frontend: Image Picker in Chat Input

Add a hidden `<input type="file" accept="image/*">` and a 🖼 button next to the send button:

### ⚠️ Android WebView: Do NOT use `display:none` + `.click()`

In Android WebView, calling `.click()` on a hidden `<input type="file">` via JavaScript is **silently ignored** — the `WebChromeClient.onShowFileChooser` is only triggered on direct user gesture. Neither `display:none` + `.click()`, nor dynamically creating an input and calling `.click()`, nor `<label>` wrapping works.

✅ **Working approach: Transparent overlay input**

Place the `<input type="file">` visually on top of the 🖼 icon with `opacity:0` so the user taps the input directly:

```html
<div class="chat-input-area">
  <input type="text" id="chat-input" placeholder="输入消息...">
  <div style="position:relative;width:36px;height:36px;flex-shrink:0">
    <input type="file" id="vision-input" accept="image/*" onchange="sendVisionImage(this)"
      style="position:absolute;top:0;left:0;width:100%;height:100%;
             opacity:0;z-index:2;cursor:pointer;font-size:0">
    <span style="position:absolute;top:0;left:0;width:100%;height:100%;
               display:flex;align-items:center;justify-content:center;
               font-size:20px;z-index:1;color:#8e8e93;pointer-events:none">🖼</span>
  </div>
  <button id="chat-send">➤</button>
</div>
```

Key points:
- `opacity:0` makes the input invisible but still interactive
- `z-index:2` puts the input above the icon (`z-index:1` with `pointer-events:none`)
- The user taps the icon area → direct gesture on `<input>` → `onShowFileChooser` fires
- Do NOT use `<label>` wrapping (same limitation as `.click()` in Android WebView)

```javascript
async function sendVisionImage(input) {
  const file = input.files[0];
  if (!file) return;
  // Show user message immediately
  appendMessage({from: userId, text: `📷 [图片] ${file.name}`, time, isSelf: true});
  // Show loading indicator
  const loading = document.createElement('div');
  loading.className = 'msg other';
  loading.innerHTML = '🔄 正在识别图片...';
  document.getElementById('chat-messages').appendChild(loading);
  
  const formData = new FormData();
  formData.append('user_id', userId);
  formData.append('image', file);
  try {
    const resp = await fetch('/api/chat/vision', { method:'POST', body: formData });
    const result = await resp.json();
    loading.remove();
    if (!result.ok) {
      appendMessage({from: 'AI', text: '❌ ' + (result.error || '识别失败'), ...});
    }
    // AI reply arrives via SSE, no need to append here
  } catch(e) {
    loading.remove();
    appendMessage({from: 'AI', text: '❌ 网络错误: ' + e.message, ...});
  }
  input.value = '';
}
```

**Important**: The AI's reply is delivered via SSE (Server-Sent Events), not as the HTTP response to the upload request. The `POST /api/chat/vision` endpoint saves the reply to chat history and pushes it via SSE. The frontend's `receiveMessage` handler will pick it up. The loading indicator is removed once the HTTP response confirms the server has processed the image.

### Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| Vision model API key hardcoded in source | User's text model config may not support vision | Keep vision key separate — hardcode on server or use a dedicated vision model provider |
| Large images cause timeout/timeout | base64 encoding of multi-MB images | Limit file input to `accept="image/*"` (not video). Consider max size check on server side |
| No vision model available | Provider doesn't offer vision, or API key invalid | Test vision endpoint separately before integrating. Use a known-working provider (GPT-4o, MiMo Omni, etc.) |
| SSE double-delivery of vision result | Both `chat/vision` endpoint AND `chat/completion` push the same reply | Only push from one place — the vision endpoint handles its own SSE push. Don't also send the vision text through `chat/send` |
| **User image message appears twice** | Frontend shows "📷 [图片]" optimistically via `appendMessage`, AND backend pushes the same message via SSE → `receiveMessage` appends it again | **Remove the SSE push for the user's image message.** Keep `save_message` (for history persistence + `fetchMissedMessages`), but only push the AI's analysis result via SSE. The frontend's optimistic display is sufficient for the user's own message |
| Image shows in uploaded file list but no AI analysis | Frontend waited for HTTP response instead of SSE | The `POST` response just confirms the server received the image. The actual AI reply comes through SSE moments later |

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

## User Authentication & Persistent Profiles

For multi-user apps where data (AI configs, servers, memory) must survive server restarts and work across devices, add password-based authentication with file-backed user profiles.

### Storage: JSON User Profiles

```python
import hashlib, secrets, time

USER_DIR = Path('/tmp/im-app-users')
USER_DIR.mkdir(parents=True, exist_ok=True)
USER_LOCK = threading.Lock()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def load_user_profile(username: str) -> dict | None:
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
```

Profile structure:
```json
```
  "password_hash": "sha256hex...",
  "token": "session_token_for_auto_login",
  "ai_presets": [{"name":"DeepSeek","api_key":"...","base_url":"http://...","model":"..."}],
  "ai_active": 1,
  "servers": [{"name":"My Server","host":"...","port":22,"username":"root","password":"..."}],
  "memory": "Personal notes about the user",
  "created_at": 1234567890.0
}
```

### Auth Endpoints

```python
@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({'ok': False, 'error': '用户名和密码不能为空'}), 400
    if len(username) < 2 or len(password) < 4:
        return jsonify({'ok': False, 'error': '用户名至少2字符，密码至少4字符'}), 400
    if load_user_profile(username):
        return jsonify({'ok': False, 'error': '用户名已存在'}), 400
    profile = {
        'password_hash': hash_password(password),
        'ai_presets': [], 'ai_active': 0,
        'servers': [], 'memory': '', 'created_at': time.time(),
    }
    save_user_profile(username, profile)
    return jsonify({'ok': True})

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    profile = load_user_profile(username)
    if not profile:
        return jsonify({'ok': False, 'error': '用户不存在'}), 400
    if profile.get('password_hash') != hash_password(password):
        return jsonify({'ok': False, 'error': '密码错误'}), 400
    # Load profile into in-memory config
    ai_configs[username] = {
        'presets': profile.get('ai_presets', []),
        'active': profile.get('ai_active', 0),
    }
    return jsonify({
        'ok': True,
        'profile': {
            'ai_presets': profile.get('ai_presets', []),
            'ai_active': profile.get('ai_active', 0),
            'servers': profile.get('servers', []),
            'memory': profile.get('memory', ''),
        }
    })
```

### Profile Save Endpoint (for servers & memory)

```python
@app.route('/api/user/profile', methods=['POST'])
def user_profile():
    data = request.json
    user_id = data.get('user_id', '')
    profile = load_user_profile(user_id)
    if not profile:
        return jsonify({'ok': False, 'error': '用户不存在'}), 400
    if 'servers' in data:
        profile['servers'] = data['servers']
    if 'memory' in data:
        profile['memory'] = data['memory']
    save_user_profile(user_id, profile)
    return jsonify({'ok': True})
```

### Token Auto-Login (Persist Session Across App Restarts)

Without auto-login, users must re-enter credentials every time they clear the app from recent tasks (killing the WebView's JS context). Fix: generate a session token on login, save it to localStorage, and auto-authenticate on page load.

#### Backend: Token Generation on Login

Modify the login endpoint to generate a token and store it in the profile:

```python
import secrets

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    # ... validate username/password ...
    
    # Generate session token
    token = secrets.token_hex(32)
    profile['token'] = token
    save_user_profile(username, profile)
    
    return jsonify({
        'ok': True,
        'token': token,  # ← return token to frontend
        'profile': { ... }
    })
```

#### Backend: Token Verification Endpoint

```python
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
        'profile': { ... }
    })
```

#### Frontend: Save Token & Auto-Login

On successful login, save `{username, token}` to localStorage:

```javascript
// In onAuthSuccess:
localStorage.setItem('im_auth', JSON.stringify({username: name, token: token}));
```

On page load, check for saved token and auto-login (instead of always showing the login modal):

```javascript
(function() {
  const saved = localStorage.getItem('im_auth');
  if (saved) {
    try {
      const auth = JSON.parse(saved);
      if (auth.username && auth.token) {
        autoLogin(auth.username, auth.token);
        return;
      }
    } catch(_) {}
  }
  // No saved token - show login modal
  document.getElementById('login-modal').classList.add('show');
})();

async function autoLogin(username, token) {
  try {
    const resp = await fetch('/api/auth/token_login', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({username, token}),
    });
    const data = await resp.json();
    if (data.ok) {
      await onAuthSuccess(username, data.profile, token);
    } else {
      // Token invalid - clear and show login
      localStorage.removeItem('im_auth');
      document.getElementById('login-modal').classList.add('show');
    }
  } catch(e) {
    document.getElementById('login-modal').classList.add('show');
  }
}
```

### Pitfalls: Token Auto-Login

| Issue | Cause | Fix |
|-------|-------|-----|
| Token never expires | Token stored permanently in profile | Add `token_expires_at` field, or regenerate token on each login |
| Token stolen | Insecure localStorage in shared device | Personal app only — production would use HTTP-only cookies |
| Token mismatch after server restart | Profile has no `token` field (created before this feature) | Login once to generate a token. `token_login` returns 400 with "token invalid", frontend falls back to login modal |
```

### Auto-Persist AI Config on Every Change

Modify the `POST /api/chat/config` handler to also save to the profile:

```python
@app.route('/api/chat/config', methods=['GET', 'POST'])
def chat_config():
    # ...
    if request.method == 'POST':
        ai_configs[user_id] = {
            'presets': data.get('presets', []),
            'active': data.get('active', 0),
        }
        # Also persist to user profile
        profile = load_user_profile(user_id)
        if profile:
            profile['ai_presets'] = data.get('presets', [])
            profile['ai_active'] = data.get('active', 0)
            save_user_profile(user_id, profile)
        return jsonify({'ok': True})
```

### Frontend: Login + Register UI

Replace the simple nickname login with username + password fields and a register button:

```html
<input type="text" id="login-name" placeholder="用户名">
<input type="password" id="login-password" placeholder="密码">
<button onclick="doLogin()">登录</button>
<button onclick="doRegister()">注册新账号</button>
```

```javascript
async function doLogin() {
  const name = document.getElementById('login-name').value.trim();
  const password = document.getElementById('login-password').value;
  const resp = await fetch('/api/auth/login', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({username: name, password: password}),
  });
  const data = await resp.json();
  if (!data.ok) { toast(data.error); return; }
  await onAuthSuccess(name, data.profile);
}

async function doRegister() {
  // register, then auto-login
  // on success: await onAuthSuccess(name, loginData.profile);
}

async function onAuthSuccess(name, profile) {
  userId = name;
  aiPresets = profile.ai_presets || [];
  aiActiveIdx = profile.ai_active || 0;
  savedServers = profile.servers || [];
  // Also save servers locally so they work offline
  localStorage.setItem('im_servers', JSON.stringify(savedServers));
  if (profile.memory) {
    document.getElementById('memory-text').value = profile.memory;
  }
  updateAiDisplay();
  initChat();
}
```

When saving servers (via `connectServer`), also persist to the user profile:

```javascript
// After saving to localStorage:
fetch('/api/user/profile', {
  method: 'POST', headers: {'Content-Type':'application/json'},
  body: JSON.stringify({ user_id: userId, servers: savedServers }),
}).catch(() => {});
```

## AI Function Calling for Tool Execution (e.g. Cloud Disk Control)

The AI can be given tools to execute real operations (SFTP file management, etc.) via OpenAI-compatible function calling. This bridges the chat AI and the backend operations.

### Tool Definitions

Define tools as OpenAI function definitions:

```python
CLOUD_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出云盘目录下的文件和文件夹",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_text_file",
            "description": "读取云盘上的文本文件内容",
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
                    "path": {"type": "string", "description": "要删除的路径"}
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
            "description": "获取云盘的磁盘使用情况",
            "parameters": {"type": "object", "properties": {}}
        }
    },
]
```

### Route Tools to Users via `user_id`

In `disk_connect`, store `user_id` in the connection info so the AI can find the right server:

```python
@app.route('/api/disks/connect', methods=['POST'])
def disk_connect():
    data = request.json
    user_id = data.get('user_id', '')
    # ...
    sftp_connections[conn_id] = {'client': client, 'sftp': sftp, 'info': {**data, 'user_id': user_id}}
```

Then in the tool execution function, look up the user's connection by `user_id`:

```python
def execute_cloud_tool(user_id: str, func_name: str, args: dict) -> dict:
    # Find the user's active connection
    conn_info = None
    for cid, conn in list(sftp_connections.items()):
        if conn['info'].get('user_id') == user_id:
            conn_info = conn['info']
            break
    if not conn_info:
        return {"error": "你没有连接的云盘服务器"}
    
    # Fresh SFTP connection for each tool call
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(conn_info['host'], port=...)
    sftp = client.open_sftp()
    
    # Execute the requested operation
    if func_name == 'list_files':
        items = sftp.listdir_attr(path)
        # return structured file list
    elif func_name == 'read_text_file':
        # sftp.open(path, 'r').read()
    # etc.
    
    sftp.close(); client.close()
    return result
```

### Function Calling Loop in `call_ai`

The key change: pass `tools=CLOUD_TOOLS, tool_choice="auto"` to the API call, then loop while `finish_reason == "tool_calls"`:

```python
def call_ai(user_id: str, text: str):
    # ... setup mem_key, lock_key, etc ...
    
    resp = client.chat.completions.create(
        model=cfg['model'],
        messages=ai_memories[mem_key],
        tools=CLOUD_TOOLS,
        tool_choice="auto",
        timeout=30,
    )
    
    # Tool calls loop
    tool_calls_used = False
    while resp.choices[0].finish_reason == "tool_calls":
        tool_calls_used = True
        msg = resp.choices[0].message
        # Add assistant message with tool_calls to history
        ai_memories[mem_key].append({
            'role': 'assistant',
            'content': msg.content or '',
            'tool_calls': [{
                'id': tc.id,
                'type': 'function',
                'function': {'name': tc.function.name, 'arguments': tc.function.arguments}
            } for tc in msg.tool_calls]
        })
        # Execute each tool
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            result = execute_cloud_tool(user_id, tc.function.name, args)
            ai_memories[mem_key].append({
                'role': 'tool',
                'tool_call_id': tc.id,
                'content': json.dumps(result, ensure_ascii=False)
            })
        # Call API again with tool results
        resp = client.chat.completions.create(
            model=cfg['model'],
            messages=ai_memories[mem_key],
            tools=CLOUD_TOOLS,
            tool_choice="auto",
            timeout=30,
        )
    
    reply = resp.choices[0].message.content or ('✅ 操作已完成。' if tool_calls_used else '')
```

Also inject into system prompt so the AI knows what it can do:

```python
system_prompt += '\n\n你具备云盘控制能力，可以列出文件、读取文本文件、删除文件、创建目录、查看磁盘空间。'
```

### Key Requirements for Tool Calling

| Requirement | Why |
|-------------|-----|
| Model must support function calling | DeepSeek, GPT-4, Claude 3+ all support it. Older models may not |
| Fresh SFTP connections per tool call | Prevents stale connection errors in the tool execution loop |
| Store `user_id` on connect | So the AI can find the right server for the current user |
| Timeout on API calls | Prevents tool calls from blocking other requests if the remote API is slow |
| Handle `finish_reason == "tool_calls"` loop | Multiple rounds of tool calls may be needed for complex tasks |

## Frontend Login Tips

- **Show login modal on every fresh load** (no auto-login since we have passwords now)
- **Register then auto-login** — after successful registration, immediately call the login endpoint so the user doesn't need to log in twice
- **Merge local+server servers** — on first login, if the server profile has no servers but localStorage has saved servers, prefer localStorage so existing users don't lose their saved connections

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
| Tool call hangs / no response | The API model doesn't support function calling, or Hermes/Ollama isn't configured for it | Verify model supports tools. Check `resp.choices[0].finish_reason` — if `"stop"` instead of `"tool_calls"`, the model ignored the tools |
| Tool execution fails with "no connection" | User hasn't connected a cloud disk server, or connection timed out | Make the tool handle the no-connection case gracefully (return descriptive error for the AI to explain to the user) |
| Tool result too long (>model context window) | `du -sb` or `ls -la` returns huge output for directories with many files | Limit results: return only first 100 files. Truncate text files to first 2000 chars |
| Duplicate tool calls / infinite loop | AI keeps calling the same tool without making progress | Add max_tool_calls limit (e.g., 10 iterations) and break the loop |
