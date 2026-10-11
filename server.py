"""
Local development server for the KeenASR Reading Pod.

KeenASR runs its WebAssembly threads in the browser, which requires the page
to be cross-origin isolated. This server therefore adds the COOP/COEP headers
to every response, and serves the model bundle (*.tgz) with
`Content-Encoding: gzip` so the browser unzips it before KeenASR untars it.

Usage:
    python server.py                 # http://localhost:8000
    python server.py --port 8080
"""

import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PUBLIC_DIR = Path(__file__).resolve().parent / "public"


class KeenASRHandler(SimpleHTTPRequestHandler):
    # Set explicitly: on Windows the registry can map .js to text/plain,
    # which breaks ES modules.
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".wasm": "application/wasm",
        ".json": "application/json",
    }

    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cache-Control", "no-store")  # development only

        # KeenASR expects the browser to gunzip the model bundle.
        if self.path.split("?")[0].endswith(".tgz"):
            self.send_header("Content-Encoding", "gzip")

        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", default="127.0.0.1",
                        help="interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000,
                        help="port to listen on (default: 8000)")
    args = parser.parse_args()

    if not PUBLIC_DIR.is_dir():
        raise SystemExit(f"Cannot find the public folder: {PUBLIC_DIR}")

    handler = functools.partial(KeenASRHandler, directory=str(PUBLIC_DIR))
    server = ThreadingHTTPServer((args.host, args.port), handler)

    print(f"KeenASR Reading Pod running at http://localhost:{args.port}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
