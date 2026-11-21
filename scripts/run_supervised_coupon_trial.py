"""One specifically authorized SV06 coupon trial, not a production print backend.

Default is local preparation only. Upload never starts a job. Starting needs a
verified uploaded payload and is journalled before its single POST attempt.
No credentials or host address are written into the journal or stdout.
"""
from pathlib import Path
import argparse
from datetime import datetime,timezone
import hashlib
import http.client
import json
import math
import os
import secrets
import sys
from urllib.parse import quote,urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio.engine_parser import read
from orca_wave_studio.octoprint import OctoPrintTransport
from orca_wave_studio.contracts import digest

FOLDER=ROOT/'study/evidence/physical-preflight/constant-pitch25-held'
EXPECTED='0f09c5a502726a0f5d367677ecb3b9f43aa22287036d9069cf7243440d757353'
MACHINE=os.environ.get('OWS_TRIAL_MACHINE_PRESET')
JOURNAL=FOLDER/'physical-trial-compact-journal.json'


def stamp():return datetime.now(timezone.utc).isoformat()


def save(j):
    temp=JOURNAL.with_suffix('.tmp')
    temp.write_text(json.dumps(j,indent=2,ensure_ascii=False),encoding='utf8')
    temp.replace(JOURNAL)


def commands(data):
    return b'\n'.join(line.split(b';',1)[0].strip() for line in data.splitlines()
                      if line.split(b';',1)[0].strip())


def prepare():
    data=(FOLDER/'HOLD-constant-pitch25-SV06.gcode').read_bytes()
    if digest(data)!=EXPECTED:raise RuntimeError('Held source differs from the reviewed Preview.')
    body=json.loads((FOLDER/'nominal-body-bound.json').read_bytes())
    preview=json.loads((FOLDER/'preview-verification.json').read_bytes())
    if body['gcode_sha256']!=EXPECTED or body['status']!='PASS_NOMINAL_BODY_BOUND':
        raise RuntimeError('Nominal component-body bound is missing or failed.')
    if preview['source_sha256']!=EXPECTED or not preview['preview_gcode_byte_identical']:
        raise RuntimeError('Native Preview payload comparison missing.')
    marker=b'; OWS CONSTANT PITCH TRIAL / BENCH ONLY / PRINT DISABLED'
    if data.count(marker)!=1:raise RuntimeError('Unexpected experiment marker.')
    # The first full-comment upload was confirmed changed by server annotation
    # plugins (M117 layer display and @Object host directives); it was never
    # selected or started. Avoid their comment triggers in this single-object
    # physical copy without disabling or configuring any server plugin.
    # The server always appends this exact inert processing footer. Include
    # it locally so the canonical payload and its downloaded copy are equal.
    # No server or printer configuration is changed.
    footer=(b'; BEGIN DISPLAYLAYERPROGRESS SETTINGS\n'
            b'; DisplayLayerProgress_layerIndicatorProcessed = true\n'
            b'; END   DISPLAYLAYERPROGRESS SETTINGS\n')
    trial=commands(data)+b'\n'+footer
    if commands(trial)!=commands(data):raise RuntimeError('Trial changed executable motion commands.')
    # Metadata lives in the reviewed Preview. The executable stream of the
    # compact copy must be exactly identical before its limits are inherited.
    parsed=read(data,set(),{0:'1'})
    maximum=[-math.inf]*3;minimum=[math.inf]*3
    peak_zspeed=peak_flow=0.
    positive_moves=0
    for m in parsed.moves.values():
        if None in m.end:continue
        for i,v in enumerate(m.end):
            minimum[i]=min(minimum[i],v);maximum[i]=max(maximum[i],v)
        if None in m.start:continue
        length=math.dist(m.start,m.end)
        if m.deposits:
            positive_moves+=1
            if length<=0 or m.f<=0:raise RuntimeError('Invalid extrusion feed/position.')
            if m.layer>=5:
                speed=m.f/60
                peak_zspeed=max(peak_zspeed,speed*abs(m.end[2]-m.start[2])/length)
                peak_flow=max(peak_flow,m.de*(math.pi*1.75**2/4)*speed/length)
    if any(lo<0 or hi>limit for lo,hi,limit in zip(minimum,maximum,(220,220,250))):
        raise RuntimeError('Motion outside confirmed SV06 volume.')
    if peak_zspeed>5.001 or peak_flow>12.001:
        raise RuntimeError('Trial exceeds its Z/flow limits.')
    if b'M203 X80 Y80 Z10 E30' not in trial or b'M190 S65' not in trial or b'M109 S200' not in trial or b'M104 S195' not in trial:
        raise RuntimeError('Reviewed machine/temperature settings changed.')
    if JOURNAL.exists():
        j=json.loads(JOURNAL.read_text(encoding='utf8'))
        if j['trial_sha256']!=digest(trial):raise RuntimeError('Different trial already journalled.')
        return j
    name='OWS_coupon25_Voolt3D_trial_compact_'+digest(trial)[:12]+'.gcode'
    path=FOLDER/name
    path.write_bytes(trial)
    j={'created_at_utc':stamp(),'state':'PREPARED_AUTHORIZED_SUPERVISED_TRIAL',
       'printer_name':'Sovol SV06 0.4 nozzle -3DPrinter','material':'PLA Voolt3D sem FP',
       'held_preview_sha256':EXPECTED,'trial_sha256':digest(trial),
       'executable_commands_sha256':digest(commands(trial)),
       'executable_commands_equal_to_reviewed_preview':True,
       'comment_free_transport_copy':True,'server_annotation_plugins_unchanged':True,
       'filename':name,'file_path':str(path),'bytes':len(trial),
       'authorization_quote':'pode imprimir tem espaço eu conferi a peça que foi criado e a folga',
       'user_confirmed_stock_head_clearance':True,'user_supervising':True,'bed_clear_confirmed':True,
       'controlled_trial_authorized':True,'production_approved':False,'physical_result_validated':False,
       'known_trial_limitations':['First cut-cell transition minimum is 0.0377 mm, below the ordinary planar profile minimum of 0.07 mm; deposition is an experimental observation in this trial.',
           'Growing bead/nozzle contact model is uncalibrated; installed CAD registration is not measured.',
           'Support removal, surface accuracy, bridging and adhesion have not been physically validated.'],
       'nominal_body_clearance_bound_mm':body['nominal_body_minimum_bound_mm'],
       'motion_bounds_mm':[minimum,maximum],'upper_peak_z_speed_mm_s':peak_zspeed,
       'upper_peak_volumetric_flow_mm3_s':peak_flow,'positive_deposition_moves':positive_moves,
       'temperatures_c':{'initial_nozzle':200,'nozzle':195,'bed':65},
       'upload_attempted':False,'start_attempted':False,'cancel_attempted':False,
       'automatic_print_retry_allowed':False}
    save(j)
    return j


def client():
    if not MACHINE:
        raise RuntimeError('Set OWS_TRIAL_MACHINE_PRESET to the explicitly authorized local machine preset.')
    s=json.loads(Path(MACHINE).read_bytes())
    base=s['print_host'].strip()
    if '://' not in base:base='http://'+base
    return OctoPrintTransport(base,s['printhost_apikey'],allow_real_printer=True,timeout=30.)


def request(c,endpoint,method='GET',value=None):
    conn=c._connect()
    try:
        data=json.dumps(value).encode() if value is not None else None
        headers={'X-Api-Key':c._key}
        if data is not None:headers['Content-Type']='application/json'
        conn.request(method,c._path(endpoint),body=data,headers=headers)
        with conn.getresponse() as r:
            body=r.read(1024*1024+1)
            if r.status not in (200,204):raise RuntimeError(f'HTTP {r.status} for {endpoint.split("/")[0]}')
            if len(body)>1024*1024:raise RuntimeError('Excessive response.')
            return json.loads(body) if body else {}
    finally:conn.close()


def ready(c):
    status=c.status()
    if not status['ready']:raise RuntimeError('Printer is not ready and idle.')
    profiles=request(c,'printerprofiles')['profiles']
    current=[p for p in profiles.values() if p.get('current')]
    if len(current)!=1:raise RuntimeError('Ambiguous active printer profile.')
    p=current[0];v=p['volume'];e=p['extruder']
    if p['name']!='Sovol SV06' or [v[k] for k in ('width','depth','height')]!=[220.,220.,250.] or e['nozzleDiameter']!=.4 or e['count']!=1:
        raise RuntimeError('Connected printer differs from the authorized SV06.')
    return status


def remote_bytes(c,name):
    conn=c._connect()
    try:
        path=c._url.path.rstrip('/')+'/downloads/files/local/'+quote(name,safe='')
        conn.request('GET',path,headers={'X-Api-Key':c._key})
        with conn.getresponse() as r:
            if r.status!=200:raise RuntimeError('Uploaded payload download failed.')
            return r.read(4*1024*1024+1)
    finally:conn.close()


def status(c,j):
    p=request(c,'printer');job=request(c,'job')
    return {'timestamp_utc':stamp(),'state':job['state'],'flags':p['state']['flags'],
            'temperature':{k:v for k,v in p.get('temperature',{}).items() if k in ('tool0','bed')},
            'job_file':job.get('job',{}).get('file',{}).get('name'),
            'progress':job.get('progress',{}),'target_trial':j['filename']}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['prepare','upload','start','status','cancel'])
    stage=parser.parse_args().stage
    j=prepare()
    if stage=='prepare':
        print(json.dumps({k:j[k] for k in ('state','filename','trial_sha256','motion_bounds_mm','upper_peak_z_speed_mm_s','upper_peak_volumetric_flow_mm3_s')},indent=2));return
    c=client()
    try:
        if stage=='upload':
            if j['upload_attempted']:raise RuntimeError('Upload already attempted; inspect the journal and remote file instead of retrying.')
            ready(c)
            data=Path(j['file_path']).read_bytes()
            if digest(data)!=j['trial_sha256']:raise RuntimeError('Local trial hash differs.')
            j.update(upload_attempted=True,upload_intent_at_utc=stamp(),state='UPLOAD_SENT_OR_UNCERTAIN');save(j)
            receipt=c._upload(data,j['filename'],j['trial_sha256'],start_print=False,cancelled=None)
            response=receipt['response']
            if response.get('effectivePrint') is not False or response.get('effectiveSelect') is not False:
                raise RuntimeError('Unexpected upload selection or start.')
            remote=response.get('files',{}).get('local',response.get('file',{}))
            if remote.get('name')!=j['filename'] or remote.get('path')!=j['filename']:
                raise RuntimeError('Uploaded file identity differs.')
            actual=digest(remote_bytes(c,j['filename']))
            if actual!=j['trial_sha256']:raise RuntimeError('Server payload differs; do not print.')
            j.update(state='UPLOADED_HASH_VERIFIED_NOT_STARTED',uploaded_at_utc=stamp(),
                     upload_http_status=receipt['http_status'],server_sha256=actual,
                     server_payload_byte_identical=True);save(j)
        elif stage=='start':
            if j['start_attempted'] or j['state']!='UPLOADED_HASH_VERIFIED_NOT_STARTED':
                raise RuntimeError('No verified unstarted upload, or start already attempted. Never repeat automatically.')
            ready(c)
            if digest(remote_bytes(c,j['filename']))!=j['trial_sha256']:raise RuntimeError('Server hash changed.')
            request(c,'files/local/'+quote(j['filename'],safe=''),'POST',{'command':'select','print':False})
            job=request(c,'job')
            if job['job']['file']['name']!=j['filename'] or job['job']['file']['origin']!='local':
                raise RuntimeError('Selected job identity differs.')
            ready(c)
            j.update(start_attempted=True,start_intent_at_utc=stamp(),state='START_SENT_OR_UNCERTAIN');save(j)
            request(c,'job','POST',{'command':'start'})
            j.update(state='START_ACCEPTED',start_accepted_at_utc=stamp());save(j)
        elif stage=='cancel':
            job=request(c,'job')
            if job.get('job',{}).get('file',{}).get('name')!=j['filename']:
                raise RuntimeError('Another file is selected; do not cancel a different job.')
            if j['cancel_attempted']:raise RuntimeError('Cancel already attempted; inspect status.')
            j.update(cancel_attempted=True,cancel_intent_at_utc=stamp());save(j)
            request(c,'job','POST',{'command':'cancel'})
            j.update(state='CANCEL_ACCEPTED');save(j)
        result=status(c,j)
        j['last_status']=result
        save(j)
        print(json.dumps({'journal_state':j['state'],**result},indent=2))
    except Exception as exc:
        j.update(last_error_type=type(exc).__name__,last_error_at_utc=stamp())
        save(j)
        # Exception text excludes host/key because HTTP helpers emit only
        # endpoint categories. Low-level network errors are withheld.
        print(json.dumps({'state':j['state'],'error_type':type(exc).__name__,
                          'automatic_retry':False,'message':str(exc) if isinstance(exc,RuntimeError) else 'Network result requires read-only inspection.'}))
        raise SystemExit(1)


if __name__=='__main__':main()
