from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent / "site"


class DownloadHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_HEAD(self) -> None:
        if self.path == "/download":
            self.send_download_headers(send_body=False)
            return
        super().do_HEAD()

    def do_GET(self) -> None:
        if self.path == "/download":
            self.send_download_headers(send_body=True)
            return
        super().do_GET()

    def send_download_headers(self, send_body: bool) -> None:
        zip_path = ROOT / "downloads" / "PrivacyAlarm-Windows.zip"
        data = zip_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", 'attachment; filename="PrivacyAlarm-Windows.zip"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if send_body:
            self.wfile.write(data)

    def end_headers(self) -> None:
        if self.path.endswith(".zip"):
            filename = Path(self.path).name
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), DownloadHandler)
    print(f"Serving {ROOT} at http://127.0.0.1:{args.port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
