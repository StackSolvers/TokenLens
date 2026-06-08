import http.server
import argparse
import json
import os
import socketserver
import time
import urllib.parse
import webbrowser

from tokenlens_core import collect_all_usage, compact_summary, load_config


HOST = "127.0.0.1"
PORT = 8080
MAX_PORT_ATTEMPTS = 20


class LocalTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = False


class APIHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path in ("/api/usage", "/api/summary"):
            try:
                query_params = urllib.parse.parse_qs(parsed_path.query)
                custom_path = query_params.get("dir", [None])[0]
                config = load_config()
                data = collect_all_usage(config, custom_antigravity_dir=custom_path)
                if parsed_path.path == "/api/summary":
                    data = {
                        "summary": data.get("summary", {}),
                        "agents": data.get("agents", []),
                        "sources": data.get("sources", []),
                        "compact": compact_summary(data),
                    }
                self.send_json(200, data)
            except Exception as exc:
                self.send_json(500, {"error": f"{type(exc).__name__}: {str(exc)[:200]}"})
            return

        super().do_GET()

    def send_json(self, status, data):
        try:
            self.send_response(status)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            return


def create_server():
    preferred = int(os.environ.get("TOKENLENS_PORT", PORT))
    last_error = None
    for offset in range(MAX_PORT_ATTEMPTS):
        port = preferred + offset
        try:
            return LocalTCPServer((HOST, port), APIHandler), port
        except OSError as exc:
            last_error = exc
    raise RuntimeError(f"No free localhost port found from {preferred} to {preferred + MAX_PORT_ATTEMPTS - 1}: {last_error}")


def start_server():
    with create_server()[0] as httpd:
        host, port = httpd.server_address
        print(f"Serving at http://{host}:{port}", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the local TokenLens dashboard server.")
    parser.add_argument("--no-browser", action="store_true", help="Start the server without opening a browser.")
    args = parser.parse_args()

    try:
        httpd, port = create_server()
    except Exception as exc:
        print(f"Failed to start TokenLens server: {exc}")
        raise SystemExit(1)

    url = f"http://{HOST}:{port}"
    print(f"Serving at {url}", flush=True)
    if not args.no_browser and not os.environ.get("TOKENLENS_NO_BROWSER"):
        time.sleep(1)
        webbrowser.open(url)

    try:
        with httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down...")
