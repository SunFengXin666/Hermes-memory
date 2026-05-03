Hermes Agent web management panel deployed at /root/hermes-webui/app.py. A Flask app that proxies to the Hermes API Server (port 8642) with dashboard, chat, logs, sessions, and config viewer. Run with: cd /root/hermes-webui && python3 app.py. Access at http://localhost:3000.
§
Mihomo proxy at /etc/mihomo/ (systemd mihomo.service). Mixed proxy 127.0.0.1:7890, SOCKS 7891, API 9090. Use export https_proxy=http://127.0.0.1:7890 for foreign downloads (curl/wget/git). All foreign traffic goes through proxy; domestic sources (aliyun, tencent, pypi mirrors) direct. Subscription from yfssce.net. Geoip/geosite via ghproxy.net mirror.
§
Vision model providers: auxiliary vision switched to Xiaomi MiMo (MiMo-V2.5-Omni) in config. nvidia/nemotron-nano-12b-v2-vl:free on OpenRouter decommissioned. MiMo API key: tp-c05czm1kueef6yqlxczc9hv03zlak7u3hobtnwjxun4tbqxr.
§
NapCat QQ Bot (Docker) running at ws://127.0.0.1:3001 (no token needed for WebSocket). Also WebSocket at 6099 port (with token). Send-image helper scripts at /opt/napcat/send_image.js (uses NCWebsocket library, target QQ 3240171077, file path /root/qrcode.png). Also /opt/napcat/send.js (native ws). To send QR/image to QQ via NapCat: cp screenshot /root/qrcode.png && cd /opt/napcat && node send_image.js. NapCat Docker container name: napcatf.
§
番茄小说网(fanqienovel.com)作家后台：手机号15601447368。Cookie注入登录可用（CDP Network.setCookie）。Key cookies: sessionid/sessionid_ss/sid_guard/sid_tt=83658aa347c0559752de36a8f5a0cb62, uid_tt/uid_tt_ss=00da09923efe2f27798708fcb5b67c4e, domain=fanqienovel.com, httpOnly&secure=true。验证码登录有火山引擎滑块。browser.cdp_url设置为http://127.0.0.1:9222解决频繁掉线。
§
用户小说《代码深处的体温》（原《跨越维度的深情》），番茄小说网连载，作者恰逢787。已发3章：你好，露丝（第3章）。100章大纲+人物档案在/root/novel/。标题不加"第X章"，发时勾选AI标记。各章约2000字。
§
GitHub auto-sync (SunFengXin666/Hermes-memory, via on_session_end plugin): local clone at /root/hermes-memory-backup/, sync.sh copies MEMORY.md + USER.md + 4 core system files (AGENTS.md, README.md, CONTRIBUTING.md, SOUL.md) + all skills/ SKILL.md, then git add+commit+push. No cron — syncs after each conversation ends. Plugin: github-sync, file at ~/.hermes/hermes-agent/plugins/github-sync/.