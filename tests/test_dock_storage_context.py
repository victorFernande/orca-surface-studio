from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from orca_wave_studio import plugin


class DockStorageContextTests(unittest.TestCase):
    def test_dock_and_worker_reuse_path_resolved_inside_plugin_callback(self):
        with tempfile.TemporaryDirectory() as folder:
            storage=Mock(return_value=folder)
            sdk=SimpleNamespace(host=SimpleNamespace(plugin=SimpleNamespace(storage=storage)))
            with patch.object(plugin,'orca',sdk),patch.object(plugin,'_native_storage',None):
                expected=Path(folder)
                self.assertEqual(plugin._storage(),expected)
                storage.side_effect=RuntimeError('plugin.storage() must be called from a plugin callback')
                self.assertEqual(plugin._storage(),expected)
                self.assertEqual(plugin.NativeHost().slicer_workspace(),expected/'native-slicer')
                storage.assert_called_once_with()

    def test_failed_context_does_not_cache_a_fallback_location(self):
        storage=Mock(side_effect=RuntimeError('outside callback'))
        sdk=SimpleNamespace(host=SimpleNamespace(plugin=SimpleNamespace(storage=storage)))
        with patch.object(plugin,'orca',sdk),patch.object(plugin,'_native_storage',None):
            with self.assertRaisesRegex(RuntimeError,'outside callback'):
                plugin._storage()
            self.assertIsNone(plugin._native_storage)
            storage.side_effect=None;storage.return_value='legitimate-plugin-path'
            self.assertEqual(plugin._storage(),Path('legitimate-plugin-path'))

    def test_separate_sdk_instance_cannot_reuse_another_plugin_location(self):
        sdk=SimpleNamespace(host=SimpleNamespace(plugin=SimpleNamespace(storage=Mock(return_value='own-path'))))
        with patch.object(plugin,'orca',sdk),patch.object(plugin,'_native_storage',(object(),Path('other'))):
            self.assertEqual(plugin._storage(),Path('own-path'))
            sdk.host.plugin.storage.assert_called_once_with()
