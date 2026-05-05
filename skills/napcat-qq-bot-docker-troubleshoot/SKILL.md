---
name: napcat-qq-bot-docker-troubleshoot
description: Diagnose and fix NapCat QQ Bot (Docker) disconnection issues — account offline, WebSocket unresponsive, container alive but QQ logged out.
category: devops
when_to_use: |
  User says QQ bot is not responding / can't connect / offline.
  NapCat logs show "账号状态变更为离线".
  QQ bot stopped sending/receiving messages on a server running NapCat in Docker.
  Container appears running (docker ps shows UP) but bot is unresponsive.
triggers:
  - user says QQ bot 连不上/掉线/没反应
  - docker logs show "账号状态变更为离线"
  - system lag was fixed (killed Chrome) and now QQ bot needs reconnection
  - container restart needed for NapCat
---

# NapCat QQ Bot Docker Troubleshooting

Quick workflow for when NapCat QQ Bot (running in Docker container `napcatf`) loses connection — usually caused by memory pressure on constrained servers.

## Phase 0: Identify Which QQ Bot Is Down

There are **two independent QQ bot systems** on this server. When user says "QQ bot 连不上":

| System | Type | Connection | How to check |
|--------|------|-----------|-------------|
| **NapCat** (Docker, `napcatf`) | QQ NT protocol bot using a real QQ account | `ws://127.0.0.1:3001` (OneBot API) | `docker ps --filter name=napcat` + `docker logs napcatf --tail 10` |
| **Hermes Gateway QQ Bot** (official API) | Tencent Bot API using app_id + client_secret | `wss://api.sgroup.qq.com/websocket` | `cat /root/.hermes/logs/gateway.log \| grep QQBot \| tail -5` |

**Quick check:**
```bash
# Check gateway logs for QQ Bot status
grep -E "QQBot|qqbot" /root/.hermes/logs/gateway.log 2>/dev/null | tail -10
```

**Hermes Gateway QQ Bot failure symptoms:**
```
WebSocket error: WebSocket closed           # recurring disconnects every ~1 min
Reconnect failed: Failed to get QQ Bot gateway URL:  # token expired
```

**Confirm token expiration:**
```bash
curl -s -H "Authorization: Bot {app_id}.{client_secret}" https://api.sgroup.qq.com/gateway/bot
# HTTP 401, {"message":"Token错误","code":11243} → token expired
```

### Fix: Hermes Gateway QQ Bot Token Expiration

1. **Verify the problem:**
   ```bash
   # Check gateway logs
   grep -E "QQBot|qqbot" /root/.hermes/logs/gateway.log 2>/dev/null | tail -5
   # Expected error: 'invalid appid or secret' (code 100016) or 'Token错误' (code 11243)
   ```

2. **Login to QQ Open Platform:**
   - Navigate browser to https://q.qq.com/
   - **PREFERRED: QR code scan** — click **快捷登录** (quick login) to get a QR code
     - Screenshot the QR code area and send to user's QQ via NapCat:
       ```bash
       cp /root/.hermes/cache/screenshots/browser_screenshot_xxx.png /root/qrcode.png
       python3 -c "
       import json, asyncio, websockets, base64
       async def send():
           async with websockets.connect('ws://127.0.0.1:3001') as ws:
               await asyncio.wait_for(ws.recv(), timeout=5)
               with open('/root/qrcode.png', 'rb') as f:
                   img_b64 = base64.b64encode(f.read()).decode()
               msg = {'action': 'send_private_msg', 'params': {'user_id': 3240171077,
                   'message': [{'type':'text','data':{'text':'扫码登录开放平台：'}},
                               {'type':'image','data':{'file':f'base64://{img_b64}'}}]}}
               await ws.send(json.dumps(msg))
               resp = await asyncio.wait_for(ws.recv(), timeout=10)
               print(resp)
       asyncio.run(send())
       "
       ```
     - After user scans, a **选择登录主体 (Select Login Entity)** dialog appears. Click the listed account (e.g., `3240171077@qq.com`), then click **确认登录**.
   - **⚠️ Password login pitfalls:** Entering QQ number + password often triggers image CAPTCHA (图片验证码). The CAPTCHA renders inside a cross-origin iframe making it nearly impossible to automate via browser snapshot. If CAPTCHA appears, use the **快捷登录** link in the iframe to switch back to QR code mode.
   - The page text says **"推荐使用快捷登录，防止盗号"** — always try QR first.

3. **Navigate to bot management:**
   - Left sidebar → click **机器人** (Bot/Robot) section
   - Find bot with app_id **1903820137** (name "787")
   - Click the bot row (ref=e11) to enter detail page
   - The detail page shows `AppID` and hidden `AppSecret`

4. **Regenerate client_secret:**
   - Click **查看** (View) to reveal the secret
   - A dialog appears: **确认重置** (Confirm Reset) — click it
   - ⚠️ **IMPORTANT — the "二次查看将会强制重置" logic:** The first click of "查看" just reveals the current secret. Only clicking a SECOND time triggers the actual forced reset. If you already viewed the secret once, just click "查看" again and confirm.
   - The new AppSecret appears in plaintext: `AppSecret\n<new_value>\n`
   - **Critical — get the FULL value:** The secret may be partially truncated in the browser UI display. Use browser_console to extract the raw text:
     ```javascript
     // In browser_console tool:
     document.body.innerText.match(/AppSecret\s*\n([^\n]{30,60})/)?.[1]?.trim()
     ```
   - **⚠️ CRITICAL PITFALL — tool display truncation:** Both `read_file` and terminal commands like `cat | grep` will truncate long lines in the HERMES UI, showing **`...`** where the middle characters should be. Example: `client_secret: Rj1KeyJf1O...U4fH` when the real value is `Rj1KeyJf1OmAZzPqIkDhBgCiFnLuU4fH`. Never trust a truncated display — always verify the raw bytes:
     ```bash
     # Verify the actual file content (sed prints raw line)
     sed -n '394p' /root/.hermes/config.yaml | cat -A
     # If you see "..." in the output, the file actually has "..." — it's NOT a display truncation
     ```
   - **Test the secret directly** before updating config:
     ```bash
     curl -s -X POST "https://bots.qq.com/app/getAppAccessToken" \
       -H "Content-Type: application/json" \
       -d '{"appId":"1903820137","clientSecret":"<new_secret>"}'
     # Expected: {"access_token": "xxx...", "expires_in": "xxx"}
     # If you get {"code":100016,"message":"invalid appid or secret"}, the secret is wrong
     ```

5. **Update config.yaml:**
   
   The `client_secret` is at this exact path in `/root/.hermes/config.yaml`:
   ```yaml
   platforms:
     qq:
       extra:
         client_secret: <new_secret>   # ← Replace this
   ```
   
   **Use `sed` for reliable replacement** (patch tool may struggle with long strings containing special chars):
   ```bash
   # Replace the client_secret line
   sed -i 's|client_secret:.*|client_secret: <full_new_secret>|' /root/.hermes/config.yaml
   
   # Verify it worked
   grep client_secret /root/.hermes/config.yaml
   ```

6. **Restart Hermes Gateway:**
   ```bash
   # Kill existing gateway process
   pkill -f "hermes_cli.main gateway run" 2>/dev/null
   sleep 3
   
   # Start new one
   nohup /root/.hermes/hermes-agent/venv/bin/python \
     -m hermes_cli.main gateway run --replace \
     >> /root/.hermes/logs/gateway.log 2>&1 &
   ```
   
   Alternative if systemd is configured:
   ```bash
   systemctl restart hermes
   ```

7. **Verify:**
   ```bash
   sleep 8
   grep -E "QQBot|qqbot|connected|access token" /root/.hermes/logs/gateway.log | tail -5
   # Expected: "Access token refreshed" → "WebSocket connected" → "Session resumed"
   # NOT: "invalid appid or secret" or "Token错误"
   ```

---

## Phase 1: Check Container Status

```bash
# Is container running?
docker ps -a --filter name=napcat

# Recent logs — look for "账号状态变更为离线"
docker logs napcatf --tail 50 2>&1
```

**Key log signals:**
- `账号状态变更为离线` → QQ account logged out, need re-login
- `LongTask(...): duration=3000ms+` → severe memory pressure, likely root cause
- `WebSocket Server Started :::3001` → WS server is up, port is listening

## Phase 2: Quick Fix — Restart Worker Process

If container is running and WS port (3001) is responding but account is offline:

### Option A: Restart via NapCat WebUI (recommended)

1. Access WebUI at `http://127.0.0.1:6099/webui`
2. Login with token (get from container): 
   ```bash
   docker exec napcatf cat /app/napcat/config/webui.json | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])"
   ```
   Default username: `napcat-webui`
3. Navigate to **系统配置** → **登录配置**
4. Click **重启进程** button — worker restarts, account re-logs in automatically if credentials cached
5. Verify: look for `QQ登录成功` in WebUI status bar or `docker logs napcatf --tail 5`

### Option B: Restart Full Docker Container

```bash
docker restart napcatf
sleep 10
docker logs napcatf --tail 10 2>&1
```

After restart, check for:
- WebSocket Server Started :::3001
- Account auto-login (may take 5-15s)

## Phase 3: If Account Doesn't Auto-Reconnect

If restarting doesn't bring the account back online:

1. **Fix memory pressure first** — NapCat's QQ client needs memory to initialize:
   ```bash
   pkill -f chromium-browser  # kills Chrome, frees ~1GB+
   free -h                    # verify available > 500MB
   ```

2. **Try Quick Login on WebUI:**
   - Go to **系统配置** → **登录配置**
   - Click **获取已登录账号列表**
   - Click on the listed account (e.g., "hungry 2764388952")
   - Click **保存**
   - Click **重启进程** again

3. **QR Code login** (if token expired):
   - Enter QQ number in "快速登录QQ" textbox
   - Save → restart worker
   - Check NapCat logs for QR code URL or check VNC (port 5900/6081)

## Phase 4: Test Reconnection

Once account is back online, verify:

```bash
# Test WebSocket endpoint responds
curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:3001/
# Expected: 426 (Upgrade Required) — means WS server is live

# Send test message via WebSocket
python3 -c "
import json, asyncio, websockets
async def test():
    async with websockets.connect('ws://127.0.0.1:3001') as ws:
        # Wait for lifecycle connect event
        await ws.recv()
        # Send test message
        msg = {'action': 'send_private_msg', 'params': {'user_id': 3240171077, 'message': 'Bot 已重连。'}}
        await ws.send(json.dumps(msg))
        resp = await asyncio.wait_for(ws.recv(), timeout=5)
        print(resp)
asyncio.run(test())
" 2>&1
```

## Root Cause: Memory Pressure

NapCat runs QQ's full browser-based protocol inside Docker. On a 3.6GB server:
- When memory drops below ~200MB available, QQ's internal browser chokes
- LongTask durations spike (1-10s delays)
- QQ server detects abnormal behavior and force-disconnects (账号状态变更为离线)
- Chrome renderer processes are the #1 memory culprit — they accumulate over days

**Prevention:**
```bash
# Add swap for safety margin
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile

# Kill Chrome when not actively using it
pkill -f chromium-browser
```

## NapCat WebUI Reference

| Detail | Value |
|--------|-------|
| WebUI URL | `http://127.0.0.1:6099/webui` |
| Default username | `napcat-webui` |
| WebSocket (bot API) | `ws://127.0.0.1:3001` (no token) |
| WebSocket (web API) | `ws://127.0.0.1:6099` (token required) |
| Docker container | `napcatf` |
| Config directory | `/app/napcat/config/` inside container |
| Account nickname | `hungry` (2764388952) |

## Pitfalls

- **Don't confuse NapCat (QQ protocol bot) with Hermes Gateway QQ Bot (official API bot).** NapCat uses an actual QQ account via NT protocol; the gateway bot uses app_id 1903820137 via `api.sgroup.qq.com`. They're independent.
- **WebUI token may work as query param** `?token=xxx` on some endpoints (e.g., `/api/status?token=xxx`) but not on all. Use the browser login page for reliability.
- **Restarting the Docker container** is more thorough than restarting the worker via WebUI — it clears stale state in the container runtime.
- **Don't kill Hermes gateway process** — that's a separate service. Only kill chromium/chrome processes for memory.
- **QQ account 2764388952 (hungry)** logs in automatically on restart if token is cached. If token expired, it needs QR code re-scan from the WebUI.
