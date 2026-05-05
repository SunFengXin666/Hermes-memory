Mihomo proxy at /etc/mihomo/ (systemd mihomo.service). Mixed proxy 127.0.0.1:7890, SOCKS 7891, API 9090. Use export https_proxy=http://127.0.0.1:7890 for foreign downloads (curl/wget/git). All foreign traffic goes through proxy; domestic sources (aliyun, tencent, pypi mirrors) direct. Subscription from yfssce.net. Geoip/geosite via ghproxy.net mirror.
§
NapCat QQ Bot (Docker) running at ws://127.0.0.1:3001 (no token needed for WebSocket). Also WebSocket at 6099 port (with token). Send-image helper scripts at /opt/napcat/send_image.js (uses NCWebsocket library, target QQ 3240171077, file path /root/qrcode.png). Also /opt/napcat/send.js (native ws). To send QR/image to QQ via NapCat: cp screenshot /root/qrcode.png && cd /opt/napcat && node send_image.js. NapCat Docker container name: napcatf.
§
番茄小说网作家后台：手机15601447368，Cookie登录(sessionid/sid_guard/sid_tt/uid_tt)，browser.cdp_url=http://127.0.0.1:9222。小说《代码深处的体温》，作者恰逢787，/root/novel/有100章大纲。
§
GitHub auto-sync on_session_end (plugin github-sync): /root/hermes-memory-backup/sync.sh. Repo: SunFengXin666/Hermes-memory.
§
Android APK build env on this server: JDK 17 /opt/java/, Android SDK /opt/android-sdk (platform 34), Gradle 8.5 /opt/gradle/gradle-8.5. IM+云盘 project at /root/im-app/ (Flask), Android project at /root/im-app-android/. APK at /root/im-app.apk.
§
IM+云盘 app /root/im-app/ (Flask+Android WebView). SFTP需set_keepalive(15)防断开。Android WebView文件选择必须用`<label>`包裹`<input type=file>`——JS触发`.click()`/透明覆盖层均无效。Vision用MiMo `mimo-v2-omni` @ token-plan-cn.xiaomimimo.com/v1, key: tp-cr3x7h17d0ss3kupmhid5jhcngsdk4gg75k3yve2jnby218r。Flask端口8080。Hermes API代理(localhost:8642)模型名必须用`hermes-agent`。
§
Server only 3.6GB RAM — memory is #1 bottleneck. Chrome renderer processes accumulate over days (~150MB each). First step when lag reported: `pkill -f chromium-browser`. No swap configured.
§
Daily memory plugin "daily-memory" (on_session_end, ~/.hermes/hermes-agent/plugins/daily-memory/): auto-saves all conversations (QQ, CLI, cron) to ~/daily-memories/YYYY-MM-DD.md. WebUI at /root/webui/ (port 8080) has /api/save-conversation for each WebUI exchange.