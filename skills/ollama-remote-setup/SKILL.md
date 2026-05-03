---
name: ollama-remote-setup
description: "Install Ollama on a remote Linux server via SSH — download binary, create systemd service, pull and test a model."
version: 1.0.0
author: hermes
license: MIT
metadata:
  hermes:
    tags: [ollama, ssh, remote, model-serving, devops]
    related_skills: [ssh-remote-control]
    requires:
      python: [paramiko]
---

# Ollama Remote Setup

Install and configure Ollama on a remote Linux server via SSH. Covers downloading, systemd service creation (when the installer script fails to create one), model pulling, and API verification.

## When to Use

- User says "在XX服务器上装Ollama" / "能不能跑个小模型"
- Need to set up Ollama on a remote machine with limited RAM (1-2GB) for small models (0.5B-1B)
- Install script succeeds but systemd service wasn't created
- Need to pull and test a model after installation

## Prerequisites

- Remote server accessible via SSH
- Python paramiko installed locally (`pip3 install paramiko`)
- Password or key for the remote server

## Step-by-Step

### 1. SSH Connection

```python
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username='ubuntu', password='your_password', timeout=10)
```

### 2. Check Server Specs

```python
cmds = [
    'free -h',
    'df -h / | tail -1',
    'uname -m',
    'nproc',
]
for cmd in cmds:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
    print(stdout.read().decode().strip())
```

Minimum for small models (qwen2.5:0.5b): ~1GB RAM free, 500MB disk, any x86_64 CPU.

### 3. Install Ollama

```python
stdin, stdout, stderr = ssh.exec_command(
    'curl -fsSL https://ollama.com/install.sh | sh 2>&1', timeout=300)
```

ollama.com is accessible from Chinese mainland servers directly (no proxy needed).

### 4. Fix: Create systemd Service (if install script fails to)

Sometimes the install script downloads the binary but doesn't create the systemd service. Check:

```python
stdin, stdout, stderr = ssh.exec_command('systemctl is-active ollama 2>&1', timeout=5)
```

If the service doesn't exist, create it manually:

```python
cmds = [
    'sudo tee /etc/systemd/system/ollama.service > /dev/null << \'EOF\'\n'
    '[Unit]\n'
    'Description=Ollama Service\n'
    'After=network-online.target\n'
    '\n'
    '[Service]\n'
    'ExecStart=/usr/local/bin/ollama serve\n'
    'User=ubuntu\n'
    'Group=ubuntu\n'
    'Restart=always\n'
    'RestartSec=3\n'
    'Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"\n'
    '\n'
    '[Install]\n'
    'WantedBy=default.target\n'
    'EOF',
    'sudo systemctl daemon-reload',
    'sudo systemctl start ollama',
    'sudo systemctl enable ollama',
]
for cmd in cmds:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
```

### 5. Pull a Model

Small models suitable for 1-2GB RAM:

| Model | Size | RAM Needed |
|-------|------|------------|
| qwen2.5:0.5b | ~397MB | ~800MB free |
| llama3.2:1b | ~800MB | ~1.5GB free |
| tinyllama:1.1b | ~637MB | ~1.2GB free |

Pull command:
```python
stdin, stdout, stderr = ssh.exec_command('ollama pull qwen2.5:0.5b 2>&1', timeout=600)
```

### 6. Verify via API (not interactive CLI)

The `ollama run` command is interactive (TTY) and will time out over SSH. Always test via API:

```python
stdin, stdout, stderr = ssh.exec_command(
    'curl -s http://127.0.0.1:11434/api/generate '
    '-d \'{"model":"qwen2.5:0.5b","prompt":"你好","stream":false}\' 2>&1',
    timeout=30)
import json
result = json.loads(stdout.read().decode())
print(result.get('response', ''))
```

### 7. Cleanup Connection

```python
ssh.close()
```

## 8. Connect Remote Ollama to Local Hermes Agent

After Ollama is running on the remote server, configure Hermes Agent (running locally) to use it as an LLM provider.

### 8a. Open Remote Server's Firewall

The remote server's security group / cloud firewall must allow inbound traffic on port **11434**:

- **Tencent Cloud / Alibaba Cloud / AWS / GCP**: Go to the cloud console → Security Group → Add inbound rule:
  - Protocol: TCP
  - Port: 11434
  - Source: `0.0.0.0/0` (or your local server's IP for security)
- **UFW (Ubuntu)**: `sudo ufw allow 11434/tcp`
- **firewalld (CentOS/RHEL)**: `sudo firewall-cmd --add-port=11434/tcp --permanent && sudo firewall-cmd --reload`

After opening, verify from the local machine:
```bash
curl -s --noproxy '*' --connect-timeout 5 http://<REMOTE_IP>:11434/api/tags
# Should return: {"models":[...]}
```

### 8b. Configure Hermes to Use Remote Ollama

Ollama exposes an OpenAI-compatible API, so configure Hermes with the OpenAI provider pointing to the remote Ollama:

```bash
hermes config set model.provider openai
hermes config set model.base_url http://<REMOTE_IP>:11434/v1
hermes config set model.api_key ollama
```

Or edit `~/.hermes/config.yaml` directly:
```yaml
model:
  default: qwen2.5:0.5b
  provider: custom
  base_url: http://<REMOTE_IP>:11434/v1
  api_key: ""    # Ollama doesn't require auth
```

**Note:** Some Hermes providers may not recognize `api_key: ""` as valid. If so, set `api_key: "ollama"` (the value doesn't matter).

### 8c. Alternative: SSH Tunnel (No Firewall Change Needed)

If you can't or don't want to open the security group, use SSH port forwarding:

On your local machine:
```bash
ssh -L 11434:127.0.0.1:11434 ubuntu@<REMOTE_IP> -N
```

Then configure Hermes to connect via localhost:
```bash
hermes config set model.base_url http://127.0.0.1:11434/v1
```

The SSH tunnel encrypts all traffic and bypasses cloud security groups entirely. For persistent tunnels, use `autossh` or systemd.

### 8d. Test the Connection

From Hermes, run a quick test:
```bash
hermes chat -q "用中文回答：你好，你是谁？"
```

Or verify the API endpoint directly:
```bash
curl -s http://<REMOTE_IP_OR_LOCALHOST>:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5:0.5b",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }' 2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('choices',[{}])[0].get('message',{}).get('content','ERROR'))"
```

## Pitfalls

1. **`ollama run` over SSH** — Always use the REST API (`curl http://127.0.0.1:11434/api/generate`) instead of `ollama run` which is TTY-based.

2. **PATH issues** — After pip installs, commands go to `~/.local/bin/`. Use full paths or export PATH.

3. **Model pull timeout** — qwen2.5:0.5b is 397MB; on slow connections set timeout to 600s.

4. **Low memory** — If the server runs out of RAM, ollama will OOM. Use swap (`free -h` to check). On 1.9GB RAM servers with swap, qwen2.5:0.5b works fine.

5. **No GPU** — ollama will warn "No NVIDIA/AMD GPU detected. Ollama will run in CPU-only mode." This is fine for small models.

6. **Package install failures on Chinese servers** — If `apt-get install` fails with DNS errors, the server may have Chinese DNS that can't resolve foreign package mirrors. Use Tencent mirrors (`mirrors.tencentyun.com`) or set proxy.
