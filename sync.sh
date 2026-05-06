#!/bin/bash
# Auto-sync Hermes Agent persistent memory to GitHub (bidirectional)
export https_proxy=http://127.0.0.1:7890
export http_proxy=http://127.0.0.1:7890

cd /root/hermes-memory-backup

# ── 1. Pull latest from GitHub first ──
git pull --no-edit origin main 2>/dev/null || true

# ── 2. Copy latest local files ──
cp /root/.hermes/memories/MEMORY.md ./MEMORY.md
cp /root/.hermes/memories/USER.md ./USER.md

# Copy daily memories
cp -r /root/daily-memories/. ./daily-memories/ 2>/dev/null || true

# Copy Hermes Agent core system files
cp /root/.hermes/hermes-agent/AGENTS.md ./AGENTS.md
cp /root/.hermes/hermes-agent/README.md ./README.md
cp /root/.hermes/hermes-agent/CONTRIBUTING.md ./CONTRIBUTING.md
cp /root/.hermes/SOUL.md ./SOUL.md

# Copy all Hermes skills (SKILL.md files) to repo
for skill_dir in /root/.hermes/skills/*/*/; do
    skill_name=$(basename "$skill_dir")
    mkdir -p "./skills/$skill_name"
    cp "$skill_dir/SKILL.md" "./skills/$skill_name/SKILL.md" 2>/dev/null || true
done


# ── IM App (清云) sync ──
# Core app files
cp /root/webui/app.py ./im-app/app.py
cp /root/webui/build_spa.py ./im-app/build_spa.py
cp /root/webui/gen_new_splash.py ./im-app/gen_new_splash.py
cp /root/webui/gen_android_icons.py ./im-app/gen_android_icons.py
cp /root/webui/index.html ./im-app/index.html

# Templates
mkdir -p ./im-app/templates
for f in chat login settings models memories disk; do
    cp /root/webui/templates/${f}.html ./im-app/templates/${f}.html 2>/dev/null || true
done

# Static
mkdir -p ./im-app/static
cp /root/webui/static/sw.js ./im-app/static/sw.js 2>/dev/null || true
cp /root/webui/static/spa-nav.js ./im-app/static/spa-nav.js 2>/dev/null || true
cp /root/webui/static/manifest.json ./im-app/static/manifest.json 2>/dev/null || true

# Capacitor configs
mkdir -p ./im-app/capacitor/www
cp /root/webui/capacitor/android/app/src/main/assets/capacitor.config.json ./im-app/capacitor/ 2>/dev/null || true
cp /root/webui/capacitor/android/app/src/main/assets/capacitor.plugins.json ./im-app/capacitor/ 2>/dev/null || true
cp /root/webui/capacitor/android/app/src/main/res/xml/config.xml ./im-app/capacitor/ 2>/dev/null || true
cp /root/webui/capacitor/www/index.html ./im-app/capacitor/www/ 2>/dev/null || true

# Copy user data (per-user chats & providers)
cp -r ./users/. ./users/ 2>/dev/null || true

# ── 3. After copying, also copy back any GitHub-side changes ──
# (If someone edited MEMORY.md/USER.md on GitHub, overwrite local)
if [ -f ./MEMORY.md ]; then
    cp ./MEMORY.md /root/.hermes/memories/MEMORY.md
fi
if [ -f ./USER.md ]; then
    cp ./USER.md /root/.hermes/memories/USER.md
fi

# ── 4. Check if anything changed ──
if git diff --quiet; then
    exit 0
fi

# ── 5. Commit and push ──
git add MEMORY.md USER.md AGENTS.md README.md CONTRIBUTING.md SOUL.md skills/ daily-memories/ users/ im-app/
git commit -m "sync: memory + skills update $(date '+%Y-%m-%d %H:%M')"
git push
