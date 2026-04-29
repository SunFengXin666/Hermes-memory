---
name: chrome-devtools-remote-china
description: Set up Chrome DevTools remote debugging on Chinese mainland servers where Google CDN (chrome-devtools-frontend.appspot.com) is blocked by the Great Firewall. Covers creating a Python reverse proxy to remove CSP restrictions and route CDN resources through mihomo proxy.
tags:
  - devtools
  - remote-debugging
  - chromium
  - gfw
  - china
  - reverse-proxy
---

# Chrome DevTools Remote Debugging on Chinese Servers

## When to Use

Use this skill when you need to set up Chrome DevTools remote debugging (`--remote-debugging-port`) on a server in mainland China (Tencent Cloud, Alibaba Cloud, etc.) and the user cannot open `chrome://inspect` or the DevTools frontend because `chrome-devtools-frontend.appspot.com` is blocked by the GFW.

The symptom is: the DevTools inspector page opens but stays blank/spinning, or the WebSocket disconnects with no error.

## The Problem

When you open `http://localhost:9222/devtools/inspector.html?ws=...`:

1. Chromium serves the HTML page with a **Content-Security-Policy** that only allows scripts from `chrome-devtools-frontend.appspot.com` (Google CDN).
2. The CDN is blocked in China, so scripts fail to load → DevTools doesn't work.
3. The `--custom-devtools-frontend` flag changes where the JS runtime loads resources from, but **does NOT change the CSP** — so custom CDN URLs are still blocked.

## The Solution

Create a **Python reverse proxy** on a separate port (e.g., 9223) that:

1. **Intercepts `/devtools/inspector.html`**, fetches it from Chromium (port 9222), **removes the CSP meta tag**, and **rewrites relative paths** (`./entrypoints/...`) to absolute proxy URLs so all assets load through the proxy.
2. **Proxies all other paths** to `https://chrome-devtools-frontend.appspot.com` **through the mihomo proxy** (`http://127.0.0.1:7890`).

### Why `--custom-devtools-frontend` is Still Needed

Even with the CSP removed, the DevTools JavaScript runtime at runtime tries to load UI components and panel modules from `chrome-devtools-frontend.appspot.com`. The `--custom-devtools-frontend=http://127.0.0.1:9223/` flag tells Chromium to replace that CDN host with your proxy URL — so when the JS code fetches `chrome-devtools-frontend.appspot.com/serve_file/@hash/panel.js`, it instead fetches `http://127.0.0.1:9223/serve_file/@hash/panel.js`, which your proxy forwards to the real CDN through mihomo.

Without this flag, the DevTools will load the shell page but stay blank/spinning because the JS modules can't fetch their dependencies from the blocked CDN.

## Setup Steps

### 1. Proxy Script (Threaded — Required!)

The proxy **must use multi-threading** (`ThreadingMixIn + HTTPServer`). The default `socketserver.TCPServer` is single-threaded and will block when handling slow CDN file transfers, causing the DevTools page to hang.

Save to `/tmp/threaded_proxy.py`:

```python
#!/usr/bin/env python3
"""Threaded DevTools proxy:
- /devtools/* -> Chromium (9222), removes CSP + rewrites paths
- /* -> chrome-devtools-frontend.appspot.com via mihomo proxy
"""
import socketserver, http.server, urllib.request, re, sys
from http.server import HTTPServer, BaseHTTPRequestHandler

CHROME = "http://127.0.0.1:9222"
CDN = "https://chrome-devtools-frontend.appspot.com"
PROXY = "http://127.0.0.1:7890"

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            path = self.path.split('?')[0]
            
            if path.startswith('/devtools/'):
                url = CHROME + path
                with urllib.request.urlopen(url, timeout=30) as r:
                    data = r.read()
                    if 'inspector.html' in path:
                        # 1. Remove CSP blocking non-Google CDNs
                        data = re.sub(rb'<meta[^>]*Content-Security-Policy[^>]*>', b'', data)
                        # 2. Rewrite relative paths (./entrypoints/...) to absolute proxy URLs
                        data = re.sub(rb'(src|href)="(\./)', rb'\1="http://127.0.0.1:9223/devtools/', data)
                    ct = r.headers.get('Content-Type', 'application/octet-stream')
                    self.send_response(r.status)
                    self.send_header('Content-Type', ct)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(data)
                return
            
            # Everything else -> CDN via mihomo proxy
            ph = urllib.request.ProxyHandler({"https": PROXY, "http": PROXY})
            o = urllib.request.build_opener(ph)
            with o.open(CDN + path, timeout=30) as r:
                d = r.read()
                self.send_response(r.status)
                ct = r.headers.get('Content-Type', 'application/octet-stream')
                self.send_header('Content-Type', ct)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(d)
        except Exception as e:
            self.send_response(502)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))
    
    def log_message(self, *a): pass

class ThreadedServer(socketserver.ThreadingMixIn, HTTPServer):
    allow_reuse_address = True

s = ThreadedServer(("127.0.0.1", 9223), H)
sys.stderr.write("Threaded DevTools proxy on :9223\n")
s.serve_forever()
```

### 2. Start Chromium with Required Flags

```bash
# Kill any existing instance first  
kill $(ps aux | grep 'chromium.*remote-debugging' | grep -v grep | awk '{print $2}') 2>/dev/null
  
# Start with all required flags
xvfb-run chromium-browser --no-sandbox --disable-gpu \
  --remote-debugging-port=9222 \
  --remote-allow-origins=* \
  --window-size=1280,720 \
  --user-data-dir=/tmp/chrome_debug \
  --custom-devtools-frontend="http://127.0.0.1:9223/" \
  2>/tmp/chrome_debug.log
```

### 3. Start the Proxy

```bash
python3 /tmp/devtools_proxy_final.py &
```

### 4. Open a Page and Navigate It (WebSocket is More Reliable)

`curl -X PUT /json/new?url=...` often leaves the page as `about:blank` because the navigation doesn't complete. Use the WebSocket DevTools Protocol to navigate:

```python
import json, websocket, urllib.request

# Create a new tab
page = json.loads(urllib.request.urlopen(
    urllib.request.Request("http://127.0.0.1:9222/json/new", method='PUT')).read())
page_id = page['id']

# Navigate via WebSocket (more reliable than curl PUT)
ws = websocket.create_connection(
    f"ws://127.0.0.1:9222/devtools/page/{page_id}", timeout=10,
    header={"Origin": "http://localhost:9222"})
ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
ws.recv()  # ack
ws.send(json.dumps({"id": 2, "method": "Page.navigate",
    "params": {"url": "https://example.com"}}))
ws.recv()  # frameStartedNavigating
import time; time.sleep(5)  # wait for load
ws.close()
```

### 5. Provide SSH Tunnel + DevTools URL to User

```bash
echo "SSH: ssh -L 9222:127.0.0.1:9222 -L 9223:127.0.0.1:9223 user@server"
echo "URL: http://localhost:9223/devtools/inspector.html?ws=localhost:9222/devtools/page/$PAGE_ID"
```

## Pitfalls

- **Chinese fonts must be installed** if the remote page displays Chinese text. Without CJK fonts (`wqy-microhei`, `NotoSansSC`, `SourceHanSansSC`), Chinese characters render as boxes (□□□). Install via:

  ```bash
  # Download and install CJK fonts
  export https_proxy=http://127.0.0.1:7890  # if behind proxy
  mkdir -p /usr/share/fonts/chinese/

  # Option A: Adobe Source Han Sans SC
  curl -sL --max-time 60 "https://github.com/adobe-fonts/source-han-sans/raw/release/OTF/SimplifiedChinese/SourceHanSansSC-Regular.otf" \
    -o /usr/share/fonts/chinese/SourceHanSansSC.otf

  # Option B: WenQuanYi Micro Hei
  curl -sL --max-time 30 "https://github.com/anthonyfok/fonts-wqy-microhei/raw/master/wqy-microhei.ttc" \
    -o /usr/share/fonts/chinese/wqy-microhei.ttc

  # Update font cache
  fc-cache -fv
  
  # Verify
  fc-list :lang=zh | head -3
  # Should show: Source Han Sans SC, WenQuanYi Micro Hei, etc.
  ```

  Then restart Chromium for the fonts to take effect. Do this step before the user connects.

- **Proxy must be multi-threaded.** The default `socketserver.TCPServer` is single-threaded; one slow CDN file request will block all other requests (JS, CSS, HTML), causing the DevTools page to hang. Use `ThreadingMixIn + HTTPServer` instead.
- **Strip query parameters when proxying.** When the proxy receives a request like `/devtools/entrypoints/inspector/inspector.js?t=123`, use `path.split('?')[0]` to strip the query string before constructing the upstream URL. Otherwise the query params may confuse Chromium's HTTP server.
- **Path rewriting is needed.** The inspector.html uses relative paths like `./entrypoints/inspector/inspector.js`. These must be rewritten to absolute proxy URLs (`http://127.0.0.1:9223/devtools/...`) so all assets go through the proxy. Without this, the browser tries to load them relative to the proxy's origin and breaks.
- **CSP is the root cause.** The `--custom-devtools-frontend` flag alone does NOT fix the problem — the inspector.html has a hardcoded CSP that blocks any CDN except the official Google one. You MUST remove the CSP from the HTML.
- **Two SSH tunnels needed.** Port 9222 (Chromium debugger) and 9223 (proxy/CDN) both need to be forwarded.
- **`--remote-allow-origins=*` is required.** Without this flag, Chromium rejects WebSocket connections from non-localhost origins with a 403 error.
- **Mihomo/other proxy must be running** on `http://127.0.0.1:7890` for the CDN proxy to work. Adjust `PROXY` variable if using a different proxy.
- **Xvfb must be installed** for headless Chromium: `yum install xorg-x11-server-Xvfb` or `apt install xvfb`.
- **Process persistence:** Background processes started via Hermes `terminal(background=true)` may be killed when the CLI session ends. For long-running sessions, start them in a `tmux`/`screen` session or use systemd. Alternatively, save the setup as a skill so it can be recreated quickly on next use.
- **Reusing old Chrome profile:** To preserve login sessions across Chromium restarts, reuse the same `--user-data-dir` (e.g., `/tmp/chrome_v5`). Note that server reboots will invalidate most login cookies (session cookies are not persisted).
- If the user gets "WebSocket disconnected", it's usually because: (a) SSH tunnel dropped, (b) DevTools frontend failed to load (CSP/CDN issue), or (c) the tab was closed.
- On CentOS/RedHat, use `chromium-browser`. On Ubuntu, use `chromium-browser` or `chromium`.

### 6. (Optional) Persist as systemd Services

To keep proxy + Chromium running **across Hermes CLI exits and server reboots**, create two systemd service files:

**Proxy service** (`/etc/systemd/system/devtools-proxy.service`):
```ini
[Unit]
Description=Chrome DevTools CDN Proxy (bypass GFW)
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /tmp/threaded_proxy.py
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
```

**Chrome service** (`/etc/systemd/system/devtools-chrome.service`):
```ini
[Unit]
Description=Chrome Remote Debugging (DevTools)
After=network.target devtools-proxy.service
Requires=devtools-proxy.service

[Service]
Type=simple
ExecStart=/usr/bin/xvfb-run chromium-browser --no-sandbox --disable-gpu --remote-debugging-port=9222 --remote-allow-origins=* --window-size=1280,720 --user-data-dir=/tmp/chrome_debug --custom-devtools-frontend="http://127.0.0.1:9223/"
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
systemctl daemon-reload
systemctl enable --now devtools-proxy devtools-chrome
```

After a server reboot, the services auto-start. The user just needs to re-establish the SSH tunnel and open the DevTools URL.

## Verification

1. After starting Chromium: `ss -tlnp | grep 9222` should show LISTEN.
2. After starting proxy: `ss -tlnp | grep 9223` should show LISTEN.
3. Test CSP removal: `curl -s "http://127.0.0.1:9223/devtools/inspector.html" | grep -i "content-security-policy" || echo "CSP removed OK"`
4. Test path rewriting: `curl -s "http://127.0.0.1:9223/devtools/inspector.html" | grep -o 'src="http://[^"]*"' | head -1` should show the proxy URL (e.g., `http://127.0.0.1:9223/devtools/...`), not relative paths.
5. Test JS proxying: `curl -s --max-time 5 "http://127.0.0.1:9223/devtools/entrypoints/inspector/inspector.js" | head -3` should return valid JavaScript.
