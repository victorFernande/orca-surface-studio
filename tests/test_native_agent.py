import json
from pathlib import Path
from queue import Empty, Queue
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from orca_wave_studio.contracts import digest
from orca_wave_studio import native_agent as native
from orca_wave_studio.package import build_sliced_package
from orca_wave_studio.simulator import OctoPrintSimulator


class NativeAgentLogicTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.sim = self.enterContext(OctoPrintSimulator())
        self.agent = native.BenchAgent()
        self.addCleanup(native.configure_native_agent, dict)
        self.addCleanup(self.agent.disconnect_printer)
        data = b"; bench candle\r\nG1 X2\n"
        self.path = Path(self.temp) / "wave.gcode.3mf"
        build_sliced_package(data, self.path, plate_index=1)
        self.ctx = {"base_url": self.sim.base_url, "api_key": self.sim.api_key,
                    "expected_sha256": digest(data), "plate_index": 1,
                    "bench_only": True, "approval_current": True}
        native.configure_native_agent(lambda: self.ctx.copy())
        self.params = SimpleNamespace(filename=str(self.path), dev_id=native.DEVICE_ID,
                                      dev_ip=urlsplit(self.sim.base_url).netloc, plate_index=2)
        self.conn = SimpleNamespace(host=self.params.dev_ip, port="", dev_id=self.params.dev_id)
        self.events = []
        self.queue = Queue()
        self.agent.set_queue_on_main_fn(self.queue.put)
        self.agent.set_on_local_connect_fn(lambda *args: self.events.append(("connect", *args)))
        self.agent.set_on_printer_connected_fn(lambda *args: self.events.append(("connected", *args)))
        self.agent.set_on_local_message_fn(lambda dev, msg: self.events.append(("message", dev, json.loads(msg))))

    def pump_until(self, condition):
        deadline = time.monotonic() + 3
        while not condition() and time.monotonic() < deadline:
            try:
                self.queue.get(timeout=0.05)()
            except Empty:
                pass
        self.assertTrue(condition())

    def connect(self):
        self.assertEqual(self.agent.connect_printer(self.conn), 0)
        self.pump_until(lambda: any(ev[0] == "message" for ev in self.events))

    def start(self, cancel=None, progress=None):
        return self.agent.start_local_print(self.params, progress, cancel)

    def test_discovery_connect_state_and_version(self):
        found = []
        self.agent.set_on_ssdp_msg_fn(lambda text: found.append(json.loads(text)))
        self.assertTrue(self.agent.start_discovery(True, True))
        self.pump_until(lambda: bool(found))
        self.assertEqual(found[0]["dev_ip"], self.params.dev_ip)
        self.assertEqual(found[0]["dev_id"], self.params.dev_ip)
        self.assertEqual(self.agent.set_user_selected_machine(self.params.dev_ip), 0)
        self.assertEqual(self.agent.get_user_selected_machine(), self.params.dev_ip)
        self.assertEqual(found[0]["dev_type"], "Sovol SV06")
        self.assertEqual(self.sim.requests, [])
        self.connect()
        self.assertIn(("connect", 0, native.DEVICE_ID, ""), self.events)
        self.assertIn(("connected", native.DEVICE_ID), self.events)
        status = self.events[-1][2]["print"]
        self.assertEqual(status["gcode_state"], "IDLE")
        self.assertEqual(status["home_flag"], 1 << 8)
        self.assertTrue(status["sdcard"])
        self.assertNotIn("nozzle_temper", status)
        self.assertEqual(self.agent.send_message(self.conn.dev_id, '{"info":{"command":"get_version"}}', 0, 0), 0)
        self.pump_until(lambda: any(ev[0] == "message" and "info" in ev[2] for ev in self.events))
        self.assertEqual(self.events[-1][2]["info"]["module"][0]["sw_ver"], "1.11.0")

    def test_correct_plate_bytes_only_once(self):
        self.connect()
        progress = []
        self.assertEqual(self.start(progress=lambda *a: progress.append(a)), 0)
        self.assertEqual([p[0] for p in progress], [0, 1, 6])
        self.assertEqual(self.sim.captures[0]["sha256"], self.ctx["expected_sha256"])
        self.assertTrue(self.agent.last_event["effectivePrint"])
        self.assertEqual(self.start(), -1)
        self.assertEqual(len(self.sim.captures), 1)

    def test_native_lan_probe_is_inert_and_only_accepts_stock_probe(self):
        self.connect()
        path = Path(self.temp) / "resources" / "check_access_code.txt"
        path.parent.mkdir()
        probe = SimpleNamespace(filename=str(path), project_name="verify_job", connection_type="lan",
                                dev_id=self.params.dev_id, dev_ip=self.params.dev_ip)
        def verify():
            return self.agent.start_send_gcode_to_sdcard(probe, None, None, None)
        path.write_bytes(b"unrelated payload")
        self.assertEqual(verify(), -1)
        path.write_bytes(b"just a test file")
        self.ctx["approval_current"] = False
        self.assertEqual(verify(), -1)
        self.ctx["approval_current"] = True
        self.assertEqual(verify(), 0)
        receipt, = self.sim.captures
        self.assertEqual(receipt["gcode"], b"just a test file")
        self.assertFalse(receipt["print"] or receipt["select"])
        self.assertFalse(receipt["receipt"]["effectivePrint"])
        self.assertEqual(self.start(), 0)
        self.assertTrue(self.sim.captures[1]["print"])

    def test_fail_closed_on_wrong_plate_or_changed_approval(self):
        self.connect()
        self.params.plate_index = 1
        self.assertEqual(self.start(), -1)
        self.params.plate_index = 2
        correct_sha = self.ctx["expected_sha256"]
        self.ctx["expected_sha256"] = "0" * 64
        self.assertEqual(self.start(), -1)
        self.ctx["expected_sha256"] = correct_sha
        self.assertEqual(self.start(cancel=lambda: True), -18)
        def revoke(stage, code, message):
            if stage == 1:
                self.ctx["approval_current"] = False
        self.assertEqual(self.start(progress=revoke), -18)
        self.assertEqual(self.start(), -1)
        self.assertEqual(self.sim.captures, [])

    def test_reject_nonready_and_unmarked_local_server(self):
        self.connect()
        self.sim.ready = False
        self.assertEqual(self.start(), -1)
        self.sim.ready = True
        with patch.object(native.OctoPrintTransport, "status", return_value={"version": {}, "ready": True}):
            self.assertEqual(self.start(), -1)
        self.assertEqual(self.sim.captures, [])

    def test_uncertainty_blocks_automatic_repetition_and_new_approval(self):
        self.connect()
        self.sim.drop_response = True
        self.assertEqual(self.start(), -1)
        self.assertEqual(self.agent.last_event["outcome"], "uncertain")
        self.assertEqual(self.start(), -1)
        self.assertEqual(len(self.sim.captures), 1)
        self.sim.drop_response = False
        self.ctx["approval_id"] = "explicit-new-approval"
        self.sim.effective_print = False
        self.assertEqual(self.start(), -1)
        self.assertEqual(self.agent.last_event["outcome"], "uploaded_only")
        self.assertFalse(self.agent.last_event["effectivePrint"])
        self.assertEqual(len(self.sim.captures), 2)

    def test_disconnect_supersedes_queued_callbacks(self):
        self.assertEqual(self.agent.connect_printer(self.conn), 0)
        first = self.queue.get(timeout=3)
        self.agent.disconnect_printer()
        first()
        while not self.queue.empty():
            self.queue.get_nowait()()
        self.assertEqual(self.events, [])
        self.assertEqual(self.start(), -1)

    def test_connect_returns_before_network_read(self):
        started = threading.Event()
        release = threading.Event()
        status = native.OctoPrintTransport.status
        def blocked(tx):
            started.set()
            if not release.wait(2):
                raise AssertionError("Synchronous connect blocked UI")
            return status(tx)
        with patch.object(native.OctoPrintTransport, "status", blocked):
            self.assertEqual(self.agent.connect_printer(self.conn), 0)
            self.assertTrue(started.wait(2))
            self.assertFalse(self.events)
            release.set()
            self.pump_until(lambda: any(ev[0] == "message" for ev in self.events))

    def test_discovery_diagnostics_do_not_depend_on_native_constructor(self):
        recorded = []
        native.configure_native_agent(lambda: self.ctx.copy(), event_sink=lambda event, **fields:
                                      recorded.append((event, fields)))
        self.assertTrue(self.agent.start_discovery(True, True))
        self.assertEqual(recorded, [("discovery", {"dev_id": self.params.dev_ip, "dev_ip": self.params.dev_ip})])
        self.assertNotIn(self.sim.api_key, str(recorded))

    def test_loopback_only_unsupported_commands_and_device_identity(self):
        self.conn.host = "192.0.2.1"
        self.assertEqual(self.agent.connect_printer(self.conn), -1)
        self.assertEqual(self.sim.requests, [])
        self.conn.host = self.params.dev_ip
        self.connect()
        self.params.dev_id = "different-device"
        self.assertEqual(self.start(), -1)
        self.assertEqual(self.agent.send_message_to_printer(self.conn.dev_id, '{"print":{"command":"gcode_line"}}', 0, 0), -1)
        self.assertEqual(self.agent.start_sdcard_print(self.params, None, None), -1)
        self.assertEqual(self.agent.start_send_gcode_to_sdcard(self.params, None, None, None), -1)
        self.assertEqual(self.sim.captures, [])
        self.ctx["base_url"] = "http://192.0.2.1:81"
        self.assertFalse(self.agent.start_discovery(True, True))
        self.assertEqual(self.start(), -1)
