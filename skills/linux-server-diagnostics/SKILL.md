---
name: linux-server-diagnostics
description: Diagnose and remedy Linux server performance issues — memory pressure, high load, disk space exhaustion. Targeted at memory-constrained headless servers (3-4GB RAM) running Docker, Chrome, Hermes Agent, and other services.
category: devops
when_to_use: |
  User reports system lag/slowness/crashes on a Linux server.
  Any complaint about "卡" (lag), high load, OOM kills, or disk full.
  Proactive health check before deploying new services on a constrained machine.
triggers:
  - user says system is slow/卡/laggy
  - user asks about memory or disk usage
  - before deploying new services on a memory-constrained server
  - routine server health check
---

# Linux Server Diagnostics

A systematic workflow for diagnosing and fixing performance issues on Linux servers, especially memory-constrained (3-4GB) headless servers running Docker, Chromium, and AI agent services.

## Phase 1: Quick Health Check

Run these in parallel to get baseline:

```bash
# Memory
free -h

# Load + iowait
uptime

# CPU/memory top consumers
ps aux --sort=-%mem | head -15

# Disk space
df -h /

# Top disk consumers
du -h --max-depth=1 / 2>/dev/null | sort -rh | head -15
```

### Key Metrics to Interpret

| Metric | Warning | Critical |
|--------|---------|----------|
| available memory | < 500MB | < 100MB |
| load average | > CPU cores × 2 | > CPU cores × 5 |
| iowait | > 10% | > 30% |
| disk usage | > 80% | > 90% |

- `kswapd0` consuming CPU → memory exhausted, system thrashing
- iowait high + low memory → probable swap thrashing (or no swap configured)

## Phase 2: Memory Deep Dive

If memory is low:

```bash
# Full process memory ranking
ps aux --sort=-%mem | awk '{print $4"%", $6/1024"MB", $11, $2}'

# Check swap (if configured)
swapon --show

# Check for OOM kills
dmesg | grep -i "out of memory" | tail -5
```

### Common Memory Hogs on This Server

1. **Chromium/Chrome** — Renderer processes accumulate over days. Each renderer 70-150MB. Browser stays open for remote debugging. **Fix:** `pkill -f chromium-browser` kills all instantly.
2. **Hermes Agent gateway** — ~400-500MB baseline, normal.
3. **Open WebUI** — ~600MB with uvicorn workers.
4. **Docker containers** — Each adds overhead.

### When to Kill Chrome

Chrome on this server is used for browser-based login (cookie injection, SMS login) and remote debugging. It's not needed continuously. Kill it when:
- User reports lag
- Available memory < 200MB
- Chrome has been running > 24 hours (renderer leak accumulation)

```bash
# Kill all chromium processes (main + all renderers)
pkill -f chromium-browser

# Verify
pgrep -c chromium-browser  # should be 0
```

## Phase 3: Disk Space Deep Dive

If disk > 80% used:

```bash
# Drill into /var
du -h --max-depth=1 /var 2>/dev/null | sort -rh | head -10

# Drill into /root
du -h --max-depth=1 /root 2>/dev/null | sort -rh | head -10

# Docker space
docker system df

# Log space
du -h --max-depth=1 /var/log 2>/dev/null | sort -rh | head -5
```

### Common Disk Hogs

| Location | Typical Size | Reclaimable? |
|----------|-------------|--------------|
| `/var/lib/containerd` | 9-15GB | Docker images/containers |
| `/var/lib/docker` | 5-10GB | Docker overlay filesystem |
| `/var/log/journal` | 1-3GB | ✅ Yes — systemd logs |
| `/root/.gradle` | 500-800MB | ✅ Yes — Android build cache |
| `/root/.cache` | 500-800MB | ✅ Yes — general cache |
| `/root/.npm` | 200-300MB | ✅ Yes — npm cache |

### Safe Cleanup Commands

```bash
# 1. Clean systemd journal to 500MB
journalctl --vacuum-size=500M

# 2. Clean npm cache
npm cache clean --force 2>/dev/null || true

# 3. Clean Gradle cache (if not actively building)
rm -rf /root/.gradle/caches/* 2>/dev/null || true

# 4. Clean .cache (safe — apt/pip/yarn caches rebuild)
rm -rf /root/.cache/* 2>/dev/null || true

# 5. Docker prune (caution — removes unused images/containers)
docker system prune -f --volumes 2>/dev/null || true
# More aggressive: docker system prune -a -f  # removes all unused images
```

## Phase 4: Long-term Fixes

### Add Swap (if no swap configured)
Critical for servers with < 4GB RAM running Docker + Chrome:

```bash
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### Configure Chrome to Use Less Memory
If Chrome must stay running:
- Limit renderer processes: start with `--renderer-process-limit=1`
- Use `--disable-gpu` and `--disable-software-rasterizer`

### Schedule Regular Cleanup
For servers running 24/7:
- Cron job to restart Chrome daily
- Cron job to vacuum journal weekly
- Monitor with `free -h` + `df -h` sent as alert

## Pitfalls

- **Don't kill Hermes Agent gateway** (PID 1918681+) — it's critical for agent operation. The current CLI session (~300MB) also belongs to Hermes.
- **Don't `docker system prune -a` blindly** — if Docker images are actively used (NapCat, etc.), check with `docker images` first. Use `docker system prune` (no -a) for safe cleanup.
- **Chrome auto-restart** — some setups monitor Chrome and restart it. If Chrome comes back immediately after kill, check for a systemd service or restart script.
- **`kill` vs `pkill`** — `kill <PID>` kills only the main process; renderer children may survive. `pkill -f chromium-browser` kills all matching processes.
- **Open WebUI** on port 8080 may conflict with other services. Check before stopping.
- **QQ desktop client** runs as a process (~60MB) — it's unusual on a server, check if intentional before killing.
- **Tencent Cloud YunJing (YDService)** — vendor monitoring agent, ~70MB. Do not kill.
