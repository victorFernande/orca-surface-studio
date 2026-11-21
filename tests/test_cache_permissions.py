from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from orca_wave_studio.plugin import preview_cache_read_targets


class CachePermissionTargetsTests(unittest.TestCase):
    def test_scope_is_only_the_orca_cache_tree_and_needs_no_storage_or_temp_probe(self):
        with tempfile.TemporaryDirectory() as root:
            with (patch('orca_wave_studio.plugin._storage',side_effect=AssertionError('callback only')),
                  patch('tempfile.gettempdir',side_effect=AssertionError('no filesystem probe'))):
                targets=preview_cache_read_targets({'TEMP':root})
            self.assertEqual(targets,[str(Path(root)/'orcaslicer_model'/'*')])
            self.assertNotEqual(targets,[str(Path(root)/'*')])

    def test_ambiguous_paths_do_not_widen_a_request(self):
        for value in ('relative','*',str(Path.cwd()/'..'/'temp'),str(Path.cwd()/'*'/'temp')):
            with self.subTest(value=value):self.assertEqual(preview_cache_read_targets({'TEMP':value}),[])
        self.assertEqual(preview_cache_read_targets({}),[])
