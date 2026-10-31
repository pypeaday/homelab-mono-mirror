#!/usr/bin/env python3
"""alert-triage — sits between SigNoz alertmanager webhook and Gotify.

Chain: SigNoz rule -> alertmanager webhook POST /alert -> tier1 rules ->
optional LLM verdict (ollama) -> notify (gotify) | digest queue | suppress.

Fail-open: any internal error (LLM down, bad payload, etc.) -> notify anyway.
Shadow mode (MODE=shadow): verdicts are computed+logged but everything notifies,
tagged with the would-be verdict. Enforce mode acts on the verdict.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(os.environ.get("PORT", "8931"))
MODE = os.environ.get("MODE", "shadow")  # shadow | enforce
GOTIFY_ENDPOINT = os.environ.get("GOTIFY_ENDPOINT", "http://gotify:80/message")
GOTIFY_TOKEN = os.environ.get("GOTIFY_TOKEN", "")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "")  # empty = tier2 disabled
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "30"))
DEDUP_MIN = int(os.environ.get("DEDUP_MIN", "30"))
DIGEST_SEC = int(os.environ.get("DIGEST_SEC", "1800"))
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
RULES_FILE = os.environ.get("RULES_FILE", "/etc/alert-triage/rules.json")

VERDICTS_LOG = DATA_DIR / "verdicts.jsonl"
RAW_DIR = DATA_DIR / "raw"
DIGEST_Q = DATA_DIR / "digest.jsonl"
STATE = DATA_DIR / "state.json"

_lock = threading.Lock()


def log(rec):
    rec["type"] = "alert.triage"
    print(json.dumps(rec), flush=True)


def load_state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {"seen": {}}  # fingerprint -> last fired epoch


def save_state(st):
    STATE.write_text(json.dumps(st))


def append_jsonl(path, rec):
    with path.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def load_rules():
    """User-tunable tier-1 config. All fields optional; missing file is fine."""
    try:
        return json.loads(Path(RULES_FILE).read_text())
    except Exception:
        return {}


def gotify(title, message, priority=5):
    if not GOTIFY_TOKEN:
        log({"event": "gotify_skip", "reason": "no GOTIFY_TOKEN"})
        return
    body = urllib.parse.urlencode(
        {"title": title, "message": message, "priority": priority}
    ).encode()
    req = urllib.request.Request(
        f"{GOTIFY_ENDPOINT}?token={GOTIFY_TOKEN}", data=body
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log({"event": "gotify_error", "error": str(e)})


def tier1(alert, st, cfg):
    """Deterministic verdict. Returns (verdict, reason, tier) or None to pass to LLM."""
    labels = alert.get("labels", {})
    rule = labels.get("alertname", labels.get("alert", "unknown"))
    fp = alert.get("fingerprint") or f"{rule}:{json.dumps(labels, sort_keys=True)}"
    status = alert.get("status", "firing")
    sev = labels.get("severity", "info")

    # resolved echoes: forward cheaply, never LLM
    if status == "resolved":
        return "notify", "resolved notice", "t1"

    # standing/flapper allowlist: rule names configured to digest
    digest_rules = cfg.get("digest_rules", [])
    if rule in digest_rules:
        return "digest", f"rule '{rule}' on digest list", "t1"

    # suppress allowlist
    suppress_rules = cfg.get("suppress_rules", [])
    if rule in suppress_rules:
        return "suppress", f"rule '{rule}' on suppress list", "t1"

    # dedupe by fingerprint within cooldown (cooldown measured from last
    # *delivered* notification, set in triage() — so a chronic flapper
    # surfaces once per window rather than vanishing forever)
    last = st["seen"].get(fp, 0)
    if last and (time.time() - last) < DEDUP_MIN * 60:
        return "suppress", f"dedupe: notified {int((time.time()-last)/60)}min ago", "t1"

    # severity floor
    if sev in cfg.get("suppress_severities", []):
        return "suppress", f"severity '{sev}' below floor", "t1"

    # critical bypass (default on): page immediately, no LLM wait
    if sev == "critical" and cfg.get("critical_bypass", True):
        return "notify", "critical bypass", "t1"

    # refire digest: first occurrence still pages/LLMs; once a fingerprint
    # has notified, repeats go to the digest instead of re-paging forever
    if rule in cfg.get("digest_on_refire", []) and st["seen"].get(fp):
        return "digest", f"refire of '{rule}' (first firing paged)", "t1"

    return None


def llm_verdict(alert, recent):
    if not OLLAMA_BASE:
        return None
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    prompt = (
        "You are an alert triage filter for a homelab. Decide whether this "
        "firing alert should page the owner NOW (notify), go in a periodic "
        "summary (digest), or be dropped (suppress).\n\n"
        f"ALERT: {json.dumps({'labels': labels, 'annotations': annotations})}\n"
        f"RECENT VERDICTS: {json.dumps(recent[-5:])}\n\n"
        "Rules: notify = actionable NOW, likely real outage/security/data loss. "
        "digest = real but not urgent (capacity, warnings, standing states). "
        "suppress = noise, flap, self-healing, expected behavior.\n"
        'Respond ONLY with JSON: {"verdict":"notify|digest|suppress",'
        '"reason":"<=160 chars"}'
    )
    body = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
    ).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/generate", data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as r:
        out = json.loads(r.read())["response"]
    v = json.loads(out)
    if v.get("verdict") not in ("notify", "digest", "suppress"):
        raise ValueError(f"bad verdict {v}")
    return {"verdict": v["verdict"], "reason": v.get("reason", "")[:160]}


def triage(alert, st):
    cfg = load_rules()
    labels = alert.get("labels", {})
    rule = labels.get("alertname", labels.get("alert", "unknown"))
    sev = labels.get("severity", "info")
    fp = alert.get("fingerprint") or f"{rule}:{json.dumps(labels, sort_keys=True)}"
    status = alert.get("status", "firing")
    annotations = alert.get("annotations", {})
    desc = annotations.get("description") or annotations.get("summary") or ""

    # Compact "k=v" of identifying labels — survives template failures in the
    # rule description so the page still says which site/host/dataset fired.
    skip = {"alertname", "alert", "severity", "team", "fingerprint",
            "ruleid", "rulename", "notify_channel"}
    kv = " ".join(f"{k}={v}" for k, v in sorted(labels.items())
                  if k.lower() not in skip and v not in ("", None))

    # recent verdicts for same rule (context for llm + debugging)
    recent = []
    if VERDICTS_LOG.exists():
        for line in VERDICTS_LOG.read_text().splitlines()[-200:]:
            try:
                r = json.loads(line)
                if r.get("rule") == rule:
                    recent.append(r)
            except Exception:
                pass

    t0 = time.time()
    v1 = tier1(alert, st, cfg)
    tier = "t1"
    if v1:
        verdict, reason, _ = v1
    else:
        try:
            v2 = llm_verdict(alert, recent)
        except Exception as e:
            v2 = None
            log({"event": "llm_error", "rule": rule, "error": str(e)})
        if v2:
            verdict, reason, tier = v2["verdict"], v2["reason"], "t2"
        else:
            verdict, reason = "notify", "fail-open (no LLM verdict)"

    rec = {
        "ts": int(time.time()), "rule": rule, "severity": sev,
        "fingerprint": fp, "status": status, "verdict": verdict,
        "reason": reason, "tier": tier, "desc": desc[:200], "kv": kv,
        "ms": int((time.time() - t0) * 1000), "mode": MODE,
    }
    append_jsonl(VERDICTS_LOG, rec)
    log(rec)

    effective = verdict if MODE == "enforce" else "notify"
    if effective == "suppress":
        return rec
    if effective == "digest":
        append_jsonl(DIGEST_Q, rec)
        return rec

    with _lock:
        st["seen"][fp] = time.time()
    tag = "" if MODE == "enforce" else f"[shadow:{verdict}] "
    title = f"{tag}[{sev.upper()}] {rule}" + (f" — {kv}" if kv else "")
    msg = f"{desc}\n---\ntriage: {verdict} ({tier}) — {reason}"
    prio = 8 if sev == "critical" else 5
    gotify(title, msg, prio)
    return rec


def flush_digest():
    while True:
        time.sleep(DIGEST_SEC)
        try:
            if not DIGEST_Q.exists():
                continue
            items = [json.loads(l) for l in DIGEST_Q.read_text().splitlines() if l.strip()]
            DIGEST_Q.write_text("")
            if not items:
                continue
            lines = [f"• [{i['severity']}] {i['rule']}"
                     + (f" ({i['kv']})" if i.get('kv') else "")
                     + f" — {i['reason']}" for i in items]
            gotify("alert digest", f"{len(items)} digested alerts:\n" + "\n".join(lines), 3)
            log({"event": "digest_flush", "count": len(items)})
        except Exception as e:
            log({"event": "digest_error", "error": str(e)})


def read_decisions(n=50):
    if not VERDICTS_LOG.exists():
        return []
    lines = VERDICTS_LOG.read_text().splitlines()[-n:]
    out = []
    for l in lines:
        try:
            out.append(json.loads(l))
        except Exception:
            pass
    return out


FAVICON = ("data:image/svg+xml,"
           "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E"
           "%3Cpath fill='%237da7ff' d='M2 3h20l-8 9.5V20l-4 2.5v-10z'/%3E%3C/svg%3E")

PAGE = """<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=30>
<meta name=viewport content="width=device-width,initial-scale=1">
<link rel=icon href="__FAVICON__">
<title>alert triage</title>
<style>
body{font:14px/1.45 ui-monospace,monospace;background:#0f1115;color:#d7dde6;margin:0;padding:24px;max-width:1200px}
h1{font-size:18px;font-weight:600;margin:0 0 4px}
.sub{color:#8b94a3;font-size:12px;margin-bottom:20px}
a{color:#7da7ff}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:24px}
.card{background:#161b24;border:1px solid #232a36;border-radius:8px;padding:12px 14px}
.card .n{font-size:26px;font-weight:600;line-height:1.1}
.card .l{color:#8b94a3;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin-top:2px}
.card.c-notify .n{color:#ff7d9c}.card.c-digest .n{color:#ffd479}
.card.c-suppress .n{color:#7f8ea3}.card.c-failopen .n{color:#ee7733}
.card.c-llm .n{color:#009988}
table{border-collapse:collapse;width:100%}
td,th{padding:6px 10px;border-bottom:1px solid #232a36;text-align:left;vertical-align:top}
th{color:#8b94a3;font-size:11px;text-transform:uppercase;letter-spacing:.05em}
.v{padding:1px 8px;border-radius:10px;font-size:12px;font-weight:600}
.notify{background:#3a1622;color:#ff7d9c}.digest{background:#3a2e12;color:#ffd479}
.suppress{background:#1d2430;color:#7f8ea3}
.sev-critical{color:#ff7d9c}.sev-warning{color:#ffd479}
.t{color:#8b94a3;font-size:12px;white-space:nowrap}
.reason{color:#9fb0c3}.rule{white-space:nowrap}
</style>
<h1>alert triage</h1>
<div class=sub>__INSIGHT__ &middot; __MODE__ mode &middot; refresh 30s &middot; <a href="/decisions">json</a></div>
<div class=cards>__CARDS__</div>
<table><tr><th>time</th><th>rule</th><th>sev</th><th>verdict</th><th>tier</th><th>reason</th><th>ms</th></tr>
__ROWS__</table>"""


def page_html():
    day_ago = time.time() - 86400
    recent = [r for r in read_decisions(500) if r.get("ts", 0) >= day_ago]
    n = len(recent)
    by = {"notify": 0, "digest": 0, "suppress": 0}
    llm = failopen = 0
    for r in recent:
        by[r.get("verdict", "")] = by.get(r.get("verdict", ""), 0) + 1
        if r.get("tier") == "t2":
            llm += 1
        if "fail-open" in r.get("reason", ""):
            failopen += 1
    cards = [
        ("", "alerts / 24h", n),
        ("c-notify", "paged", by["notify"]),
        ("c-digest", "digested", by["digest"]),
        ("c-suppress", "suppressed", by["suppress"]),
        ("c-llm", "llm verdicts", llm),
        ("c-failopen", "fail-open", failopen),
    ]
    cards_html = "".join(
        f'<div class="card {c}"><div class=n>{v}</div><div class=l>{l}</div></div>'
        for c, l, v in cards
    )
    insight = f"{n} alerts triaged, {by['notify']} paged" if n else "no alerts yet"
    rows = []
    for r in reversed(recent[-150:]):
        v = r.get("verdict", "?")
        t = time.strftime("%m-%d %H:%M:%S", time.localtime(r.get("ts", 0)))
        sev = r.get("severity", "?")
        rows.append(
            f'<tr><td class=t>{t}</td><td class=rule>{r.get("rule","?")}</td>'
            f'<td class="sev-{sev}">{sev}</td><td><span class="v {v}">{v}</span></td>'
            f'<td>{r.get("tier","?")}</td><td class=reason>{r.get("reason","")}'
            f'{" — "+r["desc"] if r.get("desc") else ""}</td><td>{r.get("ms","")}</td></tr>'
        )
    return (PAGE.replace("__ROWS__", "".join(rows) or "<tr><td colspan=7>no verdicts yet</td></tr>")
                .replace("__MODE__", MODE)
                .replace("__CARDS__", cards_html)
                .replace("__INSIGHT__", insight)
                .replace("__FAVICON__", FAVICON))


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _html(self, body):
        b = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._html(page_html())
        if self.path == "/healthz":
            return self._send(200, {"ok": True, "mode": MODE})
        if self.path.startswith("/decisions"):
            return self._send(200, {"decisions": read_decisions()})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path not in ("/alert", "/alertmanager"):
            return self._send(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        try:
            payload = json.loads(raw)
        except Exception:
            return self._send(400, {"error": "bad json"})

        # keep last 200 raw payloads for replay/debugging
        RAW_DIR.mkdir(exist_ok=True)
        ts = int(time.time() * 1000)
        (RAW_DIR / f"{ts}.json").write_bytes(raw)
        raws = sorted(RAW_DIR.iterdir())
        for old in raws[:-200]:
            old.unlink()

        st = load_state()
        alerts = payload.get("alerts") or [payload]  # single-alert bodies ok too
        results = []
        for a in alerts:
            try:
                results.append(triage(a, st))
            except Exception as e:
                # fail-open: never eat a page
                log({"event": "triage_error", "error": str(e)})
                gotify("[unfiltered] alert-triage error", f"{e}\n{json.dumps(a)[:1500]}", 5)
        save_state(st)
        self._send(200, {"processed": len(results)})

    def log_message(self, *a):
        pass  # quiet; access logs go through verdict log


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(exist_ok=True)
    threading.Thread(target=flush_digest, daemon=True).start()
    log({"event": "start", "port": PORT, "mode": MODE,
         "llm": OLLAMA_BASE or "disabled"})
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
