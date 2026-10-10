#!/usr/bin/env python3
"""Dead-simple reel gallery: serve a directory of .mp4s as an inline-playable
grid. No build step — the listing is generated per request, so a render that
lands in the directory shows up on refresh.

    python3 scripts/gallery.py [DIR] [--port 8788]
"""
import argparse
import html
import http.server
import json
import os
import subprocess
import time

PAGE = """<!doctype html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>reels</title>
<style>
  :root { color-scheme: dark; }
  body { background: #050c15; color: #e6eef7; margin: 0;
         font: 14px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; }
  header { padding: 20px 28px 8px; display: flex; gap: 14px; align-items: baseline; }
  h1 { font-size: 18px; margin: 0; color: #e0a458; font-weight: 600; }
  .count { color: #5e748c; }
  .up { color: #e0a458; text-decoration: none; font-size: 12px; }
  .up:hover { color: #f2c48c; }
  .grid { display: grid; padding: 12px 28px 28px; gap: 22px;
          grid-template-columns: repeat(auto-fill, minmax(440px, 1fr)); }
  .card { background: #0a1420; border: 1px solid #16283d; border-radius: 10px;
          overflow: hidden; }
  video { display: block; width: 100%; aspect-ratio: 16/9; background: #000; }
  .meta { padding: 10px 14px; display: flex; justify-content: space-between;
          gap: 12px; align-items: baseline; }
  .name { color: #e6eef7; overflow: hidden; text-overflow: ellipsis;
          white-space: nowrap; }
  .name a { color: inherit; text-decoration: none; }
  .name a:hover { color: #e0a458; }
  .facts { color: #5e748c; white-space: nowrap; font-size: 12px; }
  .empty { padding: 60px 28px; color: #5e748c; }
  .section { padding: 18px 28px 0; font-size: 12px; text-transform: uppercase;
             letter-spacing: .14em; color: #5e748c; }
  .section.review { color: #4fd1a5; }
  .section.cruft { margin-top: 14px; }
  details { margin-top: 4px; }
  summary { padding: 6px 28px; cursor: pointer; color: #5e748c; font-size: 12px; }
  summary:hover { color: #93a7bd; }
  .audio-list { padding: 4px 28px 30px; }
  .row { display: flex; gap: 12px; align-items: center; padding: 7px 10px;
         border-bottom: 1px solid #0f1d2c; }
  .row audio { height: 28px; flex: 1; min-width: 0; }
  .row .name { width: 260px; font-size: 12px; }
  .row .facts { font-size: 11px; }
</style></head><body>
<header><h1>reels</h1><a class="up" href="http://ghost:8095" title="upload (LAN)">↑ upload</a><span class="count">{count} video{s}</span></header>
{body}
</body></html>
"""


def probe(path):
    """Return (duration_seconds, size_bytes) — duration via ffprobe."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", path],
            capture_output=True, text=True, timeout=10,
        )
        dur = float(json.loads(out.stdout)["format"]["duration"])
    except Exception:
        dur = 0.0
    return dur, os.path.getsize(path)


def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def fmt_dur(s):
    m, sec = divmod(int(round(s)), 60)
    return f"{m}:{sec:02d}" if s else "?"


class Handler(http.server.SimpleHTTPRequestHandler):
    gallery_dir = "."

    def do_GET(self):
        if self.path.rstrip("/") in ("", "/index.html"):
            self.send_gallery()
        else:
            super().do_GET()

    def send_gallery(self):
        files = sorted(
            (f for f in os.listdir(self.gallery_dir)
             if f.rsplit(".", 1)[-1] in ("mp4", "mp3", "wav", "m4a")
             and not f.startswith(".")),
            key=lambda f: os.path.getmtime(os.path.join(self.gallery_dir, f)),
            reverse=True,
        )
        # Videos are the deliverables; audio files are comparison/dev samples.
        videos = [f for f in files if f.endswith(".mp4")]
        audio = [f for f in files if not f.endswith(".mp4")]

        def facts(p, dur, size, mtime):
            return (f'<span class="facts">{fmt_dur(dur)} &middot; '
                    f'{fmt_size(size)} &middot; {mtime}</span>')

        cards = []
        for f in videos:
            p = os.path.join(self.gallery_dir, f)
            dur, size = probe(p)
            mtime = time.strftime("%b %d %H:%M", time.localtime(os.path.getmtime(p)))
            url = "/" + html.escape(f, quote=True)
            url_v = f"{url}?v={int(os.path.getmtime(p))}"
            cards.append(
                f'<div class="card"><video src="{url_v}" controls '
                f'preload="metadata"></video>'
                f'<div class="meta"><span class="name"><a href="{url}" '
                f'download>{html.escape(f)}</a></span>'
                f'{facts(p, dur, size, mtime)}</div></div>'
            )
        body = ""
        if videos:
            body += '<div class="section review">for review</div>'
            body += '<div class="grid">' + "".join(cards) + "</div>"
        else:
            body += '<div class="empty">no .mp4 files here yet</div>'
        if audio:
            rows = []
            for f in audio:
                p = os.path.join(self.gallery_dir, f)
                dur, size = probe(p)
                mtime = time.strftime("%b %d %H:%M",
                                      time.localtime(os.path.getmtime(p)))
                url = "/" + html.escape(f, quote=True)
                url_v = f"{url}?v={int(os.path.getmtime(p))}"
                rows.append(
                    f'<div class="row"><span class="name"><a href="{url}" '
                    f'download>{html.escape(f)}</a></span>'
                    f'<audio src="{url_v}" controls></audio>'
                    f'{facts(p, dur, size, mtime)}</div>'
                )
            body += (f'<div class="section cruft">dev samples '
                     f'&middot; {len(audio)}</div>'
                     f'<details><summary>show/hide</summary>'
                     f'<div class="audio-list">' + "".join(rows) +
                     "</div></details>")
        page = (PAGE.replace("{body}", body)
                    .replace("{count}", str(len(videos)))
                    .replace("{s}", "" if len(videos) == 1 else "s"))
        data = page.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", nargs="?", default="output")
    ap.add_argument("--port", type=int, default=8788)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    os.chdir(args.dir)
    print(f"serving {os.getcwd()} -> http://{args.host}:{args.port}")
    http.server.ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
