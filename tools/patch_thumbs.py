"""Point the small image slots at the 160px variants.

Adds one global helper, __ihT(url, width), then rewrites the src expression
at the render sites whose own CSS class says they paint at <=72 CSS px:
the 88 map markers (40x40) and the avatar/thumbnail slots.

The helper is deliberately conservative. It rewrites only:
  * images.unsplash.com URLs, whose CDN resizes from the query string, and
  * local paths present in the generated-thumbnail manifest.
Anything else - QR codes, data URIs, other hosts, undefined - is returned
untouched, so no rewrite can produce a 404.
"""
import json
import os
import re
import sys

DIST, BUNDLE = sys.argv[1], sys.argv[2]
W = 160

BS = chr(92)          # backslash, kept out of literals so the file stays portable
BQ = chr(96)          # backtick

# ---- manifest of paths that actually have a -160 twin on disk ---------------
have = []
for sub in ('images', 'assets'):
    d = os.path.join(DIST, sub)
    for n in sorted(os.listdir(d)):
        b, e = os.path.splitext(n)
        if e.lower() in ('.jpg', '.jpeg') and not b.endswith('-%d' % W) \
           and os.path.exists(os.path.join(d, '%s-%d.jpg' % (b, W))):
            have.append('/%s/%s' % (sub, n))

src = open(BUNDLE, encoding='utf-8').read()
orig = src

table = json.dumps({p: 1 for p in have}, separators=(',', ':'))
helper = (
    '(function(){var IHT=' + table + ';'
    'globalThis.__ihT=function(u,w){'
    'if(typeof u!=="string"||!u)return u;'
    'if(u.indexOf("images.unsplash.com")!==-1)'
    'return u.replace(/([?&]w=)' + BS + 'd+/,"$1"+w).replace(/([?&]q=)' + BS + 'd+/,"$1"+70);'
    'if(IHT[u])return u.replace(/' + BS + '.jpe?g$/i,"-"+w+".jpg");'
    'return u;};})();'
)

# ---- 1. map markers ---------------------------------------------------------
MARKER = '<img src="${b.image}"'
assert src.count(MARKER) == 1, src.count(MARKER)
src = src.replace(MARKER, '<img src="${__ihT(b.image,%d)}"' % W)

# ---- 2. small React <img> sites --------------------------------------------
SMALL = re.compile(r'\bw-(?:7|8|9|10|12|14|18)\b')
OPEN = 't.jsx("img",{loading:"lazy",decoding:"async",'


def _skip_quoted(s, i, n):
    """i points at the opening quote; return index just past the closing quote."""
    q = s[i]
    i += 1
    while i < n:
        if s[i] == BS:
            i += 2
            continue
        if s[i] == q:
            return i + 1
        if q == BQ and s[i] == '$' and i + 1 < n and s[i + 1] == '{':
            depth, i = 1, i + 2
            while i < n and depth:
                if s[i] in '"' + "'" + BQ:
                    i = _skip_quoted(s, i, n)
                    continue
                if s[i] == '{':
                    depth += 1
                elif s[i] == '}':
                    depth -= 1
                i += 1
            continue
        i += 1
    raise ValueError('unterminated string')


def props_span(s, start):
    """End index of the balanced props object whose first char is at `start`."""
    depth, i, n = 1, start, len(s)
    while i < n:
        ch = s[i]
        if ch in '"' + "'" + BQ:
            i = _skip_quoted(s, i, n)
            continue
        if ch in '{([':
            depth += 1
        elif ch in '})]':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError('unbalanced props')


def expr_end(s, start):
    """End of the value expression at `start`: the top-level comma or closer."""
    depth, i, n = 0, start, len(s)
    while i < n:
        ch = s[i]
        if ch in '"' + "'" + BQ:
            i = _skip_quoted(s, i, n)
            continue
        if ch in '{([':
            depth += 1
        elif ch in '})]':
            if depth == 0:
                return i
            depth -= 1
        elif ch == ',' and depth == 0:
            return i
        i += 1
    raise ValueError('unbalanced expr')


edits, skipped = [], []
pos = 0
while True:
    k = src.find(OPEN, pos)
    if k == -1:
        break
    pos = k + len(OPEN)
    end = props_span(src, pos)
    props = src[pos:end]
    cls = re.search(r'className:"([^"]*)"', props)
    label = cls.group(1) if cls else '?'
    if not cls or not SMALL.search(label):
        skipped.append('full-size: ' + label[:46])
        continue
    sm = re.search(r'(?<![\w$])src:', props)
    if not sm:
        skipped.append('no src: ' + label[:46])
        continue
    vs = pos + sm.end()
    ve = expr_end(src, vs)
    expr = src[vs:ve]
    if 'qrCode' in expr or 'qrserver' in expr:
        skipped.append('qr code: ' + expr[:40])
        continue
    edits.append((vs, ve, expr, label[:52]))

for vs, ve, expr, cls in reversed(edits):
    src = src[:vs] + '__ihT(%s,%d)' % (expr, W) + src[ve:]

src = helper + src

# one call per rewritten React site, plus the one inside the marker template
# (the helper itself is a `__ihT=` assignment, not a call).
assert src.count('__ihT(') == len(edits) + 1, (src.count('__ihT('), len(edits))
open(BUNDLE, 'w', encoding='utf-8', newline='').write(src)

print('manifest: %d local photos have a -%d twin' % (len(have), W))
print('markers : 1 template rewritten (88 markers at 40x40)')
print('react   : %d small <img> sites rewritten' % len(edits))
for _, _, e, c in edits:
    print('    src:%-30s .%s' % (e, c))
print('skipped : %d sites left at full size' % len(skipped))
print('bundle  : %d -> %d bytes (+%d)' % (len(orig), len(src), len(src) - len(orig)))
