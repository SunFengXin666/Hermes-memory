#!/usr/bin/env python3
"""轻量每日记忆查看器"""
import json
import os
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

MEMORIES_DIR = Path(os.path.expanduser("~/daily-memories"))
PORT = int(os.environ.get("PORT", 8080))
os.chdir(str(MEMORIES_DIR))

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(MEMORIES_DIR), **kwargs)
    def log_message(self, format, *args):
        print(f"[memories] {args[0]} {args[1]} {args[2]}")

# Generate list.json on startup
files = sorted([f.stem for f in MEMORIES_DIR.glob("*.md")], reverse=True)
(MEMORIES_DIR / "list.json").write_text(json.dumps(files))
print(f"[memories] {len(files)} daily memories found")

server = HTTPServer(("0.0.0.0", PORT), Handler)
print(f"[memories] Serving on http://0.0.0.0:{PORT}")
server.serve_forever()
