#!/bin/bash
# Auto-sync Hermes Agent persistent memory to GitHub
export https_proxy=http://127.0.0.1:7890
export http_proxy=http://127.0.0.1:7890

cd /root/hermes-memory-backup

# Copy latest memory files
cp /root/.hermes/memories/MEMORY.md ./MEMORY.md
cp /root/.hermes/memories/USER.md ./USER.md

# Check if anything changed
if git diff --quiet; then
    exit 0
fi

# Commit and push
git add MEMORY.md USER.md
git commit -m "sync: memory update $(date '+%Y-%m-%d %H:%M')"
git push
