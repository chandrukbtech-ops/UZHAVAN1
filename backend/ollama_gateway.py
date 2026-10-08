import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MAX_REQUEST_BYTES = 256 * 1024
OLLAMA_URL = os.getenv("OLLAMA_LOCAL_URL", "http://127.0.0.1:11434/api/chat")
GATEWAY_TOKEN = os.getenv("OLLAMA_GATEWAY_TOKEN", "")


class OllamaGatewayHandler(BaseHTTPRequestHandler):
    server_version = "UzhavanOllamaGateway"

    def do_POST(self) -> None:
        if self.path != "/api/chat":
            self.send_error(404)
            return

        supplied_token = self.headers.get("X-Ollama-Gateway-Token", "")
        if not hmac.compare_digest(supplied_token, GATEWAY_TOKEN):
            self.send_error(401)
            return

        try:
            request_size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400)
            return
        if request_size <= 0 or request_size > MAX_REQUEST_BYTES:
            self.send_error(413)
            return

        body = self.rfile.read(request_size)
        try:
            json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_error(400)
            return

        request = Request(
            OLLAMA_URL,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=180) as response:
                result = response.read()
                status = response.status
        except HTTPError as exc:
            result = b'{"error":"Local Ollama rejected the request."}'
            status = exc.code
        except (OSError, URLError, TimeoutError):
            result = b'{"error":"Local Ollama is unavailable."}'
            status = 503

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(result)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(result)

    def log_message(self, format: str, *args: object) -> None:
        print(f"Ollama gateway: {format % args}")


def main() -> None:
    if len(GATEWAY_TOKEN) < 32:
        raise RuntimeError("Set OLLAMA_GATEWAY_TOKEN to a random value of at least 32 characters.")

    server = ThreadingHTTPServer(("127.0.0.1", 11435), OllamaGatewayHandler)
    print("Authenticated Ollama gateway listening on 127.0.0.1:11435")
    server.serve_forever()


if __name__ == "__main__":
    main()
