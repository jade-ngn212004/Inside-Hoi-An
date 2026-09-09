# Inside Hoi An — Bug Audit

Audited 2026-09-08 against the deployed build at `https://inside-hoi-an.ai.studio/`
and the local copy in `dist/`.

## How this was tested

No application source exists in this folder, only the compiled bundle, so this is a
**runtime audit**, not a code review. The app was driven through the Chrome DevTools
Protocol with a fresh browser profile per run, capturing uncaught exceptions, console
errors, failed network requests, HTTP status codes, and DOM/accessibility state. Every
top-level tab was then clicked in sequence. All 77 hotlinked Unsplash URLs were checked
individually.

Confirmed healthy: **zero** uncaught exceptions, **zero** console errors, and **zero**
failed requests on the live site and across all ten interactive tabs. 111 images all
carry `alt` text, all 107 buttons have accessible names, no duplicate element IDs, no
insecure `http://` links, and every `target="_blank"` link sets `rel="noopener"`.

---

## Defects found on the live site

Items 1-6 and 9-10 are fixed in the local copy; 7-8 need the source.

**Defect 9 is the most severe finding in this audit** and is listed at the end only
because it was found later, on a user report. It makes the AI Concierge impossible to
close.

### 1. Two dead image hotlinks — FIXED locally
`photo-1541888946425-d0fbb18086f6` and `photo-1592417817098-8f3d6eb22509` both return
**404 from Unsplash**. The browser reports `net::ERR_BLOCKED_BY_ORB` and renders a
broken image. The first is the cover for a heritage-construction road advisory; the
second is the cover for the countryside cycling/Tra Que tour.

75 of the 77 Unsplash URLs are fine, so this is two dead links, not a systemic problem.

*Fix applied:* both now point at already-bundled local photos
(`/images/chua_cau_covered_bridge.jpg`, `/images/tra_que_cau_bong_festival.jpg`).
*Proper fix in source:* replace the two URLs, and stop hotlinking Unsplash for
content images. Third-party image IDs disappear without warning.

### 2. Pinch-zoom is disabled — FIXED locally
The viewport tag set `maximum-scale=1.0, user-scalable=no`. This blocks pinch-zoom on
mobile and **fails WCAG 2.1 SC 1.4.4 (Resize Text)**. It matters here because this is a
travel app used one-handed, outdoors, on small screens, on a map.

*Fix applied:* viewport is now `width=device-width, initial-scale=1.0, viewport-fit=cover`.

### 3. Wrong document language — FIXED locally
`<html lang="vi">` while the interface defaults to English. Screen readers pick voice and
pronunciation from this attribute, so English content was being read with Vietnamese
phonetics.

*Fix applied:* `lang="en"`.
*Proper fix in source:* set `lang` from the active language toggle, so it flips to `vi`
when the user switches. A static value is wrong for a bilingual app either way.

### 4. Social previews are blank — FIXED locally
The page declared `twitter:card=summary_large_image` but shipped **no `og:image` and no
`twitter:image`**. Every share on Facebook, Messenger, Zalo, or X rendered without a
picture. For a tourism site that is a real distribution cost, and the site is currently
being shared via a Facebook link.

*Fix applied:* added `og:image`, `og:image:alt`, `twitter:image`, and `og:url`, pointing
at the lantern-festival photo.

### 5. No favicon — FIXED locally
`/favicon.ico` did not exist. The host answered with the SPA fallback, so the browser
received **HTML with status 200** where it expected an icon, and showed a blank page icon.

*Fix applied:* added `favicon.svg` and linked it.

### 6. Map stylesheet loaded from a third-party CDN — FIXED locally
Leaflet's CSS came from `unpkg.com`. That is a single point of failure outside your
control; if unpkg is slow, blocked, or down, the map controls and marker positioning
render unstyled. Vietnamese ISP-level CDN interference makes this more than theoretical.

*Fix applied:* Leaflet CSS is vendored to `/assets/leaflet-1.9.4.css`.

### 7. No `<h1>` on the page — NEEDS SOURCE
The document outline starts at `<h3>`. There is no first-level heading anywhere. This
hurts search ranking for a site whose whole purpose is discovery, and it removes the
main landmark screen-reader users navigate by.

*Fix in source:* make the site title or current view title an `<h1>`, then demote the
existing `<h3>` blocks so the outline runs h1 -> h2 -> h3 without skipping.

### 8. Two search inputs have no accessible name — NEEDS SOURCE
Both rely on `placeholder` alone, which is not an accessible name and disappears on
input. **Fails WCAG 4.1.2 (Name, Role, Value).**

| Input | Placeholder |
|---|---|
| `#search-input-header` | Search bridge, food, banks... |
| map search field (no id) | Search places, cafes, dining, heritage sights... |

*Fix in source:* add `aria-label` to each, or a visually hidden `<label for>`.

### 9. AI Concierge cannot be closed — modal stacking inversion — FIXED locally

**Reported by the user, reproduced and confirmed on the live site.** Opening the AI
Concierge traps you in it. The close button does nothing, Escape does nothing, and the
only escape is a page reload.

*Root cause.* The site header is `sticky … z-[1050]` and spans the full width at
y=0-65. The Concierge drawer is `fixed inset-0 z-50`. **The header therefore paints on
top of the open drawer and intercepts every pointer event in the drawer's top 65px** —
which is precisely where the close (X) button sits, at y=18-54. The button is visible
but not hittable. `document.elementFromPoint()` at the button's centre returns the
header, not the button.

This is why it looks broken rather than missing: you can see the X, you click it, and
nothing happens.

*Blast radius.* **Ten** overlays ship as `fixed inset-0 z-50`, all of them below the
header. Only one overlay in the app (`z-[1200]`) is correctly above it. Any control any
of those ten place in the top 65px is dead. The SOS drawer escapes the bug only because
it happens to be the `z-[1200]` one.

Measured, same browser and viewport, AI Concierge:

| | z-index | X reachable | click X | Escape |
|---|---|---|---|---|
| Live site | 50 | no | stuck | stuck |
| Local, after fix | 1100 | yes | closes | closes |

*Fix applied:* a CSS rule in `index.html` raising `.fixed.inset-0.z-50` to `z-index:1100`
— above the 1050 header, below the 1200 overlay, so relative order is preserved.
*Proper fix in source:* stop interleaving overlay and chrome z-indexes. Put modals in a
portal above all page chrome, and define a small named scale (base / header / overlay)
instead of hand-picked numbers like 50, 1050 and 1200.

### 10. No keyboard dismiss on any overlay — SHIMMED locally

No overlay binds an Escape handler, on live or locally. Combined with defect 9 this is
what made the Concierge a hard trap. It is also a dialog convention users rely on, and
leaves keyboard-only users with no way out.

*Shim applied:* a small `keydown` listener in `index.html` activates the topmost open
overlay's own close button. It is keyed to this build's X icon path, so it is a local
stopgap, not a real fix.
*Proper fix in source:* handle Escape in the shared dialog component, along with focus
trapping and restoring focus to the trigger on close.

---

## Mobile audit (390x844, iPhone-class, device emulation)

Measured with Chrome device emulation at a 390px layout viewport with touch input,
against both the live site and the local copy. The two were identical before these
fixes, so every defect below is in the deployed app.

| | live (before) | local (after) |
|---|---|---|
| page scroll width, viewport 390 | 581 | 390 |
| elements forcing page scroll | 2 | 0 |
| map top | y=722 | y=655 |
| map visible without scrolling | 122px | 189px |
| smallest text | 8px | 11px |
| controls under 44px | 187 of 188 | 185 of 188 |

### 11. The header does not fit a phone, and pushes controls off-screen — FIXED locally

The header row is a `nowrap` flex row whose right cluster is `flex-shrink-0` and 346px
wide, inside a 390px viewport. It refused to shrink, so it ran off the edge and gave
the entire page 191px of horizontal scroll.

Three controls sat past the right edge and were **not reachable by touch** (confirmed by
hit-testing at each element's centre):

| control | x position | on screen |
|---|---|---|
| AI Concierge | 352 | no |
| language toggle (EN) | 475 | no |
| hamburger menu | 543 | no |

The app also renders two different menu triggers, one `xl:hidden` and one `md:hidden`.
The `xl:hidden` one is reachable at x=235; the `md:hidden` one is the stranded one.

*Fix applied:* the header row wraps below 1024px and the cluster is allowed to shrink.
Everything is now on screen and tappable, at a cost of roughly 58px of header height.
*Proper fix in source:* on phones, keep the wordmark, SOS and one menu button in the bar
and move the rest into the menu. There is not room for five controls plus a logo at
390px, and there should only be one menu trigger.

### 12. The map, the app's primary job, is buried on phones — PARTLY FIXED locally

The map started at y=722 on an 844px screen, leaving 122px visible. Above it sit a
64px header, a 137px currency strip and a 455px weather and advisories block.

Worse, **the bottom "Map" tab does not reveal the map**. Clicking it leaves `scrollY` at
0 and the map at y=780. The app's primary navigation control for its primary feature
does nothing observable.

*Fix applied:* tightened padding on both strips and capped the weather block at 40vh
with its own internal scroll, so the content is kept rather than hidden. The map moved
up 67px and 55% more of it is visible.
*Proper fix in source:* a map-first mobile layout. The map should own the viewport, with
currency and weather as collapsible sheets, and the bottom tabs should actually switch
views. This is the single biggest mobile improvement available and it needs the source.

I also tried forcing the weather grid to two columns. It saved only 27px and squeezed
the cards to 173px, which made the forecast headings overlap the readings. **I withdrew
that rule**; the note remains in `index.html` so nobody retries it.

### 13. Text down to 8px — FIXED locally

The build ships 3 elements at 8px, 17 at 9px and 174 at 10px. This is a guide read
outdoors, in daylight, at arm's length. 8px is not legible in that setting.

*Fix applied:* a type floor on phones — 8px, 9px and 9.5px become 11px; 10px and 10.5px
become 11.5px. Nothing below 11px now renders on mobile.
*Proper fix in source:* stop using `text-[8px]` and `text-[9px]` at all. 11px should be
the floor, and badges that only fit at 8px are a sign the badge should be dropped.

### 14. Touch targets — PARTLY FIXED locally

187 of 188 controls measured under 44x44, and 42 under the WCAG 2.5.8 minimum of 24x24.
The four bottom tabs were 36px tall. Many directory links are 19px tall.

*Fix applied:* header buttons and the bottom tabs are now at least 40 and 44px on touch
devices.
*Proper fix in source:* the 19px directory links need real padding. A CSS override
cannot reach them safely without disturbing the lists they sit in.

---

## UI/UX review

A design review was run against the running build at 390, 768 and 1440 widths in both
languages, measuring live DOM geometry, computed styles and contrast ratios rather than
eyeballing screenshots.

**What is genuinely good:** contrast on the dark surfaces is strong (body text 7.6:1 to
15.7:1, well past AA). All 111 images carry alt text. No button lacks an accessible
name. The filter strip is correctly a horizontal scroller.

### 15. Contrast failure on the VR360 button — FIXED locally

White 12px bold on an amber-to-rose gradient measures **2.1:1** at the light end, against
a 4.5:1 AA requirement. It fails across the button's whole width. The star badge on map
pins is the same problem, white on amber-500 at 2.1:1.

*Fix applied:* the FAB gradient is darkened to `#b45309 -> #9f1239`, which keeps the
brand ramp and clears AA. Scoped to the map control stack so the main AI Concierge call
to action is untouched.
*Also worth knowing:* the rose badges (HOT / LIVE / NEW / 360) measure 4.51:1. They pass
by 0.01, at 8px. Technically compliant, practically illegible.

### Corrections to the review

Two findings did not survive verification, and I am recording them so nobody chases them:

- **"Vietnamese layout breaks on mobile" is not real.** It was measured while my own
  two-column weather rule was briefly live, and that rule was what crushed the forecast
  cells. I withdrew the rule. Re-measured afterwards: **zero** crushed elements, on both
  the live site and this copy, in Vietnamese at 390px. Vietnamese renders correctly.
- **"Banks & ATMs swallows its own label" is not a layout bug.** Flex-shrink on that
  button is already 0. The build hides the label below the `sm` breakpoint deliberately.
  The real defect is that the resulting icon-only button has no accessible name, and CSS
  cannot add one.

### Withdrawn fixes

Three CSS rules were written, measured, found wanting, and removed. The reasoning is
left in `index.html` so they are not retried:

| rule | why it was withdrawn |
|---|---|
| weather grid to 2 columns | saved 27px, and squeezed cards to 173px so headings overlapped readings |
| reposition map FAB stack | no free band exists; a horizontal row landed on top of the filter chips |
| force Banks & ATMs label | flex-shrink was already 0; the label is hidden by design |

### Needs source — ranked by impact

1. **88 map markers with no clustering.** 68 of 88 overlap another marker, 274
   overlapping pairs, and 23 markers within a 50px radius at the densest point. The
   Ancient Town renders as a solid mass of 40px photo circles with no separable targets.
   Photo avatars are the most expensive possible marker style at this density. This is
   the single biggest map-quality win available.
2. **The map has no zoom control, no locate-me and no attribution.** There are zero
   `.leaflet-control` elements. Someone standing in Hoi An cannot ask "what is near me",
   and the missing attribution is a tile-licensing exposure, not just a UI gap.
3. **A concluded event is the hero of the map screen.** A full-viewport panel labelled
   "Ended - Archived Event", for something that finished on 2 September 2026, occupies
   the largest single piece of real estate in the product and covers the map.
4. **Be Vietnam Pro never renders.** All 21 faces report `unloaded`; body text resolves
   to Segoe UI. Playfair Display from the same stylesheet loads fine, so this is a load
   path bug, not the environment. It matters twice over: the font was drawn for stacked
   Vietnamese diacritics, which the system fallback handles badly at 9-11px, and the
   fallback is not metric-compatible (a Vietnamese test string measures 12% narrower),
   so every pill and badge reflows if the font ever does arrive. Self-host the subset.
5. **A 1751px white footer under a dark app.** Scrolling down from the map drops the
   user into a link farm of roughly 60 entries at 18.6px row height, below the WCAG
   minimum, with labels truncated mid-word. It is crawler content wearing UI clothing.
6. **Badge and accent inflation.** Twelve badges are visible at once on a 390px screen,
   six of them at 8px, across eight distinct accent hues. SOS, a real emergency control,
   renders in the same rose at the same size as the "HOT" marketing badge. Reserve rose
   for SOS and delete HOT / NEW / LIVE / 360, which describe the app's enthusiasm rather
   than the user's need. This is the thing that makes the design read as templated.
7. **Playfair Display used below its legible size.** It is set at 14-16px for the
   wordmark and the currency heading. It is a high-contrast didone; its hairlines vanish
   below about 20px on a dark ground. It earns its keep at 24px and nowhere smaller.
8. **No `<h1>`, and two unlabelled search inputs.** Carried over from defects 7 and 8.

---

## Visual polish pass (rules 20-33)

Six independent design lenses surveyed the running build at 1440x1100 and 390x844 in both
languages, a synthesis pass merged them into one restrained rule set, and an adversarial
panel checked each rule for whether it matches, whether it regresses, and whether it
respects the existing design.

**The governing finding: this app's identity is not broken, it is under-rendered.** Most of
what looked like design problems were things the build already declares that the Tailwind
compiler silently dropped. So the pass mostly restores the designer's own intent rather
than imposing anything new.

| | before | after |
|---|---|---|
| elements rendering in Be Vietnam Pro | 2 | 645 |
| elements falling back to the system font | 643 | 0 |
| `:focus-visible` rules in the stylesheet | 0 | 3 |
| distinct font sizes | 11 | 10 |
| desktop text at 8-9px | 12 elements | 0 |
| mobile controls under 24px | 42 | 35 |

### What was silently dropped by the compiler, now restored

- **The body font never rendered.** Be Vietnam Pro is linked, parsed and paid for on every
  page load, but a `.font-sans` utility shadowed it, so every Vietnamese place name in a
  Vietnamese guide was set in Segoe UI. It now renders on 645 elements. Be Vietnam Pro runs
  about 5% wider, so the event description's line clamp went from 2 lines to 3 to keep its
  last words visible.
- **`stone-750` and `stone-850` were never generated.** They appear in 87 class strings but
  do not exist in Tailwind's palette, so a whole tier of surfaces rendered hollow and 11
  hairlines fell back to `currentColor`, drawing brighter than the text they contained.
  Defined as tokens: 15 surfaces and 11 borders now render as designed.
- **`py-0.2` is not on Tailwind's scale**, so seven badges had literally 0px of vertical
  padding and read as text jammed against a border. Now inset properly.

### Deliberate design decisions

- **The bottom tab bar now mirrors the header** instead of being a white light-mode slab
  under a dark app. This is the one place the pass spends boldness, because it is the only
  theme contradiction visible on every screen without scrolling. Eight declarations, no
  `!important`. It also finally applied a 44px touch minimum that an earlier rule of mine
  missed, because the bar is `sticky`, not `fixed`.
- **One red means danger.** The promo badges (`360`, `HOT`, `LIVE`) left the emergency red
  and became amber-tinted chips matching the existing `GUIDE` badge, so SOS is now the only
  red control on screen. This strengthens the app's own idiom rather than importing one.
- **A focus ring in the brand amber**, where there was previously no keyboard focus styling
  at all, plus a `prefers-reduced-motion` block, placed last so it wins.
- **Scroller edges fade** instead of slicing labels mid-word, matching the fade already used
  on the weather panel.

### Notably rejected

The synthesis pass **rejected darkening the white footer**, and it was the closest call. The
evidence was real: the footer is a pure-white slab making up 54% of the mobile document, and
the page gets brighter as you scroll into it. It was rejected because remapping roughly 20
Tailwind colour utilities with 35 `!important` declarations on a compiled bundle is the
change most likely to make the owner say "that is not my app any more", and it degrades
silently as new content is added in unmapped colour classes. The bottom tab bar delivers the
same theme argument for 8 declarations and one verified element.

Also rejected: a full desktop type-scale rebuild (restacks the scale rather than fixing its
execution, and the truncation risk compounds with the wider font), a shadow elevation system
(redundant once the stone tokens render), press feedback on all 107 buttons (highest
unverified blast radius in the set), and radius unification (inconsistency across views is
not a defect on any one screen).

### Verification status

Four rules cleared the full three-check adversarial panel. The session hit its usage limit
partway through verification, so the remaining ten were never checked by the panel. **I
verified those myself** rather than shipping them unchecked: every selector confirmed to
match real elements, and the whole set measured for regressions.

Confirmed after the pass: zero console errors, zero failed requests, zero broken images on
desktop. On mobile, no horizontal overflow, the map top unchanged at y=655, and touch
targets improved. Vietnamese at 390px shows no overflow and zero crushed elements. Both
modal drawers still open and close by click and by Escape.

---

## Brand assets and PWA

Built from `InsideHoiAnLogo.png` (1254x1254, cream ground `#FAF3E3`, rounded-square app-icon
form). Nothing was redrawn; every asset is a crop or scale of the supplied artwork.

### Where the logo now appears

| Surface | Asset | Which crop, and why |
|---|---|---|
| Header mark | `/brand/logo-art.png` | The illustration **cut out of its cream ground**, sitting directly on the dark header. See "Making the header mark prominent". |
| Favicon | `/favicon.ico` (16/32/48) + PNG fallbacks | Same tight crop. Tested at 36px against two looser crops; the tight one was the only one that reads. |
| iOS home screen | `/apple-touch-icon.png` (180, opaque) | iOS applies its own mask, so this one is deliberately square and full-bleed. |
| Android install | `/icons/icon-192.png`, `/icons/icon-512.png` | Full logo including the wordmark, which is legible at these sizes. |
| Android adaptive | `/icons/icon-*-maskable.png` | Full logo at 70% inside a cream field, so nothing is clipped by whatever mask the launcher applies. |
| Social sharing | `/og-card.png` (1200x630) | A purpose-built card: the mark on the app's own near-black ground, amber wordmark, tagline and place list. A bare square logo crops badly in social previews. |

The header change is one CSS rule. The tile previously rendered a lantern emoji; it now carries
the logo's illustration. The author's amber gradient ring around the tile is kept.

### PWA

- **`/manifest.webmanifest`** — standalone display, `#0c0a09` background, `#1c1917` theme, four
  icons (two `any`, two `maskable`), plus narrow and wide screenshots so the Android install
  prompt shows the app rather than a bare icon. Chrome's own parser reports **zero errors**.
- **`/sw.js`** — a service worker with four caching strategies, chosen per resource type:

| Request | Strategy | Why |
|---|---|---|
| navigations | network-first, cached shell as fallback | a redeploy is picked up immediately; offline still opens |
| `/assets/*` | cache-first | filenames are content-hashed, so they can never go stale |
| `/images`, `/brand`, `/icons` | cache-first, capped at 60 | local photography is large and static |
| map tiles (`mt*.google.com/vt`) | stale-while-revalidate, capped at 400 | tiles are opaque cross-origin; the cap keeps quota sane |
| `/api/*` | network-first, last good response retained | bookings still render offline |

- The page also declares `theme-color`, which the earlier review flagged as missing: Android
  Chrome and iOS Safari were framing this dark amber guide in white browser chrome.
- `serve.py` now serves `.webmanifest` as `application/manifest+json` and marks `sw.js`
  `no-store` with `Service-Worker-Allowed: /`, so an updated worker always reaches a client
  that already installed an old one.

### Verification status — read this before trusting the offline claim

Verified here: the manifest parses with zero errors in Chrome, all 11 precached URLs return
200, `sw.js` is valid JavaScript with all four handlers present, `register()` resolves, and the
brand mark renders in the header.

**Not verified here: actual caching and offline behaviour.** `caches.open()` fails with
`UnknownError: Unexpected internal error` in every headless Chrome configuration on this
machine — new headless, old headless, sandboxed and not. That is an environment fault, not a
fault in the worker, but it means I could not prove the offline path end to end.

To confirm it yourself, in a normal Chrome window at `http://127.0.0.1:4173`:

1. DevTools > Application > Service Workers — the worker should show as activated and running.
2. Application > Cache Storage — `ih-shell-v1` should hold 11 entries after the first load.
3. Tick Network > Offline, reload — the app should still open, map tiles limited to those
   already visited.
4. The install icon should appear in the address bar.

### Deployment note

`og:image` points at `https://inside-hoi-an.ai.studio/og-card.png`. Social scrapers require an
absolute URL, so **the card has to be deployed to that path before link previews will work**.
The same applies to the icons, the manifest and the service worker: they are local files here.

---

## Payment method marks

The checkout and footer render an "Accepted Payment Methods" strip: ten methods, each a
white pill with an 8px dot in the brand's own colour plus its name. The colours are already
correct in the data (Visa `#1a1f71`, MoMo `#ae2070`, VNPay `#005baa`, VietQR `#007542` and so
on). The strip appears in four places, and is labelled "Payment methods supported in the
proposed platform".

**Real brand marks are not shipped, deliberately.** All ten are registered trademarks. I will
not redraw them by hand, because a slightly wrong Visa mark is worse than no mark, and I will
not pull them from an image search into someone else's project. They should come from each
brand's own merchant asset kit, under that brand's usage rules.

**What is shipped is the wiring**, so adding them later needs no code change:

| Piece | What it does |
|---|---|
| `dist/brand/pay/` | Drop `visa.svg`, `momo.svg`, `paypal.svg` and so on here |
| `dist/brand/pay/marks.json` | The manifest the page reads; ships listing nothing |
| `serve.py` | Generates that manifest from the folder, so locally a dropped file just appears |
| shim in `index.html` | Swaps the dot for the mark at 14px tall, keeps the text label, adds an `aria-label` |

Verified both directions: with no files the strip is byte-identical to before and the console
stays at zero errors; drop one file in and that badge upgrades while the other nine are
untouched.

**A defect I introduced and fixed.** The first version probed for each file with an `Image()`
load. That produced a 404 per missing mark - 36 console errors and 18 failed requests in an
app this audit had just certified as logging none. Replaced with the single manifest fetch.

**One caution worth passing on.** This checkout does not process real payments. Full brand
marks on a non-functional checkout can imply processing relationships that do not exist, so
the "proposed platform" wording should stay next to them.

---

## Performance pass (rules 35-40, `tools/`)

The app felt sluggish. It was measured before anything was changed, driving Chrome over
the DevTools Protocol at 10 Mbps with 4x CPU throttling, and the finding was not what the
"feels slow" symptom suggested: **76% of the busy main thread was inside the compositor,
not in application code.** The app was not computing slowly. It was being asked to move
and decode far more pixels than it displays.

Three things were doing it:

1. **26 MB of photography per visit.** The bundled art was saved at roughly one byte per
   pixel - quality ~98 with no chroma subsampling - so a 1200x896 photo cost about 1 MB.
2. **Every one of those photos was also a thumbnail.** The map draws 88 markers at
   **40x40 px**, and each one loaded the same full-size file the full-bleed detail card
   uses. 111 images on the page carried 99.5 megapixels of intrinsic size between them.
3. **Blur behind opaque surfaces.** The header (`bg-stone-900/98`), the bottom tab bar
   and map chrome (`/95`) and a 1152x427 panel (`/95`) all carried `backdrop-blur`. At
   95-98% opacity there is nothing legible behind them to blur, but the compositor still
   re-blurred the full surface on every frame that scrolled underneath.

### Measured, before and after

10 Mbps, 4x CPU throttle, browser cache on, 1440x900:

| | before | after | |
|---|---|---|---|
| Transferred | 26.3 MB | **1.66 MB** | 15.8x less |
| — images | 24.7 MB | **1.0 MB** | 24.8x less |
| — script | 1114 KB | **322 KB** | gzip |
| — stylesheet | 126 KB | **19 KB** | gzip |
| Image pixels decoded | 99.5 MP | **5.0 MP** | 20x less |
| Load (networkidle2) | 8.6 s | **3.7 s** | 2.3x faster |
| First Contentful Paint | 2.79 s | **2.12 s** | |
| CLS | 0.0155 | 0.0157 | unchanged |

Scrolling *during* that first load - while the images are still streaming in, which is
when the app actually feels bad - went from a median frame of **55 ms with 13 of 18
frames dropped** to **7 ms with 1 of 207 dropped**. Once everything is decoded, the
original scrolled smoothly too; the jank was the download-and-decode storm, not a
permanent rendering fault.

Tab switching at normal CPU speed, median of three runs: Search 11 ms (was 11), Map
13 ms (was 14), Food 29 ms (was 26), **Social 55 ms (was 127)**. Typing in the map search
field now lands inside a single frame on every keystroke; it previously spilled past one
frame on the worst keystrokes (worst 14.5-18.8 ms, was 21.4-25 ms).

### What was changed

Asset side, all reversible and reproducible from `tools/` (see `tools/README.md`):

- **Photos re-encoded** with a per-image quality search rather than a fixed number:
  quality steps up from 78 until RMS error against the original is under 4/255. 27.7 MB
  of JPEG/PNG became 9.6 MB. A `.webp` twin is written beside each file.
- **160px thumbnails** generated for every photo. A map marker now costs **6 KB instead
  of 285 KB**.
- **`serve.py`** gained gzip for text, WebP content negotiation under the original `.jpg`
  URL with `Vary: Accept`, and real `Cache-Control` - hashed `/assets/` immutable for a
  year, photos a week, the shell still `no-store`.

Bundle side, two scripts, both asserting on what they find rather than editing blind:

- 86 Unsplash URLs asked for `w=1200` (four for `w=2000&q=90`) when nothing here paints
  wider than ~900 CSS px; now `w=1000&q=72`.
- All 29 React `<img>` sites got `loading="lazy"` and `decoding="async"`.
- A `__ihT(url, width)` helper now feeds the 88 markers and 11 avatar slots their 160px
  variant. It rewrites only Unsplash URLs and local paths verified present in a generated
  manifest; QR codes, other hosts and `undefined` pass through untouched, so no rewrite
  can 404.

CSS side, rules 35-40 in `dist/index.html`:

- **35.** The Google Fonts stylesheet was render-blocking. It already carries
  `display=swap`, so the page was designed to paint in the fallback and swap - it just
  never got the chance. Now loaded with `media="print"` and flipped on load.
- **36 / 36b.** `backdrop-filter` removed where the background is 90-98% opaque. The blur
  was doing one thing worth keeping - smearing the 2-5% sliver of page showing through
  into an unreadable wash - so the five full-width pinned surfaces go fully opaque in the
  colour they were already 95-98% of. Smaller chips keep their translucency; at chip size
  a 5% sharp bleed and a 5% blurred one look the same.
- **37.** `transition-property: all` on 156 elements meant every hover also animated
  width, height and padding, each forcing a re-layout mid-animation. Replaced with
  Tailwind's own default transition list: everything paintable or composited, nothing
  that moves other boxes.
- **38.** `content-visibility: auto` on the footer - 866 px of a 2120 px document, below
  the fold, with its own share of the always-running pulse animations.
- **39.** `contain: layout paint` on the Leaflet container, so 88 markers mutating on
  every pan cannot invalidate layout back out into the page.
- **40.** Intrinsic sizing on marker images.

### Verification status

Verified by reconstructing the pre-pass build from `.perf-backup/` and serving both side
by side. Desktop (1440x900) and mobile (390x844): identical document height, scroll
width, DOM node count (+4, the payment-marks strip), button count, marker count, marker
images loaded, and header text. **Zero** broken images and **zero** uncaught exceptions
on both. Screenshot diff is 0.04-0.06% of pixels above a 64/255 threshold, all of it text
antialiasing against the newly-opaque bars and marker photos resampled from 160px sources.

The bundle was parsed with `vm.Script` after each patch, and `__ihT` was unit-tested
against local paths, Unsplash URLs, QR-code URLs, a non-existent file, `undefined`,
`null` and `""`.

**Not addressed:** the bundle contains no `React.memo` and only 20 `useMemo` calls, so
state changes re-render broadly. That needs the source. It is not currently the
bottleneck and was left alone deliberately.

**These changes live in the compiled bundle and in `dist/` media, so they are lost the
moment the app is rebuilt from source.** Re-run `tools/` after any rebuild, or better,
move the image pipeline and the `loading`/`decoding` attributes upstream.

---

## Making the header mark prominent

The first pass put the logo's illustration into the header inside its own cream tile. That was
faithful to the artwork but wrong in context: a cream box on a near-black header reads as a
sticker pasted on, and it could not grow without becoming a bright block.

**The fix was to remove the container, not to enlarge it.** The artwork is cut out of its cream
ground by flood-filling the background inward from the edges, which deletes the ground while
preserving the white linework *inside* the drawing (67% of pixels removed). It now sits
directly on the header, so it can be much larger without introducing any light area. The amber
sun and orange lantern carry it, and those are already the app's own accent colours.

The author's amber-to-rose gradient ring goes with it. The artwork no longer needs a container,
and the polish pass reserved rose for the SOS control.

**How the size was chosen.** Six treatments were rendered against the live page with Puppeteer
and compared at real scale: the shipping baseline, cutouts at 40, 48 and 56px, a cutout on a
dark tile with an amber hairline, and a cutout with an amber halo. The dark tile reintroduced a
frame that competed with the artwork for no gain. The halo was invisible at header size and was
cut. Of the plain cutouts, 56px was the largest that still balanced the two-line wordmark.

| | before | after |
|---|---|---|
| mark size, desktop | 40x40 inside a ring | 72x56, no container |
| mark size, mobile | 40x40 | 56x44 |
| light-coloured area in the header | a 36px cream tile | none |

It steps down to 44px on phones so the wrapped mobile header does not grow and eat the vertical
space the map fought for. Verified on both viewports: the rule wins on specificity with no
`!important`, the ring gradient computes to `none`, there is no horizontal overflow, the modals
still open and close, and the console stays at zero errors. The mobile map moved 4px lower, 655
to 659, which is the cost of the larger mark.

---

## The logo's own wordmark, and an install hint

### The wordmark was the missing half of the logo

The header set "INSIDE HOI AN" as plain amber serif text, so the logo's *designed* wordmark
was never used. That drawing is not generic type: the **O is a wave roundel** and the **A
contains the Japanese Covered Bridge**, Hoi An's own landmark. Throwing it away and setting
the name in a stock serif loses the part of the logo that is specific to this town.

It could not simply be dropped in, because it is drawn in dark green (`#304137`) on cream and
would have been invisible on a near-black header. So the ink was extracted to an alpha channel
by luminance and re-tinted to the app's amber. The mark and the wordmark now come from the
same artwork.

The text is **not** removed. Only its colour is transparent, so screen readers, search engines
and copy-paste still see "INSIDE HOI AN". Verified in the DOM after the change.

Six colour and size treatments were rendered against the live header with Puppeteer and
compared at real scale. Cream and warm white both read as cold against this warm palette;
amber matches the accent the header already used. At 30px the lockup crowded the tagline; at
42px it breathes. An earlier version hid the tagline to make room, which was unnecessary once
measured: at 42px the brand block is 55px inside a 65px header, with nothing clipped.

| | before | after |
|---|---|---|
| wordmark | amber serif text, 139x28 | the logo's drawn wordmark, 132x42 |
| wave-O and bridge-A | not shown | shown |
| tagline | visible | still visible |
| header height | 65px | 65px |

It steps down to 34px on phones. No horizontal overflow at either width, and the console stays
at zero errors.

### A minimal install hint

Nothing in the interface told a visitor the app was installable, which is the one thing about
a PWA a user cannot discover alone. There is now a single dismissible chip above the bottom
nav, not a banner.

It is deliberately quiet, and never appears when it would be useless:

- not once the app is already installed (`display-mode: standalone`)
- not after it has been dismissed once (remembered in `localStorage`)
- not in a browser with no install path at all
- not for 2.5 seconds after load, so it never competes with first paint

Chrome and Edge fire `beforeinstallprompt`, so there the chip drives the real install dialog.
iOS Safari has no such event, so there it explains the Share then "Add to Home Screen" route,
which is the only way in on that platform. It follows the app's language toggle, so it reads
"Cài đặt ứng dụng" in Vietnamese.

Verified at both widths: it sits inside the viewport, does not overlap the bottom tab bar,
sits at `z-index: 900` so modals still cover it, dismisses on click and on Escape, and both of
its buttons are 44px touch targets. Test hook `window.__installChip()` forces it to render.

---

## Header lockup: spacing, the GUIDE pill, and clicking home

### The tagline was colliding with the wordmark

Swapping the text wordmark for the logo's drawing exposed a spacing assumption. The tagline
carries `-mt-0.5`, a **-2px** top margin that was tuned for the old text: a 28px line box
around ~18px glyphs leaves roughly 5px of internal leading underneath, and the negative margin
pulled the tagline up into that empty space.

An image has no internal leading. Its ink runs to the edge of its box. So the same -2px pulled
"Curated Heritage Guide & Map" **into** the underside of HOI AN - measured at -2px, meaning
they overlapped.

Six size and spacing pairs were rendered and compared. 42px with 5px of air was the most
prominent but left the brand block at 62px inside a 65px header, about 1.5px of margin, which
is too tight to survive a font fallback. **38px with 4px of air** keeps the wordmark dominant
at a 57px block, with 4px of headroom.

| | before | after |
|---|---|---|
| wordmark | 132x42 | 119x38 |
| tagline gap | -2px, overlapping | +4px |
| brand block height | 55px | 57px in a 65px header |

### The GUIDE pill is gone

Removed at your request, and it agrees with the polish pass, which had already argued that too
many badges were competing at once. The logo's own wordmark now says what the product is, so a
second amber chip repeating it beside the name was noise.

### The brand block did nothing when clicked

A real defect, not a preference. The block is styled `cursor-pointer group`, so it advertises
itself as clickable, but **no handler was ever attached**. Verified before changing anything:
clicking it left `scrollY` at 1220 and the URL untouched.

The whole block - mark, wordmark and tagline, 236x65 - now navigates home. It is a real
navigation rather than a scroll-to-top because the current tab, open panels and filters live in
React state that a stylesheet cannot reach; going to `/` is the only way to genuinely return to
the default view. It skips the navigation when the user is already home, at the top, with
nothing open, so it never reloads for nothing.

It is also keyboard reachable now, which it was not: `role="link"`, `tabindex="0"`, an
`aria-label`, and Enter or Space activate it.

Verified: clicking the logo while scrolled returns to y=0, clicking the wordmark does the same,
clicking while already home does not reload, the block takes focus, and the console stays at
zero errors.

---

## Header navigation: half of it was unreachable — ALL OF IT REVERTED

> **Status: withdrawn at the owner's request.** Everything in this section was applied,
> measured, and then removed. The nav bar, its pills and badges, the container width and the
> search position are all exactly as the build shipped them. The measurements below are kept
> because the underlying problem is real and worth fixing upstream, but **none of it is in
> the file any more.**
>
> What is still applied from the header work: the logo mark, the logo's own wordmark, the
> tagline spacing fix, the GUIDE pill removal, and the brand block acting as a home link.


You asked whether the horizontally scrolling top nav was bad UX. It was, and worse than it
looked. Measured before changing anything:

| | value |
|---|---|
| nav items | 8 |
| nav content width | 1290px |
| space given to it | 588px |
| **hidden behind the scroll** | **702px, 5 of 8 items** |

The hidden items were **AI Itinerary, AI Translator, My Bookings and Partnerships**, with
Culture & Sports cut mid-word. My Bookings carries a live count badge showing 2 bookings, so a
user with bookings could not reach them. The nav is styled `no-scrollbar`, so there was not
even a scrollbar hinting that more existed.

**The part that makes it a real defect rather than a preference:** widening the browser did not
help. The container is capped at `max-w-7xl`, 1280px, so the nav had exactly 588px whether the
monitor was 1280, 1440 or 1920. Identical measurements at all three.

On moving SOS, the concierge and the language toggle right: they were already flush right, but
against a 1280px column rather than the screen. Uncapping moves them to the true edge, from
x=1584 to x=1904 on a 1920 display.

### What changed, at 1280 and up

1. The header container uses the real screen width instead of a 1280px column.
2. The search moves across to sit with the right-hand controls, freeing its 90px for the nav.
3. The nav wraps instead of scrolling, so nothing is ever out of reach.

| width | nav hidden before | after | header height |
|---|---|---|---|
| 1920 | 702px, 5 items | 0 | 78px, one row |
| 1440 | 702px, 5 items | 0 | 91px, two rows |
| 1280 | 702px, 5 items | 0 | 126px, two rows |

The map starts 13 to 61px lower on desktop as a result, which is the cost of the extra rows.

### Deliberately not applied below 1280

Wrapping in the narrower column produces three or four nav rows: measured **196px of header at
1024 and 210px at 768**, roughly a quarter of the viewport, which costs more than the hidden
items are worth on a screen that also offers the menu button. Below 1280 the nav is left
exactly as it shipped. Mobile is untouched: header 170px and map top 659px, both unchanged.

### How the nav bar reads, and what was fixed (REVERTED)

With nothing hidden any more, three things still looked wrong. All were measured on the
rendered page rather than guessed at.

1. **"Partnerships" was the only green thing in an amber nav.** Emerald text on an emerald
   ground, louder than every primary view beside it, for the least important link in the row.
   The button and its icon both had to be overridden: the icon carries its own
   `text-emerald-400`, so neutralising the button alone left a green glyph on a grey label.
2. **The right-hand controls floated.** They were vertically centred against a nav that now
   wraps to two rows, leaving dead space above and below. They align to the first row instead.
3. **Five badges competed.** `360`, `HOT`, `LIVE`, `NEW` and a booking count. Four of those
   describe the app's enthusiasm; only the count carries information. The four are dimmed to
   55% and slightly reduced. The count is untouched.

A divider between the four views and the four tools was tried and **dropped**: at this size it
was invisible, so it was a rule that did not earn its place.

### What is still not right, honestly

- **At 1440 the second row has a ragged right edge**, with a wide gap before the search. That
  is inherent to wrapping eight items into two rows and cannot be tidied without changing how
  many items there are.
- **Eight top-level items is too many.** The real fix is information architecture: keep four or
  five primary destinations in the bar and move Partnerships, AI Translator and My Bookings
  into the existing menu. That is a source change, not a stylesheet one.
- **SOS and AI Concierge are two saturated gradient pills side by side**, so the emergency
  control and a feature button compete at equal volume. Muting the concierge to an outline
  would leave SOS as the only saturated element in the header. One rule, available on request.

### The two-row header: what was applied, and what could not be (REVERTED)

**Applied: the header no longer hugs the screen edges.** Uncapping it entirely left the brand
and the controls 16px from each side of a 1920 monitor. It is now capped at 1600px, which gives
a 176px margin each side at 1920 while still being 320px wider than the 1280 the build shipped
with. Nothing is clipped and the header stays 91px.

**Already true: SOS and the language toggle are top right.** They sit at the right edge of the
first row, now 176px in from the screen edge rather than flush against it.

**Not applied: search and AI Concierge centred on a second row.** Five implementations were
tried against the live page - CSS grid with named areas, flex wrap with auto-margin centring,
a forced full-width break, and two column arrangements. Every one either made the header far
taller or broke the "SOS top right" requirement:

| attempt | header at 1440 | outcome |
|---|---|---|
| current | 91px | - |
| grid, named areas | 133px | SOS fell to the second row |
| flex wrap, auto margins | 170px | SOS on row two, brand hard against the left |
| forced full-width search row | 214px | three rows |
| cap + centred search | 206px | SOS and the concierge dropped under the brand |

**The reason is structural, not stylistic.** The header is a single flex row with four children:
brand, search, nav, and one control node that contains SOS, AI Concierge and the language
toggle together. Moving the concierge to a different row from its two siblings means splitting
that node, and CSS cannot split a DOM node. `display: contents` dissolves it, but then flex
line-breaking decides where all three land, and it puts SOS on the second row every time.

**The fix upstream is small.** In the source, split the control node in two: keep SOS and the
language toggle in the top-right cluster, and put the search and the concierge in their own
centred row beneath the nav. That is a markup change of a few lines and would land exactly the
layout described, without the height cost, because the rows would be explicit rather than the
result of flex wrapping.

---

## Header breathing room

The header row is a fixed `h-16`, 64px, and the brand mark is 56px tall. That left **4px above
the logo and 5px below** on desktop, so the mark was nearly touching the top of the browser
window. The wrapped mobile header already had 12px above, so desktop was the outlier.

Symmetric 8px padding on the row takes it to 13px above and 14px below, matching what mobile
already felt like. Scoped to 1024 and up, where the header is the single tall row; below that
it wraps and already carries its own padding.

| | before | after |
|---|---|---|
| space above the logo | 4px | 13px |
| header height | 65px | 82px |
| map top | y=365 | y=382 |

Mobile is untouched: 12px above the mark, 170px header, map top y=659, all unchanged.

## Mobile audit and map-first pass (rules 41-50)

Reported as "I can't even see the map on mobile", then "tickets, events and translate
are stretched out" and "the Search/Map/Food/Social bar sometimes floats to the middle".
Audited by driving Chrome at five widths - 320, 360, 390, 430 and 768 - through all
nineteen destinations in the header and the tab bar, measuring every element's box
against its container rather than eyeballing screenshots.

### 20. The map was 78% below the fold — FIXED

Not a rendering fault. The map was present, sized and drawing all 88 markers; it was
simply pushed off the bottom of the screen by everything stacked above it.

| device | header | content above map | map height | **map actually visible** |
|---|---|---|---|---|
| iPhone SE 320 | 218px | 597px | 504px | **90px** |
| Android 360 | 218px | 666px | 676px | **130px** |
| iPhone 14 390 | 170px | 659px | 780px | **185px** |
| iPhone Max 430 | 170px | 676px | 868px | **256px** |

The app opened on a currency table and a five-day weather forecast, and the sliver of
map that remained was covered by the events banner and the install chip.

The previous audit recorded this as defect 12 and deferred it: *"the real fix is a
map-first mobile layout, which needs source."* It does not. The map wrapper and the two
information strips are siblings in one flex column, so giving the strips a positive
`order` moves the map above them (rule 41) — the strips keep every pixel of content,
one swipe down. Rule 42 then sizes the map to exactly the gap between the header and
the tab bar, using a runtime-measured `--ih-chrome` because the header is 170px at
390px wide and 218px at 320px, and `dvh` so it does not sit under iOS's collapsing
address bar. Leaflet is told to re-measure whenever that value changes, or it keeps
drawing at the old size.

| device | before | after |
|---|---|---|
| iPhone SE 320 | 90px | **300px (all of it)** |
| Android 360 | 130px | **461px (all of it)** |
| iPhone 14 390 | 185px | **613px (all of it)** |
| iPhone Max 430 | 256px | **701px (all of it)** |
| iPad mini 768 | 396px | **777px (all of it)** |

### 21. Tickets threw away 890px of every row — FIXED

The worst defect in this pass, and invisible on a desktop. Every page wrapper inside
`<main>` is `max-w-7xl mx-auto ... flex-1`. `<main>` is `flex flex-col`, and **auto
margins on the cross axis switch off a flex item's stretch** — so instead of taking the
parent's width, the wrapper sized to its own max-content and clamped at
`max-w-7xl` = 1280px. Inside a 390px `<main>` with `overflow-hidden`, that cut 890px off
the right of every row with no scrollbar and no way to reach it: headings ended
mid-word, body copy stopped mid-sentence, and three of four booking buttons were gone.

Measured: `<main>` box 390px, content 1280px. It survives on desktop only because the
viewport is wider than 1280. One line restores the stretch (rule 46), and the wrappers
then behave the way `max-w-7xl mx-auto` reads on the page.

### 22. Controls crushed or clipped in four sections — FIXED

| where | what was measured | fix |
|---|---|---|
| Events | 6-segment date filter, 413px row in a 390px column, labels wrapping to three lines; price/audience dropdowns cut off | rule 48 — scrolls sideways, one-line labels |
| Translate | 3-segment mode switch, every label broken across three lines in 364px | rule 48 |
| VR360 | scene picker 1118px wide inside a 390px panel with `overflow-hidden`: **787px unreachable**, plus 108px of the control cluster | rule 49 — scrolls sideways |
| Tab bar | Search / Map / Food / Social needed 387px, so the document scrolled sideways 67px at 320px — which also dragged the install chip's **close button off-screen, making it undismissable** | rule 43 tightens padding below 400px; rule 44 clamps any bottom-anchored chip |

Horizontal overflow measured 67px at 320px and 27px at 360px before, **0px at every
width after**.

### 23. The events banner covered the map — FIXED

`absolute bottom-4` inside the map wrapper, rendering expanded at 727px — taller than
the whole map on a phone. Harmless while the map was off-screen; once rule 41 brought
the map up it covered 97% of it. Rule 47 caps it and lets its body scroll, the same
treatment rule 15 gave the weather panel. Its own Minimize button still wins. The cap
is 28vh, dropping to 21vh under a 700px-tall screen, because on a short phone the map
itself is only ~300px and a viewport-relative cap would still have taken half of it.
Measured after: the panel is 37-40% of the map instead of 97%.

Rule 49b also moved the four map-mode pills from `top-20` to `top: 8rem`. The search
field and chip row occupy the first 114px of the map, so the pills were painted on top
of the chips and both were unreadable where they crossed - the defect the earlier audit
logged as 17 and withdrew as unfixable ("four labelled pills do not fit a 390px phone
at all"). They fit; they were starting too high. Overlap measured 370px2 before, **0
at every width after**.

### 24. The tab bar floating to mid-screen — HARDENED, not reproduced

Could not be reproduced in emulation: it is pinned to the bottom in all nineteen
destinations, at the top, middle and bottom of every page, with overlays open, and with
a search that matches nothing. That points at the two things a desktop browser cannot
reproduce, and both produce exactly this symptom:

* **The on-screen keyboard.** By default only the visual viewport shrinks, so a bar
  pinned to the bottom of the unchanged layout viewport ends up part-way up what you
  can see. Fixed with `interactive-widget=resizes-content` on the viewport meta.
* **iOS Safari's collapsing address bar.** `min-h-screen` is `100vh`, which on iOS is
  the height with the address bar *collapsed* — taller than the visible area while it
  is showing. Rule 50 switches it to `dvh` (with `svh` as the fallback) on mobile.

Rule 50 also gives the bar the `env(safe-area-inset-bottom)` padding it never had: the
page sets `viewport-fit=cover`, so without it the tab labels sit under the home
indicator on any notched iPhone.

**If it still happens, it is worth knowing exactly when** — which tab, and whether the
keyboard was open — because that distinguishes the two causes above from a third.

### Not defects

* **SOS panel, 32px "clipped".** A decorative watermark at `-right-8 -bottom-8
  opacity-15`, deliberately hung off the corner and clipped. Intentional.
* **The map filter chip row, 1811px wide.** Inside `overflow-x-auto`; a real scroller,
  reachable by design.

### Verification

Nineteen destinations x five widths. After: **0px horizontal overflow at every width**,
tab bar pinned in every section at every scroll position, **0 uncaught exceptions, 0
failed requests, 0 broken images**, 88 markers drawing on every device. Desktop
re-checked and unchanged.

One regression was caught and fixed during this pass: the rule-45 MutationObserver ran
its callback on every React render, costing 18 of 114 frames while scrolling and taking
the median frame from 7ms to 13.9ms. Debounced and self-disconnecting, the median is
back to 7.1ms.

Page weight rose from 1.66 MB to ~2.7 MB, all of it map tiles and marker art. That is
the cost of the map now being on screen and therefore actually loading, rather than
sitting below the fold where `loading="lazy"` deferred it — the fix working, not
regressing.

## Not a defect: local-copy limitations

The live site has a real backend. This folder does not, so these are stubbed:

| Endpoint | Local behavior |
|---|---|
| `GET /api/bookings` | Served from a captured snapshot in `dist/_api/` |
| `POST /api/ai/guide-chat` | 501 with an explanatory JSON body |
| `POST /api/ai/plan-itinerary` | 501 |
| `POST /api/ai/translate` | 501 |
| `POST /api/partners/apply` | 501 |

The AI Concierge opens and renders locally but cannot answer. That needs the deployed
backend, not a fix here.

## Security note

The bundle contains **no embedded API key** and makes no direct calls to the Gemini API.
All AI work is proxied through the site's own `/api/ai/*` endpoints, which is the correct
design. The `GEMINI_API_KEY` in `.env.local` is unused by this build.

## Files changed

| File | Change |
|---|---|
| `dist/index.html` | Fixes 2-6, 9-15, polish 20-33, brand mark, PWA wiring, performance 35-40, mobile map-first 41-50 |
| `dist/manifest.webmanifest`, `dist/sw.js` | New: PWA manifest and service worker |
| `dist/brand/`, `dist/icons/`, `dist/favicon.ico`, `dist/apple-touch-icon.png`, `dist/og-card.png` | New: brand assets from InsideHoiAnLogo.png |
| `serve.py` | Manifest media type, no-store on the service worker; gzip, WebP negotiation, Cache-Control |
| `dist/assets/index-B97Xc7BA.js` | Fix 1 (two string replacements); performance pass (Unsplash sizes, lazy/async decode, `__ihT` thumbnails) |
| `dist/favicon.svg` | New |
| `dist/assets/leaflet-1.9.4.css` | Vendored |
| `dist/images/` | 17 images the first download missed |
| `dist/_api/api_bookings.json` | Captured API response |
| `dist/images/`, `dist/assets/*.jpg` | Re-encoded; `.webp` twins and `-160` thumbnails added |
| `tools/` | New: the four scripts that reproduce the performance pass |
| `serve.py`, `serve.bat` | Local server |

Unmodified originals are in `.original-backup/`. The pre-performance-pass
`index.html`, `sw.js`, `serve.py`, bundle and all 47 original media files are in
`.perf-backup/`.

**These fixes live in the compiled bundle, so they are lost the moment the app is
rebuilt from source.** Items 1-8 all need to be applied upstream to stick.
