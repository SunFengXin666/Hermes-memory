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
---

## mihomo（Clash Meta）代理配置经验总结

### 背景
主服务器 49.232.224.90 在大陆（墙内），需要通过代理访问外网。

### 为什么用 mihomo
- 原版 Clash 不支持 VLESS reality 协议
- mihomo（MetaCubeX/Clash.Meta）支持 reality，能完整伪造目标网站 TLS 指纹
- 安装：下载 release，chmod +x，mv 到 /usr/local/bin/mihomo

### 核心经验

**1. 订阅链接是 base64 编码的 URI**
```
echo "base64字符串" | base64 -d
```
解码后才是真实节点配置。参数（UUID、pub key、short ID）全部从解码后的 URI 提取，不要手动填写。

**2. VLESS reality 关键参数（容易填错）**
| 参数 | 说明 | 正确示例 |
|------|------|---------|
| public key | base64 解码后 32 字节 | okMflU6BFXrrv8dyyRjAXyFsD5FhOjju6avLRoDwmTM（43位base64）|
| short ID | 十六进制字符串 | 3d5743d52b5b6701 |
| server | 填节点域名，不是目标域名 | v3.cdn.0y6hzhd2pd.yafdns.net |
| server name | 填目标网站域名（用于 TLS 伪造） | www.microsoft.com |

**3. 踩坑记录**
- hysteria2 的 QUIC 握手在大陆被阻断（`context deadline exceeded`），国内不要用
- server 填 www.microsoft.com 会解析到大陆 CDN（61.147.219.124），导致连接失败
- 出口 IP：188.253.124.94（新加坡）

**4. git push 在代理下超时**
git-remote-https 连接 github.com:443 成功，但 push 时卡住。用 GitHub API 替代：
```bash
# 获取 SHA
GET https://api.github.com/repos/{owner}/{repo}/contents/{path}
# 更新
PUT https://api.github.com/repos/{owner}/{repo}/contents/{path}
```

**5. GeoLite2 MMDB 在大陆无法下载**
服务器访问不了 github.com/maxmind，直接从其他镜像站下载或跳过（规则不依赖 geoip-match 时不影响）。

### mihomo 关键配置项
```yaml
mixed-port: 7890
allow-lan: true
bind-address: 0.0.0.0
log-level: info
external-controller: 0.0.0.0:9090

proxies:
  - name: "v3-cdn"
    type: vless
    server: v3.cdn.0y6hzhd2pd.yafdns.net
    port: 25111
    uuid: [REDACTED]
    flow: xtls-rprx-vision
    client-fingerprint: chrome
    reality-opts:
      public-key: okMflU6BFXrrv8dyyRjAXyFsD5FhOjju6avLRoDwmTM
      short-id: 3d5743d52b5b6701
    servername: www.microsoft.com

proxy-groups:
  - name: Proxy
    type: select
    proxies:
      - v3-cdn

rules:
  - MATCH,Proxy
```

### 验证命令
```bash
# 代理端口测试
curl --proxy http://127.0.0.1:7890 http://httpbin.org/ip
curl --proxy socks5://127.0.0.1:7891 http://httpbin.org/ip

# 查看出口 IP
curl --proxy http://127.0.0.1:7890 ifconfig.me

# 查看日志
sudo journalctl -u mihomo --no-pager -f
```
