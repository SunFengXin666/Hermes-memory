---
name: android-webview-apk
description: "Build an Android APK that wraps a web app (Flask/React/any web UI) in a WebView, compiled on a headless Linux server without Android Studio. Covers setting up JDK + Android SDK + Gradle behind GFW/proxy, project structure, and common build pitfalls."
version: 1.0.0
author: Hermes Agent
tags: [android, apk, webview, gradle, sdk, mobile, china-server, proxy]
---

# Android WebView APK Builder

Build a native Android APK that opens a web app (Flask/any HTTP backend) inside a WebView. Designed for servers in mainland China where Docker pull and apt/dnf are unreliable — uses direct downloads via proxy.

## When to Use

- User wants a native Android APK from a web app (no PWA or browser URL)
- You're on a headless Linux server (no Android Studio, no GUI)
- Server is behind GFW / has restricted Docker/package-manager access
- The target app is a Flask/FastAPI/any HTTP web app that should appear as a standalone Android app

## Overview

```
┌────────────────────────────┐
│  Android APK (WebView)     │
│  ┌──────────────────────┐  │
│  │  WebView loads URL   │  │
│  │  http://server:port  │  │
│  │                      │  │
│  │  Your Flask/Web App  │  │
│  └──────────────────────┘  │
└────────────────────────────┘
```

## Setup & Build Steps

### 1. Install JDK (Adoptium Temurin)

```bash
export https_proxy=http://127.0.0.1:7890
curl -sL -o /tmp/jdk.tar.gz \
  'https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.9%2B9/OpenJDK17U-jdk_x64_linux_hotspot_17.0.9_9.tar.gz'
mkdir -p /opt/java
tar xzf /tmp/jdk.tar.gz -C /opt/java
export JAVA_HOME=/opt/java/jdk-17.0.9+9
export PATH=$JAVA_HOME/bin:$PATH
java -version
```

### 2. Install Android SDK Command-Line Tools

```bash
export https_proxy=http://127.0.0.1:7890
curl -sL -o /tmp/cmdline-tools.zip \
  'https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip'
mkdir -p /opt/android-sdk/cmdline-tools
unzip -q /tmp/cmdline-tools.zip -d /tmp/cmdline-tools-tmp
mkdir -p /opt/android-sdk/cmdline-tools/latest
mv /tmp/cmdline-tools-tmp/cmdline-tools/* /opt/android-sdk/cmdline-tools/latest/
rm -rf /tmp/cmdline-tools-tmp /tmp/cmdline-tools.zip

export ANDROID_HOME=/opt/android-sdk
export PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$PATH

# Accept licenses and install platform + build tools
yes | sdkmanager --sdk_root=$ANDROID_HOME \
  "platforms;android-34" \
  "build-tools;34.0.0"
```

### 3. Install Gradle

```bash
export https_proxy=http://127.0.0.1:7890
curl -sL -o /tmp/gradle.zip \
  'https://services.gradle.org/distributions/gradle-8.5-bin.zip'
mkdir -p /opt/gradle
unzip -q /tmp/gradle.zip -d /opt/gradle
export GRADLE_HOME=/opt/gradle/gradle-8.5
export PATH=$GRADLE_HOME/bin:$PATH
```

### 4. Create Android Project Structure

```
my-android-app/
├── build.gradle              # Root Gradle (Groovy DSL)
├── settings.gradle.kts       # Settings
├── gradle.properties         # android.useAndroidX=true
├── local.properties          # sdk.dir=/opt/android-sdk
├── app/
│   ├── build.gradle          # App module
│   ├── proguard-rules.pro
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/com/myapp/MainActivity.java
│       └── res/
│           ├── layout/activity_main.xml
│           ├── values/{strings,themes}.xml
│           ├── xml/network_security_config.xml
│           └── mipmap-*/ic_launcher.png
```

### 5. Key Files Content

**build.gradle** (root — Groovy DSL):
```groovy
buildscript {
    repositories {
        google()
        mavenCentral()
    }
    dependencies {
        classpath 'com.android.tools.build:gradle:8.2.0'
    }
}
```

**settings.gradle.kts**:
```kotlin
pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = "MyApp"
include(":app")
```

**gradle.properties**:
```
android.useAndroidX=true
org.gradle.jvmargs=-Xmx512m
```

**local.properties**:
```
sdk.dir=/opt/android-sdk
```

**app/build.gradle**:
```groovy
apply plugin: 'com.android.application'
android {
    namespace 'com.myapp.app'
    compileSdk 34
    defaultConfig {
        applicationId 'com.myapp.app'
        minSdk 24
        targetSdk 34
        versionCode 1
        versionName '1.0.0'
    }
    buildTypes {
        release { minifyEnabled false }
    }
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
}
dependencies {
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation 'androidx.swiperefreshlayout:swiperefreshlayout:1.1.0'
}
```

**AndroidManifest.xml**:
```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <application
        android:usesCleartextTraffic="true"
        android:networkSecurityConfig="@xml/network_security_config"
        android:theme="@style/Theme.MyApp"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name">

        <activity android:name=".MainActivity" android:exported="true"
            android:configChanges="orientation|screenSize|keyboardHidden"
            android:windowSoftInputMode="adjustResize">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

**MainActivity.java** (WebView wrapper):
```java
package com.myapp.app;

import android.os.Bundle;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.appcompat.app.AppCompatActivity;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

public class MainActivity extends AppCompatActivity {
    private WebView webView;
    private SwipeRefreshLayout swipeRefresh;
    private String serverUrl;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        serverUrl = getIntent().getStringExtra("server_url");
        if (serverUrl == null || serverUrl.isEmpty()) {
            serverUrl = "http://YOUR_SERVER_IP:PORT";  // ← CHANGE THIS
        }

        swipeRefresh = findViewById(R.id.swipe_refresh);
        webView = findViewById(R.id.webview);

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        // IMPORTANT: If your web app uses responsive/mobile-first CSS (media queries),
        // set setUseWideViewPort(false) so the WebView reports actual device width.
        // setUseWideViewPort(true) makes the WebView report ~980px, breaking mobile CSS.
        // For desktop-targeted web apps, setUseWideViewPort(true) may be fine.
        s.setUseWideViewPort(false);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);
        s.setUserAgentString(s.getUserAgentString() + " MyApp-Android/1.0");

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                swipeRefresh.setRefreshing(false);
            }
        });
        webView.setWebChromeClient(new WebChromeClient());
        swipeRefresh.setOnRefreshListener(() -> webView.reload());
        webView.loadUrl(serverUrl);
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) { webView.goBack(); }
        else { super.onBackPressed(); }
    }
}
```

**activity_main.xml** (layout):
```xml
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical">
    <androidx.swiperefreshlayout.widget.SwipeRefreshLayout
        android:id="@+id/swipe_refresh"
        android:layout_width="match_parent"
        android:layout_height="match_parent">
        <WebView android:id="@+id/webview"
            android:layout_width="match_parent"
            android:layout_height="match_parent" />
    </androidx.swiperefreshlayout.widget.SwipeRefreshLayout>
</LinearLayout>
```

**res/xml/network_security_config.xml**:
```xml
<network-security-config>
    <base-config cleartextTrafficPermitted="true">
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>
</network-security-config>
```

**res/values/themes.xml**:
```xml
<resources>
    <style name="Theme.MyApp" parent="Theme.AppCompat.Light.NoActionBar">
        <item name="colorPrimary">#5865F2</item>
        <item name="android:windowBackground">#2B2D31</item>
    </style>
</resources>
```

**res/values/strings.xml**:
```xml
<resources>
    <string name="app_name">My App</string>
</resources>
```

**app/proguard-rules.pro**:
```
-keepattributes *Annotation*
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
```

### 6. Generate Launcher Icons

Use Python Pillow to create PNG icons at Android density sizes:

```python
from PIL import Image
src = Image.open('source-512.png')
sizes = {'mipmap-hdpi':48, 'mipmap-mdpi':48, 'mipmap-xhdpi':96,
         'mipmap-xxhdpi':144, 'mipmap-xxxhdpi':192}
for d, s in sizes.items():
    img = src.resize((s, s), Image.LANCZOS)
    img.save(f'app/src/main/res/{d}/ic_launcher.png')
```

### 7. Build the APK

```bash
export JAVA_HOME=/opt/java/jdk-17.0.9+9
export ANDROID_HOME=/opt/android-sdk
export GRADLE_HOME=/opt/gradle/gradle-8.5
export PATH=$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH

cd /root/my-android-app
$GRADLE_HOME/bin/gradle assembleDebug --no-daemon
# APK at: app/build/outputs/apk/debug/app-debug.apk
```

### 8. Send APK to User (via NapCat QQ Bot)

**Option A: shared volume (preferred)** — Copy APK to NapCat's config volume, which is accessible inside the container:

```bash
# Check mounted volumes first:
docker inspect napcat --format '{{json .Mounts}}' | python3 -c \
  "import sys,json;[print(m['Source'],'->',m['Destination']) for m in json.load(sys.stdin)]"

# Common mount: /root/napcat_config -> /app/napcat/config (varies per setup)
cp /path/to/app-debug.apk /root/napcat_config/myapp-v1.1.apk
```

**Option B: docker cp** — Copy directly into the container:

```bash
docker cp /path/to/app-debug.apk napcatf:/root/myapp.apk
```

Then send via NapCat WebSocket API (port 3001 typically has no token; port 6099 may require a token from `passkey.json`):

```javascript
// save as /opt/napcat/send_apk.js, then: node /opt/napcat/send_apk.js
import { WebSocket } from 'ws';

const ws = new WebSocket('ws://127.0.0.1:3001');  // or 6099?access_token=xxx

ws.on('open', () => {
  setTimeout(() => {
    ws.send(JSON.stringify({
      action: 'send_private_msg',
      params: {
        user_id: USERS_QQ_NUMBER,  // e.g. 3240171077
        message: [
          { type: 'text', data: { text: '📦 v1.1 APK ready' } },
          { type: 'file', data: { file: '/app/napcat/config/myapp-v1.1.apk' } }
          // Path inside container — use shared volume path or docker cp path
        ]
      },
      echo: 'send_apk'
    }));
  }, 500);  // Wait for lifecycle event to be consumed first
});

ws.on('message', (data) => console.log('Response:', data.toString()));
ws.on('error', (err) => console.error('Error:', err.message));
setTimeout(() => process.exit(0), 8000);
```

Check NapCat config (`/root/napcat_config/onebot11.json` or `onebot11_<botid>.json`) for the correct WebSocket port and token setting.

### localStorage Persistence Pattern for Config Data

When building a WebView APK, every page refresh acts like an "app restart" — all in-memory JS state is lost. Users expect configuration (server lists, API keys, account settings) to persist across app opens.

**Pattern: Save structured config to localStorage and auto-restore**

```javascript
// 1. State: load from localStorage on page load
let savedServers = JSON.parse(localStorage.getItem('im_servers') || '[]');

// 2. Save after successful operation
function afterConnect(serverData) {
  const entry = { name, host, port, username, password };
  // Deduplicate by host+port+username
  const idx = savedServers.findIndex(s => s.host === host && s.port === port && s.username === username);
  if (idx >= 0) savedServers[idx] = entry;
  else savedServers.push(entry);
  localStorage.setItem('im_servers', JSON.stringify(savedServers));
}

// 3. Render saved-but-not-connected items as clickable entries
function renderServerList() {
  // Show connected servers + saved servers
  savedServers.filter(s => !isCurrentlyConnected(s)).forEach(s => {
    renderDisconnectedItem(s);  // "○ 已保存 (点击重连)"
  });
}

// 4. Click-to-reconnect without re-entering credentials
async function reconnectServer(saved) {
  const resp = await fetch('/api/disks/connect', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(saved),
  });
  // ... handle response, update UI
}
```

**Key considerations for WebView:**
- `setDomStorageEnabled(true)` **must** be set in `MainActivity.java` for localStorage to work
- Don't store sensitive credentials (passwords, API keys) in plaintext localStorage for production apps. For a personal/debug app behind WebView, it's acceptable.
- Render the rendered list immediately after login so saved items appear without a reconnect attempt
- Server-side sessions (SSH/SFTP) are **not** preserved across refresh — you must re-establish them on reconnect. The localStorage only preserves the **connection config**, not the connection itself.
- **Login modal visibility**: Always start the modal hidden (`class="modal login-modal"` without `show`). The IIFE decides whether to `classList.add('show')` (new user) or init directly (returning user with saved localStorage). Never rely on `setTimeout(() => doLogin(), 100)` to auto-hide a visible modal — the 100ms gap creates a flash and any error during init leaves the modal stuck visible and unresponsive.

**The 'wrong port' pitfall for SSH/SFTP in WebView apps:**
A common user mistake when filling server config: they enter the port of a different service (e.g., Ollama port 11434, HTTP port 8080) instead of SSH port **22**. Always default the port input to `22` and consider adding a placeholder note like "SSH端口 (默认22)". If the connection times out, the first thing to check is the port number.

## Pitfalls

1. **docker pull fails on Chinese servers** — Docker Hub is frequently blocked. Don't rely on Docker-based Android build images. Download JDK/Gradle/SDK directly via proxy (mihomo/clash).
2. **android.useAndroidX=true** — Must be in `gradle.properties`. Without it, `checkDebugAarMetadata` fails with a cryptic error about AndroidX dependencies.
3. **Repositories mode conflict** — If `settings.gradle.kts` has `FAIL_ON_PROJECT_REPOS`, don't declare `allprojects { repositories {} }` in `build.gradle`. Keep repos only in settings.
4. **ProGuard rules file** — Must exist (even if empty) if `proguardFiles` is referenced in `build.gradle`.
5. **icon missing** — `@mipmap/ic_launcher` references must exist as PNGs in each `mipmap-*` folder. Missing icons cause an invisible build failure.
6. **Cleartext traffic** — Android 9+ blocks HTTP by default. Set `android:usesCleartextTraffic="true"` in manifest AND provide `network_security_config.xml`.
7. **Gradle daemon conflict** — Kill old daemons (`pkill -f GradleDaemon`) before restarting a failed build. Stale daemons hold port locks.
8. **Maven/Google proxy** — Gradle needs to reach `dl.google.com` and `repo1.maven.org`. If proxy is required, set `GRADLE_OPTS` with `-Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7890` or configure in `gradle.properties`.
9. **WebView wide viewport breaks mobile CSS** — `setUseWideViewPort(true)` (the Android default) makes the WebView report ~980px CSS width, so `@media(max-width:600px)` media queries never trigger. For mobile-responsive web apps, **BOTH** fixes are needed:
   - Android code: `webView.getSettings().setUseWideViewPort(false)` so WebView reports actual device width
   - Web CSS: Use **mobile-first** CSS — default styles target phone portrait (bottom nav, single-panel pages), and `@media(min-width:768px)` switches to desktop layout (left sidebar, multi-panel). This way, even if WebView reports an unexpected width, the phone layout shows by default.
   - Server: Add `Cache-Control: no-cache, no-store, must-revalidate` headers to the Flask/backend response to prevent the WebView from serving stale HTML/CSS on relaunch.
   - Web app: Persist user session data (e.g., username, port) in `localStorage` so page refresh doesn't force re-login. Auto-login on page load with `localStorage.getItem('im_username')`.

10. **WebView serve stale content** — If the Flask server updates HTML/CSS but the WebView still shows old content, add no-cache headers to the server response:
    ```python
    @app.route('/')
    def index():
        resp = make_response(render_template('index.html'))
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
    ```

### Silent JavaScript Failure: Entire Script Block Fails to Parse

**The most insidious WebView bug:** A syntax error ANYWHERE in a `<script>` block causes the ENTIRE block to fail silently — no functions are registered, no error is visible in the UI. The page renders normally (HTML+CSS load fine), but ALL JavaScript (navigation, login, API calls) is dead. The only clue is that every `typeof x` returns `"undefined"`.

**Common cause: prematurely closed template literal.** A backtick in the wrong place closes a multi-line template string early, making the next line's HTML tags parse as raw JavaScript:

```javascript
// ❌ BROKEN — backtick before the closing `</div>` closes the template early
return `<div class="server-item" onclick="fn('${name}')">`
        <div class="name">${item.name}</div>     // ← SyntaxError: 'class' unexpected
      </div>`;

// ✅ FIXED — no backtick until the actual end of the template
return `<div class="server-item" onclick="fn('${name}')">
        <div class="name">${item.name}</div>
      </div>`;
```

**Detection pattern (server-side, no device needed):**
1. Extract all `<script>` content from the HTML file
2. Run each through Node.js syntax check: `node --check extracted.js`
3. If any script block has a syntax error, the entire WebView JS runtime is dead — ALL your fixes (event delegation, inline onclick, CSS touch fixes) are irrelevant until this is fixed
4. Landing page in a headless browser + `typeof switchPage` → `"undefined"` confirms the problem

**Best defense: validate JS syntax as part of your build workflow:**
```bash
# Extract all JS from template and syntax-check
python3 -c "
import re
with open('templates/index.html') as f:
    html = f.read()
scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
for i, js in enumerate(scripts):
    import tempfile, subprocess
    with tempfile.NamedTemporaryFile(suffix='.js', mode='w', delete=False) as t:
        t.write(js)
    r = subprocess.run(['node', '--check', t.name], capture_output=True, text=True)
    if r.returncode != 0:
        print(f'SCRIPT BLOCK {i}: SYNTAX ERROR')
        print(r.stderr)
    else:
        print(f'SCRIPT BLOCK {i}: OK')
    import os; os.unlink(t.name)
"
```

**Practical observability tip:** Query the app from the server with a headless browser (via CDP) and check if core functions are defined:
```javascript
typeof switchPage  // "undefined" → entire script block failed
typeof userId       // "undefined" → confirms
```

No amount of inline `onclick`, event delegation, or touch-action CSS will fix a script that never parsed. **Always rule out syntax errors first when "buttons don't work" in a WebView.**

### Event Listener Registration Order in WebView SPA

In a WebView SPA (single-page app with login → main interface flow), the order of JavaScript execution matters:

**The bug:** If the auto-login IIFE (Immediately Invoked Function Expression) on page load calls functions that might throw (e.g., `renderServerList()` iterating over corrupted localStorage data, `connectWS()` failing), the thrown error halts script execution. Any event listeners registered *after* the IIFE in the source file never get bound — resulting in "buttons don't work" (navigation tabs, send button, etc. are unresponsive).

**The fix: Bind navigation even listeners FIRST, before any fallible initialization code:**

```javascript
// 1. Bind event listeners FIRST — before any code that could throw
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    // switch tabs...
  });
});

// 2. THEN run auto-init (wrapped in try-catch)
try {
  (function() {
    const saved = localStorage.getItem('im_username');
    if (saved) {
      // auto-login...
    }
  })();
} catch(e) {
  console.error('Auto-init error:', e);
  // Navigation still works despite init failure
}
```

**Loading-order pitfalls:**
- `window.onerror` handler must be defined *before* any functional code that might throw, otherwise errors are silently swallowed\n- Wrap IIFE auto-init in `try/catch` so a corrupted localStorage or broken init flow doesn't cascade into unclickable buttons\n- If the WebView shows a login modal that overlays the main UI, the modal's `show` class should be controlled by JavaScript (default hidden) rather than being present in the HTML `class` attribute — this prevents a flash of the login overlay on every page load\n- **`onclick = function()` vs `addEventListener`**: Some Android WebViews (especially on older devices or customized OEM browsers) handle `onclick = function() {}` (direct property assignment) more reliably than `addEventListener`. If navigation buttons or other click handlers fail to fire despite the DOM being ready, switch from `btn.addEventListener('click', handler)` to `btn.onclick = handler`. The trade-off: `onclick` only supports one handler per element.\n- **Cascading nav-button failure**: A common symptom in WebView SPAs is that the chat button works but cloud-disk and settings buttons don't. This usually means a JavaScript error in the auto-init IIFE (e.g., `renderServerList()` processing corrupted localStorage data) halted script execution *after* the nav-bar event listeners were registered but *before* the page-switching code ran, OR the `querySelectorAll('.nav-btn')` returned fewer elements than expected because the DOM wasn't fully loaded. The fix stack: (1) move event binding to top of `<script>`, (2) wrap IIFE in try-catch, (3) add a fallback: if auto-init fails, show a visible error toast + a "skip to main" link so the user isn't stuck at a dead modal, (4) add inline `onclick` attributes directly in the HTML, (5) use **event delegation** on a parent container instead of per-element binding, (6) add CSS `touch-action: manipulation` to eliminate the 300ms tap delay on mobile WebViews.\
\
   **Technique 4 — Inline onclick in HTML (most reliable fallback):**\
   Add `onclick` directly to the HTML element so it fires regardless of JS binding timing:\
   ```html\
   <button class="nav-btn active" data-page="chat" onclick="switchPage('chat')">💬</button>\
   <button class="nav-btn" data-page="disk" onclick="switchPage('disk')">☁️</button>\
   ```\
   Then define `switchPage(name)` as a global function in the `<script>`:\
   ```javascript\
   function switchPage(name) {\
     document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));\
     document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));\
     const btn = document.querySelector(`.nav-btn[data-page="${name}"]`);\
     if (btn) btn.classList.add('active');\
     const page = document.getElementById('page-' + name);\
     if (page) page.classList.add('active');\
   }\
   ```\
   Inline onclick is the **hardest** binding to break — it works even if `querySelectorAll` fails or DOM timings are off.\
\
   **Technique 5 — Event delegation (robust against DOM timing):**\
   Instead of binding per-element with `forEach`, bind a single listener to the parent container and use `closest()`:\
   ```javascript\
   document.querySelector('.sidebar').addEventListener('click', function(e) {\
     const btn = e.target.closest('.nav-btn');\
     if (!btn) return;\
     switchPage(btn.dataset.page);\
   });\
   ```\
   This handles dynamically added buttons and avoids the "elements not yet in DOM" timing pitfall entirely. Use this as a **supplement** to inline onclick, not a replacement — event delegation won't help if the parent container itself doesn't exist yet when the script runs.\
   \
   **Technique 6 — CSS touch fixes for mobile WebView:**\
   Some Android WebViews (especially on custom OEM browsers or lower-end devices) have a **300ms tap delay** or poor touch-event-to-click conversion. Add these CSS properties to clickable elements:\
   ```css\
   .nav-btn, button, a, .clickable {\
     touch-action: manipulation;          /* eliminates 300ms tap delay */\
     -webkit-tap-highlight-color: transparent;  /* removes gray tap flash */\
   }\
   ```\
   `touch-action: manipulation` tells the browser the element only supports single-finger tap gestures, so the browser can skip the double-tap-to-zoom delay. This is especially important for bottom-navigation buttons where delayed or dropped clicks feel like "buttons don't work."\n- **Server restart reminder**: After killing the Flask/Python server process (`fuser -k PORT/tcp`), always verify the new process started: `curl -s -o /dev/null -w '%{http_code}' http://localhost:PORT/`. If you forget to restart, the WebView will show `net::ERR_CONNECTION_REFUSED` and the user sees a blank error page.

### Version Management for Iterative Delivery

When shipping APKs iteratively (user tests → feedback → modify → rebuild → resend):

1. **Bump versionCode and versionName** in `app/build.gradle` on every rebuild:
   ```groovy
   defaultConfig {
       versionCode 2    // increment by 1 each time
       versionName '1.1.0'  // semantic version
   }
   ```
2. **Name the APK file** with the version to avoid stale file issues: `cp app-debug.apk /shared/myapp-v1.1.apk`
3. **Changelog in the send message**: Always include a bullet list of what changed so the user knows what to test.
4. **Server must be restarted** after frontend changes (HTML/CSS/JS). Kill the old process with `fuser -k PORT/tcp` and start fresh in background.

### Adding a Directory Sandbox/Lock to an SFTP File Browser

If your APK wraps a Flask/SFTP file browser app and the user wants to lock navigation to a specific directory (users enter at a base path and cannot navigate above it):

**Frontend (JavaScript) changes:**
```javascript
// 1. State: track basePath
let basePath = '/home/ubuntu/yunpan';
let currentDiskPath = basePath;

// 2. After connecting, create + navigate into base path
basePath = '/home/ubuntu/yunpan';
try { await fetch(`/api/disks/${connId}/mkdir`, {
  method:'POST',
  headers:{'Content-Type':'application/json'},
  body: JSON.stringify({path: basePath})
}); } catch(_) {}  // mkdir fails if exists, which is fine
currentDiskPath = basePath;
document.getElementById('current-path').textContent = basePath + ' 🔒';

// 3. Lock navigation to prevent leaving basePath
function navigateToDir(path) {
  if (basePath !== '/' && path !== basePath && !path.startsWith(basePath + '/')) {
    toast('🔒 不能超出根路径');
    loadDiskDir(basePath);
    return;
  }
  loadDiskDir(path);
}

// 4. Update diskGoBack() to stop at basePath
function diskGoBack() {
  if (currentDiskPath === '/' || currentDiskPath === basePath) return;
  const parent = currentDiskPath.split('/').slice(0, -1).join('/') || '/';
  if (parent === basePath || parent.startsWith(basePath + '/')) {
    loadDiskDir(parent);
  } else {
    loadDiskDir(basePath);  // clamp to basePath
  }
}

// 5. Save base_path with server config in localStorage
const saveEntry = { name, host, port, username, password, base_path: '/home/ubuntu/yunpan' };
savedServers.push(saveEntry);
localStorage.setItem('im_servers', JSON.stringify(savedServers));
```

**Backend (Flask) changes:**
No backend changes needed — the locking is enforced client-side. The SFTP connection can access any path; the frontend simply refuses to navigate above `basePath`. The `mkdir` endpoint is called to auto-create the directory on first connect.

**When to use this pattern:**
- The user complains about directory clutter in root `/` and wants a clean workspace
- The SSH user doesn't have write permission to `/` (E.g., [Errno 13] Permission denied when creating folders in root)
- The app is shared among multiple users and each should be confined to their own directory
- You want to prevent accidental navigation into system directories

## Verification

```bash
# Check APK exists and size
ls -lh app/build/outputs/apk/debug/app-debug.apk

# Verify APK signature
/opt/android-sdk/build-tools/34.0.0/apksigner verify \
  app/build/outputs/apk/debug/app-debug.apk

# Check manifest contents
/opt/android-sdk/build-tools/34.0.0/aapt dump badging \
  app/build/outputs/apk/debug/app-debug.apk | head -20
```
