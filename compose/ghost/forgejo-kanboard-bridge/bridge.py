#!/usr/bin/env python3
"""Forgejo → Kanboard mirror.

Receives Forgejo issue webhooks (X-Gitea-Signature HMAC) and mirrors each
issue as a Kanboard card: opened → card in the mapped board's first column,
edited → title/description sync, closed → card closed (drops off board),
reopened → card reopens in the first column.

Dedup is stateless: the card's `reference` field stores "forgejo:<repo>#<n>"
and lookups scan the board's open tasks for that reference.

POST /sync — backfill: mirror every open issue on every repo the webhook
covers (uses the Forgejo API token).

Config via env: KANBOARD_URL, KANBOARD_TOKEN, FORGEJO_API_URL,
FORGEJO_TOKEN, FORGEJO_WEBHOOK_SECRET, REPO_MAP (JSON glob→project_id),
DEFAULT_PROJECT.
"""
import fnmatch
import hashlib
import hmac
import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

KANBOARD_URL = os.environ["KANBOARD_URL"].rstrip("/")
KANBOARD_TOKEN = os.environ["KANBOARD_TOKEN"]
FORGEJO_API = os.environ["FORGEJO_API_URL"].rstrip("/")  # https://git.paynepride.com/api/v1
FORGEJO_TOKEN = os.environ["FORGEJO_TOKEN"]
WEBHOOK_SECRET = os.environ["FORGEJO_WEBHOOK_SECRET"]
REPO_MAP = json.loads(os.environ.get("REPO_MAP", "{}"))
DEFAULT_PROJECT = int(os.environ.get("DEFAULT_PROJECT", "11"))  # Dev


def project_for(repo_full_name):
    for pattern, pid in REPO_MAP.items():
        if fnmatch.fnmatch(repo_full_name, pattern):
            return int(pid)
    return DEFAULT_PROJECT


def kb(method, params=None):
    body = json.dumps({"jsonrpc": "2.0", "method": method, "id": 1,
                       "params": params or {}}).encode()
    req = urllib.request.Request(
        f"{KANBOARD_URL}/jsonrpc.php", data=body,
        headers={"Content-Type": "application/json"})
    req.add_header("Authorization",
                   "Basic " + __import__("base64").b64encode(
                       f"jsonrpc:{KANBOARD_TOKEN}".encode()).decode())
    res = json.load(urllib.request.urlopen(req))
    if "error" in res:
        raise RuntimeError(f"{method}: {res['error']}")
    return res.get("result")


def fj(path):
    req = urllib.request.Request(f"{FORGEJO_API}{path}",
                                 headers={"Authorization": f"token {FORGEJO_TOKEN}"})
    return json.load(urllib.request.urlopen(req))


def find_task(project_id, ref):
    """Return the Kanboard task carrying this forgejo reference, or None."""
    for task in kb("getAllTasks", {"project_id": project_id, "status_id": 1}) or []:
        if task.get("reference") == ref:
            return task
    return None


def first_column(project_id):
    cols = kb("getColumns", {"project_id": project_id}) or []
    return int(cols[0]["id"]) if cols else None


def mirror_issue(repo, issue):
    ref = f"forgejo:{repo}#{issue['number']}"
    pid = project_for(repo)
    title = f"{repo}#{issue['number']}: {issue['title']}"
    desc = f"{issue.get('html_url','')}\n\n{issue.get('body') or ''}"
    existing = find_task(pid, ref)

    if issue.get("state") == "closed":
        if existing:
            kb("closeTask", {"task_id": existing["id"]})
        return "closed"
    if existing:
        kb("updateTask", {"id": existing["id"], "title": title,
                          "description": desc})
        return "updated"

    tid = kb("createTask", {"title": title, "project_id": pid,
                            "description": desc, "reference": ref,
                            "column_id": first_column(pid)})
    if tid:
        kb("setTaskTags", {"project_id": pid, "task_id": tid,
                           "tags": ["forgejo"]})
    return "created"


def backfill(owner="nic"):
    """Mirror every open issue on every repo owned by `owner`."""
    created = []
    for repo in fj(f"/users/{owner}/repos?limit=100") or []:
        full = repo["full_name"]
        for issue in fj(f"/repos/{full}/issues?state=open&limit=50&type=issues") or []:
            try:
                res = mirror_issue(full, issue)
                if res == "created":
                    created.append(f"{full}#{issue['number']}")
            except Exception as e:
                print(f"backfill {full}#{issue['number']}: {e}")
    return created


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)

        if self.path == "/sync":
            self._json(200, {"created": backfill()})
            return

        # Forgejo signs with HMAC-SHA256 in X-Gitea-Signature / X-Forgejo-Signature /
        # X-Hub-Signature-256 (possibly "sha256="-prefixed); tolerate all of them
        sig = (self.headers.get("X-Gitea-Signature") or
               self.headers.get("X-Forgejo-Signature") or
               self.headers.get("X-Hub-Signature-256") or "")
        if sig.startswith("sha256="):
            sig = sig[7:]
        expect = hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expect):
            print(f"reject POST {self.path} sig={sig[:12]!r} "
                  f"headers={dict(self.headers).keys()}", flush=True)
            self._json(401, {"error": "bad signature"})
            return

        event = json.loads(raw)
        if "issue" not in event or "repository" not in event:
            print(f"skip POST {self.path}: not an issue event", flush=True)
            self._json(200, {"skipped": "not an issue event"})
            return
        repo, num = event["repository"]["full_name"], event["issue"]["number"]
        res = mirror_issue(repo, event["issue"])
        print(f"{event.get('action')} {repo}#{num} -> {res}", flush=True)
        self._json(200, {"result": res})


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8077), Handler).serve_forever()
