---
name: mobile-webview-sse-reconnect
description: Handle SSE (Server-Sent Events) disconnection and message recovery when a mobile WebView app is backgrounded and resumed — preventing lost AI replies and stale connections.
version: 1.0.0
author: Hermes Agent
---

# Mobile WebView SSE Reconnect on Resume

When a mobile WebView app (Android/iOS) uses SSE for real-time AI chat replies, backgrounding the app kills the WebView's JavaScript execution and drops the SSE connection. When the user returns, the connection is dead and any AI replies sent while the app was in the background are lost.

This skill describes how to detect the resume event, re-establish the SSE connection, and catch any missed messages via polling.

## When to Use

- You have a mobile WebView-based chat app that uses SSE (Server-Sent Events) for real-time AI replies
- User reports "I sent a message, switched apps, came back, and the reply never appeared"
- The chat uses `EventSource` for streaming AI responses
- You need to handle Android `onPause`/`onResume` and iOS background lifecycle in WebView

**Not for**: Native apps with proper background services (use foreground service + push notifications instead), or apps that use WebSocket (different reconnection pattern).

## The Problem

In a mobile WebView:

1. User sends a chat message
2. AI starts generating — SSE pushes chunks/replies
3. User presses Home / switches apps → Android calls `onPause()` → WebView JS is **suspended**
4. SSE `<EventSource>` is **silently closed** (no `onerror` fires, no cleanup)
5. AI finishes replying and SSE pushes the final message — **it's lost**
6. User returns to app → WebView JS resumes → SSE is gone
7. User sees the last loading/sent message but no AI reply

## Detection: `visibilitychange` API

The browser fires a `visibilitychange` event when the user switches tabs or apps:

```javascript
document.addEventListener('visibilitychange', function() {
  if (!document.hidden && userId) {
    // User returned — reconnect SSE and fetch missed messages
    connectSSE();
    fetchMissedMessages();
  }
});
```

**Why not `pageshow`/`focus`?** The `visibilitychange` event fires reliably on both Android and iOS WebView when the app is backgrounded and resumed. `pageshow` only fires on initial page load (not resume). `focus` fires but doesn't indicate visibility state.

## Reconnect: SSE Re-establishment

Typically you already have an SSE reconnect function with exponential backoff:

```javascript
let eventSource = null;
let sseReconnectTimer = null;

function connectSSE() {
  if (eventSource) eventSource.close();
  
  eventSource = new EventSource(`/api/chat/events?user_id=${encodeURIComponent(userId)}`);
  
  eventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      handleSSEMessage(data);
    } catch(_) {}
  };
  
  eventSource.onerror = () => {
    // Reconnect on error (after 5s)
    if (sseReconnectTimer) clearTimeout(sseReconnectTimer);
    sseReconnectTimer = setTimeout(() => connectSSE(), 5000);
  };
}
```

Calling `connectSSE()` on `visibilitychange` ensures a fresh connection is established immediately on resume, without waiting for the error-triggered reconnect timeout.

## Recovery: Fetch Missed Messages

Reconnecting SSE only handles **future** messages. To catch replies that were sent while the app was in the background, poll the chat history API and append any new messages:

```javascript
async function fetchMissedMessages() {
  if (!userId) return;
  try {
    const resp = await fetch(`/api/chat/history?user_id=${encodeURIComponent(userId)}&model_idx=${aiActiveIdx}`);
    const data = await resp.json();
    if (!data.ok || !data.history) return;
    
    const el = document.getElementById('chat-messages');
    const existingCount = el.querySelectorAll('.msg').length;
    
    if (data.history.length > existingCount) {
      const newMsgs = data.history.slice(existingCount);
      // Remove placeholder if present
      const ph = el.querySelector('div[style*="text-align:center"]');
      if (ph) ph.remove();
      
      newMsgs.forEach(msg => {
        const div = document.createElement('div');
        div.className = `msg ${msg.isSelf ? 'self' : 'other'}`;
        div.innerHTML = `${msg.text}<div class="time">${msg.time || ''}</div>`;
        el.appendChild(div);
      });
      el.scrollTop = el.scrollHeight;
    }
  } catch(_) {}
}
```

**How it works**: The server persists every message to a history file (e.g., JSONL). Each message has an index. The frontend compares `data.history.length` (server) against `el.querySelectorAll('.msg').length` (client). Any new messages are appended.

### Prerequisites

For this to work, the server must:

1. **Persist messages to a server-side history** — messages survive server restarts and WebView kills
2. **Expose a GET endpoint** that returns all messages for a user+model combination
3. **Include ALL messages** — both user and AI — in the history response

```python
# Server endpoint example
@app.route('/api/chat/history', methods=['GET'])
def chat_history():
    user_id = request.args.get('user_id', '')
    model_idx = int(request.args.get('model_idx', 0))
    history = load_history(user_id, model_idx)
    return jsonify({'ok': True, 'history': history})
```

## Complete Integration

Add this block after your existing keyboard/modal event listeners:

```javascript
// ═══ BACKGROUND/RESUME: re-connect SSE and catch missed replies ═══
document.addEventListener('visibilitychange', function() {
  if (!document.hidden && userId) {
    connectSSE();
    fetchMissedMessages();
  }
});
```

## Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| `visibilitychange` fires on every tab switch (desktop) | The same event fires for desktop tab switching | Expected behavior — it's harmless to reconnect SSE on desktop. Events are deduplicated server-side or filtered by `model_idx` |
| Duplicate messages on resume | SSE sends the last message again while `fetchMissedMessages` also catches it | Both paths deliver the same message. The `receiveMessage` handler should filter by `model_idx` and check for duplicates if needed. Accept occasional duplicates — the user won't see them if the message content is identical |
| `fetchMissedMessages` fires before SSE reconnects | Race condition: SSE pushes an old message between `fetchMissedMessages` and `connectSSE` | Acceptable: the old message has the same `text` and `time` as an already-rendered message. The user sees no visible change |
| History API is slow (with many messages) | Fetching 1000+ messages on every resume | Limit history endpoint to return only last N messages (e.g., last 50). Or track the last-known message ID client-side and only request newer ones |
| SSE reconnects but `document.hidden` is `true` | Race condition: visibility changes while JS is executing | Guard with `if (!document.hidden)` — simple boolean check |
| App is killed by Android (process killed) | `visibilitychange` never fires — the process is killed without warning | This is unavoidable. On fresh load, `connectSSE()` is called in `initChat()`, and the initial login response already includes the full chat history. No special handling needed |
| `fetchMissedMessages` shows private/other-model history | URL uses wrong `model_idx` | Always pass the correct `${aiActiveIdx}` in the history API call |
