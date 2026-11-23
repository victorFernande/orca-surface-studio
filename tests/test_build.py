import base64
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import tomllib
from email.parser import Parser
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("wave_build",ROOT/"scripts"/"build_and_install.py")
build_module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_module)


class BuildTests(unittest.TestCase):
    def test_tab_rename_keeps_visibility_grants_and_other_capabilities(self):
        for visible in (False,True):
            with self.subTest(visible=visible),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);bundle=root/'bundle.py';bundle.write_text('# fixture\n')
                target=root/'plugins'/'orca_wave_studio';target.mkdir(parents=True)
                original={'enabled':False,'capabilities':[
                    {build_module.LEGACY_PAGE_NAME:visible},{'Other action':False}],
                    'permissions':{'fs_read':['existing/*'],'process':[]},'custom':'keep'}
                before=json.dumps(original).encode()
                (target/'.install_state.json').write_bytes(before)
                build_module.install(bundle,root/'plugins')
                actual=json.loads((target/'.install_state.json').read_bytes())
                expected={**original,'capabilities':[
                    {build_module.PAGE_NAME:visible},{'Other action':False}]}
                self.assertEqual(actual,expected)
                self.assertEqual((target/'.install_state.before-surface-tab.json').read_bytes(),before)
                persisted=(target/'.install_state.json').read_bytes()
                build_module.install(bundle,root/'plugins')
                self.assertEqual((target/'.install_state.json').read_bytes(),persisted)

    def test_explicit_new_tab_preference_is_not_replaced_by_old_preference(self):
        before=json.dumps({'capabilities':[
            {build_module.LEGACY_PAGE_NAME:True},{build_module.PAGE_NAME:False}]}).encode()
        self.assertEqual(build_module.renamed_page_state(before),before)

    def test_install_preserves_hidden_page_and_grants_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            bundle=root/"bundle.py"
            bundle.write_text("# fixture\n")
            target=root/"plugins"/"orca_wave_studio"
            target.mkdir(parents=True)
            content=b'{"enabled":true,"capabilities":[{"Estudio":false}],"permissions":{"keep":"exact"}}\n'
            (target/".install_state.json").write_bytes(content)
            build_module.install(bundle,root/"plugins",enable_new=True)
            self.assertEqual((target/".install_state.json").read_bytes(),content)
            self.assertEqual((target/"orca_wave_generator.py").read_bytes(),bundle.read_bytes())

    def test_new_persistent_install_has_no_permission_grants(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            bundle=root/"bundle.py"
            bundle.write_text("# fixture\n")
            target=build_module.install(bundle,root/"plugins",enable_new=True)
            state=json.loads((target/".install_state.json").read_text(encoding="utf-8"))
            self.assertTrue(state["enabled"])
            self.assertNotIn("permissions",state)

    def test_wheel_records_match_files_and_universal_bundle(self):
        bundle,wheel=build_module.build()
        self.assertEqual(bundle.read_bytes(),(ROOT/"dist"/"orca_wave_generator_any.py").read_bytes())
        with zipfile.ZipFile(wheel) as archive:
            self.assertEqual(len([n for n in archive.namelist() if '/locales/' in n and n.endswith('.json')]),7)
            project=tomllib.loads((ROOT/'pyproject.toml').read_text())['project']
            metadata_name=next(name for name in archive.namelist() if name.endswith('.dist-info/METADATA'))
            metadata=Parser().parsestr(archive.read(metadata_name).decode())
            self.assertEqual(metadata['Name'],project['name'])
            self.assertEqual(metadata.get_all('Requires-Dist'),project['dependencies'])
            self.assertTrue(wheel.name.startswith(project['name'].replace('-','_')+'-'))
            self.assertTrue(metadata_name.startswith(project['name'].replace('-','_')+'-'))
            records=[name for name in archive.namelist() if name.endswith(".dist-info/RECORD")]
            self.assertEqual(len(records),1)
            for name,value,size in csv.reader(io.StringIO(archive.read(records[0]).decode())):
                if not value:
                    continue
                content=archive.read(name)
                expected=base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
                self.assertEqual(value,"sha256="+expected)
                self.assertEqual(int(size),len(content))
        # Exercise the installed data path in fresh processes, without the source tree.
        for artifact in (bundle,ROOT/'dist'/'orca_wave_generator_any.py',wheel):
            with self.subTest(artifact=artifact.name),tempfile.TemporaryDirectory() as folder:
                if artifact.suffix=='.whl':
                    with zipfile.ZipFile(artifact) as archive:
                        archive.extractall(folder)
                setup=(f'import runpy; runpy.run_path({str(artifact)!r});'
                       if artifact.suffix=='.py' else f'import sys;sys.path.insert(0,{folder!r});')
                script=setup+('from orca_wave_studio.language_packs import load_language_packs;'
                    'from orca_wave_studio.studio_ui import get_studio_html;'
                    'packs,errors=load_language_packs(strict=True);assert len(packs)==7 and not errors;'
                    'assert "日本語" in get_studio_html({"language":"ja"});')
                subprocess.run([sys.executable,'-B','-W','error','-c',script],cwd=folder,check=True,capture_output=True)
