"""Serve the built site with caching disabled.

``python -m http.server`` lets the browser cache ``index.html`` and the app
modules, which makes local changes look missing after a rebuild.  This server
sends ``Cache-Control: no-store`` so a normal reload always picks up the files.

Usage: python scripts/serve.py [directory] [port]
"""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import sys


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        super().end_headers()


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "dist"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    handler = partial(NoCacheHandler, directory=root)
    print(f"Serving {root} at http://localhost:{port} (cache disabled)")
    ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


if __name__ == "__main__":
    main()
