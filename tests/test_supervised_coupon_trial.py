"""Start guards tested with a fake client only; no printer/network access."""
import contextlib
import copy
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/run_supervised_coupon_trial.py'
spec=importlib.util.spec_from_file_location('supervised_trial',SCRIPT)
trial=importlib.util.module_from_spec(spec)
spec.loader.exec_module(trial)


class SupervisedTrialTests(unittest.TestCase):
    def journal(self):
        return {'state':'UPLOADED_HASH_VERIFIED_NOT_STARTED','start_attempted':False,
                'filename':'test.gcode','trial_sha256':trial.digest(b'payload')}

    def run_start(self,j,request,remote=b'payload'):
        snapshots=[]
        with patch.object(trial,'prepare',return_value=j),patch.object(trial,'client',return_value=object()),\
             patch.object(trial,'ready'),patch.object(trial,'remote_bytes',return_value=remote),\
             patch.object(trial,'save',side_effect=lambda state:snapshots.append(copy.deepcopy(state))),\
             patch.object(trial,'request',side_effect=request),patch.object(trial,'status',return_value={'state':'Printing'}),\
             patch.object(sys,'argv',['trial','start']),contextlib.redirect_stdout(io.StringIO()):
            trial.main()
        return snapshots

    def test_comment_only_trial_keeps_exact_executable_stream(self):
        a=b'; PRINT DISABLED\nG90 ; note\nM83\nG1 X1 E1\n'
        b=a.replace(b'; PRINT DISABLED',b'; SPECIFIC USER AUTHORIZED TRIAL')
        self.assertEqual(trial.commands(a),trial.commands(b))

    def test_start_is_journalled_before_one_start_post(self):
        j=self.journal();calls=[]
        def request(c,endpoint,method='GET',value=None):
            calls.append((endpoint,method,value))
            if endpoint=='job' and method=='GET':
                return {'job':{'file':{'name':j['filename'],'origin':'local'}}}
            if endpoint=='job' and method=='POST':
                self.assertTrue(j['start_attempted'])
                self.assertEqual(j['state'],'START_SENT_OR_UNCERTAIN')
            return {}
        snapshots=self.run_start(j,request)
        self.assertEqual(sum(e=='job' and m=='POST' for e,m,v in calls),1)
        self.assertEqual(calls[0][2],{'command':'select','print':False})
        self.assertTrue(any(s.get('state')=='START_SENT_OR_UNCERTAIN' for s in snapshots))

    def test_repeated_start_or_hash_change_never_posts(self):
        for duplicate in (True,False):
            j=self.journal();j['start_attempted']=duplicate;calls=[]
            with self.assertRaises(SystemExit):
                self.run_start(j,lambda *a,**kw:calls.append(a),remote=b'wrong')
            self.assertEqual(calls,[])

    def test_different_selected_job_never_starts(self):
        j=self.journal();starts=[]
        def request(c,endpoint,method='GET',value=None):
            if method=='POST' and endpoint=='job':starts.append(value)
            return {'job':{'file':{'name':'another.gcode','origin':'local'}}} if method=='GET' else {}
        with self.assertRaises(SystemExit):self.run_start(j,request)
        self.assertEqual(starts,[])


if __name__=='__main__':unittest.main()
