"""Surgical performance patches to the compiled bundle.

There is no source for this build, so the two changes below are made against
the minified output. Both are shape-preserving string edits, not rewrites:

 1. Remote Unsplash art is requested at w=1200 (54 URLs) and w=2000&q=90
    (4 URLs). Nothing in this layout renders a photo wider than ~900 CSS px,
    so the extra pixels are decoded and thrown away. Unsplash's CDN resizes
    from the query string, so this is a pure URL edit.

 2. All 29 React <img> sites render eagerly and decode synchronously. Adding
    loading/decoding first in the props object means any site that sets its
    own value still wins, because a later duplicate key overrides an earlier.
"""
import re, sys, shutil, os

path = sys.argv[1]
src = open(path, encoding='utf-8').read()
orig = src

# --- 1. Unsplash sizes -------------------------------------------------------
before_1200 = src.count('auto=format&fit=crop&w=1200&q=80')
before_2000 = src.count('auto=format&fit=crop&w=2000&q=90')
src = src.replace('auto=format&fit=crop&w=1200&q=80', 'auto=format&fit=crop&w=1000&q=72')
src = src.replace('auto=format&fit=crop&w=2000&q=90', 'auto=format&fit=crop&w=1400&q=78')

# --- 2. img decoding hints ---------------------------------------------------
IMG = 't.jsx("img",{'
before_img = src.count(IMG)
src = src.replace(IMG, 't.jsx("img",{loading:"lazy",decoding:"async",')

# --- guard rails -------------------------------------------------------------
assert src.count('t.jsx("img",{loading:"lazy",decoding:"async",') == before_img
assert 'w=1200&q=80' not in src
assert len(src) > len(orig)

open(path, 'w', encoding='utf-8', newline='').write(src)
print(f'unsplash w=1200 -> w=1000 : {before_1200} refs')
print(f'unsplash w=2000 -> w=1400 : {before_2000} refs')
print(f'img lazy + async decode   : {before_img} sites')
print(f'bundle {len(orig)} -> {len(src)} bytes')
