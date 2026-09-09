# .original-backup

Everything in this folder is a **copy kept for recovery**. Nothing here is served,
and nothing in `dist/` reads from it. Safe to ignore day to day; safe to raid if a
change needs undoing.

There used to be a second backup folder, `.perf-backup/`. It has been folded in here
so there is one place to look.

```
.original-backup/
  index.html                    the app as first downloaded, before any audit fix
  index-B97Xc7BA.js             the bundle as first downloaded, unpatched
  index.html.pre-polish         snapshot taken before the visual polish pass (rules 20-33)
  index.html.pre-nav-revert     snapshot taken before the navigation revert
  pre-perf/                     the five files the performance pass replaced
  original-media/               the 47 photos at their original quality
  retired-from-dist/            files removed from dist/ because nothing referenced them
```

## pre-perf/

The versions that were live immediately **before** the performance pass (rules 35-40).
Restoring all five returns the app to its pre-pass behaviour exactly.

| file | what changed after this copy |
|---|---|
| `index.html` | rules 35-40 added: non-blocking fonts, blur removal, transition list, `content-visibility` |
| `index-B97Xc7BA.js` | Unsplash widths, `loading`/`decoding` on 29 `<img>`, the `__ihT` thumbnail helper |
| `sw.js` | cache names bumped to v2, navigation preload, Unsplash caching |
| `serve.py` | gzip, WebP negotiation, `Cache-Control` |
| `manifest.webmanifest` | unchanged; kept so the set restores cleanly |
| `thumb-manifest.json` | the list of photos that got a `-160` variant |

## original-media/

The 47 images as they shipped, at roughly **one byte per pixel** — quality ~98 with no
chroma subsampling, about 1 MB for a 1200x896 photo. `dist/` now holds re-encoded
versions of these under the same filenames.

**This is the only copy.** Keep it. It is 27 MB, which is nothing, and it is what you
would need to re-encode differently later — a different quality target, AVIF, or larger
variants for high-DPI screens. Re-encoding from the already-compressed files in `dist/`
would compound the loss.

To restore any single photo: copy it back over the same path in `dist/`, then re-run
`tools/optimize_media.py` and `tools/make_thumbs.py`.

## retired-from-dist/

Files removed from `dist/` because no HTML, CSS, JavaScript, manifest or service worker
in the project named them. Filenames use `__` where the original path had a `/`.

| file | why it was retired |
|---|---|
| `brand__logo.png` | superseded by `brand/logo-art.png` |
| `brand__wordmark-white.png` | unused colourway; the build uses the amber one |
| `brand__wordmark-cream.png` | unused colourway |
| `brand__lockup-h.png` | unused horizontal lockup |
| `favicon.svg` | never referenced; `/favicon.ico` and the PNG icons are what ship |

Restore by copying back to `dist/` with the `__` turned back into `/`.
