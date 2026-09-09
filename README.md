# Inside Hoi An

An interactive guide to Hoi An Ancient Town, Vietnam. It is a map-first travel app: 88
curated places pinned across the old town and the villages around it, a food directory, an
artisan and tailor index, and a booking flow for cyclo tours, basket boats and bicycle
trips. Bilingual throughout, English and Vietnamese.

**Live:** <https://javier-sysflow.github.io/Inside-Hoi-An-jade-s_project-/>

## What it does

- **The map.** 88 spots across Ancient Town, Tra Que, An Bang, Cam Thanh and Thanh Ha,
  filterable by vehicles, accommodation, cafes, dining, heritage sites, crafts, tailors,
  spas, nature, nightlife, events, banks and ATMs, tours and safety points.
- **Food.** Browse by cuisine or by street, from Cao Lau and White Rose dumplings to the
  banh mi counters on Tran Phu.
- **Book an experience.** Heritage cyclo tours, sampan boats, coconut basket boats and
  bamboo bicycles, with a checkout and an e-ticket. Payments are a prototype, not live.
- **Em An, the AI concierge.** A local guide chat, plus an itinerary planner and a
  Vietnamese translator. These call the app's own backend, which is not part of this copy.
- **Practical things a traveller actually opens.** Indicative currency rates, weather and
  UV, safety advisories, a VR360 tour, and an SOS panel.

Installable as a PWA, so it can be added to a phone home screen and opened offline.

## Important: this is a compiled build, not the source

The app was recovered from the deployed site as a **compiled production bundle.** There is
no React source in this repository, so there is nothing here to edit in the normal sense.
Everything in `dist/` is that build, with a stylesheet and a few small scripts layered on
top of it to fix what the audit found.

**A rebuild from the real source wipes every fix in here.** They are written down so they
can be reapplied upstream, not so they can live in a bundle forever. Read
**[BUG-AUDIT.md](BUG-AUDIT.md)** before changing anything.

Some of what that audit found and fixed:

- The AI concierge could not be closed. The sticky header sat above the modal and swallowed
  every click on its close button. Ten overlays shipped below the header.
- On a phone the page scrolled sideways 191px, and three header controls, including the menu
  button, sat off-screen and could not be tapped.
- The body font never rendered. 645 elements were falling back to the system font because a
  utility class shadowed it, which matters most for stacked Vietnamese diacritics.
- Two dead image links, no favicon, blank social previews, pinch-zoom disabled, and no
  keyboard focus styling anywhere in the app.

Still open, and needing the source: the map draws 88 markers with no clustering, 274 of them
overlapping, and has no zoom, locate or attribution controls.

## Run it locally

Python 3, nothing to install.

```
serve.bat              # Windows, double-click
python serve.py 4173   # or run it directly
```

Then open <http://127.0.0.1:4173>.

`serve.py` mirrors the live host closely enough to exercise the app offline: it replays
captured JSON for `/api/*`, serves the PWA manifest with the right media type, and marks the
service worker no-store so updates reach clients that already installed it.

## How it deploys

`.github/workflows/pages.yml` publishes `dist/` to GitHub Pages on every push to `main`.

This matters because Pages serves the repository root by default, and the root has no
`index.html` - only this README, which is why an unconfigured Pages site shows the README
instead of the app. All asset paths are **relative**, so the app works both at a domain root
and under a project sub-path like `/Inside-Hoi-An-jade-s_project-/`.

## Layout

| path | what it is |
|---|---|
| `dist/` | the app. `index.html` carries every fix as commented CSS rules |
| `dist/brand/` | logo assets derived from `InsideHoiAnLogo.png` |
| `dist/icons/`, `manifest.webmanifest`, `sw.js` | PWA icons, manifest, service worker |
| `dist/_api/` | captured API responses, so bookings still render offline |
| `tools/` | image and bundle scripts from the performance pass |
| `.original-backup/` | pristine copies, so changes can be diffed against what shipped |
| `BUG-AUDIT.md` | the audit: findings, measurements, and what was withdrawn |

## Caveats

- **The AI features need the real backend.** `/api/ai/*` and `/api/partners/apply` have no
  server here, so the concierge opens and renders but cannot answer.
- **Payments are a prototype.** The checkout is labelled "supported in the proposed platform"
  and processes nothing.
- **Weather, currency and advisories are demo data**, labelled as such in the interface.
- `.env.local` is gitignored and holds only a placeholder key.
