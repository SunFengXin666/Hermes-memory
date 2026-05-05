---
name: mihomo-proxy-setup
description: "Install and configure mihomo (clash meta) on Chinese mainland servers (Tencent Cloud, Alibaba Cloud, etc.) for split-routing proxy — domestic traffic direct, foreign traffic through subscription-based proxy nodes. Covers handling blocked GitHub downloads, geoip/geosite MMDB download failures, port conflicts, and systemd service setup."
version: 1.0.0
metadata:
  hermes:
    tags: [proxy, vpn, mihomo, clash, gfw, tencent-cloud, alibaba-cloud, split-routing, china, devops]
    requires:
      commands: [curl, sudo, systemctl]
---

# Mihomo Proxy Setup (China Mainland Server)

## When to Use

Use this skill when:
- A user on a Chinese mainland VPS (Tencent Cloud, Alibaba Cloud, etc.) needs to access blocked websites (Google, GitHub, OpenAI, Gemini, etc.)
- The server has limited outbound network access (GitHub/Docker Hub timeouts)
- The user has a proxy subscription URL (airport/clash subscription)
- You need split-routing: domestic traffic (Baidu, Alibaba Cloud, Tencent Cloud, pip, apt) goes DIRECT, foreign traffic goes through proxy
- Setting up mihomo (clash meta) as a systemd service for persistent use

## Prerequisites

- Linux server (x86_64), root/sudo access
- A proxy subscription URL (base64-encoded or standard clash format)
- sudo access

## Steps

### 1. Install mihomo

GitHub releases often time out from Chinese VPS. Use a mirror:

```bash
curl -sL "https://ghproxy.net/https://github.com/MetaCubeX/mihomo/releases/download/v1.19.24/mihomo-linux-amd64-v1.19.24.gz" -o /tmp/mihomo.gz
cd /tmp
gzip -d mihomo.gz
chmod +x mihomo
sudo mv mihomo /usr/local/bin/mihomo
```

> **Pitfall**: Direct download from github.com will timeout. Always use ghproxy.net or similar CN mirror.

### 2. Create config directory

```bash
sudo mkdir -p /etc/mihomo
```

### 3. Write config.yaml with split-routing

Key configuration points:

**Ports**: Use ONLY `mixed-port` OR `port`, not both set to the same value — they conflict and cause "address already in use" errors.
```yaml
mixed-port: 7890
socks-port: 7891
```

**Proxy-provider**: Point to the user's subscription URL
```yaml
proxy-providers:
  myprovider:
    type: http
    url: "https://your-subscription-url"
    interval: 86400
    health-check:
      enable: true
      url: http://www.gstatic.com/generate_204
      interval: 300
```

**Proxy group structure** — CRITICAL: Do NOT include `DIRECT` in the main proxy group's `proxies` list, or url-test will always select DIRECT (faster ping) and proxy won't work:
```yaml
proxy-groups:
  - name: 🚀 Proxy
    type: url-test
    use:
      - myprovider
    # NO 'proxies: [DIRECT]' here!
    url: http://www.gstatic.com/generate_204
    interval: 300
```

Instead, put DIRECT as a fallback in a separate group or as the Domestic group's primary:
```yaml
  - name: 🇨🇳 Domestic
    type: select
    proxies:
      - DIRECT
      - 🚀 Proxy
```

**Routing rules** — essential for Chinese servers:
```yaml
rules:
  # Internal/private IPs -> DIRECT (top priority)
  - IP-CIDR,127.0.0.0/8,DIRECT
  - IP-CIDR,10.0.0.0/8,DIRECT
  - IP-CIDR,172.16.0.0/12,DIRECT
  - IP-CIDR,192.168.0.0/16,DIRECT
  - IP-CIDR,100.64.0.0/10,DIRECT
  - IP-CIDR,9.0.0.0/8,DIRECT     # Tencent Cloud internal
  - IP-CIDR,169.254.0.0/16,DIRECT

  # Chinese cloud/mirror sites -> DIRECT
  - DOMAIN-SUFFIX,aliyun.com,DIRECT
  - DOMAIN-SUFFIX,tencent.com,DIRECT
  - DOMAIN-SUFFIX,qcloud.com,DIRECT
  - DOMAIN-SUFFIX,pypi.org,DIRECT
  - DOMAIN-SUFFIX,tsinghua.edu.cn,DIRECT
  - DOMAIN-SUFFIX,ustc.edu.cn,DIRECT
  - DOMAIN-SUFFIX,cn,DIRECT

  # Foreign blocked sites -> Proxy
  - DOMAIN-SUFFIX,google.com,📱 Google
  - DOMAIN-SUFFIX,github.com,🚀 Proxy
  - DOMAIN-SUFFIX,openai.com,🚀 Proxy
  # ... etc.

  # Chinese IP -> DIRECT
  - GEOIP,CN,🇨🇳 Domestic

  # Default -> Proxy
  - MATCH,🌍 Global
```

### 4. Handle GeoIP/Geosite database

mihomo auto-downloads MMDB and geosite.dat, but from Chinese VPS these downloads often fail (connection timeout). Pre-download them from mirror:

```bash
curl -sL "https://ghproxy.net/https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geoip.metadb" -o /tmp/geoip.metadb
sudo mv /tmp/geoip.metadb /etc/mihomo/geoip.metadb

curl -sL "https://ghproxy.net/https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geosite.dat" -o /tmp/geosite.dat
sudo mv /tmp/geosite.dat /etc/mihomo/geosite.dat
```

> **Pitfall**: If MMDB download fails, mihomo will crash with `fatal: Parse config error: rules[...] [GEOIP,CN,Domestic] error: can't download MMDB: context deadline exceeded`. Pre-download is essential.

### 5. Create systemd service

```ini
[Unit]
Description=Mihomo Proxy Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/mihomo -d /etc/mihomo
WorkingDirectory=/etc/mihomo
Restart=on-failure
RestartSec=5
LimitNOFILE=100000

[Install]
WantedBy=multi-user.target
```

Write to `/etc/systemd/system/mihomo.service` and enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable mihomo
sudo systemctl start mihomo
```

### 6. Verify

```bash
# Check service status
sudo systemctl status mihomo

# Test proxy (Baidu should work DIRECT)
curl -s --proxy http://127.0.0.1:7890 https://www.baidu.com -o /dev/null -w "%{http_code}"

# Test proxy (Google should go through proxy)
curl -s --proxy http://127.0.0.1:7890 https://www.google.com -o /dev/null -w "%{http_code}"

# Check which nodes are loaded
curl -s http://127.0.0.1:9090/proxies | python3 -m json.tool | head -50
```

### 7. User instructions

Tell the user to use the proxy in their terminal:
```bash
export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890
```

And to unset when not needed:
```bash
unset http_proxy https_proxy
```

## Common Pitfalls

1. **Port conflict**: Don't set both `port: 7890` and `mixed-port: 7890` — causes "address already in use" error. Use only `mixed-port`.

2. **DIRECT in url-test proxy group**: If a url-test group includes `DIRECT` as a fallback, mihomo will always prefer it (DIRECT has <1ms latency), defeating the proxy. Keep DIRECT out of proxy groups that should use proxy nodes.

3. **Stale mihomo process**: The first `mihomo version` or `mihomo` run (without -d flag) creates a default config in `~/.config/mihomo/` and may start listening on port 7890. Always kill all mihomo processes before starting the configured one.

4. **MMDB download failure**: GitHub hosted MMDB downloads timeout from China. Always pre-download via ghproxy mirror.

5. **Subscription health-check**: Proxy nodes might have delays of 200-400ms from China. That's normal. They won't be as fast as DIRECT but should still work for browsing/API access.

## Maintenance Commands

```bash
sudo systemctl status mihomo     # Status
sudo systemctl restart mihomo    # Restart
sudo journalctl -u mihomo -n 50  # View recent logs
curl http://127.0.0.1:9090/proxies  # API: view proxy nodes and groups
curl http://127.0.0.1:9090/version   # API: check version
```

## Accessing Foreign APIs Through the Proxy (Vision/AI)

Some AI/vision API providers block Chinese mainland VPS IPs (Tencent Cloud, Alibaba Cloud, etc.). Key findings:

### Groq API — Blocked from China IPs

Groq returns **"Forbidden"** when accessed directly from Tencent Cloud IPs. Must go through proxy:
```bash
export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890
```

As of April 2026, Groq has **decommissioned all vision models** (llama-3.2-11b-vision-preview, llama-3.2-90b-vision-preview). Only text models are available. Groq is NOT a viable option for vision/image analysis from Chinese servers.

### Google Gemini API — Free Tier Needs Billing

New Google AI Studio API keys may show "limit: 0" (quota exhausted) even on the free tier. This typically means the Google Cloud project needs a **billing account** linked (no charge — just identity verification for anti-abuse).

If you see `Quota exceeded for metric: ...generate_content_free_tier_requests, limit: 0`:
- Go to https://console.cloud.google.com/billing
- Link a payment method (free tier limits still apply, you won't be charged)
- The same API key will then work

Gemini API works through the proxy from Chinese servers.

### OpenAI / Anthropic APIs

These typically work from Chinese VPS without issues. No special proxy handling needed for access (though the requests themselves may go through proxy for speed).

### Configuring Docker to Use the Proxy

On Chinese servers, Docker can't pull images from ghcr.io or Docker Hub directly. Configure Docker daemon to use mihomo:

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
cat << 'EOF' | sudo tee /etc/systemd/system/docker.service.d/proxy.conf
[Service]
Environment="HTTP_PROXY=http://127.0.0.1:7890"
Environment="HTTPS_PROXY=http://127.0.0.1:7890"
Environment="NO_PROXY=localhost,127.0.0.1,::1"
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
# Verify
docker info | grep -i proxy
```

Now `docker pull ghcr.io/...` and `docker pull ...` will work through the proxy. This is essential for running Docker-based tools behind the proxy.

### Running Containers with Per-Container Proxy

For containers that need to reach BOTH local services (host machine) AND external services (proxy), daemon-level proxy causes issues. Use per-container proxy instead:

```bash
# Get Docker host gateway IP (172.17.0.1 typically)
docker network inspect bridge --format '{{(index .IPAM.Config 0).Gateway}}'
# → 172.17.0.1

# Run with per-container proxy — CRITICAL: set NO_PROXY for health checks
docker run -d \
  -p 3000:8080 \
  --add-host host.docker.internal:host-gateway \  # Linux: host.docker.internal doesn't exist without this
  --name my-container \
  -e HTTP_PROXY="http://172.17.0.1:7890" \
  -e HTTPS_PROXY="http://172.17.0.1:7890" \
  -e NO_PROXY="localhost,127.0.0.1,::1,172.17.0.1,host.docker.internal" \
  my-image
```

**Key pitfalls:**

1. **`host.docker.internal` on Linux**: Linux Docker does NOT have a built-in `host.docker.internal` DNS entry. Always add `--add-host host.docker.internal:host-gateway` to reach host services by name inside the container.

2. **Health checks fail through proxy**: If a container has HTTP_PROXY set but NO_PROXY doesn't include `localhost,127.0.0.1`, the health check command (e.g., `curl http://localhost:8080/health`) will try to go through the Mihomo proxy at 127.0.0.1:7890, which will fail. Always set `NO_PROXY=localhost,127.0.0.1,::1,172.17.0.1`.

3. **Connection hanging on startup**: Containers that try to reach external services (telemetry, model downloads, update checks) during initialization will hang indefinitely if the proxy isn't configured. Set HTTP_PROXY at container level (not daemon level) to limit scope.

4. **Port already in use**: Previous `docker run` attempts may leave ports bound via `docker-proxy`. Use `docker rm -f <name>` before retrying.

### Deploying Open WebUI with Proxy + Local Hermes API

Open WebUI is a common AI chat UI that needs to connect to a local OpenAI-compatible API (like Hermes Agent's API server on port 8642) while also reaching external resources through the proxy:

```bash
# Step 1: Pull the image (already in cache? check first)
docker images ghcr.io/open-webui/open-webui

# Step 2: Run with correct network and proxy settings
docker run -d \
  -p 3000:8080 \
  --add-host host.docker.internal:host-gateway \
  --name open-webui \
  -e OPENAI_API_BASE_URL="http://host.docker.internal:8642/v1" \
  -e OPENAI_API_KEY="your-api-key" \
  -e WEBUI_SECRET_KEY="generate-a-random-key" \
  -e ANONYMIZED_TELEMETRY=false \
  -e HTTP_PROXY="http://172.17.0.1:7890" \
  -e HTTPS_PROXY="http://172.17.0.1:7890" \
  -e NO_PROXY="localhost,127.0.0.1,::1,172.17.0.1,host.docker.internal" \
  ghcr.io/open-webui/open-webui:main
```

**Troubleshooting:**
- Container exits with code 255: Health check failure. Check NO_PROXY setting.
- Container shows "(health: starting)" for >30s: Uvicorn is hanging on startup. Check `docker logs` — if logs end at the banner, the app is stuck connecting to an external service. Set HTTP_PROXY.
- "Connection reset by peer" on port: Uvicorn hasn't started listening. Use `--no-healthcheck` as a temporary test to see full logs.
- `host.docker.internal` doesn't resolve inside container: Use `docker exec` to test with `python3 -c "import socket; print(socket.getaddrinfo('host.docker.internal', 8642))"`. If it fails, the `--add-host` flag is missing or Docker version doesn't support `host-gateway` (use `172.17.0.1` directly instead).

### Testing API Keys Through Proxy

Quick test pattern for any provider:
```bash
export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890

# List available models
curl -s --max-time 15 "https://api.groq.com/openai/v1/models" \
  -H "Authorization: Bearer $GROQ_API_KEY"

# Test a simple chat completion
curl -s --max-time 15 "https://api.groq.com/openai/v1/chat/completions" \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":"hi"}]}'
```

## Configuring Hermes Agent for Vision on China Servers

To enable vision/image analysis in Hermes Agent when the main model doesn't support it (e.g., DeepSeek), configure a separate auxiliary vision provider:

```bash
# Option 1: Gemini (requires billing setup on GCP)
hermes config set auxiliary.vision.provider google
hermes config set auxiliary.vision.model gemini-2.0-flash

# Option 2: OpenAI
hermes config set auxiliary.vision.provider openai
hermes config set auxiliary.vision.model gpt-4o-mini

# Option 3: OpenRouter (free tier — nvidia/nemotron-nano-12b-v2-vl:free)
# Get an API key from https://openrouter.ai/keys
hermes config set auxiliary.vision.provider openrouter
hermes config set auxiliary.vision.model nvidia/nemotron-nano-12b-v2-vl:free
hermes config set auxiliary.vision.model gpt-4o-mini
```

Set the corresponding API key in `~/.hermes/.env`:
```bash
echo "GOOGLE_API_KEY=your_key_here" >> ~/.hermes/.env
# or
echo "OPENAI_API_KEY=your_key_here" >> ~/.hermes/.env
```

> **Note**: The vision auxiliary model uses a **different provider** than the main chat model. Available auxiliary providers: `google`, `openai`, `anthropic`, `groq` (text only), `auto` (auto-detect from available keys).

> **Pitfall**: The `auto` provider for auxiliary vision may silently fail if no vision-capable API key is configured. Always test explicitly:
> ```bash
> export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890
> # Test Gemini via proxy
> curl -s "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=$GOOGLE_API_KEY" \
>   -H "Content-Type: application/json" \
>   -d '{"contents":[{"parts":[{"text":"ok"}]}]}'
> ```

## Using a Browser Through the Proxy

### Headless Chromium (CLI)

From the terminal, Chromium can use the proxy via `--proxy-server` flag. This works for headless rendering, screenshots, and DOM extraction:

```bash
# Dump page HTML (like curl but renders JS)
chromium-browser --headless --no-sandbox --proxy-server="http://127.0.0.1:7890" --dump-dom https://gemini.google.com

# Take a screenshot
chromium-browser --headless --no-sandbox --proxy-server="http://127.0.0.1:7890" --screenshot=/tmp/gemini.png --window-size=1280,800 https://gemini.google.com

# Open interactive (if server has a display/X11 forwarding)
chromium-browser --proxy-server="http://127.0.0.1:7890" https://gemini.google.com
```

### Hermes Agent's `browser_navigate` tool

The built-in `browser_navigate` tool does NOT inherit shell proxy environment variables. It will timeout trying to access blocked foreign sites. Workaround: use headless Chromium from terminal as shown above.

### Proxy Group Naming Convention

Use emoji prefixes for proxy group names — they render well in mihomo dashboard and API responses:

| Group | Name | Purpose |
|-------|------|---------|
| 🚀 Proxy | url-test proxy nodes only | Main outbound group, no DIRECT |
| 🎯 Auto-Select | fallback: proxy or direct | Automatic selector |
| 🌍 Global | select: proxy/auto/direct | Catch-all for unmatched traffic |
| 🇨🇳 Domestic | select: direct/proxy | Chinese traffic |
| 📱 Google | select: proxy or auto | Google/Gemini services |
| 💬 Telegram | select: proxy or auto | Telegram |
| 🎬 Netflix | select: proxy or auto | Netflix |

> **CRITICAL**: In `url-test` type groups (like 🚀 Proxy), do NOT include `DIRECT` in the `proxies` list. If DIRECT is present, url-test will always select it (sub-1ms vs 200-400ms proxy latency), defeating the proxy. Put DIRECT only in `select` groups like 🇨🇳 Domestic.
