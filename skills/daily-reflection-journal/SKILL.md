---
name: daily-reflection-journal
description: "Set up an automated daily journal/reflection system using Hermes Agent cron + session_search. Periodically summarizes conversations, saves structured markdown to timestamped files, updates a JSON index, serves via HTTP, backs up to GitHub, and sends chat notifications."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [cron, journal, reflection, daily-summary, session-search, productivity, automation]
    related_skills: [github-auto-sync, webhook-subscriptions]
---

# Daily Reflection Journal — Automated Summarization System

Set up a cron job that periodically retrieves the day's conversations, summarizes what was accomplished, learned, and what's pending, then persists the summary as a timestamped markdown file, updates a JSON index for a web viewer, backs up to GitHub, and sends a notification (QQ/Telegram/Discord).

## When to Use

The user wants some variant of:
- "每天自动总结我当天的对话和学习内容"
- "Set up a daily journal that auto-summarizes my conversations"
- "我想每天晚上自动生成今日总结"
- "Auto-save a summary of what I did today"
- "Create a daily memory / reflection system"
- "每晚把今天干了什么整理成笔记"
- "自动记录每天学到的新知识"

This is distinct from:
- **`github-auto-sync`** — that skill covers *how* to sync files to GitHub (the git mechanics). This skill covers the *full end-to-end workflow*: what to summarize, the file structure, the cron prompt design, the web viewer, and the notification chain.
- **`webhook-subscriptions`** — event-driven (external POST → agent run). This skill is time-driven (cron → agent run).

## Architecture

```
[Hermes Cron] 23:59 daily
      │
      ├─ session_search() → today's conversations
      ├─ Summarize → YYYY-MM-DD.md (structured markdown)
      ├─ Update list.json ←─→ index.html (web viewer)
      ├─ git push to GitHub (via sync.sh)
      └─ node → NapCat QQ Bot (or Telegram/Discord)\n```

### File Layout (`~/daily-memories/`)

```
~/daily-memories/
├── index.html          # Web viewer (marked.js-based, dark theme)
├── list.json           # ["2026-05-05", "2026-05-04", ...] (newest first)
├── server.py           # Python HTTP server (serves on PORT, default 8080)
├── 2026-05-05.md       # Daily summary
├── 2026-05-04.md
└── ...
```

## Setup Steps

### 1. Create storage directory

```bash
mkdir -p ~/daily-memories
```

### 2. Create the web viewer (index.html)

Create `~/daily-memories/index.html` — a standalone HTML page that:
- Loads `list.json` to show a date sidebar
- Uses `marked.js` (from CDN) to render `.md` files
- Dark theme, responsive design

See the companion `index.html` template in this skill's `templates/` directory.

### 3. Create the HTTP server (server.py)

A simple Python `http.server`-based static file server that serves the `~/daily-memories/` directory:

```python
#!/usr/bin/env python3
import json, os
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

MEMORIES_DIR = Path(os.path.expanduser("~/daily-memories"))
PORT = int(os.environ.get("PORT", 8080))
os.chdir(str(MEMORIES_DIR))

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(MEMORIES_DIR), **kwargs)

# Generate list.json on startup
files = sorted([f.stem for f in MEMORIES_DIR.glob("*.md")], reverse=True)
(MEMORIES_DIR / "list.json").write_text(json.dumps(files))

server = HTTPServer(("0.0.0.0", PORT), Handler)
print(f"Serving daily memories on http://0.0.0.0:{PORT}")
server.serve_forever()
```

**Auto-start on boot:** Add a `@reboot` cron entry:
```bash
(crontab -l 2>/dev/null; echo "@reboot sleep 10 && cd ~/daily-memories && python3 server.py > /tmp/daily-memories.log 2>&1") | crontab -
```

### 4. Create the cron job

Use `cronjob create` within Hermes Agent — the key is a well-crafted prompt:

```bash
# Done via Hermes Agent cronjob tool — NOT crontab
hermes cron create "daily-reflection" \
  --prompt "..." \
  --schedule "59 23 * * *" \
  --enabled-toolsets "session_search,terminal,file,web"
```

### 5. The Cron Prompt Template

The cron prompt must be **self-contained** — it can't ask the user for input. It must:

1. **Search today's sessions:**
   ```
   Use session_search (no args) to find today's conversations.
   ```

2. **Summarize into structured markdown:**
   ```
   Format:
   ## 📋 今日总结
   
   ### ✅ 已完成
   - (grouped by topic)
   
   ### 🔍 发现的坑 / 学到的知识
   - (technical details, root causes, solutions)
   
   ### 📝 明日待办
   - (unfinished items)
   ```

3. **Save to file:**
   ```
   Save to ~/daily-memories/YYYY-MM-DD.md (today's date).
   ```

4. **Update JSON index:**
   ```
   Regenerate list.json: ls *.md, strip .md suffix, sort reverse, write as JSON array.
   ```

5. **Git push for backup:**
   ```
   cd /root/hermes-memory-backup && bash sync.sh
   ```
   (sync.sh must include `daily-memories/` in its `git add` and copy steps)

6. **Send notification:**
   ```
   curl -X POST -H "Content-Type: application/json" \
     -d '{"action":"send_private_msg","params":{"user_id":TARGET_QQ,"message":"📅 今日记忆已生成\nhttp://server:8080"}}' \
     http://127.0.0.1:3001/
   ```
   (NapCat QQ Bot WebSocket HTTP API — port 3001, no token)

### 6. Integrate with GitHub backup

Edit `sync.sh` (your existing GitHub backup script) to include the daily-memories directory:

```bash
# Add after the regular copy steps:
cp -r ~/daily-memories/. ./daily-memories/ 2>/dev/null || true

# In git add:
git add ... daily-memories/
```

### QQ Notification via NapCat (not curl)

NapCat's port 3001 is a **WebSocket endpoint**, not HTTP. The `curl` approach in earlier versions of this skill is wrong — it will fail silently. Instead, use a Node.js WebSocket client script.

Create `/opt/napcat/send_qq_text.js`:

```javascript
/**
 * Send QQ private text message via NapCat WebSocket (port 3001, no token)
 * Usage: node send_qq_text.js [QQ] "message"
 * Default QQ is your target user
 */
const WebSocket = require('ws');

const targetQQ = process.argv[2] && /^\d+$/.test(process.argv[2])
  ? Number(process.argv[2]) : 3240171077;
const message = process.argv[3] || process.argv[2] || '测试消息';

const ws = new WebSocket('ws://127.0.0.1:3001');
const timeout = setTimeout(() => { console.error('Timeout'); process.exit(1); }, 8000);

ws.on('open', () => {
  ws.send(JSON.stringify({
    action: 'send_private_msg',
    params: { user_id: targetQQ, message },
    echo: 'send_text'
  }));
});

ws.on('message', (data) => {
  const resp = JSON.parse(data.toString());
  if (resp.echo === 'send_text') {
    clearTimeout(timeout);
    process.exit(resp.status === 'ok' || resp.retcode === 0 ? 0 : 1);
  }
});

ws.on('error', (err) => { console.error(err.message); process.exit(1); });
setTimeout(() => process.exit(0), 8000);
```

In the cron prompt, call it as:
```bash
cd /opt/napcat && node send_qq_text.js "📅 每日记忆 - 2026-05-05\n\n✅ 已完成\n<摘要>\n\n🔍 学到\n<要点>\n\n📝 明日\n<待办>"
```

Keep QQ messages under 8 lines — NapCat truncates long messages silently.

### Serving via nginx (alternative to server.py)

Instead of `python3 server.py`, use a Docker nginx container for production:

```bash
docker run -d --name daily-memories \
  -p 4000:80 \
  -v ~/daily-memories:/usr/share/nginx/html:ro \
  --restart unless-stopped \
  nginx:alpine
```

Benefits: less memory (~5MB vs Python's ~20MB), auto-restart via Docker, better caching headers.

### list.json regeneration (one-liner)

Include this in the cron prompt to regenerate the JSON index:

```bash
python3 -c "import json,glob; files=sorted([f.replace('.md','') for f in glob.glob('*.md')], reverse=True); open('list.json','w').write(json.dumps(files))"
```

Run this from `~/daily-memories/` after writing the new .md file.

### Cron `run` reschedules, doesn't execute immediately

`cronjob run` updates `next_run_at` to now+scheduler_tick — it does **not** run the job synchronously. The next scheduler tick (usually within 30-60s) triggers execution. Use `cronjob list` to verify `last_run_at` and `last_status` changed.

## Pitfalls & Troubleshooting

- **Cron job session_search() returns nothing:** If the user just started talking, there may be no sessions yet. The prompt should handle "no sessions found" gracefully (output "今日无记录" instead of failing).
- **list.json must match .md files:** Always regenerate list.json after creating a new .md file, otherwise the web viewer shows nothing. Include this step in the cron prompt.
- **QQ Bot 3001 vs 6099:** Port 3001 is WebSocket without token (simpler for internal scripts). Port 6099 requires a token but supports the NCWebsocket library. Use 3001 for simple `send_private_msg` calls from cron.
- **Network hairpin on Chinese cloud servers:** Tencent Cloud / Alibaba Cloud don't support hairpin NAT — you can't curl your own public IP from inside the server. Use `localhost` or `127.0.0.1` for internal connections.
- **Memory bottleneck:** The daily generation runs the full Hermes Agent loop. On a 3-4GB RAM server, ensure there's ~1GB free at the scheduled time. Kill Chrome renderer processes (`pkill -f chromium-browser`) before the scheduled time if memory is tight.
- **Cron job won't run if Hermes Agent gateway isn't running:** Check with `systemctl --user status hermes-gateway` or check cron job status with `cronjob list` and look at `last_status`.
- **Hermes Agent skill must be loaded:** Before setting up cron jobs, load the `hermes-agent` skill — it documents the actual `cronjob` tool syntax and available options.
- **Timezone of cron:** The Hermes Agent cron scheduler uses the server's local time. Check with `timedatectl` or `date +%Z`. For China servers this is usually `Asia/Shanghai (CST, UTC+8)`.
