# Inside Hoi An

A working copy of the **Inside Hoi An** web app, with an audit and a set of fixes applied on
top of it. Interactive neighbourhood guide, map, food directory and experience booking for Hoi
An Ancient Town, bilingual English/Vietnamese.

## What this repository is, and is not

This is **not the source tree.** The app was recovered from the deployed site as a compiled
production build, so there is no React source here to edit. Everything in `dist/` is that
build plus a stylesheet and a few small scripts layered on top of it.

That matters for anyone picking this up: **a rebuild from the real source wipes every fix in
here.** They are documented so they can be reapplied upstream, not so they can live here
forever.

## Run it

Requires Python 3. No install step.

```
serve.bat            # Windows, double-click
python serve.py 4173 # or run it directly
```

Then open <http://127.0.0.1:4173>. Port 4173 is used because 3000 was already taken.

`serve.py` is a small static server that also mirrors the live host: it replays captured JSON
for `/api/*`, serves the PWA manifest with the right media type, and marks the service worker
no-store so updates reach installed clients.

## Read this first

**[BUG-AUDIT.md](BUG-AUDIT.md)** is the main document. It records every defect found, how it
was measured, what was fixed, what was deliberately withdrawn and why, and what needs the
real source. Highlights:

- The AI Concierge could not be closed. The sticky header sat above the modal and swallowed
  clicks on its close button.
- Two dead image links, no favicon, blank social previews, and pinch-zoom disabled.
- On mobile the page scrolled sideways 191px and three header controls were unreachable.
- The intended body font never rendered; 645 elements were falling back to the system font.
- The map ships 88 markers with no clustering and no zoom, locate or attribution controls.

## Layout

| path | what it is |
|---|---|
| `dist/` | the app. `index.html` carries every fix, in commented rules |
| `dist/brand/` | logo assets derived from `InsideHoiAnLogo.png` |
| `dist/icons/`, `dist/manifest.webmanifest`, `dist/sw.js` | PWA: icons, manifest, service worker |
| `dist/_api/` | captured API responses so bookings render offline |
| `tools/` | image optimisation and bundle patch scripts from the performance pass |
| `.original-backup/` | pristine copies, so changes can be diffed against what shipped |
| `BUG-AUDIT.md` | the audit |

## Before deploying

`og:image` points at an absolute URL on the live domain, so link previews stay broken until
`og-card.png`, the icons, the manifest and the service worker are actually deployed to those
paths. `.env.local` is gitignored and holds only a placeholder key.
