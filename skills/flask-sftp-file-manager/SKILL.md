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

## Disk Usage Endpoint

Two approaches for getting disk usage:

### Preferred: `statvfs` (SFTP native)

```python
@app.route('/api/disks/<conn_id>/usage', methods=['GET'])
def disk_usage(conn_id):
    conn = sftp_connections.get(conn_id)
    info = conn['info']
    client = paramiko.SSHClient()
    client.connect(...)
    sftp = client.open_sftp()
    stat = sftp.statvfs('/home/ubuntu/yunpan')
    total = stat.f_blocks * stat.f_frsize
    free = stat.f_bavail * stat.f_frsize
    used = total - free
    sftp.close(); client.close()
    return jsonify({'ok': True, 'total': total, 'used': used, 'free': free})
```

### Fallback: `df -B1` via SSH

Some SFTP servers don't support `statvfs` (returns 400 error). Use SSH `exec_command` as fallback:

```python
import re

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, port=port, username=user, password=pw, timeout=15)
stdin, stdout, stderr = client.exec_command("df -B1 /path | tail -1")
output = stdout.read().decode().strip()
client.close()
parts = output.split()
if len(parts) >= 4:
    total = int(parts[1])
    used = int(parts[2])
    free = int(parts[3])
else:
    # fallback error
```

Display as a colored progress bar: green (<60%), orange (60-85%), red (>85%), refreshed after upload/delete.

## Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| "Socket is closed" | Persistent SFTP connection dropped by server/firewall | **Fresh connection per request** — don't reuse |
| Upload hangs forever | Background thread crashes silently | Use synchronous upload instead, or add SSE error notification |
| "local_path is an unexpected keyword argument" | Paramiko `put` uses positional args | `sftp.put(local_path_str, remote_path_str)` |
| Files partially transferred | Connection dropped mid-transfer | Fresh connections + synchronous upload (retry inside exception handler) |
| Duplicate server entries | Multiple connections to same host | Disconnect existing on reconnect |
| Upload modal shows old file | Progress bar state not reset | Reset progress display on `diskUpload()` open |
| Progress bar never stops | setInterval not cleared globally | Use module-level `uploadTimer` variable |
