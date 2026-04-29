Hermes Agent web management panel deployed at /root/hermes-webui/app.py. A Flask app that proxies to the Hermes API Server (port 8642) with dashboard, chat, logs, sessions, and config viewer. Run with: cd /root/hermes-webui && python3 app.py. Access at http://localhost:3000.
§
Mihomo proxy at /etc/mihomo/ (systemd mihomo.service). Mixed proxy 127.0.0.1:7890, SOCKS 7891, API 9090. Use export https_proxy=http://127.0.0.1:7890 for foreign downloads (curl/wget/git). All foreign traffic goes through proxy; domestic sources (aliyun, tencent, pypi mirrors) direct. Subscription from yfssce.net. Geoip/geosite via ghproxy.net mirror.
§
Vision model providers: Groq vision models decommissioned (Apr 2026). OpenRouter nvidia/nemotron-nano-12b-v2-vl:free has ~50 daily limit (429 after exhausted). Gemini free tier shows "limit: 0" without GCP billing. Groq blocks Tencent Cloud IPs — use proxy.
§
NapCat QQ Bot (Docker) running at ws://127.0.0.1:3001 (no token needed for WebSocket). Also WebSocket at 6099 port (with token). Send-image helper scripts at /opt/napcat/send_image.js (uses NCWebsocket library, target QQ 3240171077, file path /root/qrcode.png). Also /opt/napcat/send.js (native ws). To send QR/image to QQ via NapCat: cp screenshot /root/qrcode.png && cd /opt/napcat && node send_image.js. NapCat Docker container name: napcatf.
§
番茄小说网(fanqienovel.com)作家后台：手机号15601447368。Cookie注入登录可用（CDP Network.setCookie）。Key cookies: sessionid/sessionid_ss/sid_guard/sid_tt=83658aa347c0559752de36a8f5a0cb62, uid_tt/uid_tt_ss=00da09923efe2f27798708fcb5b67c4e, domain=fanqienovel.com, httpOnly&secure=true。验证码登录有火山引擎滑块。browser.cdp_url设置为http://127.0.0.1:9222解决频繁掉线。
§
用户小说《代码深处的体温》（原《跨越维度的深情》），番茄小说网连载，作者恰逢787。已发3章：你好，露丝（第3章）。100章大纲+人物档案在/root/novel/。标题不加"第X章"，发时勾选AI标记。各章约2000字。
§
Hermes Agent persistent memory (MEMORY.md + USER.md) auto-synced to GitHub repo SunFengXin666/Hermes-memory every 30 min via cron job. Local clone at /root/hermes-memory-backup/, sync script at /root/hermes-memory-backup/sync.sh. Remote URL has token embedded for auth.