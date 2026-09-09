# tools/ — performance pass

Four scripts, run in this order, that turn a fresh `dist/` into the optimised one.
They are idempotent enough to re-run, but they rewrite `dist/` **in place**, so take
a copy first (`.perf-backup/` holds the originals from the first run).

```
python tools/optimize_media.py dist    # re-encode every photo, write .webp twins
python tools/make_thumbs.py    dist    # 160px variants for markers and avatars
python tools/patch_bundle.py   dist/assets/index-B97Xc7BA.js   # unsplash sizes + lazy/async
python tools/patch_thumbs.py   dist dist/assets/index-B97Xc7BA.js   # point small slots at the thumbs
```

Requires Pillow (`pip install pillow`). `patch_bundle.py` and `patch_thumbs.py` must
run in that order and **exactly once** per bundle — `patch_thumbs.py` looks for the
props shape `patch_bundle.py` leaves behind, and both assert on what they find rather
than editing blind, so a second run fails loudly instead of double-patching.

## Why these exist

The app ships as a compiled bundle with no source in this folder, so the usual fixes
(`srcset`, `React.memo`, code splitting, an image pipeline) are not available. These
four do what can be done from outside: shrink what is sent, and stop the browser
decoding pixels nobody sees.

The measured effect, at 10 Mbps with 4x CPU throttling and the browser cache on:

| | before | after |
|---|---|---|
| transferred | 26.3 MB | 1.66 MB |
| of which images | 24.7 MB | 1.0 MB |
| image pixels decoded | 99.5 MP | 5.0 MP |
| load (networkidle2) | 8.6 s | 3.7 s |

## What each one does

**`optimize_media.py`** — the build's art was saved at roughly one byte per pixel
(quality ~98, no chroma subsampling). This re-encodes each file, stepping quality up
from 78 until the RMS error against the original falls under 4/255, so detailed images
keep their detail instead of being crushed to a fixed number. Writes a `.webp` twin
beside each file; `serve.py` serves it to clients that advertise `image/webp`. Never
replaces a file the re-encode made bigger.

**`make_thumbs.py`** — the map draws 88 markers at 40x40 and the lists draw avatars at
28-72px, all pointing at the same 1200x896 source the full-bleed cards use. This writes
a 160px twin (2x for the largest of those slots) as `<name>-160.jpg` and `.webp`.

**`patch_bundle.py`** — two string edits. 86 Unsplash URLs asked the CDN for `w=1200`
(and four for `w=2000&q=90`) when nothing in this layout paints a photo wider than about
900 CSS px; they now ask for `w=1000&q=72`. And all 29 React `<img>` sites get
`loading="lazy"` and `decoding="async"` inserted first in the props object, so any site
that sets its own value still overrides ours.

**`patch_thumbs.py`** — installs a `__ihT(url, width)` helper and rewrites the src
expression at the 11 render sites whose own CSS class says they paint at ≤72px, plus the
marker template. The helper only rewrites Unsplash URLs (whose CDN resizes from the query
string) and local paths it has verified are present in the generated manifest; QR codes,
data URIs, other hosts and `undefined` pass through untouched, so no rewrite can 404.

## What is not in here

The remaining cost is React re-rendering: the bundle contains no `React.memo` and only
20 `useMemo` calls, so state changes re-render broadly. Fixing that needs the source.
It is not currently the bottleneck — interaction latency measured 11-30 ms per tab
switch at normal CPU speed — so it is worth knowing about, not worth bundle surgery.
