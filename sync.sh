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
git add MEMORY.md USER.md AGENTS.md README.md CONTRIBUTING.md SOUL.md skills/
git commit -m "sync: memory + skills update $(date '+%Y-%m-%d %H:%M')"
git push
