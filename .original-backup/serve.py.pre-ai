"""Local server for the downloaded Inside Hoi An build.

Mirrors the live host closely enough to exercise the app offline:
  * serves dist/ as the web root
  * replays captured JSON for /api/* from dist/_api/
  * falls back to index.html for extensionless routes (SPA deep links),
    while still returning a real 404 for missing files, so broken
    asset references stay visible instead of being masked
  * serves the PWA manifest with the correct media type and marks the
    service worker no-store so updates always reach installed clients.

Performance behaviour, added after profiling the build (see BUG-AUDIT.md):
  * gzip for text payloads. The bundle is ~1.05 MB of JavaScript and the
    stylesheet another 114 KB; uncompressed they dominate the critical path.
  * WebP content negotiation. optimize_media.py writes a .webp twin beside
    every photo; when the client advertises image/webp it gets the smaller
    file under the original .jpg URL, with Vary: Accept so caches behave.
  * real Cache-Control. Vite's asset filenames are content-hashed, so they
    can be immutable for a year; photos get a week; the shell stays no-store.
"""
import gzip
import http.server
import io
import json
import mimetypes
import os
import posixpath
import sys
import urllib.parse

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 4173
BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(BASE, "dist")
API = os.path.join(ROOT, "_api")

# Worth compressing: text that is large and repetitive. Never images or fonts,
# which are already compressed and only get bigger.
COMPRESSIBLE = {
    "text/html", "text/css", "text/javascript", "application/javascript",
    "application/json", "image/svg+xml", "application/manifest+json",
    "text/plain", "text/markdown",
}
MIN_COMPRESS = 1024

# Never cached: the shell has to be re-fetched or an update can never reach a
# client that already installed the old service worker.
NO_STORE = {"/", "/index.html", "/sw.js"}


class Handler(http.server.SimpleHTTPRequestHandler):
    server_version = "InsideHoiAn/2.0"
    protocol_version = "HTTP/1.1"

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".webmanifest": "application/manifest+json",
        ".mjs": "text/javascript",
        ".webp": "image/webp",
        ".avif": "image/avif",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    # ---- helpers ----------------------------------------------------------
    def _local_path(self, url_path):
        """Map a URL path to a file inside ROOT, refusing anything that escapes."""
        path = urllib.parse.unquote(url_path.split("?", 1)[0].split("#", 1)[0])
        path = posixpath.normpath(path)
        parts = [p for p in path.split("/") if p and p not in (".", "..")]
        return os.path.join(ROOT, *parts)

    def _cache_control(self, url_path, disk_path):
        if url_path in NO_STORE or url_path.endswith(".webmanifest"):
            return "no-store"
        # Vite writes content-hashed names into /assets, so they can never change
        # meaning under the same URL.
        if url_path.startswith("/assets/") and not url_path.endswith((".jpg", ".png", ".webp")):
            return "public, max-age=31536000, immutable"
        if disk_path.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".avif", ".ico", ".svg")):
            return "public, max-age=604800"
        if disk_path.lower().endswith((".woff", ".woff2", ".ttf")):
            return "public, max-age=31536000, immutable"
        return "public, max-age=3600"

    def _negotiate_webp(self, disk_path):
        """Serve the .webp twin when the client accepts it. Returns (path, varies)."""
        if not disk_path.lower().endswith((".jpg", ".jpeg", ".png")):
            return disk_path, False
        accept = self.headers.get("Accept", "")
        twin = os.path.splitext(disk_path)[0] + ".webp"
        if "image/webp" in accept and os.path.isfile(twin):
            # Only if it is actually smaller - the generator skips files where
            # WebP lost, but a hand-dropped file could go the other way.
            try:
                if os.path.getsize(twin) < os.path.getsize(disk_path):
                    return twin, True
            except OSError:
                pass
        return disk_path, os.path.isfile(twin)

    def _send(self, body, ctype, status=200, cache=None, varies=False, extra=None):
        encoding = None
        base_type = ctype.split(";", 1)[0].strip()
        if (base_type in COMPRESSIBLE and len(body) >= MIN_COMPRESS
                and "gzip" in self.headers.get("Accept-Encoding", "")):
            buf = io.BytesIO()
            # mtime=0 keeps the bytes deterministic between runs.
            with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6, mtime=0) as gz:
                gz.write(body)
            packed = buf.getvalue()
            if len(packed) < len(body):
                body, encoding = packed, "gzip"

        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if encoding:
            self.send_header("Content-Encoding", encoding)
        if cache:
            self.send_header("Cache-Control", cache)
        vary = []
        if encoding or base_type in COMPRESSIBLE:
            vary.append("Accept-Encoding")
        if varies:
            vary.append("Accept")
        if vary:
            self.send_header("Vary", ", ".join(vary))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, body, status=200):
        self._send(body, "application/json; charset=utf-8", status, cache="no-store")

    def _api_file(self, path):
        name = path.strip("/").replace("/", "_") + ".json"
        candidate = os.path.join(API, name)
        return candidate if os.path.isfile(candidate) else None

    # ---- request handling -------------------------------------------------
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        url_path = self.path.split("?", 1)[0]

        # Generated from the directory so dropping a mark in just works locally.
        # A static marks.json ships alongside as the fallback for real hosting.
        if url_path == "/brand/pay/marks.json":
            folder = os.path.join(ROOT, "brand", "pay")
            marks = []
            if os.path.isdir(folder):
                for name in sorted(os.listdir(folder)):
                    stem, ext = os.path.splitext(name)
                    if ext.lower() in (".svg", ".png", ".webp"):
                        marks.append({"id": stem, "src": "/brand/pay/" + name})
            return self._send_json(json.dumps({"marks": marks}).encode("utf-8"))

        if url_path.startswith("/api/"):
            snapshot = self._api_file(url_path)
            if snapshot:
                with open(snapshot, "rb") as fh:
                    return self._send_json(fh.read())
            return self._send_json(
                json.dumps({"error": "No local snapshot for this endpoint.",
                            "path": url_path}).encode("utf-8"),
                status=501,
            )

        disk = self._local_path(url_path)
        if os.path.isdir(disk):
            disk = os.path.join(disk, "index.html")
            url_path = "/index.html"

        # SPA deep links: an extensionless path that is not a real file is a
        # client route. A missing *file* still 404s, so broken asset references
        # stay visible instead of silently returning the shell.
        if not os.path.isfile(disk) and "." not in posixpath.basename(url_path):
            disk = os.path.join(ROOT, "index.html")
            url_path = "/index.html"

        if not os.path.isfile(disk):
            return self._send(b"404 - not found\n", "text/plain; charset=utf-8", 404,
                              cache="no-store")

        disk, varies = self._negotiate_webp(disk)
        ctype = self.guess_type(disk)
        if ctype.startswith("text/") or ctype in (
                "application/javascript", "application/json", "image/svg+xml",
                "application/manifest+json"):
            if "charset" not in ctype:
                ctype += "; charset=utf-8"

        try:
            with open(disk, "rb") as fh:
                body = fh.read()
        except OSError:
            return self._send(b"500 - unreadable\n", "text/plain; charset=utf-8", 500,
                              cache="no-store")

        extra = {}
        if url_path == "/sw.js":
            extra["Service-Worker-Allowed"] = "/"

        self._send(body, ctype, cache=self._cache_control(url_path, disk),
                   varies=varies, extra=extra)

    def do_POST(self):
        # The live app POSTs to /api/ai/* and /api/partners/apply. There is no
        # backend here, so answer explicitly rather than letting it hang.
        return self._send_json(
            json.dumps({
                "error": "This is a static local copy. The AI and partner "
                         "endpoints need the real backend.",
                "path": self.path.split("?", 1)[0],
            }).encode("utf-8"),
            status=501,
        )

    def log_message(self, fmt, *args):
        # One line per request is fine; the default also prints the date twice.
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    mimetypes.init()
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Inside Hoi An -> http://127.0.0.1:{PORT}  (root: {ROOT})")
        print("gzip: on   webp negotiation: on   hashed assets: immutable")
        httpd.serve_forever()
