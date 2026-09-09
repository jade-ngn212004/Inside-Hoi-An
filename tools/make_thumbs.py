"""Generate 160px thumbnails for every local photo.

The map draws 88 markers at 40x40 CSS px and the lists draw avatars at
28-72px, all pointing at the same 1200x896 source the detail cards use.
160px covers every one of those slots at 2x DPR.
"""
import os, sys
from PIL import Image

DIST = sys.argv[1]
W = 160
made = []
for sub in ('images', 'assets'):
    d = os.path.join(DIST, sub)
    if not os.path.isdir(d):
        continue
    for name in sorted(os.listdir(d)):
        base, ext = os.path.splitext(name)
        if ext.lower() not in ('.jpg', '.jpeg') or base.endswith(f'-{W}'):
            continue
        src = os.path.join(d, name)
        img = Image.open(src); img.load()
        img = img.convert('RGB')
        scale = W / max(img.size)
        thumb = img.resize((max(1, round(img.width*scale)), max(1, round(img.height*scale))), Image.LANCZOS)
        jp = os.path.join(d, f'{base}-{W}.jpg')
        wp = os.path.join(d, f'{base}-{W}.webp')
        thumb.save(jp, 'JPEG', quality=82, optimize=True, progressive=False, subsampling='4:2:0')
        thumb.save(wp, 'WEBP', quality=80, method=6)
        made.append((f'/{sub}/{name}', os.path.getsize(src), os.path.getsize(jp), os.path.getsize(wp)))

print(f'{"source":<58} {"full":>8} {"thumb":>7} {"webp":>7}')
for url, a, b, c in made:
    print(f'{url:<58} {a/1024:7.0f}K {b/1024:6.0f}K {c/1024:6.0f}K')
print(f'\n{len(made)} thumbnails; a 40px marker now costs '
      f'{sum(c for _,_,_,c in made)/len(made)/1024:.1f}K instead of '
      f'{sum(a for _,a,_,_ in made)/len(made)/1024:.0f}K')

import json
json.dump([u for u, *_ in made], open(os.path.join(os.path.dirname(DIST), '.perf-backup', 'thumb-manifest.json'), 'w'), indent=1)
