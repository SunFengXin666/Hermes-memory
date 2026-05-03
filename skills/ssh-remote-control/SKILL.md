---
name: ssh-remote-control
description: "SSH into remote Linux servers to execute commands, install software, transfer files, and manage the machine — using Python paramiko when sshpass is unavailable (CentOS/RHEL with broken DNS, minimal systems)."
version: 1.0.0
author: hermes
license: MIT
metadata:
  hermes:
    tags: [ssh, remote, paramiko, server, devops]
    requires:
      python: [paramiko]
---

# SSH Remote Control

SSH into remote Linux servers using Python's paramiko library. Reliable fallback when `sshpass` isn't available (common on CentOS/RHEL with broken package repos).

## When to Use

- User says "去XX服务器上装XX" / "控制那台服务器" / "SSH到XXX"
- Need to run commands, install software, check status on a remote machine
- `sshpass` is not installed and can't be installed (broken DNS, no EPEL, minimal system)
- Need to transfer files via SCP or run multi-step workflows on a remote host

## Prerequisites

```bash
pip3 install paramiko    # Already installed on this system
```

## Basic Pattern

```python
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# Connect with password
ssh.connect(host, username='ubuntu', password='password', timeout=10)

# Run a command
stdin, stdout, stderr = ssh.exec_command('command', timeout=30)
output = stdout.read().decode()
error = stderr.read().decode()

ssh.close()
```

## Common Command Patterns

### Single command, get output
```python
stdin, stdout, stderr = ssh.exec_command('hostname && whoami && cat /etc/os-release | head -3', timeout=10)
print(stdout.read().decode())
```

### Multiple independent commands
```python
cmds = [
    'which python3 node pip3',
    'python3 --version',
    'free -h',
    'df -h /',
]
results = {}
for cmd in cmds:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    results[cmd] = stdout.read().decode().strip()
```

### Install packages with apt
```python
stdin, stdout, stderr = ssh.exec_command(
    'sudo apt-get install -y python3-pip 2>&1 | tail -5',
    timeout=60
)
```

### Install Python packages (PEP 668 workaround)
On Ubuntu 24.04+, pip refuses system installs. Use `--break-system-packages`:
```python
stdin, stdout, stderr = ssh.exec_command(
    'pip3 install openclaw --break-system-packages 2>&1',
    timeout=120
)
```

## Pitfalls

1. **Unknown host key** — Always call `ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())` or first-time connections will fail.

2. **Command timeout** — `exec_command()` has two timeouts: the `timeout` param (data read timeout) and the channel timeout. Set both high enough for slow operations. For `apt-get install` or `pip3 install`, use `timeout=120` or more.

3. **Password with special chars** — Python will handle special chars in the password string naturally. Just pass it as a normal string.

4. **PATH issues** — Commands installed via `pip3 install --user` go to `~/.local/bin/` which may not be on the non-interactive SSH PATH. Either use full paths or set PATH explicitly:
   ```python
   ssh.exec_command('export PATH=$PATH:/home/ubuntu/.local/bin && cmdop-sdk --help', timeout=10)
   ```

5. **stderr vs stdout** — Some commands output to stderr even on success (e.g., `apt-get` warnings). Check both `stdout.read().decode()` and `stderr.read().decode()`.

6. **sudo password** — If the user configured passwordless sudo (common on cloud VPS), `sudo` commands work without interaction. If not, you'll need to use `run()` with `get_pty()` and send the password.

7. **Connection from Chinese VPS** — If connecting to a foreign server from a Chinese VPS, you may need to set the proxy first:
   ```python
   import os
   os.environ['https_proxy'] = 'http://127.0.0.1:7890'
   ```
   But actually paramiko SSH connects directly (not HTTP), so proxy isn't needed for SSH itself.

## SFTP File Transfers (paramiko)

### Basic SFTP upload/download
```python
import paramiko
from pathlib import Path

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, port=22, username='ubuntu', password='password', timeout=15)
sftp = client.open_sftp()

# Upload
sftp.put('/local/file.txt', '/remote/file.txt')
# Download
sftp.get('/remote/file.txt', '/local/file.txt')

sftp.close()
client.close()
```

### 🔑 CRITICAL: Fresh connection per operation (reliability pattern)
In unstable network environments (GFW, proxy, long idle times), persistent SSH/SFTP connections get **"Socket is closed"** errors. **Never reuse a long-lived SFTP connection** for file uploads/downloads — always create a fresh connection for each operation.

```python
# BAD: Persistent connection gets "Socket is closed" after idle
sftp = long_lived_conn['sftp']  # ❌ Will fail randomly

# GOOD: Fresh connection per operation
def upload_file(host, port, username, password, local_path, remote_path):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=port, username=username, password=password, timeout=30)
    sftp = client.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    client.close()
```

### SSH Keepalive (for connections that must persist)
If you must keep a connection alive (e.g., interactive shell), set keepalive to prevent timeout:
```python
client.connect(host, port=22, username='ubuntu', password='password', timeout=10)
client.get_transport().set_keepalive(15)  # Ping every 15 seconds
```

But prefer stateless pattern (connect → do work → close) over keepalive.

### Async upload with frontend polling (mobile app pattern)
For mobile apps where SFTP is slow/unreliable:
1. Phone HTTP uploads file to Flask server (immediate)
2. Flask saves locally and starts SFTP in background thread (fresh connection)
3. Flask responds immediately with `{status: 'uploading', filename: 'xxx'}`
4. Frontend shows progress bar and polls directory listing every 2s
5. When remote file appears, close progress and show success

```python
# Flask server: save file, then async SFTP
local_tmp = UPLOAD_DIR / f"ul_{uuid.uuid4().hex[:12]}_{file.filename}"
file.save(str(local_tmp))
threading.Thread(target=_do_sftp_upload, args=(conn_info, local_tmp, remote_path), daemon=True).start()
return jsonify({'ok': True, 'status': 'uploading', 'filename': file.filename})

def _do_sftp_upload(info, local_path, remote_path):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(info['host'], port=info['port'], username=info['username'], password=info['password'], timeout=30)
    sftp = client.open_sftp()
    sftp.put(str(local_path), remote_path)
    sftp.close()
    client.close()
    Path(local_path).unlink(missing_ok=True)
```

```javascript
// Frontend: poll remote dir until file appears
const iv = setInterval(async () => {
  const resp = await fetch(`/api/disks/${id}/list?path=/remote/dir`);
  const data = await resp.json();
  if (data.entries.some(e => e.name === targetFile)) {
    clearInterval(iv);
    // success: close modal, show toast, refresh list
  }
}, 2000);
```

### SFTP directory listing
```python
items = sftp.listdir_attr('/remote/path')
entries = [{
    'name': item.filename,
    'size': item.st_size,
    'mtime': item.st_mtime,
    'is_dir': bool(item.st_mode & 0o40000) if item.st_mode else False,
} for item in items]
```

## Verification

After connecting, always verify:
- `hostname` to confirm correct machine
- `whoami` to confirm correct user
- `cat /etc/os-release` to know the OS

Then run the actual task.
