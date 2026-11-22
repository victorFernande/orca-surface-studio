import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('publisher',Path(__file__).resolve().parents[1]/'scripts/publish_orcacloud.py')
publisher=importlib.util.module_from_spec(spec);spec.loader.exec_module(publisher)


class PublicationPolicyTests(unittest.TestCase):
    def test_current_hold_stops_before_credentials_or_network(self):
        with patch.object(publisher,'urlopen',side_effect=AssertionError('network called')) as network:
            with self.assertRaisesRegex(SystemExit,'bloqueada'):publisher.main()
            network.assert_not_called()
    def test_missing_invalid_and_disabled_policies_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'publication-policy.json'
            for data in (None,'invalid','{}','{"orca_cloud_enabled":"true"}','{"orca_cloud_enabled":false}'):
                if data is not None:path.write_text(data)
                with self.assertRaises(SystemExit):publisher.check_publication_policy(root)
            path.write_text(json.dumps({'orca_cloud_enabled':True}))
            publisher.check_publication_policy(root)
