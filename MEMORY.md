Mihomo proxy at /etc/mihomo/ (systemd mihomo.service). Mixed proxy 127.0.0.1:7890, SOCKS 7891, API 9090. Use export https_proxy=http://127.0.0.1:7890 for foreign downloads (curl/wget/git). All foreign traffic goes through proxy; domestic sources (aliyun, tencent, pypi mirrors) direct. Subscription from yfssce.net. Geoip/geosite via ghproxy.net mirror.
§
NapCat QQ Bot (Docker) running at ws://127.0.0.1:3001 (no token needed for WebSocket). Also WebSocket at 6099 port (with token). Send-image helper scripts at /opt/napcat/send_image.js (uses NCWebsocket library, target QQ 3240171077, file path /root/qrcode.png). Also /opt/napcat/send.js (native ws). To send QR/image to QQ via NapCat: cp screenshot /root/qrcode.png && cd /opt/napcat && node send_image.js. NapCat Docker container name: napcatf.
§
番茄小说网作家后台：手机15601447368，Cookie登录(sessionid/sid_guard/sid_tt/uid_tt)，browser.cdp_url=http://127.0.0.1:9222。小说《代码深处的体温》，作者恰逢787，/root/novel/有100章大纲。
§
GitHub memory rule: 先拉后推。每次任务前 cd /root/hermes-memory-backup && bash sync.sh（pull+copy+push）。on_session_end 插件自动触发。Repo: SunFengXin666/Hermes-memory。
§
Remote server 81.70.229.222 (Tencent Cloud), Ubuntu 24.04, user: ubuntu. Has Ollama v0.22.1 (systemd, port 11434), model qwen2.5:0.5b. SSH accessible from this host.
§
Android APK build env on this server: JDK 17 /opt/java/, Android SDK /opt/android-sdk (platform 34), Gradle 8.5 /opt/gradle/gradle-8.5. IM+云盘 project at /root/im-app/ (Flask), Android project at /root/im-app-android/. APK at /root/im-app.apk.
§
User's IM+Cloud Android app project at /root/im-app/ (Flask backend + HTML/JS frontend) and /root/im-app-android/ (Android WebView APK wrapper). Run Flask: cd /root/im-app && python3 app.py --host 0.0.0.0 --port 8080. Build APK: set env JAVA_HOME/ANDROID_HOME/GRADLE_HOME, cd /root/im-app-android && gradle assembleDebug --no-daemon. APK at app/build/outputs/apk/debug/app-debug.apk.