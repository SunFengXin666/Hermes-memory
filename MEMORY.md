Mihomo proxy (systemd) 127.0.0.1:7890 mixed, SOCKS 7891, API 9090. Use export https_proxy=http://127.0.0.1:7890 for foreign downloads. Subscription yfssce.net. Geoip/geosite via ghproxy.net.
Tailscale v1.96.4 installed. Server IP 100.107.11.26, WSL (qiafeng) 100.124.41.87, same tailnet under flechasdraftsye168@gmail.com.
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
每日记忆: 仅23:59 cron自动生成每日总结（会话记录不逐条存）。Cron job "3bdc54905c93" 每晚23:59用session_search抓全天对话→写~/daily-memories/YYYY-MM-DD.md→推GitHub。WebUI不写记忆文件。
§
服务器 81.70.229.222 密码 SunFengXin521?（用户 ubuntu）。SSH/SFTP 端口 22。云盘已集成到 /root/webui/ WebUI 中。