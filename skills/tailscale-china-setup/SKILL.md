---
name: tailscale-china-setup
description: Install and configure Tailscale on Chinese mainland Linux servers where standard package repos may be unreliable (broken aliyun mirrors, DNS issues, etc.). Covers proxy-bypassed installation, auth flow, and connectivity verification.
category: devops
tags: [tailscale, vpn, tunnel, ssh, networking, china-mainland, proxy]
---

# Tailscale Setup on Chinese Mainland Servers

Install Tailscale on a Chinese mainland cloud server (Tencent Cloud, Alibaba Cloud, etc.) to enable direct SSH access from your local machine without exposing public ports.

## When to Use

- User wants Tailscale SSH access to a Chinese mainland server
- Standard package repos (aliyun mirrors, centos/pypi/etc.) are broken or returning HTML
- Server is behind the Great Firewall and needs proxy to reach foreign domains
- Goal is to avoid opening public security group ports for SSH

## Setup Steps

### 1. Install Tailscale

Set proxy first since tailscale.com is blocked in China:

```bash
export https_proxy=http://127.0.0.1:7890
curl -fsSL https://tailscale.com/install.sh | sh
```

On CentOS Stream 9, this script:
- Adds Tailscale's official repo (`/etc/yum.repos.d/tailscale.repo`)
- Installs the `tailscale` package via dnf
- Enables and starts `tailscaled` service via systemd

**Pitfall**: If dnf repos are broken (aliyun mirrors returning HTML instead of repomd.xml), the script may still work because it adds a fresh repo from Tailscale and only downloads from there. If even dnf base metadata refresh fails, disable broken repos first:
```bash
dnf config-manager --set-disabled powertools
```

### 2. Authenticate

```bash
sudo tailscale up
```

This outputs an auth URL like:
```
https://login.tailscale.com/a/XXXX
```

The user MUST open this URL in their browser and log in with their Google account (or whatever SSO they use for Tailscale). Once authenticated, the terminal will show the connection established.

**Design note**: `tailscale up` blocks until auth completes or times out (~60s default). Tell the user to open the URL and come back.

### 3. Verify Connectivity

```bash
# Check connected peers
tailscale status

# Get this server's Tailscale IP
tailscale ip
```

Expected output shows all machines in the same Tailnet:
```
100.xx.xx.xx  vm-name    user@  linux  -
100.yy.yy.yy  local-pc   user@  linux  -
```

### 4. Test Connection

From the local machine, SSH via Tailscale IP:
```bash
ssh user@100.xx.xx.xx
```

Or verify with ping from server to local machine:
```bash
ping -c 3 100.yy.yy.yy
```

## Common Pitfalls

- **Broken aliyun mirrors**: If dnf metadata refresh fails, the install script's `dnf config-manager --add-repo` step still works because it adds Tailscale's official repo separately. The script may succeed even when aliyun repos are broken.
- **Tailscale install.sh 404 on RPM**: Direct RPM download URLs like `https://pkgs.tailscale.com/stable/centos/9/tailscale-latest.x86_64.rpm` may return 404. Always use the install script instead.
- **Auth timeout**: `tailscale up` times out after ~60s if user doesn't authenticate. Just re-run it.
- **Both machines need same Tailnet account**: Both machines must be logged into the same Tailscale account (same Google/SSO email) to see each other.
- **Firewall rules**: Tailscale uses port 41641/UDP for WireGuard. On some restrictive cloud environments, ensure outbound UDP to Tailscale's DERP relays is not blocked.
- **Proxy required for install**: The install script needs to fetch from pkgs.tailscale.com (AWS CloudFront), which is blocked in China. Always set `https_proxy=http://127.0.0.1:7890` before running the script.
- **After install, proxy not needed**: Tailscale itself uses direct WireGuard connections and doesn't require proxy for ongoing operation.

## Verification

After setup, confirm:
1. `tailscale status` shows both machines in the same Tailnet
2. `ping <peer-ip>` succeeds (latency may be high via DERP relays initially, improves after direct connection)
3. SSH connection works from either direction (if SSH keys are set up)
