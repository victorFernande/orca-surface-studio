"""In-process OctoPrint fixture. Accepts bytes in memory and never executes G-code."""
from __future__ import annotations

from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import threading
from urllib.parse import urlsplit

from .contracts import digest


class OctoPrintSimulator:
    def __init__(self, *, effective_print: bool = True, reject_status: int | None = None,
                 drop_response: bool = False, ready: bool = True, api_key: str | None = None):
        self.effective_print = effective_print
        self.reject_status = reject_status
        self.drop_response = drop_response
        self.ready = ready
        self.api_key = api_key or secrets.token_hex(16)
        self.captures = []
        self.requests = []
        self.base_url = ""
        self._server = None
        self._thread = None

    def __enter__(self):
        sim = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def reply(self, code, payload):
                data = json.dumps(payload).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def authorize(self):
                sim.requests.append((self.command, self.path))
                if self.headers.get("X-Api-Key") != sim.api_key:
                    self.reply(403, {"error": "Invalid fixture API key"})
                    return False
                return True

            def do_GET(self):
                if not self.authorize():
                    return
                state = "Operational" if sim.ready else "Printing"
                responses = {
                    "/api/version": {"api": "0.1", "server": "1.11.0", "text": "OctoPrint 1.11.0",
                                     "wave_studio_simulator": True},
                    "/api/connection": {"current": {"state": state, "printerProfile": "_default"}},
                    "/api/printer": {"state": {"text": state, "flags": {"ready": sim.ready,
                                    "operational": True, "printing": not sim.ready, "paused": False,
                                    "error": False, "closedOrError": False}}},
                }
                path = urlsplit(self.path).path
                self.reply(200 if path in responses else 404, responses.get(path, {}))

            def do_POST(self):
                if not self.authorize():
                    return
                if self.path != "/api/files/local":
                    self.reply(404, {})
                    return
                try:
                    size = int(self.headers.get("Content-Length", "-1"))
                    if not 0 < size <= 256 * 1024 * 1024:
                        self.reply(413, {})
                        return
                    raw = self.rfile.read(size)
                    if len(raw) != size:
                        raise ValueError("Corpo truncado.")
                    if sim.reject_status is not None:
                        self.reply(sim.reject_status, {"error": "Rejeição configurada no simulador"})
                        return
                    ctype = self.headers.get("Content-Type", "")
                    msg = BytesParser(policy=policy.default).parsebytes(
                        f"Content-Type: {ctype}\r\nMIME-Version: 1.0\r\n\r\n".encode() + raw)
                    if msg.get_content_type() != "multipart/form-data" or msg.defects:
                        raise ValueError("Formulário multipart inválido.")
                    fields = {}
                    for part in msg.iter_parts():
                        key = part.get_param("name", header="content-disposition")
                        if key in fields:
                            raise ValueError("Campo repetido.")
                        fields[key] = part
                    file = fields["file"]
                    filename = file.get_filename()
                    if not filename:
                        raise ValueError("Nome ausente.")
                    data = file.get_payload(decode=True)
                    # OctoPrint defaults to no selection/print when these fields are omitted.
                    printing = "print" in fields and fields["print"].get_payload(decode=True) == b"true"
                    select = printing or ("select" in fields and fields["select"].get_payload(decode=True) == b"true")
                    receipt = {"files": {"local": {"name": filename, "path": filename, "origin": "local"}},
                               "done": True, "effectiveSelect": select and sim.ready,
                               "effectivePrint": printing and sim.effective_print and sim.ready}
                except (KeyError, ValueError, TypeError):
                    self.reply(400, {"error": "Multipart inválido"})
                    return
                sim.captures.append({"filename": filename, "gcode": data, "sha256": digest(data),
                                     "select": "select" in fields and fields["select"].get_payload(decode=True) == b"true",
                                     "print": printing, "receipt": receipt})
                if sim.drop_response:
                    self.close_connection = True
                    return
                self.reply(201, receipt)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.05},
                                        name="octoprint-loopback-fixture", daemon=True)
        self.base_url = f"http://127.0.0.1:{self._server.server_port}"
        self._thread.start()
        return self

    def __exit__(self, *_exc):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
