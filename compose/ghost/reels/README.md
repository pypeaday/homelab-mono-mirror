# reels — psychopomp video gallery

Two services over `/tank/encrypted/nas/media/reels`:

- **gallery** (`gallery.py` + ffmpeg image, built here) — the harbor-themed
  viewer at `https://reels.paynepride.com`. Anonymous read, mp4s in
  "for review", audio/other files under "dev samples".
- **copyparty** — uploads + indexing, LAN only at `http://ghost:8095` (`nic`
  account, `REELS_PASS` in `.env`). The ↑ upload link in the gallery header
  points here.

## Storage

No dedicated dataset — content is regenerable (psychopomp re-renders from
`~/projects/personal/psychopomp/scenes/*` source), so it lives in the media
tree:

```sh
mkdir -p /tank/encrypted/nas/media/reels
```

## Deliver

The psychopomp devin skill rsyncs finished mp4s over:

```sh
rsync -av --progress ~/projects/personal/psychopomp/output/*.mp4 \
  ghost:/tank/encrypted/nas/media/reels/
```

copyparty's `-e2dsa` watcher picks them up; the page shows them immediately.

## Notes

- copyparty args: `-v /w:/w:r:rw,nic` = anonymous read + `nic` rw.
- Browser upload UI needs the `nic` password (`REELS_PASS` in `.env`).
- Optional: point a Jellyfin "Reels" library at the same dir later if you want
  it in the TV app.
