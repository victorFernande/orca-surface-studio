"""OrcaSlicer 2.5.1 printer-agent capability for the approved loopback study."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
from urllib.parse import urlsplit

from .contracts import WaveError, digest
from . import __version__
from .octoprint import OctoPrintTransport, UploadCancelledError, UploadUncertainError, VERIFY_BYTES, VERIFY_FILE
from .package import extract_plate_gcode

try:
    from orca import printer_agent
except ModuleNotFoundError as exc:
    if exc.name != "orca":
        raise
    printer_agent = None


AGENT_ID = "orca_wave_octoprint"
NAME = "Orca Wave • OctoPrint (bancada)"
DEVICE_ID = "ORCAWAVE-OCTOPRINT-BENCH"
_context_provider = dict
_event_sink = None


def configure_native_agent(provider: Callable[[], dict], *, event_sink: Callable | None = None):
    """Install a fast, thread-safe snapshot provider. Credentials belong to the local fixture."""
    global _context_provider, _event_sink
    if not callable(provider):
        raise TypeError("O contexto requer uma função.")
    _context_provider = provider
    _event_sink = event_sink


def _context():
    value = _context_provider()
    if not isinstance(value, dict) or value.get("bench_only") is not True:
        raise WaveError("Receptor de bancada indisponível.")
    result = dict(value)
    # Validate the endpoint before ever advertising it to the host.
    OctoPrintTransport(result["base_url"], result["api_key"])
    # GUI_App::select_machine and MachineObject::dev_id_from_address use host:port.
    result.setdefault("dev_id", urlsplit(result["base_url"]).netloc)
    return result


def _endpoint(ctx):
    return ctx["base_url"], ctx["api_key"], ctx["dev_id"]


def _approval(ctx):
    sha = ctx.get("expected_sha256")
    index = ctx.get("plate_index")
    if (ctx.get("approval_current") is not True or not isinstance(sha, str)
            or re.fullmatch(r"[0-9a-f]{64}", sha) is None or type(index) is not int or not 0 <= index < 36):
        raise WaveError("Aprovação vigente da mesa e do SHA-256 necessária.")
    return (*_endpoint(ctx), index, sha, str(ctx.get("approval_id", "")))


def _host_matches(host, port, ctx):
    url = urlsplit(ctx["base_url"])
    authority = url.netloc
    expected_port = url.port or (443 if url.scheme == "https" else 80)
    return (bool(host) and host in {authority, url.hostname, f"[{url.hostname}]"}
            and (not port or str(port) == str(expected_port)))


def _fixture_status(transport):
    status = transport.status()
    if status["version"].get("wave_studio_simulator") is not True:
        raise WaveError("Receptor sem identificação de simulador Orca Wave.")
    return status


class BenchAgent:
    """Network and state logic shared with the actual Orca capability; no emulated Orca types."""
    def __init__(self):
        self._lock = threading.RLock()
        self._upload = threading.Lock()
        self._stop = threading.Event()
        self._callbacks = {}
        self._selected = ""
        self._endpoint = None
        self._connected_id = ""
        self._state = None
        self._consumed = set()
        self.last_event = {}

    def get_name(self):
        return NAME

    def _trace(self, event, **fields):
        if _event_sink is not None:
            try:
                _event_sink(event, **fields)
            except Exception:
                # Diagnostics must not interrupt host callbacks or a confirmed upload.
                pass

    def _register(self, name, callback):
        with self._lock:
            self._callbacks[name] = callback
        return 0

    def set_server_callback(self, fn):
        return self._register("server", fn)

    def set_on_ssdp_msg_fn(self, fn):
        return self._register("ssdp", fn)

    def set_on_printer_connected_fn(self, fn):
        return self._register("connected", fn)

    def set_on_subscribe_failure_fn(self, fn):
        return self._register("subscribe_failure", fn)

    def set_on_message_fn(self, fn):
        return self._register("message", fn)

    def set_on_user_message_fn(self, fn):
        return self._register("user", fn)

    def set_on_local_connect_fn(self, fn):
        return self._register("connect", fn)

    def set_on_local_message_fn(self, fn):
        return self._register("local", fn)

    def set_queue_on_main_fn(self, fn):
        return self._register("queue", fn)

    def _notify(self, name, *args, session=None):
        with self._lock:
            callback = self._callbacks.get(name)
            if not callback and name == "local":
                callback = self._callbacks.get("message")
            queue = self._callbacks.get("queue")
        if not callback:
            return
        def deliver():
            if session is None or not session.is_set():
                callback(*args)
        if queue:
            queue(deliver)
        else:
            deliver()

    def get_user_selected_machine(self):
        with self._lock:
            return self._selected

    def set_user_selected_machine(self, dev_id):
        with self._lock:
            if dev_id:
                try:
                    ctx = _context()
                    known = {ctx["dev_id"], urlsplit(ctx["base_url"]).netloc, self._connected_id}
                except (WaveError, KeyError):
                    return -1
                if dev_id not in known:
                    return -1
            self._selected = dev_id
        self._trace("selected", dev_id=dev_id)
        return 0

    def start_discovery(self, start, sending):
        if not start:
            return True
        try:
            ctx = _context()
        except (WaveError, KeyError):
            return False
        info = {"dev_name": "Sovol SV06 • bancada OctoPrint", "dev_type": "Sovol SV06",
                "dev_id": ctx["dev_id"], "dev_ip": urlsplit(ctx["base_url"]).netloc, "dev_signal": "0",
                "connect_type": "lan", "bind_state": "free", "sec_link": "secure", "ssdp_version": "v1"}
        with self._lock:
            if not self._selected:
                self._selected = ctx["dev_id"]
        self._notify("ssdp", json.dumps(info))
        self._trace("discovery", dev_id=ctx["dev_id"], dev_ip=info["dev_ip"])
        return True

    def bind_detect(self, dev_ip, sec_link, detect):
        try:
            ctx = _context()
            if not _host_matches(dev_ip, "", ctx):
                return -1
        except (WaveError, KeyError):
            return -1
        detect.dev_id = ctx["dev_id"]
        detect.model_id = "Sovol SV06"
        detect.dev_name = "Sovol SV06 • bancada OctoPrint"
        detect.version = ""
        detect.connect_type = "lan"
        detect.bind_state = "free"
        return 0

    def connect_printer(self, params):
        try:
            ctx = _context()
            if not params.dev_id or not _host_matches(params.host, params.port, ctx):
                self._trace("connect_refused", reason="endpoint_mismatch")
                return -1
        except (WaveError, KeyError):
            return -1
        with self._lock:
            self.disconnect_printer()
            self._stop = session = threading.Event()
            self._endpoint = _endpoint(ctx)
            # The host can give a saved print-host a generated ID at the same verified endpoint.
            dev_id = params.dev_id
            self._connected_id = dev_id
            self._trace("connecting", dev_id=dev_id)
            threading.Thread(target=self._monitor, args=(ctx, dev_id, session),
                             name="wave-octoprint-status", daemon=True).start()
        return 0

    def _monitor(self, ctx, dev_id, session):
        tx = OctoPrintTransport(ctx["base_url"], ctx["api_key"], timeout=3.0)
        first = True
        try:
            while not session.is_set():
                if _endpoint(_context()) != _endpoint(ctx):
                    raise WaveError("Receptor configurado mudou.")
                status = _fixture_status(tx)
                with self._lock:
                    if session.is_set():
                        return
                    self._state = status
                if first:
                    self._trace("connected", dev_id=dev_id, ready=status["ready"])
                    self._notify("connect", 0, dev_id, "", session=session)
                    self._notify("connected", dev_id, session=session)
                    first = False
                self._notify("local", dev_id, self._status_payload(status), session=session)
                session.wait(5)
        except Exception as exc:
            with self._lock:
                if session.is_set():
                    return
                self._state = None
            self._trace("connect_failed", dev_id=dev_id, error_type=type(exc).__name__)
            self._notify("connect", 1 if first else 2, dev_id, "Receptor de bancada indisponível.",
                         session=session)

    def disconnect_printer(self):
        with self._lock:
            if self._connected_id:
                self._trace("disconnect", dev_id=self._connected_id)
            self._stop.set()
            self._state = None
            self._endpoint = None
            self._connected_id = ""
        return 0

    @staticmethod
    def _status_payload(status):
        flags = status["printer"]["state"]["flags"]
        if flags.get("printing"):
            state = "RUNNING"
        elif flags.get("paused"):
            state = "PAUSE"
        elif status["ready"]:
            state = "IDLE"
        else:
            state = "FAILED"
        report = {"command": "push_status", "msg": 0, "gcode_state": state,
                  "sdcard": True, "home_flag": 1 << 8}
        temperatures = status["printer"].get("temperature", {})
        for source, target in (("tool0", "nozzle"), ("bed", "bed")):
            for field, suffix in (("actual", "_temper"), ("target", "_target_temper")):
                reading = temperatures.get(source, {}).get(field)
                if type(reading) in (int, float):
                    report[target + suffix] = reading
        return json.dumps({"print": report})

    def send_message_to_printer(self, dev_id, json_str, qos, flag):
        try:
            request = json.loads(json_str)
            with self._lock:
                if dev_id != self._connected_id or self._state is None:
                    return -1
                status = self._state
                session = self._stop
            if request.get("info", {}).get("command") == "get_version":
                version = status["version"]["server"]
                reply = json.dumps({"info": {"command": "get_version", "result": "success", "module": [
                    {"name": "ota", "sw_ver": version, "product_name": "OctoPrint (simulador)"}]}})
            elif request.get("pushing", {}).get("command") == "pushall":
                reply = self._status_payload(status)
            else:
                return -1
            self._notify("local", dev_id, reply, session=session)
            return 0
        except (KeyError, ValueError, AttributeError):
            return -1

    send_message = send_message_to_printer

    def _valid_session(self, params, ctx):
        if (self._state is None or self._endpoint != _endpoint(ctx)
                or params.dev_id != self._connected_id):
            raise WaveError("Mesma conexão de bancada ativa necessária.")
        dev_ip = getattr(params, "dev_ip", "")
        if dev_ip and not _host_matches(dev_ip, "", ctx):
            raise WaveError("Dispositivo solicitado diverge do receptor de bancada.")
        return self._stop

    @staticmethod
    def _progress(fn, stage, code, message):
        if fn:
            fn(stage, code, message)

    def start_local_print(self, params, update_fn, cancel_fn):
        self._trace("start_local_print", native_plate=params.plate_index,
                    filename=Path(params.filename).name)
        if not self._upload.acquire(blocking=False):
            return -1
        try:
            ctx = _context()
            approval = _approval(ctx)
            with self._lock:
                session = self._valid_session(params, ctx)
                if approval in self._consumed:
                    raise WaveError("Aprovação já utilizada. Consulte o recibo antes de uma nova aprovação.")
            if params.plate_index != ctx["plate_index"] + 1:
                raise WaveError("A mesa solicitada difere da mesa aprovada.")
            def cancelled():
                if (cancel_fn and cancel_fn()) or session.is_set():
                    return True
                try:
                    return _approval(_context()) != approval
                except (KeyError, WaveError):
                    return True
            if cancelled():
                raise UploadCancelledError("Envio cancelado antes da transferência.")
            self._progress(update_fn, 0, 0, "Conferindo os bytes aprovados da mesa.")
            gcode = extract_plate_gcode(Path(params.filename), ctx["plate_index"])
            actual_sha = digest(gcode)
            self._trace("extracted", native_plate=params.plate_index, approved=ctx["expected_sha256"],
                        actual=actual_sha, bytes=len(gcode))
            if actual_sha != ctx["expected_sha256"]:
                raise WaveError("SHA-256 do pacote diverge da aprovação.")
            tx = OctoPrintTransport(ctx["base_url"], ctx["api_key"], timeout=10.0)
            if not _fixture_status(tx)["ready"]:
                raise WaveError("Simulador ocupado ou indisponível.")
            self._progress(update_fn, 1, 0, "Enviando ao receptor de bancada.")
            name = f"onda-mesa-{params.plate_index}-{ctx['expected_sha256'][:16]}.gcode"
            try:
                receipt = tx.send(gcode, name, ctx["expected_sha256"], cancelled=cancelled)
            except UploadUncertainError:
                self._consumed.add(approval)
                raise
            self._consumed.add(approval)
            self.last_event = {"outcome": "sent" if receipt["effectivePrint"] else "uploaded_only",
                               "plate_index": ctx["plate_index"], **receipt}
            self._trace("receipt", gcode_sha256=actual_sha, bytes=len(gcode),
                        http_status=receipt["http_status"], effectivePrint=receipt["effectivePrint"])
            if not receipt["effectivePrint"]:
                self._progress(update_fn, 7, -1, "O simulador recebeu o arquivo sem iniciar.")
                return -1
            self._progress(update_fn, 6, 100, "Início confirmado pelo receptor de bancada.")
            return 0
        except Exception as exc:
            code = -18 if isinstance(exc, UploadCancelledError) else -1
            outcome = "uncertain" if isinstance(exc, UploadUncertainError) else ("cancelled" if code == -18 else "refused")
            self.last_event = {"outcome": outcome, "message": str(exc),
                               "gcode_sha256": locals().get("ctx", {}).get("expected_sha256")}
            self._trace("print_failed", outcome=outcome, error_type=type(exc).__name__,
                        error=str(exc) if isinstance(exc, WaveError) else "",
                        expected=self.last_event["gcode_sha256"])
            self._progress(update_fn, 7, code, str(exc))
            return code
        finally:
            self._upload.release()

    def start_print(self, params, update_fn, cancel_fn, wait_fn):
        self._trace("start_print", native_plate=params.plate_index)
        return self.start_local_print(params, update_fn, cancel_fn)

    def start_send_gcode_to_sdcard(self, params, update_fn, cancel_fn, wait_fn):
        # PrintJob::process performs this exact probe before start_local_print. Every
        # other operation on this surface is an unrelated, unsupported SD-card upload.
        if getattr(params, "project_name", "") != "verify_job" or getattr(params, "connection_type", "") != "lan":
            return -1
        path = Path(params.filename)
        if path.name != VERIFY_FILE or path.parent.name != "resources":
            return -1
        try:
            ctx = _context()
            approval = _approval(ctx)
            with self._lock:
                session = self._valid_session(params, ctx)
                if approval in self._consumed:
                    return -1
            with path.open("rb") as source:
                if source.read(len(VERIFY_BYTES) + 1) != VERIFY_BYTES:
                    return -1
            tx = OctoPrintTransport(ctx["base_url"], ctx["api_key"], timeout=3)
            if not _fixture_status(tx)["ready"]:
                return -1
            def cancelled():
                return session.is_set() or (cancel_fn and cancel_fn()) or _approval(_context()) != approval
            receipt = tx.verify_storage(cancelled=cancelled)
            self._trace("storage_preflight", bytes=receipt["bytes"], effectivePrint=False,
                        effectiveSelect=False, http_status=receipt["http_status"])
            return 0
        except Exception as exc:
            self._trace("preflight_failed", error_type=type(exc).__name__)
            return -1

    def _unsupported(self, *args):
        return -1

    start_local_print_with_record = _unsupported
    start_sdcard_print = _unsupported
    check_cert = _unsupported
    ping_bind = _unsupported
    bind = _unsupported
    unbind = _unsupported

    def request_bind_ticket(self):
        return -1, ""


if printer_agent is None:
    WaveOctoPrintAgent = None
else:
    from orca import host

    class WaveOctoPrintAgent(BenchAgent, printer_agent.PrinterAgentBase):
        _log_lock = threading.Lock()

        def __init__(self):
            printer_agent.PrinterAgentBase.__init__(self)
            BenchAgent.__init__(self)
            self._study_dir = None

        def _trace(self, event, **fields):
            super()._trace(event, **fields)
            entry = {"utc": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
            try:
                if self._study_dir is None:
                    # During initial capability discovery its plugin identity may not yet be bound.
                    directory = Path(host.plugin.storage())
                    if not (directory / "study_connection.json").is_file():
                        return
                    self._study_dir = directory
                with self._log_lock, (self._study_dir / "native-agent-events.jsonl").open("a", encoding="utf-8") as log:
                    log.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except (OSError, RuntimeError):
                pass

        def get_agent_info(self):
            return printer_agent.AgentInfo(AGENT_ID, NAME, __version__, "OctoPrint em bancada local com G-code aprovado")
