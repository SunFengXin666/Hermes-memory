---
name: flask-chat-ui
description: "Build a lightweight, single-user Flask web chat UI that proxies to an OpenAI-compatible LLM API — with chat history persistence, image upload, light/dark theme, and mobile responsiveness."
version: 1.0.0
author: Hermes Agent
---

# Flask Chat UI

Build a minimal Flask web app that serves as a chat interface for any OpenAI-compatible API (Hermes Agent, DeepSeek, OpenAI, local Ollama, etc.). Single-user, no auth, lightweight.

## When to Use

- User asks for a simple web chat interface for their LLM API
- Need a lightweight alternative to Open WebUI or similar heavy projects
- User wants a mobile-friendly, clean chat UI (微信公众号 style)
- Requirements: chat history survives refresh, image upload, clean theme, mobile responsive
- **Not for**: Multi-user auth, SSE streaming, complex tool calling UI, plugin systems

## Architecture

```
Frontend (static HTML) → POST /api/chat → Flask Proxy → LLM API
                      → POST /api/upload (optional) → Server saves file
                      → GET /api/memories → reads ~/daily-memories/*.md
```

No database, no auth, minimal dependencies. The frontend is a single `index.html` served by Flask.

## Flask Backend

### Key Endpoints

- `POST /api/chat` — Proxy chat completions to LLM API
- `GET /api/models` — List available models from LLM API
- `GET /` — Serve the frontend HTML

```python
from flask import Flask, request, jsonify, send_from_directory
import requests

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB for images

LLM_API = 'http://localhost:8642/v1'
LLM_KEY = 'your-api-key'

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    try:
        resp = requests.post(f'{LLM_API}/chat/completions', json={
            'model': data.get('model', 'hermes-agent'),
            'messages': data.get('messages', []),
            'stream': False
        }, headers={'Authorization': f'Bearer {LLM_KEY}'}, timeout=120)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
```

**Key details:**
- Pass `messages` array through as-is — supports both plain text (`content: "hello"`) and multimodal format (`content: [{type:"text",..},{type:"image_url",..}]`)
- Set timeout generously (120s) for vision model processing
- Set `MAX_CONTENT_LENGTH` for large base64 image payloads

## Frontend Features

### Chat History Persistence (localStorage)

Save conversations to `localStorage` on every assistant response. Track the active chat separately so refresh restores the correct conversation (not just the last one in history).

```javascript
let chatHistory = JSON.parse(localStorage.getItem('chats') || '[]');
let currentChatId = localStorage.getItem('activeChat') || Date.now().toString();

function saveChats() {
  localStorage.setItem('chats', JSON.stringify(chatHistory));
}

function addCurrentToHistory() {
  if (!currentChatId || messages.length === 0) return;
  const idx = chatHistory.findIndex(c => c.id === currentChatId);
  const entry = {id: currentChatId, messages: [...messages], time: Date.now()};
  if (idx >= 0) chatHistory[idx] = entry;
  else chatHistory.push(entry);
  saveChats();
}

// After save OR new chat creation, store activeChat:
localStorage.setItem('activeChat', currentChatId);
```

**Init logic — restore active chat, not last chat:**
```javascript
(function init() {
  const activeId = localStorage.getItem('activeChat');
  const chat = activeId ? chatHistory.find(c => c.id === activeId) : null;
  if (chat) {
    currentChatId = chat.id;
    messages = chat.messages;
    renderMessages();
  } else {
    // First visit — create empty chat
    messages = [];
    currentChatId = Date.now().toString();
    localStorage.setItem('activeChat', currentChatId);
  }
})();
```

**Key insight:** Without `activeChat`, refreshing after creating a new empty conversation restores the OLD saved conversation (the last entry in history), confusing users who expected the empty new chat. `activeChat` preserves exact session state across refreshes.

For the new-chat flow, show a brief toast notification so the user knows the old conversation was saved:
```javascript
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove('show'), 1500);
}
// Toast element: <div class="toast" id="toast"></div>
// CSS: .toast{position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,.7);color:#fff;padding:8px 16px;border-radius:8px;font-size:13px;z-index:300;opacity:0;transition:opacity .3s}.toast.show{opacity:1}
```

### Image Upload / Multimodal Support

Add a hidden `<input type="file">` triggered by a camera button. On selection, read as base64 and display a preview. When sending, build OpenAI multimodal content format:

```javascript
let currentImage = null;

function onImageSelected(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(ev) {
    currentImage = ev.target.result;  // data:image/...;base64,...
    // Show preview thumbnail
  };
  reader.readAsDataURL(file);
}

// In send():
if (text && currentImage) {
  content = [
    {type: 'text', text: text},
    {type: 'image_url', image_url: {url: currentImage}}
  ];
} else if (currentImage) {
  content = [
    {type: 'text', text: '描述这张图片'},
    {type: 'image_url', image_url: {url: currentImage}}
  ];
} else {
  content = text;
}
messages.push({role:'user', content});
// Clear image after send
```

### Light/White Theme (微信公众号 Style)

Use CSS variables for easy theme switching:

```css
:root{--bg:#f5f5f5;--surface:#fff;--card:#f0f0f0;--text:#333;--muted:#999;--accent:#07c160;--border:#e8e8e8}
```

Key elements:
- **User messages**: Green bubble (`--accent: #07c160`), right-aligned
- **AI messages**: Light gray bubble, left-aligned
- **Sidebar**: White with subtle border-right
- **Input bar**: White with light gray background textarea
- **Message labels**: "我" / "Hermes" below each bubble

### SVG Icons (Replacing Emoji)

Use inline SVG with `stroke="currentColor"` for clean, color-matched icons:

| Icon | SVG |
|------|-----|
| New chat (bubble) | `<svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>` |
| Daily memory (book) | `<svg viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>` |
| Camera | `<svg viewBox="0 0 24 24"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>` |
| Hamburger (menu) | 3 `<line>` elements |
| Plus (new chat) | 2 perpendicular `<line>` elements |
| Close (X) | 2 diagonal `<line>` elements |
| Logo (lightning) | `<polyline points="13 2 3 14 12 14 11 22 21 10 12 10"/>` |

All SVGs: `fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"`

### Mobile Responsive

Three key areas:

**1. Sidebar overlay on mobile (≤768px):**
```css
@media(max-width:768px){
  .sidebar{position:fixed;left:-220px;height:100vh;transition:left .3s}
  .sidebar.open{left:0}
}
.sidebar-overlay{display:none;position:fixed;top:0;left:0;width:100%;height:100%;z-index:99}
```
JS toggles `.sidebar.open` and shows/hides overlay. Tapping overlay closes sidebar.

**2. Safe area for mobile bottom nav bars:**
```css
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,viewport-fit=cover">
.input-bar{padding-bottom:calc(12px + 50px)}  /* on mobile */
```
On Xiaomi/Android browsers, `env(safe-area-inset-bottom)` often returns 0. Use a fixed 50px padding-bottom on the input bar as a reliable fallback.

**3. Top bar (hidden on desktop, shown on mobile):**
Contains hamburger menu (left), title (center), new chat button (right, `margin-left:auto`).

## SPA to Multi-Page Refactoring

As your Flask web app grows beyond just a chat interface (adding file management, memories, settings, etc.), you may outgrow the SPA approach where a single `index.html` uses JS `onshow`/`onhide` to switch between pages.

### When to Split

- User wants **separate URLs** for different features (`/disk`, `/memories`, `/`)
- **Browser back button** doesn't work in SPA mode
- Features have **conflicting JS** (e.g., chat JS polluting disk page JS namespace)
- Page-specific bugs are hard to isolate

### How to Convert

**Before (SPA):** One route, one mega HTML with JS page switching:

```python
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')
```

Sidebar navigation used `onclick`:

```html
<button class="nav-btn" onclick="switchPage('disk')">云盘</button>
```

**After (Multi-Page):** Separate routes per page:

```python
from flask import send_from_directory

@app.route('/')
def chat_page():
    return send_from_directory('templates', 'chat.html')

@app.route('/disk')
def disk_page():
    return send_from_directory('templates', 'disk.html')

@app.route('/memories')
def memories_page():
    return send_from_directory('templates', 'memories.html')
```

Sidebar uses `<a href>` for real navigation:

```html
<a href="/" class="nav-btn">新对话</a>
<a href="/memories" class="nav-btn">每日记忆</a>
<a href="/disk" class="nav-btn">云盘</a>
```

### Key Decisions When Splitting

**1. Duplicate sidebar HTML (don't over-engineer)**

Each page's HTML includes its own copy of the sidebar. This is intentional — for a simple app, Jinja2 template inheritance adds complexity without value. The sidebar CSS is identical across pages (same `:root` variables, same nav styles).

**2. Each page has its own `<script>` block**

Only include the JS needed for that page. Chat page gets chat/message/history JS. Disk page gets SFTP connection/file browser JS. This prevents:
- Variable name conflicts (e.g., `diskConnId` vs `messages`)
- Unnecessary code loading
- Accidental cross-page state sharing via closures

**3. Shared state moves to localStorage**

In the SPA, all JS variables were in-memory and shared across pages. After splitting, each page has its own JS context. Shared state (like saved server config for auto-connect) must use `localStorage`:

```javascript
// === Disk page ===
// Save on connect:
localStorage.setItem('diskServer', JSON.stringify({host, port, username, password, root_path}));

// Auto-connect on page load:
function autoConnect() {
  const saved = localStorage.getItem('diskServer');
  if (!saved) return;
  const cfg = JSON.parse(saved);
  fetch('/api/disk/connect', {method:'POST', body: JSON.stringify(cfg)})
    .then(r=>r.json()).then(data => { /* ... */ });
}
document.addEventListener('DOMContentLoaded', autoConnect);
```

**4. Keep the same CSS `:root` variables across pages**

All pages share the same theme variables (`--accent: #007aff`, `--bg: #f5f5f7`, etc.). This ensures a consistent look even though the HTML files are separate. Copy the entire `<style>` block to each page.

**5. Separate Flask routes, same Flask app**

All routes live in the same `app.py`. No need for Flask Blueprints unless the app grows significantly (>10 routes). Keep it simple:
- Chat route at `/`
- Disk route at `/disk`
- Memories route at `/memories`
- All API endpoints at `/api/...` (shared across pages)

### Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| Sidebar active state lost on page load | JS can't set `active` class on `<a>` since page reloads | Hardcode `active` class on the current page's link: `<a href="/disk" class="nav-btn active">` |
| In-memory chat history lost navigating away and back | Messages are only in JS memory, not persisted | Always `addCurrentToHistory()` on page unload or save every message to `localStorage` immediately |
| Duplicated CSS drifts across pages | Editing one page's CSS but not others | Keep CSS identical across pages; start each page with a copy from the source of truth |
| `send_from_directory` doesn't find templates | Path relative to `app.py` | Make sure templates directory exists and path is correct: `send_from_directory('templates', 'chat.html')` |

## Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| Port not accessible externally | firewalld/ufw blocking, not security group | Check `firewall-cmd --list-ports`, add port with `firewall-cmd --add-port=8080/tcp --permanent` |
| Safe-area not working on Android | Xiaomi/Android Chrome ignores `env(safe-area-inset-bottom)` | Use fixed padding (50px) instead of relying on CSS env() |
| Image too large for API | Base64 encoding of large images creates huge payloads | Set `MAX_CONTENT_LENGTH` on Flask, consider client-side resize |
| localStorage chats don't survive clearing | Browser cache clear resets localStorage | Pair with server-side save (e.g., daily memory files) for long-term persistence |
| Sidebar click doesn't close on mobile | Missing overlay or overlay not capturing clicks | Add transparent `.sidebar-overlay` behind sidebar, toggle with sidebar open/close |
| "网页拒绝了您的访问" on mobile | Server's local firewall (not cloud security group) blocking port | Check `systemctl status firewalld`, add port rule |
