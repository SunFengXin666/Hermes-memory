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

**MainActivity.java** (WebView wrapper with file upload support):
```java
package com.myapp.app;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.ValueCallback;
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
    private ValueCallback<Uri[]> uploadCallback;
    private static final int FILE_CHOOSER_REQUEST = 1001;

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

        // CRITICAL: File upload support - without onShowFileChooser, <input type="file">
        // does nothing in Android WebView. The user can select files but the "upload"
        // button silently does nothing.
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(
                WebView view,
                ValueCallback<Uri[]> filePathCallback,
                FileChooserParams fileChooserParams
            ) {
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

        swipeRefresh.setOnRefreshListener(() -> webView.reload());
        webView.loadUrl(serverUrl);
    }

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

11. **SwipeRefreshLayout interferes with chat scrolling** — When the WebView wraps a chat app where the user scrolls UP to see older messages, `SwipeRefreshLayout` intercepts upward scrolls as pull-to-refresh gestures. This causes the page to reload instead of scrolling. Fix: remove SwipeRefreshLayout entirely if the app doesn't need pull-to-refresh:
    - **Layout**: Remove `<androidx.swiperefreshlayout.widget.SwipeRefreshLayout>` wrapper, put WebView directly inside the root layout
    - **Java**: Remove `import androidx.swiperefreshlayout.widget.SwipeRefreshLayout`, remove all `swipeRefresh` references, remove `setOnRefreshListener`
    - **build.gradle**: Remove `implementation 'androidx.swiperefreshlayout:swiperefreshlayout:1.1.0'` dependency
    - Keep SwipeRefreshLayout only if the user explicitly asks for pull-to-refresh (e.g., a news reader or browser app). For chat/terminal/input-heavy apps, remove it.

12. **Flexbox `min-height: 0` bug breaks scrolling in nested flex layouts** — In Android WebView, a flex container with `overflow-y: auto` will NOT scroll if its parent flex chain doesn't have `min-height: 0` set at every level. This is a CSS Flexbox spec behavior: by default, flex items have `min-height: auto` (cannot shrink below content size), which prevents the `overflow: auto` child from establishing a scroll container. The symptom: the page looks correct, messages render, but `.chat-messages { overflow-y: auto }` never activates — content overflows invisibly or pushes siblings out of view. Fix:\n    - Add `min-height: 0` to every flex child in the chain: `.page { min-height: 0 }`, `.chat-layout { min-height: 0 }`, `.chat-area { min-height: 0 }`, `.chat-messages { min-height: 0 }`\n    - Test by adding many messages; if they don't scroll, trace up the flex hierarchy and add `min-height: 0` to each ancestor\n    - This also applies to horizontal flex overflow: use `min-width: 0` for horizontal scroll containers\n\n13. **File upload silently fails in WebView** — `<input type=\"file\">` in a WebView does nothing unless the `WebChromeClient` overrides `onShowFileChooser`. Without it, the file picker dialog never opens. The user can click \"选择文件\" and see the Android file picker, but the JavaScript `fileInput.files[0]` will be `null` because the callback was never invoked. Fix: implement `onShowFileChooser` in the WebChromeClient (see MainActivity.java template above) and handle the result in `onActivityResult`. Add `setAllowFileAccess(true)` to WebSettings (already covered above).

### WebView JS Diagnostic Protocol (buttons don't work? check these in order)

When a user reports "buttons don't work" in a WebView app (e.g., navigation tabs unresponsive, chat send button dead, login stuck), follow this diagnostic order:

1. **Quick CDP sanity check** — Load the page in a headless browser (use `browser_navigate` + `browser_console`) and check if ANY JS function is defined:
   ```javascript
   typeof switchPage  // "undefined" → entire script block failed to parse
   typeof userId       // "undefined" → confirms
   ```
   If `typeof` returns `"undefined"` for any global variable defined in the script, the entire `<script>` block failed to parse. **Stop debugging event binding or CSS fixes** — they are irrelevant until the syntax error is fixed.

2. **Syntax validation** — Extract all `<script>` content and run through Node.js syntax check:
   ```bash
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
           # Show context around the error line
           lines = js.split('\n')
           import re as re2
           m = re2.search(r'\((\d+):(\d+)\)', r.stderr)
           if m:
               ln = int(m.group(1))
               for dl in range(-3, 4):
                   idx = ln - 1 + dl
                   if 0 <= idx < len(lines):
                       print(f'  {idx+1}: {lines[idx]}')
       else:
           print(f'SCRIPT BLOCK {i}: OK')
       import os; os.unlink(t.name)
   "
   ```

3. **Common syntax error: prematurely closed template literal** — A backtick in the wrong place closes a multi-line template string early, making the next line's HTML tags parse as raw JavaScript (most insidious because the HTML still renders fine):

   ❌ **Broken** — backtick before `</div>` closes the template early:
   ```javascript
   return `<div class="server-item" onclick="fn('${name}')\">`\n        <div class=\"name\">${item.name}</div>     // SyntaxError: 'class' unexpected
         </div>`;
   ```
   ✅ **Fixed** — no backtick until the actual end:
   ```javascript
   return `<div class="server-item" onclick="fn('${name}')\">\n        <div class=\"name\">${item.name}</div>
         </div>`;
   ```

4. **Explicit style.display fallback** — If `classList` toggle works on desktop but not on some WebViews (custom OEM browsers), explicitly set `style.display` instead of relying on CSS `.active { display: flex }`:
   ```javascript
   document.querySelectorAll('.page').forEach(p => {
     p.classList.remove('active');
     p.style.display = 'none';        // ← explicit
   });
   const page = document.getElementById('page-' + name);
   if (page) {
     page.classList.add('active');
     page.style.display = 'flex';      // ← explicit
   }
   ```

5. **Event binding robustness** — If syntax is clean and display works, layer these defenses:
   - Inline `onclick` in HTML (hardest to break)
   - Event delegation on parent container (handles DOM timing)
   - `touch-action: manipulation` CSS (eliminates 300ms tap delay)

### Integrating AI Chat via OpenAI-Compatible API

If your WebView app has a chat feature (WebSocket-based) and you want to replace P2P user-to-user chat with AI chat (user talks to an LLM directly):

**Backend pattern (Flask WebSocket handler):**

```python
from openai import OpenAI

# Connect to a local OpenAI-compatible API server
# For Hermes Agent: http://localhost:8642/v1 (use API_SERVER_KEY from config)
# For other providers: https://api.openai.com/v1, etc.
AI_CLIENT = OpenAI(
    api_key='your-api-key-or-hermes-server-key',
    base_url='http://localhost:8642/v1',  # Hermes API server endpoint
)
AI_MODEL = 'deepseek-v4-flash'  # or any model available on your endpoint
ai_memories: dict[str, list] = {}  # user_id -> conversation history

@sock.route('/chat/ws')
def chat_ws(ws):
    # ... login handshake ...
    while True:
        raw = ws.receive()
        data = json.loads(raw)
        if data['type'] == 'message':
            # 1. Echo user's message back (with isSelf=true for frontend styling)
            ws.send(json.dumps({
                'type': 'message', 'from': user_id,
                'text': data['text'], 'time': data.get('time', ''),
                'isSelf': True,
            }))
            # 2. Call AI
            try:
                uid = user_id or 'default'
                if uid not in ai_memories:
                    ai_memories[uid] = [
                        {'role': 'system', 'content': 'You are a helpful AI assistant.'},
                    ]
                ai_memories[uid].append({'role': 'user', 'content': data['text']})
                # Keep last N messages to avoid context overflow
                if len(ai_memories[uid]) > 21:
                    ai_memories[uid] = [ai_memories[uid][0]] + ai_memories[uid][-20:]
                resp = AI_CLIENT.chat.completions.create(
                    model=AI_MODEL,
                    messages=ai_memories[uid],
                    timeout=30,
                )
                reply = resp.choices[0].message.content
                ai_memories[uid].append({'role': 'assistant', 'content': reply})
                # 3. Send AI reply back
                ws.send(json.dumps({
                    'type': 'message', 'from': 'AI',
                    'text': reply, 'time': '',
                    'isSelf': False,  # renders as left-aligned "other" message
                }))
            except Exception as e:
                ws.send(json.dumps({
                    'type': 'message', 'from': 'AI',
                    'text': f'⚠️ AI error: {str(e)}', 'time': '',
                    'isSelf': False,
                }))
```

**Frontend (JavaScript) changes:**

1. Remove P2P routing from `sendMessage()` — user can send without selecting a chat target:
```javascript
function sendMessage() {
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  ws.send(JSON.stringify({
    type: 'message', text,
    time: new Date().toLocaleTimeString('zh-CN', {hour:'2-digit',minute:'2-digit'})
  }));
  // Server echoes user msg + AI reply — no local append needed
}
```

2. Use server's `isSelf` field for message styling instead of comparing `from === userId`:
```javascript
function receiveMessage(data) {
  appendMessage({from: data.from, text: data.text, time: data.time, isSelf: data.isSelf});
}
```

3. Auto-enable chat input on login (no need to select a peer first):
```javascript
document.getElementById('chat-header').textContent = '💬 Chatting with AI';
document.getElementById('chat-input').disabled = false;
document.getElementById('chat-send').disabled = false;
```

**Key considerations for AI chat in WebView:**
- The `OPENAI_API_KEY` in environment variables may be masked/overridden by Hermes Agent (`***`). If you set `api_key=` with the literal masked value, the API call will fail with 401. Use either:
  - A hardcoded key from config.yaml (if available and valid)
  - The **Hermes API server** at `http://localhost:8642/v1` with API_SERVER_KEY as the bearer token — this bypasses external API key issues entirely because the Hermes gateway handles provider authentication internally
  - Read the key from `auth.json` credential pool at runtime
- `os.environ` in Flask subprocesses may not inherit the actual API keys (Hermes masks them). Test with a direct `curl` before hardcoding.
- WebSocket timeout: the AI API call is synchronous. For slow models, set a short `timeout` on the OpenAI client so the WebSocket doesn't hang. Handle errors gracefully with a user-facing fallback message.
- Conversation memory: store per-user message history in a dict with a max length (e.g., 20 turns) to prevent unbounded memory growth. Include a system prompt as the first message.

**When to use this pattern:**
- You have a WebView app with a chat interface (WebSocket backend)
- P2P chat is not useful (single user, or no other clients)
- You want the app to function as an AI assistant frontend
- You have a local Hermes Agent API server or any OpenAI-compatible endpoint

### Mobile Network Blocking WebSocket: Switch to SSE (Server-Sent Events)

**The problem:** WebSocket handshake (`ws://` upgrade request) may **time out** from mobile networks (4G/5G) to Chinese cloud servers (Tencent Cloud, Alibaba Cloud), even though regular HTTP works fine. The error looks like:
```
InvalidStateError: Failed to execute 'send' on 'WebSocket': Still in CONNECTING
```
The WebSocket `onopen` never fires. HTTP requests to the same server/port work normally.

**Root cause:** Some mobile carriers, cloud security groups, or middleboxes block WebSocket upgrade packets or introduce latency that causes the handshake to time out. Cloud server security groups that allow HTTP traffic may still interfere with the `Connection: Upgrade` header negotiation.

**Solution: Replace WebSocket with HTTP + SSE (Server-Sent Events).** SSE works over standard HTTP GET, uses the same port, and has built-in auto-reconnect in browsers via `EventSource`.

#### Backend: Flask SSE Endpoint

Replace `flask-sock` with a queue-based SSE generator:

```python
import queue, threading, json
from flask import Response

# Per-user message queues
user_queues: dict[str, queue.Queue] = {}
user_queues_lock = threading.Lock()

# Login via HTTP POST (not WebSocket handshake)
@app.route('/api/chat/login', methods=['POST'])
def chat_login():
    user_id = request.json['user_id']
    with user_queues_lock:
        user_queues.setdefault(user_id, queue.Queue())
    return jsonify({'ok': True})

# Send message via HTTP POST
@app.route('/api/chat/send', methods=['POST'])
def chat_send():
    data = request.json
    user_id = data['user_id']
    text = data['text']
    # Echo user's own message
    own_q = user_queues.get(user_id)
    if own_q:
        own_q.put(json.dumps({
            'type': 'message', 'from': user_id, 'text': text,
            'time': data.get('time', ''), 'isSelf': True,
        }))
    # Call AI asynchronously
    threading.Thread(target=call_ai, args=(user_id, text), daemon=True).start()
    return jsonify({'ok': True})

# SSE endpoint — long-lived GET
@app.route('/api/chat/events')
def chat_events():
    user_id = request.args.get('user_id', '')
    with user_queues_lock:
        user_queues.setdefault(user_id, queue.Queue())
        q = user_queues[user_id]
    def generate():
        while True:
            try:
                msg = q.get(timeout=30)  # Block until message arrives
                yield f'data: {msg}\n\n'
            except queue.Empty:
                yield ': keepalive\n\n'  # SSE comment = keepalive (no-op)
    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'})
```

Key points:
- **`q.get(timeout=30)`** — blocks up to 30s waiting for a message, then sends keepalive to prevent proxy timeouts
- **`': keepalive\\n\\n'`** — SSE comments are invisible to the client but keep the TCP connection alive
- **Asynchronous AI calls** — run in a `threading.Thread` so the SSE generator isn't blocked by API latency
- **No `flask-sock` or `simple-websocket` dependency** — SSE is built into Flask via the `Response` generator

#### Frontend: JavaScript Changes

Replace `new WebSocket(url)` with `new EventSource(url)`:

```javascript
let eventSource = null;

function initChat() {
  // Step 1: Login via HTTP
  fetch('/api/chat/login', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({user_id: userId}),
  }).then(r => r.json()).then(data => {
    if (data.ok) {
      document.getElementById('chat-input').disabled = false;
      document.getElementById('chat-send').disabled = false;
      // Step 2: Open SSE connection
      connectSSE();
    }
  });
}

function connectSSE() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource(`/api/chat/events?user_id=${encodeURIComponent(userId)}`);

  eventSource.onmessage = (e) => {
    const data = JSON.parse(e.data);
    handleSSEMessage(data);  // handle user_online, message, user_offline, etc.
  };

  eventSource.onerror = () => {
    // Auto-reconnect after 5s (built-into EventSource, but we add custom delay)
    setTimeout(() => connectSSE(), 5000);
  };
}

function sendMessage() {
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  fetch('/api/chat/send', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({user_id: userId, text, time: '...'}),
  }).catch(e => { input.value = text; });  // restore on failure
}
```

Key differences from WebSocket:
- **No `onopen` check needed** — HTTP POST always works if the page loaded
- **No `ws.readyState` guard** — SSE auto-reconnects on error; `fetch` calls are stateless
- **No `onclose`** — `EventSource` handles reconnection internally
- **Same message format** — SSE `data:` lines contain the same JSON you'd send over WebSocket

### Server-Side Chat Message Persistence (across app restarts)

When the user expects chat history to survive app closes/opens, store messages on the server:

**Backend: JSONL file per user**

```python
# At module level
CHAT_DIR = Path('/tmp/im-app-chat-history')
CHAT_DIR.mkdir(parents=True, exist_ok=True)
CHAT_LOCK = threading.Lock()

def save_message(user_id: str, msg: dict):
    file_path = CHAT_DIR / f'{user_id}.jsonl'
    with CHAT_LOCK:
        try:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(msg, ensure_ascii=False) + '\n')
        except Exception:
            pass

def load_history(user_id: str) -> list[dict]:
    file_path = CHAT_DIR / f'{user_id}.jsonl'
    if not file_path.exists():
        return []
    with CHAT_LOCK:
        try:
            lines = file_path.read_text(encoding='utf-8').strip().split('\n')
            return [json.loads(l) for l in lines if l.strip()]
        except Exception:
            return []
```

**Save messages after push_to_user()** in both the send endpoint and the AI callback:
```python
# In chat_send() — save user message
save_message(user_id, {
    'from': user_id, 'text': text,
    'time': data.get('time', ''), 'isSelf': True,
})

# In call_ai() — save AI reply
save_message(user_id, {
    'from': 'AI', 'text': reply,
    'time': '', 'isSelf': False,
})
```

**Return history on login** (not via SSE — timing issue: login POST runs before SSE connects):
```python
@app.route('/api/chat/login', methods=['POST'])
def chat_login():
    # ... login logic ...
    history = load_history(user_id)
    return jsonify({'ok': True, 'users': users_snapshot, 'history': history})
```

**Frontend: render history from login response**:
```javascript
function initChat() {
  fetch('/api/chat/login', {method:'POST', ...})
    .then(r => r.json())
    .then(data => {
      if (data.ok) {
        // Load saved history from login response
        const el = document.getElementById('chat-messages');
        el.innerHTML = '';
        if (data.history && data.history.length) {
          data.history.forEach(msg => {
            appendMessage({from: msg.from, text: msg.text, time: msg.time, isSelf: msg.isSelf});
          });
        }
        // Then connect SSE for real-time messages
        connectSSE();
      }
    });
}
```

**Key considerations:**
- Use **JSONL format** (one JSON object per line) — append-only, no read-modify-write corruption from concurrent access
- Use a `threading.Lock()` for thread-safe file writes (Flask's threaded=True)
- Store in `/tmp/` for simplicity (lost on reboot) or a persistent path like `/var/lib/im-app/` for durability
- Don't send history via SSE — the login HTTP POST runs before the SSE connection, so history would be pushed to an empty queue
- Keep the file small (auto-prune by max lines or max age) to avoid slow login loads

### Injecting Hermes Agent Memory into External AI Services

When an external web app (Flask, running on same server) calls an AI model and you want the AI to know about the user's background from Hermes Agent persistent memory:

**Read memory files on each new conversation** (not just at startup):

```python
from pathlib import Path

def load_hermes_memories() -> str:
    system_info = 'Your name is 友友, a friendly AI assistant. Answer in Chinese.'
    try:
        user_md = Path('/root/.hermes/memories/USER.md').read_text(encoding='utf-8')
        memory_md = Path('/root/.hermes/memories/MEMORY.md').read_text(encoding='utf-8')
        # Replace '§' separators with newlines for clean formatting
        user_info = user_md.replace('§', '\n').strip()
        sys_info = memory_md.replace('§', '\n').strip()
        system_info += f'\n\nUser info:\n{user_info}\n\nEnvironment:\n{sys_info}'
    except Exception:
        pass
    return system_info

# Use when creating the system prompt for a new conversation:
if user_id not in ai_memories:
    system_prompt = load_hermes_memories()  # reloads files each time
    ai_memories[user_id] = [
        {'role': 'system', 'content': system_prompt},
    ]
```

**Why reload on each conversation instead of once at startup:**
- User may update memory files via `memory()` tool or GitHub sync between conversations
- Memory files change frequently (skills, preferences, environment facts)
- Reading two small text files is fast (<1ms, no network)

**Memory file locations:**
- `/root/.hermes/memories/USER.md` — user profile, preferences, personal details
- `/root/.hermes/memories/MEMORY.md` — environment facts, project conventions, tool quirks

**Paths are server-specific.** If running the Flask app on a different machine, the memory files won't exist. Only use this pattern when the Flask app runs on the same server as Hermes Agent.

### Async SFTP File Operations (Two-Hop Timeout Pattern)

When a WebView app provides file management via a **two-hop** architecture (phone→Flask server→SFTP remote server), the HTTP response from phone→Flask can timeout while Flask→SFTP is still transferring. The file eventually arrives but the user sees a hang or "上传中..." that never resolves.

**The pattern:** Accept the file on the Flask server immediately, return `{'ok': True, 'status': 'uploading'}`, then run the SFTP upload in a background thread.

**Backend — async upload with SSE notification:**

```python
# Flask upload endpoint
@app.route('/api/disks/<conn_id>/upload', methods=['POST'])
def disk_upload(conn_id):
    conn = sftp_connections.get(conn_id)
    if not conn:
        return jsonify({'ok': False, 'error': '连接已断开'}), 404
    dest_dir = request.form.get('path', '/')
    file = request.files.get('file')
    user_id = request.form.get('user_id', '')  # for SSE notification
    if not file:
        return jsonify({'ok': False, 'error': '没有文件'}), 400
    try:
        local_tmp = UPLOAD_DIR / f"ul_{uuid.uuid4().hex[:12]}_{file.filename}"
        file.save(str(local_tmp))
        threading.Thread(target=_do_sftp_upload,
            args=(conn_id, dest_dir, str(local_tmp), file.filename, user_id),
            daemon=True).start()
        return jsonify({'ok': True, 'status': 'uploading'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

def _do_sftp_upload(conn_id, dest_dir, local_path, filename, user_id=''):
    try:
        conn = sftp_connections.get(conn_id)
        if not conn: return
        sftp = conn['sftp']
        try: sftp.stat(dest_dir)
        except: sftp.mkdir(dest_dir)
        remote_path = os.path.join(dest_dir, filename).replace('\\', '/')
        sftp.put(local_path, remote_path)
        # Push SSE event so frontend auto-refreshes
        if user_id:
            push_to_user(user_id, {'type': 'disk_refresh', 'path': dest_dir})
    except Exception:
        pass
    finally:
        try: Path(local_path).unlink(missing_ok=True)
        except: pass
```

**Frontend — upload flow:**

```javascript
async function doUpload() {
  const file = document.getElementById('upload-file').files[0];
  if (!file) return;
  
  const btn = document.querySelector('#upload-modal .btn-confirm');
  btn.textContent = '⏳ 上传中...';
  btn.disabled = true;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('path', currentDiskPath);
  formData.append('user_id', userId);  // for SSE callback

  try {
    const resp = await fetch(`/api/disks/${activeServerId}/upload`, {
      method: 'POST', body: formData
    });
    const result = await resp.json();
    btn.textContent = '上传';
    btn.disabled = false;
    if (result.status === 'uploading') {
      closeModal('upload-modal');
      toast('⏳ 后台上传中...');  // SSE will notify on completion
    }
  } catch(e) {
    btn.textContent = '上传';
    btn.disabled = false;
    toast('❌ ' + e.message);
  }
}
```

**Frontend — SSE handler for upload completion:**

```javascript
function handleSSEMessage(data) {
  switch(data.type) {
    case 'disk_refresh':
      toast('📁 上传完成');
      diskRefresh();  // reload the current directory listing
      break;
    // ... other cases
  }
}
```

**Async download (server-side caching + browser redirect):**

For downloads, the same two-hop timeout issue applies. Instead of streaming the SFTP file through Flask's response (which blocks the HTTP connection during SFTP transfer):

1. Download the SFTP file to a server temp directory
2. Return a JSON response with a direct URL
3. `window.open()` the URL in the browser — the phone's system download manager handles it

```python
import uuid
from flask import send_from_directory

DOWNLOAD_DIR = Path('/tmp/im-app-downloads')
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

@app.route('/api/disks/<conn_id>/download', methods=['GET'])
def disk_download(conn_id):
    conn = sftp_connections.get(conn_id)
    if not conn:
        return jsonify({'ok': False, 'error': '连接已断开'}), 404
    path = request.args.get('path', '')
    try:
        filename = os.path.basename(path)
        local_path = DOWNLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{filename}"
        conn['sftp'].get(path, str(local_path))
        return jsonify({'ok': True, 'url': f'/dl/{local_path.name}', 'filename': filename})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@app.route('/dl/<path:filename>')
def serve_download(filename):
    return send_from_directory(str(DOWNLOAD_DIR), filename, as_attachment=True)
```

```javascript
async function diskDownload(path) {
  toast('⏳ 下载中...');
  try {
    const resp = await fetch(`/api/disks/${activeServerId}/download?path=${encodeURIComponent(path)}`);
    const result = await resp.json();
    if (!result.ok) { toast('❌ ' + result.error); return; }
    window.open(window.location.origin + result.url, '_blank');
  } catch(e) {
    toast('❌ 下载失败: ' + e.message);
  }
}
```

**Key principles:**
- Phone→Flask first hop must return immediately (acceptable latency: <5s even for large files)
- Flask→SFTP second hop is async (can take minutes for large files over slow connections)
- Use SSE to notify the frontend when background operations complete
- The download cache dir (`/tmp/im-app-downloads/`) is ephemeral — files are lost on server restart. For production, use a persistent directory with periodic cleanup.

**When to use this pattern:**
- WebView app with server-side SFTP/SSH file management
- Large file uploads where SFTP takes >10 seconds
- Mobile networks where HTTP connections are unreliable for long-lived transfers
- Users report "上传中..." that never resolves but files eventually appear

### When to use SSE Instead of WebSocket

- Users report "Still in CONNECTING" error on mobile networks
- WebSocket handshake times out but page loads fine
- App runs on Chinese cloud servers (TencentCloud, AlibabaCloud)
- High packet loss or slow mobile connections
- You want simpler transport with built-in reconnection

#### Limitations of SSE

- **Unidirectional** — Server→Client only. Client→Server must use HTTP POST (separate endpoint).
- **Binary data** — SSE is text-only. For binary, use base64 encoding or separate upload endpoints.
- **Browser support** — `EventSource` is supported in Android WebView since 4.4 (KitKat). For very old devices, add a polyfill.
- **Max connections** — Most browsers allow ~6 SSE connections per domain. Fine for a single-user app.

#### Testing SSE Locally

```bash
# 1. Login
curl -s -X POST http://localhost:8080/api/chat/login \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"test"}'

# 2. Open SSE stream (blocks, waiting for events)
timeout 5 curl -s -N "http://localhost:8080/api/chat/events?user_id=test"

# 3. In another terminal, send a message
curl -s -X POST http://localhost:8080/api/chat/send \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"test","text":"你好"}'
# SSE stream should show: data: {"type":"message","from":"test","text":"你好","isSelf":true}
# Then: data: {"type":"message","from":"AI","text":"你好！","isSelf":false}
```

### Troubleshooting AI chat in WebView:
- **Empty response / no messages appearing**: Check that the server's `ws.send()` is using `json.dumps()` (not string concatenation which can produce invalid JSON).
- **WebSocket 500 error**: The AI API call threw an exception. Check server logs and test the API endpoint directly: `curl -s http://localhost:8642/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d '{"model":"...","messages":[{"role":"user","content":"hi"}]}'`
- **401 authentication error**: The API key is wrong or truncated. For Hermes API server, use the API_SERVER_KEY from `.env` file, not the LLM provider key.
- **Messages appear doubled**: Remove the local `appendMessage()` call in `sendMessage()` — server now echoes the user message back.
- **Input disabled / can't type**: After auto-login, explicitly set `document.getElementById('chat-input').disabled = false` and `chat-send.disabled = false`.
- **"Failed to execute 'send' on 'WebSocket': Still in CONNECTING"**: This happens when the user types and sends before the WebSocket connects. Two fixes:
  1. **Guard in sendMessage()**: Check `ws.readyState` before sending:
     ```javascript
     function sendMessage() {
       if (!text) return;
       if (!ws || ws.readyState !== WebSocket.OPEN) {
         toast('Connecting...');
         return;
       }
       ws.send(JSON.stringify(payload));
     }
     ```
  2. **Enable input in ws.onopen, not on load**: Move input enablement from the auto-login IIFE to `ws.onopen`. This prevents typing before WS is ready:
     ```javascript
     ws.onopen = () => {
       ws.send(JSON.stringify({type:'login', user_id: userId}));
       document.getElementById('chat-input').disabled = false;
       document.getElementById('chat-send').disabled = false;
     };
     ```
    Without this, `ws.send()` throws while still CONNECTING, showing an error banner in the WebView.

### Read-File Escape-Drift Trap

When using `read_file` to view HTML/JS with template literals, the tool displays `\"` (backslash-quote) for visual escaping of embedded double quotes. The actual file has just `"`. If you copy `\"` from read_file output into a `patch` old_string/new_string, the tool may reject it with "Escape-drift detected". Always read raw file content with `cat -A` or `xxd` to verify before patching.

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
- `window.onerror` handler must be defined *before* any functional code that might throw, otherwise errors are silently swallowed\n- Wrap IIFE auto-init in `try/catch` so a corrupted localStorage or broken init flow doesn't cascade into unclickable buttons\n- If the WebView shows a login modal that overlays the main UI, the modal's `show` class should be controlled by JavaScript (default hidden) rather than being present in the HTML `class` attribute — this prevents a flash of the login overlay on every page load\n- **`onclick = function()` vs `addEventListener`**: Some Android WebViews (especially on older devices or customized OEM browsers) handle `onclick = function() {}` (direct property assignment) more reliably than `addEventListener`. If navigation buttons or other click handlers fail to fire despite the DOM being ready, switch from `btn.addEventListener('click', handler)` to `btn.onclick = handler`. The trade-off: `onclick` only supports one handler per element.\n- **Cascading nav-button failure**: A common symptom in WebView SPAs is that the chat button works but cloud-disk and settings buttons don't. The fix stack: (1) move event binding to top, (2) wrap IIFE in try-catch, (3) inline onclick, (4) event delegation, (5) touch-action CSS.\
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
