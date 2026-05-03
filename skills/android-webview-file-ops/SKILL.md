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
