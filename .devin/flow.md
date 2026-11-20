**Goal:** Public-facing homelab intro section at `pype.dev/lab` (landing + hardware + services); NOT paynepride-branded.
**Now:** DONE — live at pype.dev/lab (+ /lab/hardware, /lab/services, /lab/apps shelf), all 200.
**Done:**
- Confirmed pype.dev = CF zone, site on gh-pages (markata-go build)
- Content sources: homelab-mono compose/services.csv (~90 svc), homepage config, ENVIRONMENT.md (hosts), pype.dev posts
- pages/lab/{index,hardware,services}.md in pype.dev, commit 5c0b5b0; the-homelab stub points at /lab
**Parked:**
- Brand/display name ("the lab" placeholder for now)
- lab.pype.dev subdomain → redirect to pype.dev/lab (later if wanted)
- pype.dev post mining for a "from the blog" section
**Decisions:**
- Section inside pype.dev repo, not a new site — user suggested it; existing deploy + posts already there
- markata-go templates-go/ + pype palette already exist; lab pages get a distinct template
- Service inventory lives in homelab-mono compose/services.csv → generate pages/lab/services.md from it
