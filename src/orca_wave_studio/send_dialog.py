"""Host-owned send review. Connections remain in Python, never in the WebView.

Opening this dialog performs no network request. Physical authorization is
separate from file/Preview identity and cannot be supplied by the page.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
import json
from pathlib import Path
import re

from .contracts import WaveError, digest
from .package import extract_plate_gcode
from .printer_profile import value


CONNECTION_KEYS = ('print_host', 'printhost_apikey', 'host_type', 'printer_agent',
                   'printhost_cafile', 'printhost_user', 'printhost_password')


def plain(raw):
    return str(value({'v': raw}, 'v', '') or '').strip()


@dataclass(frozen=True)
class PrinterConnection:
    profile: str
    source: str
    settings: dict = field(repr=False)

    @property
    def configured(self):
        return bool(self.settings.get('print_host') or self.settings.get('printer_agent'))

    def public(self):
        # No address, key, certificate path or username crosses the UI bridge.
        return {'profile': self.profile, 'source': self.source,
                'configured': self.configured,
                'protocol': self.settings.get('host_type') or self.settings.get('printer_agent') or 'Não configurado',
                'credential_present': bool(self.settings.get('printhost_apikey'))}


def selected_connection(bundle, remembered=None):
    """Use the edited destination; recover only the exact same saved preset.

    An embedded sliced-only preset can omit its print-host fields. Never scan
    other printers for any available address or combine a key from another host.
    """
    presets = bundle.printers
    edited = presets.get_edited_preset()
    name = str(edited.name)
    def read(preset, source):
        return PrinterConnection(name, source, {k: plain(preset.config_value(k)) for k in CONNECTION_KEYS})
    active = read(edited, 'Perfil selecionado no Orca')
    if active.configured:
        return active
    # Only an imported/embedded preset can inherit a missing connection.
    # A user deliberately clearing a normal preset's address must be respected.
    if not (getattr(edited, 'is_external', False) or getattr(edited, 'is_project_embedded', False)):
        return active
    if remembered is not None and remembered.profile == name and remembered.configured:
        return remembered
    saved = presets.find_preset(name)
    if (saved is not None and not getattr(saved, 'is_external', False)
            and not getattr(saved, 'is_project_embedded', False) and str(saved.name) == name):
        return read(saved, 'Conexão salva do mesmo perfil')
    return active


def preview_identity(path, expected_sha=None, plate_index=0):
    path = Path(path).resolve(strict=True)
    if not path.name.lower().endswith('.gcode.3mf'):
        raise WaveError('Abra o resultado no Preview do Orca antes de conferir o envio.')
    data = extract_plate_gcode(path, plate_index)
    sha = digest(data)
    if expected_sha is not None and expected_sha != sha:
        raise WaveError('O arquivo mudou depois do estudo. Abra novamente o resultado correto.')
    return {'file': path.name, 'sha256': sha, 'plate_index': plate_index, 'bytes': len(data)}


def review(identity, connection, report=None, *, verified=False, same_profile=True):
    report = report or {}
    bead = report.get('bead_deposition', {})
    reasons = []
    if not same_profile:
        reasons.append('A impressora selecionada mudou desde o estudo. Gere o resultado com esse perfil.')
    if not connection.configured:
        reasons.append('Configure a conexão neste perfil de impressora no Orca.')
    if not verified:
        reasons.append('Este Preview não tem uma conferência vigente do Studio para envio.')
    if report.get('print_allowed') is not True or report.get('physical_validation') is not True:
        reasons.append('Somente Preview: a deposição, as transições e o cabeçote ainda precisam de validação.')
    if bead.get('below_profile_minimum_occurrences', 0):
        reasons.append('Há cordões abaixo da altura mínima do perfil selecionado.')
    protocol = connection.settings.get('host_type', '').lower()
    if protocol != 'octoprint' or connection.settings.get('printer_agent'):
        reasons.append('Esta conexão requer o adaptador nativo do Orca; o envio direto do Studio ainda não o suporta.')
    elif not connection.settings.get('printhost_apikey'):
        reasons.append('A chave da conexão OctoPrint não está configurada no perfil.')
    return {**identity, 'connection': connection.public(), 'send_allowed': not reasons,
            'reasons': reasons, 'action': 'Enviar arquivo sem iniciar impressão'}


def dialog_html(state):
    # Static review, no editable destination and no arbitrary HTML from the model.
    c = state['connection']
    text = lambda v: escape(str(v), quote=True)
    reasons = ''.join('<li>'+text(r)+'</li>' for r in state['reasons'])
    connection = ('Conexão preservada · credencial '+('disponível' if c['credential_present'] else 'não informada')) if c['configured'] else 'Conexão não configurada'
    return '''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:dark;--accent:#00a896}*{box-sizing:border-box}body{margin:0;background:#191d23;color:#edf1f4;font:14px/1.5 "Segoe UI",sans-serif}main{padding:26px 28px}header{border-bottom:1px solid #39414b;padding-bottom:18px;margin-bottom:20px}small{color:#a9b6c2}h1{font-size:23px;line-height:1.2;margin:8px 0}h2{font-size:16px;margin:0 0 6px}.destination{border-left:3px solid var(--accent);padding:0 16px;margin:22px 0}dl{display:grid;grid-template-columns:80px 1fr;gap:9px 12px}dt{color:#a9b6c2}dd{margin:0;overflow-wrap:anywhere}code{font:11px/1.5 Consolas,monospace}.notice{padding:14px 16px;background:#252a31;border:1px solid #765e37;border-radius:6px}ul{padding-left:20px;margin:8px 0 0}.actions{display:flex;gap:10px;justify-content:flex-end;margin-top:22px;flex-wrap:wrap}button{font:inherit;padding:10px 16px;border-radius:5px;border:1px solid #48535e;background:#252b33;color:#edf1f4;cursor:pointer}button.primary{background:var(--accent);border-color:var(--accent);color:white}button:disabled{background:#30363d!important;color:#9ca7b1!important;border-color:#414950;cursor:default}#status{min-height:22px;color:#c7d1da;margin-top:12px}@media(max-width:480px){main{padding:18px}dl{grid-template-columns:1fr;gap:4px}dd{margin-bottom:8px}.actions button{width:100%}}
/* Orca injects its own theme after plugin styles, including body and headings. */
html body,html body main{background:#191d23!important;color:#edf1f4!important}html body h1,html body h2,html body dd,html body .notice,html body .notice *{color:#edf1f4!important}html body small,html body dt{color:#b7c3ce!important}html body .notice{background:#252a31!important}html body button{background:#252b33!important;color:#edf1f4!important}html body button.primary{background:#008f80!important}html body button:disabled{background:#30363d!important;color:#aeb9c3!important}
</style></head><body><main><header><small>SURFACE STUDIO · CONFERÊNCIA DE ENVIO</small><h1>Enviar para impressora</h1><small>Abrir esta janela não conecta, envia ou inicia impressão.</small></header>
<section class="destination"><h2>'''+text(c['profile'])+'''</h2><div>'''+text(c['protocol'])+'''</div><small>'''+text(connection)+'''</small><br><small>'''+text(c['source'])+'''</small></section>
<dl><dt>Arquivo</dt><dd>'''+text(state['file'])+'''</dd><dt>Bandeja</dt><dd>'''+text(state['plate_index']+1)+'''</dd><dt>SHA-256</dt><dd><code>'''+text(state['sha256'])+'''</code></dd></dl>
<section class="notice"><strong>'''+('Envio disponível' if state['send_allowed'] else 'Envio bloqueado para este estudo')+'''</strong><ul>'''+reasons+'''</ul></section><div id="status" role="status"></div><div class="actions"><button id="close">Fechar</button><button id="send" class="primary" '''+('' if state['send_allowed'] else 'disabled')+'''>Enviar arquivo</button></div><small>O envio, quando liberado, apenas armazena o arquivo. Não inicia a impressão.</small></main>
<script>document.getElementById('close').onclick=()=>window.orca.close();document.getElementById('send').onclick=()=>{document.getElementById('send').disabled=true;window.orca.postMessage({action:'send_file'})};window.orca.onMessage(m=>{if(typeof m==='string')m=JSON.parse(m);document.getElementById('status').textContent=m.message||''});</script></body></html>'''


def send_reviewed_file(path, identity, connection, fresh_connection, state, *, transport_factory=None, cancelled=None):
    """A single explicit upload; a forged page message cannot lift any gate."""
    if state.get('send_allowed') is not True:
        raise WaveError('Envio bloqueado: este estudo continua somente para Preview.')
    if fresh_connection != connection:
        raise WaveError('A conexão selecionada mudou. Feche e confira o envio novamente.')
    checked = preview_identity(path, identity['sha256'], identity['plate_index'])
    if checked != identity:
        raise WaveError('O arquivo mudou. Confira novamente o Preview.')
    from .octoprint import OctoPrintTransport
    transport = (transport_factory or OctoPrintTransport)(connection.settings['print_host'],
        connection.settings['printhost_apikey'], allow_real_printer=True)
    data = extract_plate_gcode(Path(path), identity['plate_index'])
    if digest(data) != identity['sha256']:
        raise WaveError('O conteúdo mudou antes do envio.')
    name = re.sub(r'[^A-Za-z0-9_.-]', '_', Path(identity['file']).name.removesuffix('.3mf'))
    return transport.upload_only(data, name, identity['sha256'], cancelled=cancelled)
