---
name: github-auto-sync
description: "Set up automatic git commit+push sync of local files to a GitHub repository — via cron or Hermes Plugin (on_session_end). Handles Chinese server proxy, credential persistence, deduplicating identical commits, and expanding scope to include Hermes Agent system files (AGENTS.md, README.md, CONTRIBUTING.md, SOUL.md) alongside user memory files."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [GitHub, Auto-Sync, Cron, Backup, Git, Automation]
    related_skills: [github-auth, github-repo-management]
---

# GitHub Auto-Sync: Local Files → GitHub Repo

Set up automatic git commit+push of specific local files to a GitHub repository. Designed for backing up Hermes Agent persistent memory (MEMORY.md, USER.md), but works for any small set of tracked files.

## When to Use

A user wants to:
- "Auto-sync my Hermes memory to GitHub"
- "Sync Hermes Agent core system files (AGENTS.md, SOUL.md) to GitHub"
- "Automatically backup these config files to a repo"
- "Set up periodic git push of local notes/changes"
- "Keep MEMORY.md and USER.md synced to GitHub"
- "Add more files to an existing auto-sync setup"
- "Expand what gets synced beyond just memory files"
- "Sync all my Hermes skills (SKILL.md files) to GitHub automatically"
- "Back up the skills I've accumulated to a repo so they're never lost"

## Prerequisites

- Git installed (`which git`)
- GitHub authentication set up — see `github-auth` skill for options OR embed PAT in remote URL (see Prerequisites: PAT Types below)
- The target GitHub repo already exists (see `github-repo-management` skill to create one)

## Prerequisites: PAT Types

**Classic PAT** (starts with `ghp_`): Grant `repo` scope for private repos or `public_repo` for public repos. Works immediately.

**Fine-grained PAT** (starts with `github_pat_`): Requires TWO additional steps on https://github.com/settings/tokens:
1. **Repository access** → "Only select repositories" → add the target repo
2. **Repository permissions** → **Contents** → "Read and Write"

If you get `remote: Permission to <user>/<repo>.git denied` after cloning, it's almost always because the fine-grained PAT hasn't been authorized for that specific repo.

## Two Sync Trigger Options

You can trigger sync via either:
- **Option A: Cron** (periodic, e.g. every 5/30 minutes) — see Step 4A below
- **Option B: Hermes Plugin on_session_end** (syncs after each conversation ends, no polling) — see Step 4B below

**Recommendation:** Use Option B (plugin) for Hermes Agent sync — it's more responsive and avoids unnecessary commits when no conversations happen. Use Option A (cron) if you want fixed-interval sync regardless of agent activity.

## Setup Flow

### Step 1: Create a local git repo for the files

If the files aren't already in a git repo:

```bash
# Create a dedicated directory for the sync
mkdir -p ~/github-sync/hermes-memory
cd ~/github-sync/hermes-memory

# Initialize a git repo
git init

# Set up git identity if not already set globally
git config user.name "Hermes Agent"
git config user.email "hermes@nousresearch.com"
```

### Step 2: Copy (or symlink) the files to track

**Option A: Symlink** (always reflects live changes, no copy step)

```bash
ln -sf /root/.hermes/memories/MEMORY.md .
ln -sf /root/.hermes/memories/USER.md .
```

**Option B: Copy script** (manual copies, more control)

Create a script that copies the latest versions before committing.

### Step 3: Connect to GitHub remote

```bash
git remote add origin https://github.com/<username>/<repo-name>.git
git add .
git commit -m "Initial sync of memory files"
git push -u origin main
```

If the remote has existing content, pull first with `--allow-unrelated-histories`:

```bash
git pull origin main --allow-unrelated-histories --no-edit
git push -u origin main
```

### Step 4B: Auto-sync via Hermes Plugin (on_session_end)

Instead of cron, create a Hermes Agent plugin that runs the sync script automatically after every conversation ends.

**Create the plugin directory:**

```bash
mkdir -p ~/.hermes/hermes-agent/plugins/github-sync
```

**Create `plugin.yaml`:**

```yaml
name: github-sync
version: 1.0.0
description: "Sync Hermes memory, system files, and skills to GitHub on session end."
author: "user"
hooks:
  - on_session_end
```

**Create `__init__.py`:**

```python
\"\"\"github-sync plugin — sync to GitHub on session end.\"\"\"

from __future__ import annotations

import logging
import subprocess
import os
from typing import Any

logger = logging.getLogger(__name__)

SYNC_SCRIPT = os.path.expanduser("<SYNC_SCRIPT_PATH>")


def _on_session_end(
    session_id: str = "",
    completed: bool = True,
    interrupted: bool = False,
    **_: Any,
) -> None:
    try:
        result = subprocess.run(
            ["bash", SYNC_SCRIPT],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            logger.info("github-sync: pushed to GitHub successfully")
        else:
            logger.warning("github-sync: exit code %d — %s", result.returncode, result.stderr.strip())
    except subprocess.TimeoutExpired:
        logger.warning("github-sync: timed out after 120s")
    except Exception as exc:
        logger.debug("github-sync: error — %s", exc)


def register(ctx) -> None:
    ctx.register_hook("on_session_end", _on_session_end)
```

Replace `<SYNC_SCRIPT_PATH>` with the actual path to your sync script (e.g. `/root/hermes-memory-backup/sync.sh`).

**Enable the plugin:**

```bash
cd ~/.hermes/hermes-agent && source venv/bin/activate
hermes plugins enable github-sync
```

The plugin takes effect on the **next session** start. Each conversation end will trigger the sync.

**If migrating from cron to plugin:** Remove the old cron entry:

```bash
rm /etc/cron.d/hermes-memory-sync   # if using /etc/cron.d/
# OR
crontab -e   # and remove the line
```

### Step 4A: Auto-sync via Cron

Two approaches — **Crontab one-liner** (simpler) or **Standalone script** (more maintainable).

**Option A: Crontab one-liner** (simpler, inline commands)

```bash
# Edit crontab
crontab -e
```

Add this line for a 5-minute interval:

```cron
*/5 * * * * cd /root/github-sync/hermes-memory && git add -A && git diff --quiet && git diff --staged --quiet || (git commit -m "auto-sync $(date '+%Y-%m-%d %H:%M')" && git push origin main 2>&1 | grep -v "Everything up-to-date")
```

**What this does:**
- `cd` to the repo directory
- `git add -A` — stage all changes
- `git diff --quiet && git diff --staged --quiet` — return 0 only if nothing changed (no commit if no changes)
- `|| (...)` — if something changed, commit with timestamp message and push
- The `grep -v "Everything up-to-date"` suppresses the "nothing to push" noise

**For Chinese servers that need proxy**, add proxy to the cron command:

```cron
*/5 * * * * export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890; cd /root/github-sync/hermes-memory && git add -A && git diff --quiet && git diff --staged --quiet || (git commit -m "auto-sync $(date '+%Y-%m-%d %H:%M')" && git push origin main 2>&1 | grep -v "Everything up-to-date")
```

**Option B: Standalone script** (more maintainable, easier to debug)

Create a script in the repo directory:

```bash
cat > /root/github-sync/hermes-memory/sync.sh << 'SCRIPT'
#!/bin/bash
# Auto-sync script — copies files, checks changes, commits and pushes
export https_proxy=http://127.0.0.1:7890
export http_proxy=http://127.0.0.1:7890

cd /root/github-sync/hermes-memory

# Copy source files (adjust paths as needed)
cp /root/.hermes/memories/MEMORY.md ./MEMORY.md
cp /root/.hermes/memories/USER.md ./USER.md

# Optional: copy Hermes Agent core system files
# cp /root/.hermes/hermes-agent/AGENTS.md ./AGENTS.md
# cp /root/.hermes/hermes-agent/README.md ./README.md
# cp /root/.hermes/hermes-agent/CONTRIBUTING.md ./CONTRIBUTING.md
# cp /root/.hermes/SOUL.md ./SOUL.md

# Optional: copy all Hermes skills (SKILL.md files) to skills/ dir
# for skill_dir in /root/.hermes/skills/*/*/; do
#     skill_name=$(basename "$skill_dir")
#     mkdir -p "./skills/$skill_name"
#     cp "$skill_dir/SKILL.md" "./skills/$skill_name/SKILL.md" 2>/dev/null || true
# done

# Check if anything changed
if git diff --quiet; then
    exit 0
fi

# Commit and push
git add MEMORY.md USER.md  # add AGENTS.md README.md CONTRIBUTING.md SOUL.md skills/ if syncing system files + skills
git commit -m "sync: auto-update $(date '+%Y-%m-%d %H:%M')"
git push
SCRIPT
chmod +x /root/github-sync/hermes-memory/sync.sh
```

Then set up cron via `/etc/cron.d/` (system-wide, survives reboot):

```bash
echo "*/30 * * * * root /root/github-sync/hermes-memory/sync.sh" > /etc/cron.d/hermes-memory-sync
```

### Step 5: Verify it works

```bash
# Check the cron job was added
crontab -l

# Force a manual test
cd /root/github-sync/hermes-memory
git add -A
git diff --quiet && git diff --staged --quiet || (git commit -m "manual test $(date '+%Y-%m-%d %H:%M')" && git push origin main)

# View the repo online
echo "https://github.com/<username>/<repo-name>"
```

## Important: Symlinked Files & Git Behavior

Git tracks the **content** of symlinked files, not the symlink itself (unless you use `git add --no-dereference`). This means:
- When MEMORY.md changes on disk → `git add -A` picks up the content change via the symlink → commit + push
- This is exactly what you want for auto-sync

If you use hardlinks (`ln`) or copies, behavior is the same.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `fatal: could not read Username for 'https://github.com'` | Git credential helper not set. Run: `git config --global credential.helper store` then do one manual push to cache the token. OR embed the token directly in the remote URL: `git remote set-url origin https://USERNAME:PAT@github.com/USER/REPO.git` — this is the simplest approach for cron automation (no interactive auth needed) |
| `remote: Invalid username or password` | Token expired or wrong scope. Generate a new PAT at https://github.com/settings/tokens with `repo` scope |
| Push fails: `[remote rejected]` | Branch protection rules. Push to a different branch or disable protection |
| Cron not executing | Check with `grep CRON /var/log/syslog` or `journalctl -u cron` — common issues: proxy not set, PATH not set (add `PATH=/usr/bin:/bin` at top of crontab) |
| `Everything up-to-date` but changes exist | The `git diff --quiet` check before commit might have an issue. Manually run the commands to debug |
| GitHub access via proxy | For Tencent Cloud / Alibaba Cloud servers, export proxy env vars before the push command (see cron example above) |
| Many small commits cluttering history | Increase cron interval (e.g., `*/30 * * * *` for every 30 minutes) |
| File too large | Git has a 100MB file limit by default. These files are typically tiny (1-3KB) — not an issue |

## Bidirectional Sync (Pull Before Push)

The basic setup above is one-directional (local → GitHub). For bidirectional sync (pull latest from GitHub, then push local changes):

**Add `git pull` before the copy-and-push steps in your sync script:**

```bash
#!/bin/bash
export https_proxy=http://127.0.0.1:7890
export http_proxy=http://127.0.0.1:7890

cd /root/github-sync/hermes-memory

# ── 1. Pull latest from GitHub first ──
git pull --no-edit origin main 2>/dev/null || true

# ── 2. Copy latest local files (overwrite GitHub versions) ──
cp /root/.hermes/memories/MEMORY.md ./MEMORY.md
cp /root/.hermes/memories/USER.md ./USER.md

# ── 3. Copy back any GitHub-side changes to local ──
# If someone edited MEMORY.md/USER.md on GitHub, overwrite local
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
git add MEMORY.md USER.md
git commit -m "sync: auto-update $(date '+%Y-%m-%d %H:%M')"
git push
```

**The key addition is step 3** — copying GitHub-side changes back to the local Hermes memory files. This ensures that if someone pushed changes to GitHub from another machine or the web UI, those changes propagate back to the local server.

**When to use bidirectional sync:**
- You or others edit memory files from multiple machines
- You use GitHub's web UI (edit-on-web) to update memory
- The memory files are shared across development/production environments
- You want to be able to roll back by pushing an older version from another clone

**Caveats:**
- Step 1 (`git pull`) may fail if there are uncommitted local changes. The `2>/dev/null || true` swallows merge conflicts. For simple text files (MEMORY.md, USER.md), this is usually fine — the copy in step 2 overwrites any conflicts.
- If there are genuine conflicts (same line edited differently in local vs remote), the later `git push` may be rejected. In that case, manually resolve: `cd /root/github-sync/hermes-memory && git status && git mergetool`.

This sets up everything in one go:

```bash
mkdir -p ~/github-sync/hermes-memory && cd ~/github-sync/hermes-memory && git init && git config user.name "Hermes Agent" && git config user.email "hermes@nousresearch.com" && ln -sf /root/.hermes/memories/MEMORY.md . && ln -sf /root/.hermes/memories/USER.md . && git remote add origin https://github.com/<USER>/<REPO>.git && git add -A && git commit -m "initial sync" && git push -u origin main
```

Then set up cron with `crontab -e`.
