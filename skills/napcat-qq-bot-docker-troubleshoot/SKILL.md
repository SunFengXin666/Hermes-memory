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
