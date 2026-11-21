"""Single-attempt OctoPrint file upload. Does not issue printer or job commands."""
from __future__ import annotations

from collections.abc import Callable
import http.client
import json
import math
import re
import secrets
from urllib.parse import quote, urlsplit

from .contracts import WaveError, digest

VERIFY_FILE = "check_access_code.txt"
VERIFY_BYTES = b"just a test file"


class UploadUncertainError(WaveError):
    """The request may have reached the server. Check its state before any new attempt."""


class UploadRejectedError(WaveError):
    """The HTTP server explicitly rejected the request."""


class UploadCancelledError(WaveError):
    """Cancellation was observed before sending the request."""


class OctoPrintTransport:
    def __init__(self, base_url: str, api_key: str, *, allow_real_printer: bool = False,
                 timeout: float = 10.0):
        if any(ord(c) < 33 or ord(c) == 127 for c in base_url):
            raise WaveError("Endereço OctoPrint inválido.")
        url = urlsplit(base_url)
        if (url.scheme not in ("http", "https") or not url.hostname or url.username is not None
                or url.password is not None or url.query or url.fragment or "\\" in base_url):
            raise WaveError("Endereço OctoPrint inválido.")
        if allow_real_printer is not True and url.hostname not in {"127.0.0.1", "::1"}:
            raise WaveError("O simulador exige o endereço literal 127.0.0.1 ou [::1].")
        if not api_key or not re.fullmatch(r"[!-~]+", api_key):
            raise WaveError("Chave OctoPrint inválida.")
        if not math.isfinite(timeout) or timeout <= 0:
            raise WaveError("Tempo limite inválido.")
        self._url = url
        self._port = url.port
        self._key = api_key
        self._timeout = timeout

    def _connect(self):
        cls = http.client.HTTPSConnection if self._url.scheme == "https" else http.client.HTTPConnection
        conn = cls(self._url.hostname, self._port, timeout=self._timeout)
        try:
            conn.connect()
        except OSError as exc:
            conn.close()
            raise WaveError("Falha ao conectar ao OctoPrint antes de enviar a solicitação.") from exc
        return conn

    def _path(self, endpoint):
        return self._url.path.rstrip("/") + "/api/" + endpoint

    @staticmethod
    def _json(response):
        data = response.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise ValueError("Resposta HTTP grande demais.")
        result = json.loads(data)
        if not isinstance(result, dict):
            raise ValueError("Resposta JSON inválida.")
        return result

    def status(self) -> dict:
        result = {}
        for endpoint in ("version", "connection", "printer"):
            conn = self._connect()
            try:
                conn.request("GET", self._path(endpoint), headers={"X-Api-Key": self._key})
                with conn.getresponse() as response:
                    if response.status != 200:
                        raise WaveError(f"OctoPrint recusou consulta {endpoint} (HTTP {response.status}).")
                    result[endpoint] = self._json(response)
            finally:
                conn.close()
        flags = result["printer"].get("state", {}).get("flags", {})
        result["ready"] = (flags.get("operational") is True and flags.get("ready") is True
                           and not any(flags.get(k) for k in (
                               "printing", "paused", "pausing", "cancelling", "error", "closedOrError")))
        return result

    def send(self, gcode: bytes, filename: str, expected_sha256: str, *,
             cancelled: Callable[[], bool] | None = None) -> dict:
        return self._send_file(gcode, filename, expected_sha256, start_print=True, cancelled=cancelled)

    def upload_only(self, gcode: bytes, filename: str, expected_sha256: str, *, cancelled=None) -> dict:
        """Store a reviewed file without selecting it or starting a print."""
        return self._send_file(gcode, filename, expected_sha256, start_print=False, cancelled=cancelled)

    def _send_file(self, gcode, filename, expected_sha256, *, start_print, cancelled):
        if not isinstance(gcode, bytes) or not gcode or digest(gcode) != expected_sha256:
            raise WaveError("G-code vazio ou SHA-256 divergente antes do envio.")
        if (not filename or len(filename.encode("utf-8")) > 255 or any(c in filename for c in '/\\:*?"<>|')
                or any(ord(c) < 32 or ord(c) == 127 for c in filename)
                or not filename.lower().endswith(".gcode")):
            raise WaveError("Nome de G-code inválido.")
        return self._upload(gcode, filename, expected_sha256, start_print=start_print, cancelled=cancelled)

    def verify_storage(self, *, cancelled=None):
        """The Orca LAN preflight uploads its fixed, inert probe without selecting or printing it."""
        receipt = self._upload(VERIFY_BYTES, VERIFY_FILE, digest(VERIFY_BYTES),
                               start_print=False, cancelled=cancelled)
        reply = receipt["response"]
        if reply.get("effectivePrint") is not False or reply.get("effectiveSelect") is not False:
            raise UploadUncertainError("O receptor não confirmou o pré-teste sem seleção e sem início.")
        return receipt

    def _upload(self, gcode, filename, expected_sha256, *, start_print, cancelled):
        def check_cancelled():
            if cancelled is not None and cancelled():
                raise UploadCancelledError("Envio cancelado antes da transferência.")
        check_cancelled()
        name = f'filename="{filename}"' if filename.isascii() else f"filename*=UTF-8''{quote(filename, safe='')}"
        boundary = secrets.token_hex(24)
        start = f"--{boundary}\r\nContent-Disposition: form-data; name="
        flag = "true" if start_print else "false"
        prefix = (f'{start}"select"\r\n\r\n{flag}\r\n{start}"print"\r\n\r\n{flag}\r\n'
                  f'{start}"file"; {name}\r\nContent-Type: application/octet-stream\r\n\r\n').encode("ascii")
        suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
        headers = {"X-Api-Key": self._key, "Content-Type": f"multipart/form-data; boundary={boundary}",
                   "Content-Length": str(len(prefix) + len(gcode) + len(suffix))}
        conn = self._connect()
        try:
            check_cancelled()
            conn.request("POST", self._path("files/local"), body=(prefix, gcode, suffix), headers=headers)
            with conn.getresponse() as response:
                if 400 <= response.status < 500:
                    raise UploadRejectedError(f"OctoPrint recusou o arquivo (HTTP {response.status}).")
                if response.status not in (200, 201):
                    raise UploadUncertainError(f"Resultado do envio incerto (HTTP {response.status}).")
                result = self._json(response)
                if type(result.get("effectivePrint")) is not bool:
                    raise UploadUncertainError("Recibo sem confirmação booleana effectivePrint.")
        except (UploadRejectedError, UploadUncertainError, UploadCancelledError):
            raise
        except (OSError, http.client.HTTPException, ValueError) as exc:
            raise UploadUncertainError("Envio sem recibo válido. Consulte a fila antes de repetir.") from exc
        finally:
            conn.close()
        return {"filename": filename, "gcode_sha256": expected_sha256, "bytes": len(gcode),
                "http_status": response.status, "effectivePrint": result["effectivePrint"],
                "response": result}
