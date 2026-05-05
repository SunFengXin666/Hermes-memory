---
name: flask-sftp-file-manager
description: "Build a Flask web app backend for remote file management via SFTP (paramiko) — connection patterns, upload/download UX, mobile-friendly UI, and handling connection drops."
version: 1.0.0
author: Hermes Agent
---

# Flask SFTP File Manager

Build a Flask web app with SFTP (paramiko) for remote file management, optimized for mobile WebView clients.

## When to Use

- User asks to build a "file manager" or "云盘" (cloud disk) frontend for a remote server
- Flask app needs SFTP file operations (list, upload, download, delete, mkdir)
- SFTP connections keep dropping with "Socket is closed" or stale connection errors
- Building a mobile-friendly web UI for file management
- Need to show disk usage (storage bar) for SFTP-mounted directories
- Upload progress UX decisions (sync vs async)

**Not for**: Android WebView setup itself (see `android-webview-file-ops`), or pure Android APK building (see `android-webview-apk`).

## Connection Pattern: Fresh Connections Per Operation

**Critical lesson: Do NOT reuse persistent SFTP connections.** Paramiko connections drop after idle periods ("Socket is closed"), and reconnection logic is fragile. Instead, create a new connection for every request:

```python
# Store only connection info, NOT the connection itself
sftp_connections: dict[str, dict] = {}  # conn_id -> {'info': connect_data}

@app.route('/api/disks/<conn_id>/list', methods=['GET'])
def disk_list(conn_id):
    conn = sftp_connections.get(conn_id)
    if not conn:
        return jsonify({'ok': False, 'error': '连接已断开'}), 404
    info = conn.get('info', {})
    try:
        # Fresh connection for every request
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(info['host'], port=int(info.get('port', 22)),
            username=info['username'], password=info.get('password', ''), timeout=15)
        sftp = client.open_sftp()
        # ... do work ...
        sftp.close()
        client.close()
        return jsonify({'ok': True, ...})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
```

This pattern applies to: list, upload, download, delete, mkdir, and any other SFTP operation.

## Connect Endpoint

The `connect` endpoint should:
- Accept host/port/username/password
- Create a new SSH connection (for validation), then store the connection info
- **Disconnect existing** connection to the same server before creating a new one

```python
@app.route('/api/disks/connect', methods=['POST'])
def disk_connect():
    data = request.json
    host, port, username = data['host'], int(data.get('port', 22)), data['username']
    password = data.get('password', '')
    
    # Disconnect existing connection to same server
    for cid, conn in list(sftp_connections.items()):
        if (conn['info'].get('host') == host and 
            conn['info'].get('port') == port and 
            conn['info'].get('username') == username):
            try: conn['sftp'].close()
            except: pass
            try: conn['client'].close()
            except: pass
            del sftp_connections[cid]
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=port, username=username, password=password, timeout=10)
    sftp = client.open_sftp()
    conn_id = str(uuid.uuid4())[:8]
    sftp_connections[conn_id] = {'client': client, 'sftp': sftp, 'info': data}
    return jsonify({'ok': True, 'conn_id': conn_id})
```

## Upload: Synchronous (Simple) vs Async (Complex)

### Synchronous (preferred for small files)

HTTP upload → save to tmp → SFTP put → respond. User sees a progress bar animation while waiting. Simple, reliable:

```python
@app.route('/api/disks/<conn_id>/upload', methods=['POST'])
def disk_upload(conn_id):
    conn = sftp_connections.get(conn_id)
    file = request.files.get('file')
    local_tmp = UPLOAD_DIR / f"ul_{uuid.uuid4().hex[:12]}_{file.filename}"
    file.save(str(local_tmp))
    
    # Fresh SSH + SFTP connection
    info = conn['info']
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(info['host'], port=int(info.get('port', 22)),
        username=info['username'], password=info.get('password', ''), timeout=30)
    sftp = client.open_sftp()
    sftp.put(str(local_tmp), remote_path)
    sftp.close(); client.close()
    local_tmp.unlink(missing_ok=True)
    return jsonify({'ok': True})
```

**Pitfall**: `sftp.put(local_path=str(local_tmp), remote_path=remote_path)` is WRONG — paramiko's `put` uses positional args: `sftp.put(str(local_tmp), remote_path)`.

### Async (for large files or slow connections)

HTTP upload → save to tmp → respond immediately → background thread does SFTP push. Frontend polls directory until file appears. See `_do_sftp_upload` pattern below.

```python
# Frontend polls every 2s for up to 80s
uploadTimer = setInterval(async () => {
    const listResp = await fetch(`/api/disks/${activeServerId}/list?...`);
    const listResult = await listResp.json();
    if (listResult.entries.some(e => e.name === targetFile)) {
        clearInterval(uploadTimer);
        closeModal('upload-modal');
        diskRefresh();
    }
}, 2000);
```

**Downside**: Background thread failures are silent — user sees "等待传输完成..." forever. Add error notifications via SSE if using async.

## File Listing: Mobile-Friendly UI

Key patterns for a mobile SFTP file browser:

- **Short-lived connections** (as above)
- **Server list as bottom drawer** (iOS-style) rather than side panel — better for mobile
- **Custom confirm dialog** for delete (replace browser's native `confirm()`)
- **Toast notifications** for feedback
- **File name matching by name** for upload completion detection (name-based, not size-based)

## Custom Confirm Dialog for Delete

Replace browser's native `confirm()` with a styled modal:

```html
<div class="modal" id="confirm-modal">
  <div class="modal-box" style="text-align:center">
    <div style="font-size:36px;margin-bottom:8px" id="confirm-icon">🗑</div>
    <h3 style="margin-bottom:4px" id="confirm-title">确认删除</h3>
    <p style="font-size:14px;color:#8e8e93" id="confirm-msg">确定要删除吗？</p>
    <div class="modal-actions" style="justify-content:center;gap:12px;margin-top:16px">
      <button class="btn-cancel" onclick="closeModal('confirm-modal')" style="padding:10px 28px">取消</button>
      <button class="btn-confirm" id="confirm-btn" onclick="closeModal('confirm-modal');" style="padding:10px 28px;background:#ff3b30">删除</button>
    </div>
  </div>
</div>
```

JavaScript to wire it up:

```javascript
let confirmCallback = null;

async function diskDelete(name) {
  if (!activeServerId) return;
  document.getElementById('confirm-icon').textContent = '🗑';
  document.getElementById('confirm-title').textContent = '确认删除';
  document.getElementById('confirm-msg').textContent = `确定要删除 "${name}" 吗？`;
  document.getElementById('confirm-btn').textContent = '删除';
  document.getElementById('confirm-btn').style.background = '#ff3b30';
  confirmCallback = async () => {
    // do delete API call
    diskRefresh();
    loadDiskUsage();
  };
  document.getElementById('confirm-btn').onclick = () => {
    closeModal('confirm-modal');
    if (confirmCallback) confirmCallback();
  };
  document.getElementById('confirm-modal').classList.add('show');
}
```

## Root Path Locking (Chroot-Like Mode)

When building a shared or quota-based SFTP file browser, you may want to **lock users into a specific directory** so they cannot navigate above it. This is like `chroot` for SFTP.

### Backend: Accept `root_path` on Connect

```python
@app.route('/api/disk/connect', methods=['POST'])
def disk_connect():
    data = request.json
    ...
    root_path = data.get('root_path', '').strip()
    if root_path:
        root_path = '/' + root_path.lstrip('/').rstrip('/')  # normalize

    # Create directory tree if not exists (like mkdir -p)
    if root_path:
        parts = root_path.strip('/').split('/')
        cur = ''
        for p in parts:
            cur += '/' + p
            try: sftp.stat(cur)
            except: sftp.mkdir(cur)

    # Store root_path in connection info
    sftp_connections[conn_id] = {
        'client': client, 'sftp': sftp,
        'info': {**data, 'root_path': root_path}
    }
    return jsonify({'ok': True, 'conn_id': conn_id, 'root_path': root_path})
```

### Frontend: Enforce Lock on Navigation

```javascript
let diskRoot = null;  // set after connect if root_path provided

async function connectServer() {
    ...
    const data = await resp.json();
    diskRoot = data.root_path || null;
    // Show 🔒 icon when locked
    const label = diskRoot ? '🔒 ' + host : '☁️ ' + host;
    document.getElementById('disk-server-name').textContent = label;
    // Start at root_path
    diskPath = diskRoot || '/';
    diskList(diskPath);
}
```

**Back button (上级) enforcement:**

```javascript
function diskGoBack() {
    if (!diskPath || diskPath === '/') return;
    if (diskRoot && diskPath === diskRoot) {
        showToast('🔒 已锁定在根路径');
        return;
    }
    const parent = diskPath.substring(0, diskPath.lastIndexOf('/')) || '/';
    if (diskRoot && !parent.startsWith(diskRoot)) {
        showToast('🔒 已锁定在根路径');
        return;
    }
    diskList(parent);
}
```

Use `startsWith(diskRoot)` for the boundary check rather than comparing string lengths — this handles edge cases where a sibling path happens to be the same length as the root.

**UI indicator**: Change the server name icon from ☁️ to 🔒 when root_path is set.

### When to lock vs not

| Scenario | root_path | Behavior |
|----------|-----------|----------|
| Admin managing entire server | empty / not set | Free mode — navigate anywhere from `/` |
| User with quota/workspace directory | `/home/user/workspace` | Locked mode — can't go above this dir |
| Project-specific sandbox | `/opt/projects/123` | Locked — user only sees their project files |

## Auto-Connect from Saved Config (Persistent Single-Server UX)

After the user connects once, save the full server config to `localStorage` so they never have to re-enter credentials. On disk page load, auto-connect if a saved config exists.

### Frontend: Save on Connect, Auto-Connect on Load

```javascript
let diskConnId = null;
let diskPath = '/';
let diskRoot = null;

// === Auto-connect ===
function autoConnect() {
  const saved = localStorage.getItem('diskServer');
  if (!saved) return;
  try {
    const cfg = JSON.parse(saved);
    if (!cfg.host) return;
    showToast('正在连接 ' + cfg.host + '…');
    fetch('/api/disk/connect', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({...cfg, root_path: cfg.root_path || undefined})
    }).then(r=>r.json()).then(data => {
      if (!data.ok) { showToast('自动连接失败'); return; }
      diskConnId = data.conn_id;
      diskRoot = data.root_path || null;
      const label = diskRoot ? '🔒 ' + cfg.host : '☁️ ' + cfg.host;
      document.getElementById('disk-server-name').textContent = label;
      document.getElementById('disk-connect-btn').textContent = '断开';
      document.getElementById('disk-connect-btn').onclick = disconnectServer;
      diskPath = diskRoot || '/';
      diskList(diskPath);
    }).catch(() => {});
  } catch(e) {}
}

// === Disconnect ===
function disconnectServer() {
  if (!diskConnId) return;
  fetch(`/api/disk/${diskConnId}/disconnect`, { method:'POST' }).catch(()=>{});
  diskConnId = null; diskRoot = null; diskPath = '/';
  document.getElementById('disk-server-name').textContent = '☁️ 未连接';
  document.getElementById('disk-connect-btn').textContent = '连接';
  document.getElementById('disk-connect-btn').onclick = showServerModal;
  document.getElementById('current-path').textContent = '/';
  document.getElementById('disk-files').innerHTML =
    '<div class="disk-empty">点击「连接」输入服务器信息</div>';
}
```

### Trigger auto-connect on page/disk switch

In `switchPage()` (or equivalent page navigation function), check if not already connected:

```javascript
function switchPage(name) {
  if (name === 'disk') {
    // ... show disk page ...
    if (!diskConnId) autoConnect();  // <--- key line
  }
  // ...
}
```

### Save config after successful manual connect

At the end of `connectServer()`, after receiving a successful response:

```javascript
localStorage.setItem('diskServer', JSON.stringify({
  host, port, username, password,
  root_path: rootPath || ''
}));
```

### Button state toggle

The same "连接" button becomes "断开" after connecting, with `onclick` toggling between `showServerModal` and `disconnectServer`. This is cleaner than having two separate buttons:

```html
<button class="disk-add-btn" id="disk-connect-btn"
        onclick="showServerModal()">连接</button>
```

```javascript
// After connect:
document.getElementById('disk-connect-btn').textContent = '断开';
document.getElementById('disk-connect-btn').onclick = disconnectServer;

// After disconnect:
document.getElementById('disk-connect-btn').textContent = '连接';
document.getElementById('disk-connect-btn').onclick = showServerModal;
```

### Pre-Filled Connection Form (Single-Server Deployments)

For single-server deployments where the user always connects to the same host, **pre-fill** the host/port/username fields so the user only needs to enter the password:

```html
<input type="text" id="srv-host" value="81.70.229.222">
<input type="number" id="srv-port" value="22">
<input type="text" id="srv-user" value="ubuntu">
<input type="password" id="srv-pass" placeholder="密码">
```

**Remove the root_path field from the modal entirely** — it's not user-configurable. Instead, hardcode the default root_path in `connectServer()`:

```javascript
async function connectServer() {
  // ...
  // Use saved root_path if available, otherwise use default
  let rootPath = '/home/ubuntu/113646';
  try {
    const saved = JSON.parse(localStorage.getItem('diskServer') || '{}');
    rootPath = saved.root_path || rootPath;
  } catch(e) {}
  // ...
  // Save config for auto-connect (preserve root_path)
  localStorage.setItem('diskServer', JSON.stringify({
    host, port, username, password,
    root_path: rootPath || ''
  }));
}
```

This combines with auto-connect to create a zero-friction UX:
1. First visit → pre-filled form → type password only → click connect
2. All subsequent visits → click 云盘 → auto-connects silently
3. "断开" button available to switch servers

### UX Flow

1. First visit → "☁️ 未连接" + "连接" button → user fills modal → connects
2. Config saved to localStorage
3. Refresh page / come back later → click "云盘" → auto-connects silently
4. "断开" button available to switch servers
5. Connecting to a new server overwrites the saved config

## Disk Usage Endpoint

Three approaches, choose based on your use case:

### Option A: `statvfs` (SFTP native, partition-level)

```python
sftp = client.open_sftp()
stat = sftp.statvfs('/path')
total = stat.f_blocks * stat.f_frsize
free = stat.f_bavail * stat.f_frsize
used = total - free
```

### Option B: `df -B1` via SSH (fallback, partition-level)

```python
stdin, stdout, stderr = client.exec_command("df -B1 /path | tail -1")
output = stdout.read().decode().strip()
parts = output.split()
if len(parts) >= 4:
    total = int(parts[1])
    used = int(parts[2])
    free = int(parts[3])
```

### Option C: `du -sb` + quota (directory-level, preferred for quota-based plans)

For apps where users have a fixed quota (e.g., 20GB) and you want to show usage of **only their directory** (not the entire partition):

```python
QUOTA_BYTES = 20 * 1024 * 1024 * 1024  # 20GB

stdin, stdout, stderr = client.exec_command("du -sb /home/ubuntu/yunpan | cut -f1")
output = stdout.read().decode().strip()
used = int(output) if output else 0
free = max(0, QUOTA_BYTES - used)
```

**Why use this**: `df` reports the entire partition's usage. If the partition is 500GB but the user only has a 20GB quota in their `/home/ubuntu/yunpan` directory, `du -sb` gives the correct directory-level usage.

Display as a colored progress bar: green (<60%), orange (60-85%), red (>85%), refreshed after upload/delete.

## AI Function Calling for SFTP Tools (Bridging Chat + File Manager)

When the Flask app has both a chat AI and an SFTP file manager, you can let the AI control the file system via OpenAI-compatible function calling. This means the user can say "list my files" or "read config.json" in the chat and get results.

### Architecture

The chat AI gets tool definitions for SFTP operations. When the AI "calls" a tool, the backend executes it via a fresh SFTP connection and feeds the result back to the AI.

### Prerequisites

1. **Store `user_id` on connect** — so the AI can find the right server for the current user
2. **Fresh SFTP connections per tool call** — each tool execution creates a new SSH+SFTP session
3. **The AI model must support function calling** (DeepSeek, GPT-4, Claude 3+)

### Implementation Summary

The SFTP tools are:
- `list_files(path)` → returns file listing with names, sizes, types
- `read_text_file(path)` → returns text content
- `delete_item(path)` → deletes file or empty directory
- `create_directory(path)` → creates directory
- `get_disk_usage()` → returns quota-based usage statistics

See `flask-byok-ai-proxy` skill for the full tool definition and function calling loop implementation.

### Pitfall: Tool Result Size

`du -sb` or recursive file listings can return large results. Truncate to prevent context window overflow:
- Limit file listings to first 100 entries
- Truncate text file reads to first 2000 characters
- Return error if directory has too many files

## File Preview (Word, Excel, PPT, Images, PDF, Text)

Add in-browser file preview to the SFTP file manager so users can view Word, Excel, PPT, images, PDFs, and text files without downloading.

### Required Libraries

```bash
pip install python-docx openpyxl python-pptx Pillow
```

### Preview Endpoint Pattern

Key design: **read the file into memory via SFTP**, process it server-side, return the preview data as JSON:

```python
# Detect file type by extension
PREVIEWABLE_IMAGES = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}
PREVIEWABLE_TEXT = {'.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.toml', '.log', '.sh'}

@app.route('/api/disks/<conn_id>/preview', methods=['GET'])
def disk_preview(conn_id):
    conn = sftp_connections.get(conn_id)
    path = request.args.get('path', '')
    ext = os.path.splitext(path)[1].lower()
    
    # Fresh SFTP connection
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(info['host'], port=int(info.get('port', 22)),
        username=info['username'], password=info.get('password', ''), timeout=15)
    sftp = client.open_sftp()
    
    if ext in PREVIEWABLE_IMAGES:
        # Read binary → base64 → data URI
        with sftp.open(path, 'rb') as f:
            raw = f.read()
        mime = {'jpg':'image/jpeg','png':'image/png','gif':'image/gif'}.get(ext, 'image/png')
        b64 = base64.b64encode(raw).decode()
        result = {'ok': True, 'type': 'image', 'data': f'data:{mime};base64,{b64}'}
    
    elif ext == '.docx':
        import io
        from docx import Document
        with sftp.open(path, 'rb') as f:
            raw = f.read()
        doc = Document(io.BytesIO(raw))
        text = '\n'.join(p.text for p in doc.paragraphs)
        tables = [[[cell.text for cell in row.cells] for row in table.rows] for table in doc.tables]
        result = {'ok': True, 'type': 'word', 'text': text, 'tables': tables}
    
    elif ext in ('.xlsx', '.xls'):
        import io
        from openpyxl import load_workbook
        with sftp.open(path, 'rb') as f:
            raw = f.read()
        wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        sheets = []
        for name in wb.sheetnames:
            ws = wb[name]
            rows = [[str(c) if c is not None else '' for c in row] for row in ws.iter_rows(values_only=True)]
            sheets.append({'name': name, 'rows': rows})
        wb.close()
        result = {'ok': True, 'type': 'excel', 'sheets': sheets}
    
    elif ext == '.pptx':
        import io
        from pptx import Presentation
        with sftp.open(path, 'rb') as f:
            raw = f.read()
        prs = Presentation(io.BytesIO(raw))
        slides = []
        for slide in prs.slides:
            texts = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        if para.text.strip(): texts.append(para.text)
                if shape.has_table:
                    for row in shape.table.rows:
                        texts.append(' | '.join(cell.text for cell in row.cells))
            slides.append(texts)
        result = {'ok': True, 'type': 'ppt', 'slides': slides}
    
    elif ext == '.pdf':
        # ⚠️ DO NOT use base64 data URI — Android WebView does not support
        # <embed src="data:application/pdf;base64,...">. The embed silently
        # fails (blank). Instead, download the PDF to a server temp directory
        # and serve via HTTP URL.
        with sftp.open(path, 'rb') as f: raw = f.read()
        local_pdf = DOWNLOAD_DIR / f"preview_{uuid.uuid4().hex[:8]}_{filename}"
        local_pdf.write_bytes(raw)
        result = {'ok': True, 'type': 'pdf', 'url': f'/dl/{local_pdf.name}', 'filename': filename, 'size': len(raw)}
    
    elif ext in PREVIEWABLE_TEXT:
        with sftp.open(path, 'r') as f:
            content = f.read(200000)  # max 200KB
        result = {'ok': True, 'type': 'text', 'content': content}
    
    else:
        result = {'ok': False, 'error': f'不支持预览 {ext} 格式'}
    
    sftp.close(); client.close()
    return jsonify(result)
```

### Frontend Preview Modal

Add a modal with a header (filename + close) and a scrollable body. Render different views based on `result.type`:

- **image**: `<img src="${data}">`
- **text**: `<pre>${escapeHtml(content)}</pre>`
- **word**: `<pre>${text}</pre>` + tables rendered as `<table>`
- **excel**: sheet tabs as buttons + per-sheet `<table>` with tab switching
- **ppt**: slide sections with slide number labels
- **pdf**: Download button with file info (not inline embed — Android WebView cannot render base64 PDF). Click triggers system DownloadManager.

Use a helper to escape HTML:

```javascript
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
```

### Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| Large images crash browser | Base64 data too large | Limit images to ~10MB via SFTP `f.read(10*1024*1024)`, show error otherwise |
| Excel with 10000+ rows | Memory + render overload | Limit rows with `ws.iter_rows(max_row=200)` for preview |
| Word doc with complex formatting (tables in headers/footers, images) | python-docx doesn't extract these | Document limitations in UI — show what's extractable |
| `.doc` (not `.docx`) unsupported | python-docx only handles .docx format | Return error message suggesting user convert to .docx |
| Base64 inline PDF in mobile WebView | Android WebView lacks a built-in PDF renderer for `data:application/pdf` URIs. `<embed src="data:...pdf...">` renders a blank white box with no error. | Download PDF to server `/tmp/` directory, serve via HTTP URL, and show a download button. The Android `DownloadListener` handles the download and the system PDF reader opens it. |
| SVGs with embedded scripts | XSS risk | Filter `<script>` tags from SVG content or render as <img>, not inline |
| Preview button shows for unsupported file types | Extension not in any list | Add fallback — try reading as text, if that fails, show "不支持预览" |

## Debugging Silent Frontend Failures

A common issue in mobile SPA Flask apps: buttons/actions do **nothing** when tapped — no error, no visible response. This is almost always a JavaScript error being silently swallowed by the mobile browser.

### Debugging Approach (Using Hermes Browser Tool)

1. **Open the page via `browser_navigate`**
2. **Click the failing button** (e.g., connect, upload, delete)
3. **Check `browser_console`** for JS errors — even empty `"exception"` entries are meaningful
4. **Test the API directly** via `browser_console` with an async expression:
   ```javascript
   try { (async()=>{const r=await fetch('/api/disk/connect',{method:'POST',...}); const d=await r.json(); console.log('OK',d) })() } catch(e) { console.error('ERR',e.message) }
   ```
   This isolates whether the bug is API-side (auth, timeout) vs frontend-side (JS undefined function, DOM error)
5. **Check function name mismatches** — the most common pattern: the HTML `onclick` handler calls `someFunction()` but the `<script>` defines it as `someOtherName()`. Common examples:
   - `toast()` vs `showToast()` — toast helper functions
   - `closeModal()` vs `hideModal()` — modal helpers
   - `diskRefresh()` vs `refreshDisk()` — etc.
6. **Search the HTML** for the function name to verify it exists:
   ```bash
   grep -n 'function toast\|function showToast' /root/webui/index.html
   ```

### Common Patterns

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Button click does nothing, no toast shown | `toast()` calls undefined function | Rename calls to match definition |
| Modal opens but confirm button does nothing | `onclick` handler references wrong function name | Check function name in HTML vs script |
| API call works from console but button fails | Frontend JS error prevents fetch from executing | Check console for any exception |
| Works on desktop Chrome but not on mobile | Xiaomi/Android browser may have stricter CSP or different error handling | Test via Hermes browser tool (uses real Chromium) |

| Issue | Cause | Fix |
|-------|-------|-----|
| "Socket is closed" | Persistent SFTP connection dropped by server/firewall | **Fresh connection per request** — don't reuse |
| Upload hangs forever | Background thread crashes silently | Use synchronous upload instead, or add SSE error notification |
| "local_path is an unexpected keyword argument" | Paramiko `put` uses positional args | `sftp.put(local_path_str, remote_path_str)` |
| Files partially transferred | Connection dropped mid-transfer | Fresh connections + synchronous upload (retry inside exception handler) |
| Duplicate server entries | Multiple connections to same host | Disconnect existing on reconnect |
| Upload modal shows old file | Progress bar state not reset | Reset progress display on `diskUpload()` open |
| Progress bar never stops | setInterval not cleared globally | Use module-level `uploadTimer` variable |
