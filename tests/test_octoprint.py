import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from orca_wave_studio.contracts import WaveError, digest
from orca_wave_studio.octoprint import (
    OctoPrintTransport, UploadCancelledError, UploadRejectedError, UploadUncertainError,
)
from orca_wave_studio.simulator import OctoPrintSimulator
from orca_wave_studio.package import build_sliced_package, extract_plate_gcode


class TransportTests(unittest.TestCase):
    data = b"; simula\xc3\xa7\xc3\xa3o\r\nG1 X12\nG1 X13\r\n; trailing space \n\xff"
    filename = "Peça de teste.gcode"

    def transport(self, sim):
        return OctoPrintTransport(sim.base_url, sim.api_key)

    def send(self, transport, **kwargs):
        return transport.send(self.data, self.filename, digest(self.data), **kwargs)

    def test_exact_bytes_and_native_status(self):
        with OctoPrintSimulator() as sim:
            tx = self.transport(sim)
            self.assertTrue(tx.status()["ready"])
            receipt = self.send(tx)
            self.assertTrue(receipt["effectivePrint"])
            capture, = sim.captures
            self.assertEqual(capture["gcode"], self.data)
            self.assertEqual(capture["sha256"], receipt["gcode_sha256"])
            self.assertEqual(capture["filename"], self.filename)
            self.assertTrue(capture["select"] and capture["print"])
            self.assertEqual(sim.requests[-1], ("POST", "/api/files/local"))

    def test_cancel_and_wrong_hash_never_upload(self):
        with OctoPrintSimulator() as sim:
            tx = self.transport(sim)
            with self.assertRaises(UploadCancelledError):
                self.send(tx, cancelled=lambda: True)
            pending = iter([False, True])
            with self.assertRaises(UploadCancelledError):
                self.send(tx, cancelled=lambda: next(pending))
            with self.assertRaises(WaveError):
                tx.send(self.data, self.filename, "0" * 64)
            self.assertEqual(sim.requests, [])
            self.assertEqual(sim.captures, [])

    def test_package_to_transport_receipt(self):
        with TemporaryDirectory() as tmp, OctoPrintSimulator() as sim:
            path = Path(tmp) / "reopen.gcode.3mf"
            report = build_sliced_package(self.data, path, plate_index=1)
            payload = extract_plate_gcode(path, 1)
            receipt = self.transport(sim).send(payload, self.filename, report["gcode_sha256"])
            self.assertEqual(sim.captures[0]["gcode"], self.data)
            self.assertEqual(sim.captures[0]["sha256"], report["gcode_sha256"])
            self.assertEqual(receipt["gcode_sha256"], report["gcode_sha256"])

    def test_reject_and_no_retry(self):
        with OctoPrintSimulator(reject_status=409) as sim:
            with self.assertRaises(UploadRejectedError):
                self.send(self.transport(sim))
            self.assertEqual(sim.requests, [("POST", "/api/files/local")])
            self.assertEqual(sim.captures, [])

    def test_effective_print_and_nonready(self):
        with OctoPrintSimulator(effective_print=False, ready=False) as sim:
            tx = self.transport(sim)
            self.assertFalse(tx.status()["ready"])
            receipt = self.send(tx)
            self.assertIs(receipt["effectivePrint"], False)
            self.assertEqual(len(sim.captures), 1)

    def test_drop_response_is_uncertain_and_single_upload(self):
        with OctoPrintSimulator(drop_response=True) as sim:
            with self.assertRaises(UploadUncertainError):
                self.send(self.transport(sim))
            self.assertEqual(sim.requests, [("POST", "/api/files/local")])
            self.assertEqual(len(sim.captures), 1)
            self.assertEqual(sim.captures[0]["gcode"], self.data)

    def test_missing_effective_print_is_uncertain(self):
        from unittest.mock import patch
        with OctoPrintSimulator() as sim:
            with patch.object(OctoPrintTransport, "_json", return_value={"done": True}):
                with self.assertRaises(UploadUncertainError):
                    self.send(self.transport(sim))
            self.assertEqual(len(sim.captures), 1)

    def test_loopback_literal_only(self):
        for host in ["localhost", "127.0.0.1.example", "127.0.0.1@other", "192.0.2.1",
                     "2130706433", "[::ffff:127.0.0.1]", "127.0.0.2", "example.com"]:
            with self.subTest(host=host), self.assertRaises(WaveError):
                OctoPrintTransport(f"http://{host}:80", "fixture")
        OctoPrintTransport("http://[::1]:1234", "fixture")
