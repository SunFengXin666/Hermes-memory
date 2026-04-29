#!/bin/bash
# Auto-sync Hermes Agent persistent memory to GitHub
export https_proxy=http://127.0.0.1:7890
export http_proxy=http://127.0.0.1:7890

cd /root/hermes-memory-backup

# Copy latest memory files
cp /root/.hermes/memories/MEMORY.md ./MEMORY.md
cp /root/.hermes/memories/USER.md ./USER.md

# Copy all Hermes skills (SKILL.md files) to repo
for skill_dir in /root/.hermes/skills/*/*/; do
    skill_name=$(basename "$skill_dir")
    mkdir -p "./skills/$skill_name"
    cp "$skill_dir/SKILL.md" "./skills/$skill_name/SKILL.md" 2>/dev/null || true
done

# Check if anything changed
if git diff --quiet; then
    exit 0
fi

# Commit and push
git add MEMORY.md USER.md skills/
git commit -m "sync: memory + skills update $(date '+%Y-%m-%d %H:%M')"
git push
