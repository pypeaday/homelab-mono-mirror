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
import urllib.parse

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
  .card.hl { border-color: #4fd1a5; }
  .plink { color: #2e4a66; text-decoration: none; cursor: pointer; }
  .plink:hover { color: #4fd1a5; }
  .plink.on { color: #4fd1a5; }
  .card:target { border-color: #e0a458; }
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
<script>
document.querySelectorAll("[data-tag]").forEach(el =>
  el.addEventListener("click", e => {
    e.preventDefault();
    fetch("/tag", {method: "POST",
      headers: {"Content-Type": "application/x-www-form-urlencoded"},
      body: "f=" + encodeURIComponent(el.dataset.tag)})
      .then(() => location.reload());
  }));
</script>
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


def read_tags(d):
    """.review dotfile: one filename per line, '#' lines are comments."""
    try:
        with open(os.path.join(d, ".review")) as fh:
            return [l.strip() for l in fh
                    if l.strip() and not l.startswith("#")]
    except OSError:
        return []


class Handler(http.server.SimpleHTTPRequestHandler):
    gallery_dir = "."

    def do_GET(self):
        if self.path.rstrip("/") in ("", "/index.html"):
            self.send_gallery()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.rstrip("/") != "/tag":
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", 0))
        name = urllib.parse.parse_qs(self.rfile.read(n).decode()).get("f", [""])[0]
        tagged = read_tags(self.gallery_dir)
        p = os.path.join(self.gallery_dir, name)
        is_media = (name.rsplit(".", 1)[-1] in ("mp4", "mp3", "wav", "m4a")
                    and os.path.isfile(p))
        if name in tagged:
            tagged.remove(name)
        elif is_media:
            tagged.append(name)
        with open(os.path.join(self.gallery_dir, ".review"), "w") as fh:
            fh.write("\n".join(tagged) + ("\n" if tagged else ""))
        self.send_response(204)
        self.end_headers()

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

        # .review dotfile: one filename per line → those cards are pinned in a
        # highlighted "tagged for review" section at the top.
        tagged = read_tags(self.gallery_dir)
        pinned = [f for f in tagged if f in videos]
        pinned_audio = [f for f in tagged if f in audio]
        rest = [f for f in videos if f not in pinned]

        def facts(p, dur, size, mtime):
            return (f'<span class="facts">{fmt_dur(dur)} &middot; '
                    f'{fmt_size(size)} &middot; {mtime}</span>')

        def card(f):
            p = os.path.join(self.gallery_dir, f)
            dur, size = probe(p)
            mtime = time.strftime("%b %d %H:%M", time.localtime(os.path.getmtime(p)))
            url = "/" + html.escape(f, quote=True)
            url_v = f"{url}?v={int(os.path.getmtime(p))}"
            anchor = html.escape("f-" + f, quote=True)
            on = f in pinned
            return (
                f'<div class="card{" hl" if on else ""}" id="{anchor}">'
                f'<video src="{url_v}" controls '
                f'preload="metadata"></video>'
                f'<div class="meta"><span class="name"><a href="{url}" '
                f'download>{html.escape(f)}</a></span>'
                f'<a class="plink" href="#{anchor}" title="link">#</a>'
                f'<a class="plink{" on" if on else ""}" href="#" '
                f'data-tag="{html.escape(f, quote=True)}" '
                f'title="toggle review tag">{"untag" if on else "tag"}</a>'
                f'{facts(p, dur, size, mtime)}</div></div>'
            )

        def arow(f):
            p = os.path.join(self.gallery_dir, f)
            dur, size = probe(p)
            mtime = time.strftime("%b %d %H:%M",
                                  time.localtime(os.path.getmtime(p)))
            url = "/" + html.escape(f, quote=True)
            url_v = f"{url}?v={int(os.path.getmtime(p))}"
            on = f in pinned_audio
            return (
                f'<div class="row"><span class="name"><a href="{url}" '
                f'download>{html.escape(f)}</a></span>'
                f'<audio src="{url_v}" controls></audio>'
                f'<a class="plink{" on" if on else ""}" href="#" '
                f'data-tag="{html.escape(f, quote=True)}" '
                f'title="toggle review tag">{"untag" if on else "tag"}</a>'
                f'{facts(p, dur, size, mtime)}</div>'
            )

        body = ""
        if pinned or pinned_audio:
            body += ('<div class="section review">tagged for review</div>'
                     '<div class="grid">' +
                     "".join(card(f) for f in pinned) + "</div>"
                     '<div class="audio-list">' +
                     "".join(arow(f) for f in pinned_audio) + "</div>")
        if rest:
            body += ('<div class="section">all videos</div>'
                     '<div class="grid">' +
                     "".join(card(f) for f in rest) + "</div>")

        if not videos:
            body += '<div class="empty">no .mp4 files here yet</div>'
        rest_audio = [f for f in audio if f not in pinned_audio]
        if rest_audio:
            body += (f'<div class="section cruft">dev samples '
                     f'&middot; {len(rest_audio)}</div>'
                     f'<details><summary>show/hide</summary>'
                     f'<div class="audio-list">' +
                     "".join(arow(f) for f in rest_audio) +
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
