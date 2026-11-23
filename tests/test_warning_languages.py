import json
from pathlib import Path
import tempfile
import unittest

from orca_wave_studio.controller import StudioController
from orca_wave_studio.language_packs import load_language_packs, resolve_language
from orca_wave_studio.studio_ui import get_studio_html


class WarningLanguageTests(unittest.TestCase):
    def test_seven_complete_warning_packs_and_region_fallback(self):
        packs,errors=load_language_packs(strict=True)
        self.assertFalse(errors)
        self.assertEqual(set(packs),{'pt','en','es','it','fr','de','ja'})
        keys={'language','warning_title','warning_body','warning_preview','warning_bead'}
        for code,pack in packs.items():
            with self.subTest(code=code):
                self.assertEqual(set(pack['translations']),keys)
                self.assertEqual(resolve_language(code+'_XX',packs),code)
        self.assertEqual(resolve_language('unsupported',packs),'en')
        self.assertEqual(resolve_language(None,packs),'pt')

    def test_language_persists_without_invalidating_a_study(self):
        with tempfile.TemporaryDirectory() as folder:
            controller=StudioController(Path(folder))
            result={'sha256':'retained','report':{'print_allowed':False}}
            controller._result=result
            controller._status='processing'
            controller._job='retained-job'
            for code in ('pt','en','es','it','fr','de','ja'):
                state=controller.handle({'action':'set_language','language':code})['state']
                self.assertEqual(state['language'],code)
                self.assertEqual(state['status'],'processing')
                self.assertIs(state['result'],result)
                self.assertEqual(controller._job,'retained-job')
                self.assertEqual(StudioController(Path(folder)).state()['language'],code)
            self.assertEqual(controller.handle({'action':'set_language','language':'it_IT'})['state']['language'],'it')
            self.assertEqual(controller.handle({'action':'set_language','language':'unknown'})['state']['language'],'en')

    def test_bad_preferences_are_recoverable(self):
        with tempfile.TemporaryDirectory() as folder:
            for content in ('not json','[]','{"language":null}'):
                Path(folder,'ui_preferences.json').write_text(content,encoding='utf-8')
                self.assertEqual(StudioController(Path(folder)).state()['language'],'pt')

    def test_new_data_only_pack_needs_no_language_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            pack={'schema_version':1,'code':'nl','native_name':'Nederlands',
                  'translations':{'warning_title':'WAARSCHUWING'}}
            Path(folder,'nl.json').write_text(json.dumps(pack),encoding='utf-8')
            packs,errors=load_language_packs(folder,strict=True)
            self.assertFalse(errors)
            self.assertEqual(resolve_language('nl_NL',packs),'nl')

    def test_both_documents_embed_offline_catalogs_and_only_current_layout(self):
        for dock in (False,True):
            html=get_studio_html({'language':'ja'},dock=dock)
            for old in ('id="presets"','id="mode-xy"','id="mode-z"',"const guideToggle=",'Mais opções','id="generate"','id="preview"'):
                self.assertNotIn(old,html)
            self.assertIn('日本語',html)
            self.assertIn('languageSelect.onchange',html)
            self.assertNotIn('__LANGUAGE_PACKS__',html)
