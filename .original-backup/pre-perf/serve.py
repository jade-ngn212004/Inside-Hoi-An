"""Local server for the downloaded Inside Hoi An build.

Mirrors the live host closely enough to exercise the app offline:
  * serves dist/ as the web root
  * replays captured JSON for /api/* from dist/_api/
  * falls back to index.html for extensionless routes (SPA deep links),
    while still returning a real 404 for missing files, so broken
    asset references stay visible instead of being masked
  * serves the PWA manifest with the correct media type and marks the
    service worker no-store so updates always reach installed clients.
"""
import http.server
import json
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 4173
BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(BASE, "dist")
API = os.path.join(ROOT, "_api")


class Handler(http.server.SimpleHTTPRequestHandler):
    # .webmanifest is not in Python's mimetypes table; browsers want
    # application/manifest+json or they ignore the manifest entirely.
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".webmanifest": "application/manifest+json",
        ".mjs": "text/javascript",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        path = self.path.split("?")[0]
        # The service worker and the shell must never be served stale, or an
        # update can never reach a client that already installed the old one.
        if not path.startswith("/api/"):
            if path in ("/", "/index.html", "/sw.js") or path.endswith(".webmanifest"):
                self.send_header("Cache-Control", "no-store")
            if path == "/sw.js":
                self.send_header("Service-Worker-Allowed", "/")
        super().end_headers()

    def _api_file(self, path):
        name = path.strip("/").replace("/", "_") + ".json"
        candidate = os.path.join(API, name)
        return candidate if os.path.isfile(candidate) else None

    def _send_json(self, body, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path.startswith("/api/"):
            snapshot = self._api_file(path)
            if snapshot:
                with open(snapshot, "rb") as fh:
                    return self._send_json(fh.read())
            return self._send_json(
                json.dumps(
                    {"error": "No local snapshot for this endpoint.", "path": path}
                ).encode("utf-8"),
                status=501,
            )

        target = os.path.join(ROOT, path.lstrip("/"))
        if path != "/" and not os.path.isfile(target) and "." not in os.path.basename(path):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        # The live app POSTs to /api/ai/* and /api/partners/apply. There is no
        # backend here, so answer explicitly rather than letting it hang.
        return self._send_json(
            json.dumps(
                {
                    "error": "This is a static local copy. The AI and partner "
                    "endpoints need the real backend.",
                    "path": self.path.split("?")[0],
                }
            ).encode("utf-8"),
            status=501,
        )


if __name__ == "__main__":
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Inside Hoi An -> http://127.0.0.1:{PORT}  (root: {ROOT})")
        httpd.serve_forever()
