# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "python-dotenv"
# ]
# ///

import os
import subprocess
import time
import difflib
import tempfile
from datetime import datetime
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

# ==== CONFIG ====
DIR_PATH = "/tank/encrypted/docker/nextcloud-zfs/nextcloud/data/__groupfolders/1/Sermons/Raw Upload"
MODE = "ssh"  # "local" or "ssh"
SSH_USER = "nic"
SSH_HOST = "ghost"

LOG_DIR = Path.home() / ".local/state/sermon-monitor"
LOG_FILE = LOG_DIR / "sermon-monitor.log"
MAX_LOG_SIZE = 1024 * 1024  # 1MB
TEMP_FILE = Path(tempfile.gettempdir()) / "sermon-monitor-prev.txt"

GOTIFY_URL = os.getenv("GOTIFY_URL", "http://gotify.local/message")
GOTIFY_TOKEN = os.getenv("GOTIFY_TOKEN", "")
CHECK_INTERVAL = 30  # seconds
# =================


def log(msg: str):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_LOG_SIZE:
        with LOG_FILE.open("r") as f:
            last_lines = f.readlines()[-20:]
        with LOG_FILE.open("w") as f:
            f.writelines(last_lines)
        print(f"{ts()} - Log rotated")
    with LOG_FILE.open("a") as f:
        f.write(f"{ts()} - {msg}\n")
    print(f"{ts()} - {msg}")


def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_listing() -> list[str]:
    if MODE == "ssh":
        cmd = [
            "ssh",
            f"{SSH_USER}@{SSH_HOST}",
            f"ls -la '{DIR_PATH}' | grep -v '^\\.'",
        ]
    else:
        if not Path(DIR_PATH).is_dir():
            return [f"Error: Directory {DIR_PATH} not found"]
        cmd = ["bash", "-c", f"ls -la '{DIR_PATH}' | grep -v '^\\.'"]

    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        return [line for line in out.splitlines() if line.strip()]
    except subprocess.CalledProcessError:
        return [f"Error: Unable to list {DIR_PATH}"]


def send_gotify(title: str, message: str):
    if not GOTIFY_TOKEN:
        log("GOTIFY_TOKEN not set, skipping notification")
        return
    try:
        r = requests.post(
            GOTIFY_URL,
            headers={"X-Gotify-Key": GOTIFY_TOKEN},
            data={"title": title, "message": message, "priority": 5},
            timeout=5,
        )
        r.raise_for_status()
    except Exception as e:
        log(f"Gotify send failed: {e}")


def detect_new_files(prev: list[str], curr: list[str]) -> list[str]:
    diff = difflib.unified_diff(prev, curr)
    added = [
        line[1:].strip()
        for line in diff
        if line.startswith("+") and not line.startswith("+++")
    ]
    # Only keep .mp3 files
    mp3s = []
    for line in added:
        parts = line.split()
        if len(parts) >= 9:
            filename = parts[-1]
            if filename.lower().endswith(".mp3"):
                mp3s.append(filename)
    return sorted(set(mp3s))


def main():
    log(f"Starting sermon monitor in {MODE.upper()} mode for {DIR_PATH}")
    prev = get_listing()
    TEMP_FILE.write_text("\n".join(prev))
    log("Initial state captured. Watching for changes...")

    while True:
        time.sleep(CHECK_INTERVAL)
        curr = get_listing()
        new_files = detect_new_files(prev, curr)

        if new_files:
            count = len(new_files)
            if count == 1:
                title = "New Sermon File Added"
                message = f"New sermon file detected: {new_files[0]}"
            else:
                title = "New Sermon Files Added"
                message = f"{count} new sermon files detected:\n" + "\n".join(new_files)
            send_gotify(title, message)
            log(f"Notification sent for {count} new file(s)")
            prev = curr
            TEMP_FILE.write_text("\n".join(curr))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped by user")
