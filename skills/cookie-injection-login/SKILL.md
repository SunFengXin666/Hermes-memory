---
name: cookie-injection-login
title: Cookie Injection Login via CDP Network.setCookie
description: Bypass CAPTCHA and SMS/password login on Chinese websites by injecting authenticated session cookies directly into the Hermes browser via Chrome DevTools Protocol.
tags:
  - browser
  - cookie
  - login
  - cdp
  - bypass
  - fanqienovel
---

# Cookie Injection Login via CDP Network.setCookie

When SMS, password, and QR login are all blocked (e.g., Volcano Engine slider), the most reliable bypass is to inject the user's authenticated session cookies directly into the Hermes browser via CDP.

## Why `document.cookie` Won't Work

Session cookies (e.g., `sessionid`, `sid_tt`) are typically **HttpOnly** — JavaScript's `document.cookie` CANNOT set them. You MUST use CDP's `Network.setCookie` which operates at the browser protocol level, bypassing JS restrictions.

## Workflow

```
User exports cookies from their real browser (Application tab)
        │
        ▼
You ask for specific cookie names + values
        │
        ▼
Find Hermes headless browser CDP port (NOT 9222)
        │
        ▼
Navigate to target domain FIRST
        │
        ▼
Inject cookies via CDP Network.setCookie (Python + websockets)
        │
        ▼
Verify login by navigating to dashboard
```

## Step 1: Ask User for Cookies

Explain that session cookies are HttpOnly. User must:
1. F12 → **Application** tab → **Cookies** → select the target domain
2. Click each cookie to see the full Value
3. Send you Name=Value pairs

**ByteDance/fanqienovel key cookies** (sessionid/sid_guard/sid_tt/uid_tt typically share same value):
- `sessionid` / `sessionid_ss` — main session (HttpOnly)
- `sid_guard` / `sid_tt` — session guard (HttpOnly)
- `uid_tt` / `uid_tt_ss` — user ID (HttpOnly)

## Step 2: Find Headless Browser CDP Port

Hermes runs TWO Chromium instances:
- **Port 9222** — visible xvfb browser (persistent, for manual use)
- **Random port** — headless browser (Hermes' actual automation target)

```bash
# Find the headless browser's port (NOT 9222)
ss -tlnp | grep chrom

# Get the page WebSocket URL
curl -s http://127.0.0.1:<PORT>/json | python3 -c "
import sys, json
for p in json.load(sys.stdin):
    print(p['webSocketDebuggerUrl'])
"
```

**Important:** The headless browser can RESTART between navigations (page crash → new CDP port). Always re-check the port before injection.

## Step 3: Navigate to Domain First

Cookies can only be set for the domain the page is currently on.

```
browser_navigate(url="https://targetdomain.com/login")
```

## Step 4: Inject Cookies via CDP

Use `execute_code` (Python with websockets library):

```python
import asyncio, json, websockets

async def set_cookies():
    ws_url = "ws://127.0.0.1:<PORT>/devtools/page/<PAGE_ID>"

    cookies = {
        "sessionid": "value_from_user",
        "sessionid_ss": "value_from_user",
        "sid_guard": "value_from_user",
        "sid_tt": "value_from_user",
    }

    msg_id = 1
    async with websockets.connect(ws_url) as ws:
        for name, value in cookies.items():
            params = {
                "name": name,
                "value": value,
                "domain": "targetdomain.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
            }
            cmd = {"id": msg_id, "method": "Network.setCookie", "params": params}
            await ws.send(json.dumps(cmd))
            resp = await ws.recv()
            result = json.loads(resp)
            print(f"{name}: {result.get('result', {}).get('success', False)}")
            msg_id += 1

asyncio.run(set_cookies())
```

## Step 5: Verify Login

```bash
browser_navigate(url="https://targetdomain.com/dashboard")
# Check snapshot for authenticated elements (username, avatar, logout button)
```

## Shortcut: Use Persistent Browser (Port 9222)

To avoid headless browser restart issues, configure Hermes to use the persistent visible browser:

```bash
hermes config set browser.cdp_url http://127.0.0.1:9222
```

After this, the CDP connection stays stable across navigations. The visible Chromium must be running (check `ss -tlnp | grep 9222`).

Reset with `hermes config set browser.cdp_url ''` if needed.

## Fanqienovel (番茄小说网) Specifics

**Key cookies** (all share the same value):
```
sessionid=83658aa347c0559752de36a8f5a0cb62
sessionid_ss=83658aa347c0559752de36a8f5a0cb62
sid_guard=83658aa347c0559752de36a8f5a0cb62
sid_tt=83658aa347c0559752de36a8f5a0cb62
uid_tt=00da09923efe2f27798708fcb5b67c4e
```

**Domain:** `fanqienovel.com`

**Login URL:** `https://fanqienovel.com/main/writer/login`

**Dashboard URL:** `https://fanqienovel.com/main/writer/`

## Pitfalls

1. **Headless browser restarts** — CDP port changes after page crashes. Always re-check.
2. **Cookies expire** — session cookies last days/weeks. If injection stops working, ask for fresh exports.
3. **Navigate to domain FIRST** — `Network.setCookie` only works for the current page's domain.
4. **Set httpOnly=True, secure=True** — for HttpOnly session cookies, both flags must match the original cookie attributes.
5. **Save to memory** — after successful injection, save cookie values to memory so you can re-inject without re-asking the user.
