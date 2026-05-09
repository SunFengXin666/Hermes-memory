Mihomo proxy (systemd) 127.0.0.1:7890 HTTP, 7891 SOCKS5, allow-lan: true. Subscription yfssce.net. Node: v3.cdn.0y6hzhd2pd.yafdns.net:25111/25112/25211 (VLESS+reality). UUID: 97e78d69-0f9e-4d98-ae54-7e65a374ff66. PubKey: okMflU6BFXrrv8dyyRjAXyFsD5FhOjju6avLRoDwmTM, ShortID: 3d5743d52b5b6701. ServerName: www.microsoft.com (订阅原始值). 出口: 188.253.124.94 (新加坡). hysteria2 (us38/us39.hy2use.net) 因 QUIC/UDP 被阻断不可用. 用 git clone / curl / apt 时设 export https_proxy=http://127.0.0.1:7890.
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
Vision用MiMo: base_url=https://token-plan-cn.xiaomimimo.com/v1, model IDs(小写+点号): mimo-v2.5, mimo-v2.5-pro, mimo-v2-omni, mimo-v2-pro. Key前16: tp-cr3x7h17d0ss3k
§
Server only 3.6GB RAM — memory is #1 bottleneck. Chrome renderer processes accumulate over days (~150MB each). First step when lag reported: `pkill -f chromium-browser`. No swap configured.
§
每日记忆: 仅23:59 cron自动生成每日总结（会话记录不逐条存）。Cron job "3bdc54905c93" 每晚23:59用session_search抓全天对话→写~/daily-memories/YYYY-MM-DD.md→推GitHub。WebUI不写记忆文件。
§
服务器 81.70.229.222 密码 SunFengXin521?（用户 ubuntu）。SSH/SFTP 端口 22。云盘已集成到 /root/webui/ WebUI 中。