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
import urllib.error
import urllib.request
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



# ---------------------------------------------------------------------------
# AI endpoints.
#
# The app POSTs to /api/ai/{guide-chat,translate,plan-itinerary}. A static host
# answers POST with 405, which is why the concierge says "Em An is momentarily
# busy" on GitHub Pages. This proxies those three calls to Gemini using the key
# in .env.local, so the key stays on the server and never reaches the browser.
# For the public site the same job is done by worker/inside-hoi-an-ai.js.
# ---------------------------------------------------------------------------

GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
              + GEMINI_MODEL + ":generateContent")

PERSONA = (
    'You are "Em An", a warm, knowledgeable local guide to Hoi An, Vietnam, '
    "answering inside the Inside Hoi An app. You know the Ancient Town, Tra Que "
    "herb village, An Bang beach, Cam Thanh coconut palms and Thanh Ha pottery "
    "village. Be specific and practical: name real streets, dishes and times of "
    "day. Cao Lau, white rose dumplings, banh mi, com ga. Mention opening hours "
    "or the best time to visit when it matters. Keep answers short, two to four "
    "sentences, unless asked for detail. Never invent prices or confirm bookings."
)

TRANSLATE_SCHEMA = {
    "type": "object",
    "properties": {
        "translatedText": {"type": "string"},
        "pronunciation": {"type": "string"},
        "literalMeaning": {"type": "string"},
        "culturalNote": {"type": "string"},
    },
    "required": ["translatedText"],
}

_STOP = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "time": {"type": "string"},
        "durationMinutes": {"type": "integer"},
        "description": {"type": "string"},
        "tip": {"type": "string"},
    },
    "required": ["name", "time", "description"],
}

ITINERARY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "suggestedDepartureTime": {"type": "string"},
        "totalWalkingMinutes": {"type": "integer"},
        "totalExperienceMinutes": {"type": "integer"},
        "totalDistanceMeters": {"type": "integer"},
        "stops": {"type": "array", "items": _STOP},
    },
    "required": ["title", "summary", "stops"],
}


def gemini_key():
    """Read GEMINI_API_KEY from .env.local. Never logged, never served."""
    path = os.path.join(BASE, ".env.local")
    if not os.path.isfile(path):
        return ""
    for line in open(path, encoding="utf-8"):
        if line.strip().startswith("GEMINI_API_KEY"):
            return line.split("=", 1)[1].strip()
    return ""


def gemini(system, contents, schema=None, timeout=45):
    key = gemini_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing from .env.local")
    # thinkingLevel "low" matters a lot here: the same question took 35.7s at the
    # model default and 5.5s at low. A chat that takes half a minute reads as broken.
    think = {"thinkingLevel": "low"}
    cfg = {"temperature": 0.8, "maxOutputTokens": 800, "thinkingConfig": think}
    if schema:
        cfg = {"temperature": 0.7, "responseMimeType": "application/json",
               "responseSchema": schema, "thinkingConfig": think}
    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system}]},
        "generationConfig": cfg,
    }
    req = urllib.request.Request(
        GEMINI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError("Gemini %s: %s" % (e.code, detail))
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts)
    if not text:
        raise RuntimeError("Gemini returned no text")
    return text


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

    # A browser that cancels a request - WebKit does this constantly while it
    # decides which images it still wants - resets the connection mid-write.
    # Unhandled, that propagates out of the handler thread and takes the whole
    # server down, which is how a browser test session kept killing this one.
    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            self.close_connection = True

    def handle_error(self, *args):
        pass

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
        path = self.path.split("?", 1)[0]
        if "/api/ai/" in path:
            return self._ai(path)
        return self._send_json(
            json.dumps({
                "error": "This is a static local copy. That endpoint needs the real backend.",
                "path": path,
            }).encode("utf-8"),
            status=501,
        )

    def _ai(self, path):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._send_json(
                json.dumps({"error": "Body must be JSON"}).encode("utf-8"), status=400)

        try:
            if path.endswith("/guide-chat"):
                message = (body.get("message") or "").strip()
                if not message:
                    return self._send_json(
                        json.dumps({"error": "message is required"}).encode("utf-8"), status=400)
                lang = body.get("language") or "en"
                contents = []
                for m in (body.get("chatHistory") or [])[-10:]:
                    if not m or not m.get("text"):
                        continue
                    role = "model" if m.get("role") == "assistant" else "user"
                    contents.append({"role": role, "parts": [{"text": m["text"]}]})
                contents.append({"role": "user", "parts": [{"text": message}]})
                system = PERSONA + " Reply in " + ("Vietnamese" if lang == "vi" else "English") + "."
                reply = gemini(system, contents)
                return self._send_json(json.dumps({"reply": reply}).encode("utf-8"))

            if path.endswith("/translate"):
                text = (body.get("text") or "").strip()
                if not text:
                    return self._send_json(
                        json.dumps({"error": "text is required"}).encode("utf-8"), status=400)
                system = (
                    "You translate for travellers in Hoi An, Vietnam. Translate from "
                    + str(body.get("sourceLanguage") or "en") + " to "
                    + str(body.get("targetLanguage") or "vi")
                    + ". Give a natural spoken translation, a simple phonetic guide an "
                    "English speaker can read aloud, the literal meaning, and one short "
                    "cultural note when it helps. Keep it brief."
                )
                out = gemini(system, [{"role": "user", "parts": [{"text": text}]}],
                             TRANSLATE_SCHEMA)
                return self._send_json(out.encode("utf-8"))

            if path.endswith("/plan-itinerary"):
                days = body.get("days") or 1
                lang = body.get("language") or "en"
                system = (
                    PERSONA + " Build a realistic Hoi An itinerary. " + str(days)
                    + " day(s), vibe: " + str(body.get("vibe") or "balanced")
                    + ", group: " + str(body.get("group") or "couple")
                    + ", pace: " + str(body.get("pace") or "moderate")
                    + ". Use real places and sensible timings, allow for the midday heat, "
                    "and put the lantern-lit Ancient Town in the evening. Write in "
                    + ("Vietnamese" if lang == "vi" else "English") + "."
                )
                prompt = "Plan %s day(s) in Hoi An." % days
                out = gemini(system, [{"role": "user", "parts": [{"text": prompt}]}],
                             ITINERARY_SCHEMA)
                return self._send_json(out.encode("utf-8"))

            return self._send_json(
                json.dumps({"error": "Unknown AI endpoint"}).encode("utf-8"), status=404)

        except Exception as exc:
            # The app shows its own friendly fallback on a non-200, so a clear
            # message here is for the developer, not the traveller.
            return self._send_json(
                json.dumps({"error": str(exc)[:400]}).encode("utf-8"), status=502)

    def log_message(self, fmt, *args):
        # One line per request is fine; the default also prints the date twice.
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    mimetypes.init()
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    http.server.ThreadingHTTPServer.daemon_threads = True
    with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Inside Hoi An -> http://127.0.0.1:{PORT}  (root: {ROOT})")
        print("gzip: on   webp negotiation: on   hashed assets: immutable")
        httpd.serve_forever()
