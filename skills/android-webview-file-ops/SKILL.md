---
name: android-webview-file-ops
description: "Configure Android WebView for file upload (onShowFileChooser) and download (setDownloadListener) — enabling native file picker and system download manager in WebView-based apps."
version: 1.0.0
author: Hermes Agent
---

# Android WebView File Upload & Download Setup

Configure Android WebView to handle file upload (via `<input type="file">`) and file download (via `<a download>` or Content-Disposition headers) using native Android APIs.

## When to Use

- User builds an Android APK wrapping a web app (Flask/React/Vue) and can't upload files
- User says "上传按钮点了没反应" (upload button click does nothing) in a WebView app
- User says "点下载没反应" or "下载不了" in a WebView app
- Building a WebView-based file browser, chat app with file attachment, or any app that needs file IO
- Trigger: anytime a WebView-based APK needs user file upload/download

## Prerequisites

- Android SDK with `WebView` (all standard Android projects)
- Gradle build setup
- The web app already has `<input type="file">` for upload and `<a>` or fetch-based download

## Setup

### 1. File Upload — `onShowFileChooser`

Add a `WebChromeClient` override that handles `onShowFileChooser`:

**Java:**
```java
import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebView;

// In your Activity class:
private ValueCallback<Uri[]> uploadCallback;
private static final int FILE_CHOOSER_REQUEST = 1001;

webView.setWebChromeClient(new WebChromeClient() {
    @Override
    public boolean onShowFileChooser(
        WebView view,
        ValueCallback<Uri[]> filePathCallback,
        FileChooserParams fileChooserParams
    ) {
        // Cancel any previous callback
        if (uploadCallback != null) {
            uploadCallback.onReceiveValue(null);
        }
        uploadCallback = filePathCallback;

        Intent intent = fileChooserParams.createIntent();
        try {
            startActivityForResult(intent, FILE_CHOOSER_REQUEST);
        } catch (Exception e) {
            uploadCallback.onReceiveValue(null);
            uploadCallback = null;
            return false;
        }
        return true;
    }
});
```

Also override `onActivityResult` to receive the file:

```java
@Override
protected void onActivityResult(int requestCode, int resultCode, Intent data) {
    if (requestCode == FILE_CHOOSER_REQUEST) {
        if (uploadCallback != null) {
            Uri[] results = null;
            if (resultCode == Activity.RESULT_OK && data != null) {
                results = WebChromeClient.FileChooserParams.parseResult(resultCode, data);
            }
            uploadCallback.onReceiveValue(results);
            uploadCallback = null;
        }
        return;
    }
    super.onActivityResult(requestCode, resultCode, data);
}
```

### 2. File Download — `setDownloadListener`

Add a `DownloadListener` that routes download requests to the system `DownloadManager`:

```java
import android.app.DownloadManager;
import android.content.Context;
import android.net.Uri;
import android.os.Environment;
import android.webkit.DownloadListener;
import android.webkit.URLUtil;

webView.setDownloadListener(new DownloadListener() {
    @Override
    public void onDownloadStart(String url, String userAgent,
        String contentDisposition, String mimetype, long contentLength) {
        DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
        request.setMimeType(mimetype);
        String filename = URLUtil.guessFileName(url, contentDisposition, mimetype);
        request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, filename);
        request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
        DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
        if (dm != null) dm.enqueue(request);
    }
});
```

### 3. Complete Activity Template

See the embedded reference for a complete `MainActivity.java` with both features integrated.

### 4. Important Notes

- **`setAllowFileAccess(true)`** is required in `WebSettings` for local file access
- **`JavaScriptEnabled(true)`** is required for `<input type="file">` to work
- The `DownloadManager` handles downloads completely in the system UI — user sees a notification
- For download via `<a download="filename">` (same-origin), the `DownloadListener` triggers automatically
- For cross-origin downloads, make sure your server sends correct `Content-Disposition` headers
- **Test on real device**: The Android emulator may not have a real file system to test uploads

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Upload button click does nothing | `WebChromeClient` missing `onShowFileChooser` override — add it |
| File picker opens but upload fails | Check `onActivityResult` is correctly implemented |
| Download button click does nothing | Add `setDownloadListener` — without it, downloads are silently dropped |
| "Cannot download" toast | Set `CacheMode` to `LOAD_DEFAULT` (not `LOAD_CACHE_ONLY`) |
| Large files timeout | Make backend upload/download async (return immediately, process in background, notify via SSE/WebSocket when done) |

## Critical: File Input via JavaScript `.click()` Does NOT Work

**This is one of the most common Android WebView bugs.** You cannot trigger the native file picker by calling `.click()` on a hidden `<input type="file">` via JavaScript. Android's `WebChromeClient.onShowFileChooser` is only invoked on **direct user gesture** on the `<input>` element — programmatic clicks are silently ignored.

### ❌ What does NOT work

```html
<!-- Hidden via display:none or opacity:0 -->
<input type="file" id="file-input" style="display:none">
<button onclick="document.getElementById('file-input').click()">Upload</button>
<!-- ^^^ This will NOT open the file picker in Android WebView -->
```

```javascript
// Dynamically creating and clicking also fails
const input = document.createElement('input');
input.type = 'file';
input.click(); // ← Android WebView ignores this
```

### ✅ What works: Transparent overlay input

Place the `<input type="file">` **visually on top of the button area** with `opacity:0`. The user taps the button area but actually taps the file input directly:

```html
<div style="position:relative; width:36px; height:36px;">
  <!-- Transparent file input on top (catches taps) -->
  <input type="file" accept="image/*"
    style="position:absolute; top:0; left:0; width:100%; height:100%;
           opacity:0; z-index:2; cursor:pointer; font-size:0">
  <!-- Visual icon underneath (user sees this) -->
  <span style="position:absolute; top:0; left:0; width:100%; height:100%;
               display:flex; align-items:center; justify-content:center;
               font-size:20px; z-index:1; color:#8e8e93; pointer-events:none">
    🖼
  </span>
</div>
```

Key points:
- `opacity:0` makes the input invisible but still interactive
- `position:absolute` places it exactly over the visual button
- `z-index:2` ensures the input is on top of the icon (which gets `z-index:1` and `pointer-events:none`)
- `font-size:0` prevents the default file input label text from showing
- The user taps the icon area → Android recognizes it as a **direct gesture** on the `<input>` → `onShowFileChooser` fires → native file picker opens

### Alternative: Use a `<label>` element

```html
<label style="cursor:pointer">
  <input type="file" accept="image/*" style="display:none" onchange="handleFile(this)">
  <span>📷 Upload</span>
</label>
```

`<label>` tapping triggers the associated input natively in most browsers, but **does NOT work in Android WebView** — it has the same limitation as `.click()`. Stick with the transparent overlay approach.

### Why this happens

Android WebView's `onShowFileChooser` is a security-sensitive callback that requires **user initiation** — the user must physically tap on the `<input type="file">` element. This prevents silent file access via JavaScript. Unlike desktop browsers where `.click()` on hidden inputs works, Android's security model is stricter. The transparent overlay is the only reliable workaround. |
