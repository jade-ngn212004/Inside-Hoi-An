"""Re-encode dist/ media in place.

The build ships AI-generated art saved at ~1 byte per pixel (quality ~98,
no chroma subsampling). Every one of those files is also used as a 32px
thumbnail somewhere. Re-encoding to a normal web quality is the single
largest win available and needs no code change, because filenames are kept.

Quality is not fixed: each image starts at a target quality and steps up
until its RMS error against the original is under the threshold, so
detailed images keep their detail instead of being uniformly crushed.
A WebP twin is written beside each JPEG for browsers that accept it.
Nothing is replaced unless the new file is actually smaller.
"""
import os, sys, math, io
from PIL import Image, ImageChops

Image.MAX_IMAGE_PIXELS = None
DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist')
DIST = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\cjrec\Downloads\inside-hoi-an\dist'

MAX_EDGE     = 1400   # longest edge; the build's own art tops out at 1376
JPEG_START   = 78
JPEG_CEILING = 90
RMS_LIMIT    = 4.0    # 0-255 scale; ~4 is visually transparent for photos
PNG_RMS_LIMIT = 3.0

def rms(a, b):
    if a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)
    a = a.convert('RGB'); b = b.convert('RGB')
    diff = ImageChops.difference(a, b)
    h = diff.histogram()
    total = 0; count = 0
    for band in range(3):
        for i, n in enumerate(h[band*256:(band+1)*256]):
            total += n * i * i; count += n
    return math.sqrt(total / count) if count else 0.0

def encode_jpeg(img, q):
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=q, optimize=True, progressive=True, subsampling='4:2:0')
    return buf.getvalue()

def encode_webp(img, q):
    buf = io.BytesIO()
    img.save(buf, 'WEBP', quality=q, method=6)
    return buf.getvalue()

def encode_png(img, quantize):
    buf = io.BytesIO()
    if quantize:
        out = img.convert('RGBA').quantize(colors=256, method=Image.Quantize.FASTOCTREE)
    else:
        out = img
    out.save(buf, 'PNG', optimize=True, compress_level=9)
    return buf.getvalue()

# Files whose on-screen size is far below their intrinsic size.
RESIZE_TO = {
    'brand/logo-mark.png': 192,   # header tile renders it at 36-40px
}
SKIP = {'favicon.ico'}

# Assets whose pixel dimensions are a contract, not a preference: the manifest
# declares `sizes` for every icon and screenshot, and the og: meta tags declare
# width and height. Chrome silently drops a screenshot whose real size does not
# match what the manifest claims, so these are compressed but never rescaled.
# (This caught a real regression: the MAX_EDGE cap shrank the 1170x2532 mobile
# screenshot to 647x1400 and quietly invalidated the manifest entry.)
NO_RESIZE_PREFIXES = ('icons/', 'screenshots/')
NO_RESIZE_FILES = {'og-card.png', 'apple-touch-icon.png', 'favicon-48.png'}


def dimensions_are_declared(rel):
    return rel.startswith(NO_RESIZE_PREFIXES) or os.path.basename(rel) in NO_RESIZE_FILES

rows = []
before_total = after_total = 0
webp_total = 0

for root, _, files in os.walk(DIST):
    for name in sorted(files):
        ext = os.path.splitext(name)[1].lower()
        if ext not in ('.jpg', '.jpeg', '.png'):
            continue
        path = os.path.join(root, name)
        rel = os.path.relpath(path, DIST).replace(os.sep, '/')
        if name in SKIP:
            continue
        orig_size = os.path.getsize(path)
        if orig_size < 12_000 and rel not in RESIZE_TO:
            continue                       # already tiny; not worth the churn
        src = Image.open(path)
        src.load()
        reference = src.copy()

        img = src
        forced = RESIZE_TO.get(rel)
        if forced:
            img = img.resize((forced, forced), Image.LANCZOS)
        elif max(img.size) > MAX_EDGE and not dimensions_are_declared(rel):
            scale = MAX_EDGE / max(img.size)
            img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)

        if ext in ('.jpg', '.jpeg'):
            img = img.convert('RGB')
            q = JPEG_START
            while True:
                data = encode_jpeg(img, q)
                err = rms(reference, Image.open(io.BytesIO(data)))
                if err <= RMS_LIMIT or q >= JPEG_CEILING:
                    break
                q += 4
            # WebP twin, matched to the same error budget.
            wq = 74
            while True:
                wdata = encode_webp(img, wq)
                werr = rms(reference, Image.open(io.BytesIO(wdata)))
                if werr <= RMS_LIMIT or wq >= 88:
                    break
                wq += 4
            wpath = os.path.splitext(path)[0] + '.webp'
            if len(wdata) < len(data):
                open(wpath, 'wb').write(wdata)
                webp_total += len(wdata)
                wnote = f'webp q{wq} {len(wdata)/1024:.0f}KB'
            else:
                wnote = 'webp skipped'
            note = f'q{q} {err:.1f}rms | {wnote}'
        else:
            plain = encode_png(img, quantize=False)
            data, note = plain, 'png re-encode'
            try:
                quant = encode_png(img, quantize=True)
                qerr = rms(reference, Image.open(io.BytesIO(quant)))
                if len(quant) < len(plain) and qerr <= PNG_RMS_LIMIT:
                    data, note = quant, f'png 256c {qerr:.1f}rms'
            except Exception:
                pass
            if forced:
                note += f' resized->{forced}px'

        if len(data) < orig_size:
            open(path, 'wb').write(data)
            new_size = len(data)
        else:
            new_size = orig_size
            note += ' (kept original, no gain)'

        before_total += orig_size
        after_total += new_size
        rows.append((orig_size, new_size, rel, note))

print(f'{"before":>9} {"after":>9} {"saved":>6}  file')
for o, n, rel, note in sorted(rows, key=lambda r: r[0] - r[1], reverse=True):
    print(f'{o/1024:8.0f}K {n/1024:8.0f}K {100*(1-n/o):5.0f}%  {rel}   [{note}]')
print()
print(f'TOTAL  {before_total/1e6:.2f} MB -> {after_total/1e6:.2f} MB  '
      f'({100*(1-after_total/before_total):.0f}% smaller, {(before_total-after_total)/1e6:.1f} MB saved)')
print(f'WebP twins written: {webp_total/1e6:.2f} MB total')
