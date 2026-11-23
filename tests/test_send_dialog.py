import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import re

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from orca_wave_studio.contracts import WaveError,digest
from orca_wave_studio.controller import StudioController
from orca_wave_studio.package import build_sliced_package
from orca_wave_studio.send_dialog import (PrinterConnection,dialog_html,preview_identity,
                                         review,selected_connection,send_reviewed_file)
from orca_wave_studio.simulator import OctoPrintSimulator


def preset(name='Printer A',*,embedded=False,external=False,**settings):
    return SimpleNamespace(name=name,is_project_embedded=embedded,is_external=external,
        config_value=lambda key:settings.get(key))


def bundle(edited,saved=None):
    return SimpleNamespace(printers=SimpleNamespace(get_edited_preset=lambda:edited,
        find_preset=lambda name:saved if saved and saved.name==name else None))


def connection(host='http://127.0.0.1:18080'):
    return PrinterConnection('Printer A','Perfil selecionado no Orca',
        {'print_host':host,'printhost_apikey':'private-test-key','host_type':'octoprint','printer_agent':''})


class SendDialogTests(unittest.TestCase):
    def test_active_edited_destination_wins_and_a_cleared_normal_profile_stays_cleared(self):
        saved=preset(print_host='http://saved.invalid',printhost_apikey='old')
        active=preset(print_host='http://edited.invalid',printhost_apikey='new',host_type='octoprint')
        c=selected_connection(bundle(active,saved),connection())
        self.assertEqual(c.settings['print_host'],'http://edited.invalid')
        self.assertEqual(c.settings['printhost_apikey'],'new')
        cleared=selected_connection(bundle(preset(),saved),connection())
        self.assertFalse(cleared.configured)

    def test_embedded_missing_destination_recovers_only_the_same_profile_atomically(self):
        old=connection()
        self.assertIs(selected_connection(bundle(preset(embedded=True)),old),old)
        saved=preset(print_host='http://saved.invalid',printhost_apikey='saved-key',host_type='octoprint')
        other=PrinterConnection('Printer B','other',old.settings)
        c=selected_connection(bundle(preset(external=True),saved),other)
        self.assertEqual(c.settings['print_host'],'http://saved.invalid')
        self.assertEqual(c.settings['printhost_apikey'],'saved-key')
        self.assertFalse(selected_connection(bundle(preset(embedded=True),preset('Printer B',print_host='wrong')),other).configured)

    def test_connection_and_generated_model_strings_do_not_leak_credentials_or_inject_html(self):
        c=connection('http://private-address.invalid')
        s=review({'file':'<img src=x onerror=alert(1)>.gcode.3mf','sha256':'a'*64,'plate_index':0},c)
        html=dialog_html(s)
        self.assertNotIn('private-test-key',html+json.dumps(s)+repr(c))
        self.assertNotIn('private-address.invalid',html+json.dumps(s)+repr(c))
        self.assertNotIn('<img src=x',html)
        self.assertIn('&lt;img',html)
        self.assertIn('id="send" class="primary" disabled',html)

    def test_unvalidated_physics_is_advisory_but_technical_errors_still_block(self):
        identity={'file':'part.gcode.3mf','sha256':'a'*64,'plate_index':0}
        for report in ({},{'print_allowed':True,'physical_validation':False},
                       {'print_allowed':'true','physical_validation':True}):
            original=json.dumps(report)
            state=review(identity,connection(),report,verified=True)
            self.assertTrue(state['send_allowed'])
            self.assertTrue(state['risk_confirmation_required'])
            self.assertEqual(json.dumps(report),original)
        qualified={'print_allowed':True,'physical_validation':True}
        self.assertFalse(review(identity,connection(),qualified,verified=False)['send_allowed'])
        self.assertFalse(review(identity,connection(),qualified,verified=True,same_profile=False)['send_allowed'])
        self.assertFalse(review(identity,connection(),{**qualified,'bead_deposition':{'below_profile_minimum_occurrences':1}},verified=True)['send_allowed'])
        self.assertFalse(review(identity,connection(),{**qualified,'bead_deposition':{'above_profile_maximum_occurrences':1}},verified=True)['send_allowed'])

    def test_unavailable_adapter_is_explicit_and_does_not_fallback_to_octoprint(self):
        c=PrinterConnection('Printer B','active',{'printer_agent':'moonraker'})
        s=review({'file':'x','sha256':'a'*64,'plate_index':0},c,{'print_allowed':True,'physical_validation':True},verified=True)
        self.assertFalse(s['send_allowed'])
        self.assertTrue(any('adaptador' in reason for reason in s['reasons']))

    def test_identity_hash_mismatch_and_blocked_send_make_no_transport(self):
        with TemporaryDirectory() as root:
            p=Path(root)/'part.gcode.3mf';data=b'G90\nG1 X1 Y2 Z.2 E.1\n'
            build_sliced_package(data,p)
            identity=preview_identity(p,digest(data))
            with self.assertRaises(WaveError):preview_identity(p,'0'*64)
            factory=Mock()
            with self.assertRaises(WaveError):
                send_reviewed_file(p,identity,connection(),connection(),review(identity,connection()),transport_factory=factory)
            factory.assert_not_called()

    def test_modified_destination_or_package_cannot_be_sent(self):
        with TemporaryDirectory() as root:
            p=Path(root)/'part.gcode.3mf';data=b'G90\nG1 X1 Y2 Z.2 E.1\n';build_sliced_package(data,p)
            identity=preview_identity(p);c=connection();s=review(identity,c,{'print_allowed':True,'physical_validation':True},verified=True)
            factory=Mock()
            with self.assertRaises(WaveError):send_reviewed_file(p,identity,c,connection('http://another.invalid'),s,risk_acknowledged=True,transport_factory=factory)
            build_sliced_package(data+b'; changed\n',p)
            with self.assertRaises(WaveError):send_reviewed_file(p,identity,c,c,s,risk_acknowledged=True,transport_factory=factory)
            factory.assert_not_called()

    def test_acknowledged_unvalidated_upload_preserves_hash_and_never_selects_or_prints(self):
        with TemporaryDirectory() as root,OctoPrintSimulator() as sim:
            p=Path(root)/'part.gcode.3mf';data=b'G90\nG1 X1 Y2 Z.2 E.1\n';build_sliced_package(data,p)
            identity=preview_identity(p);c=connection(sim.base_url)
            # Simulator has its own test key; this does not touch a real printer.
            c=PrinterConnection(c.profile,c.source,{**c.settings,'printhost_apikey':sim.api_key})
            report={'print_allowed':False,'physical_validation':False}
            state=review(identity,c,report,verified=True)
            self.assertTrue(state['send_allowed']);self.assertEqual(sim.requests,[])
            for ack in (False,None,1,'true'):
                with self.assertRaisesRegex(WaveError,'Confirme o aviso'):
                    send_reviewed_file(p,identity,c,c,state,risk_acknowledged=ack)
            self.assertEqual(sim.requests,[])
            send_reviewed_file(p,identity,c,c,state,risk_acknowledged=True)
            self.assertEqual(len(sim.captures),1)
            self.assertEqual(sim.captures[0]['gcode'],data)
            self.assertFalse(sim.captures[0]['print']);self.assertFalse(sim.captures[0]['select'])
            self.assertEqual(report,{'print_allowed':False,'physical_validation':False})

    def test_host_confirmation_is_scoped_to_one_dialog_and_one_attempt(self):
        from orca_wave_studio import plugin
        c=connection();identity={'file':'part.gcode.3mf','sha256':'a'*64,'plate_index':0}
        state=review(identity,c,{'print_allowed':False},verified=True)
        window=Mock();window.is_open.return_value=True
        create=Mock(return_value=window);validate=Mock(return_value=True)
        fake_orca=SimpleNamespace(host=SimpleNamespace(ui=SimpleNamespace(create_window=create)))
        def thread(*,target,**kwargs):return SimpleNamespace(start=target)
        with patch.object(plugin,'orca',fake_orca),patch.object(plugin.threading,'Thread',side_effect=thread),\
             patch('orca_wave_studio.send_dialog.send_reviewed_file') as upload:
            host=plugin.NativeHost();host.selected_printer_connection=Mock(return_value=c)
            host.open_send_dialog('unused',identity,c,state,validate)
            html=create.call_args.args[0];receive=create.call_args.kwargs['on_message']
            token=json.loads(re.search(r'confirmation_token:("[^"]+")',html).group(1))
            upload.assert_not_called();validate.assert_not_called()
            for payload in ({'action':'send_file'},
                            {'action':'send_file','risk_acknowledged':True,'confirmation_token':'old-window'},
                            {'action':'send_file','risk_acknowledged':'true','confirmation_token':token}):receive(payload)
            upload.assert_not_called();validate.assert_not_called()
            message={'action':'send_file','risk_acknowledged':True,'confirmation_token':token}
            receive(message);receive(message)
            upload.assert_called_once();validate.assert_called_once()
            self.assertIs(upload.call_args.kwargs['risk_acknowledged'],True)
            # The acknowledgement is not a persistent bypass or a physics certificate.
            other=plugin.NativeHost();other.selected_printer_connection=Mock(return_value=c)
            other.open_send_dialog('unused',identity,c,state,validate)
            create.call_args.kwargs['on_message'](message)
            upload.assert_called_once()
            self.assertNotIn('confirmation_token',state)

    def test_controller_can_review_current_untracked_benchy_but_cannot_authorize_it(self):
        with TemporaryDirectory() as root:
            p=Path(root)/'part.gcode.3mf';build_sliced_package(b'G1 X1 Y2 Z.2 E.1\n',p)
            host=Mock();host.allowed_source_roots.return_value=(Path(root),)
            host.project_path.return_value=str(p);host.selected_printer_connection.return_value=connection()
            controller=StudioController(Path(root),host)
            state=controller.handle({'action':'open_send_dialog','print_allowed':True})
            self.assertNotEqual(state['state']['status'],'error')
            args=host.open_send_dialog.call_args.args
            self.assertFalse(args[3]['send_allowed']);self.assertFalse(args[4]())
            self.assertTrue(args[3]['connection']['configured'])
            controller.handle({'action':'open_send_dialog','sha256':'old'})
            self.assertEqual(host.open_send_dialog.call_count,1)


if __name__=='__main__':unittest.main()
