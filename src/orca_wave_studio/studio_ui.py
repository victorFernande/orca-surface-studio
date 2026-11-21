"""Offline WebView document shared by the Orca page, dock and bench viewer."""
from __future__ import annotations

import json

from .controller import BUILTIN_PRESETS


def get_studio_html(initial_state: dict | None = None, *, dock: bool = False) -> str:
    payload = json.dumps(initial_state or {}, ensure_ascii=False, allow_nan=False)
    # The state is data inside a script element. Its contents must never end the element.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    factory = json.dumps(BUILTIN_PRESETS, ensure_ascii=False).replace("<", "\\u003c")
    return (_HTML.replace("__LAYOUT__", "dock" if dock else "page")
            .replace("__PRESET_DATA__", factory).replace("__STATE__", payload))


_HTML = r"""<!doctype html>
<html lang="pt-BR" data-theme="dark"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Orca Surface Studio</title>
<style>
:root{color-scheme:dark;--bg-app:#15171b;--bg-panel:#1d2026;--bg-card:#242830;--bg-card-hover:#2b303a;--bg-input:#16181d;--bg-viewport-top:#222731;--bg-viewport-bot:#111318;--bg-hud:rgba(23,26,33,.88);--border-subtle:#313641;--border-strong:#434b5a;--text-main:#eef2f7;--text-muted:#9aa4b4;--text-dim:#6d7788;--orca-accent:#00a896;--orca-accent-hover:#00bfa5;--orca-accent-soft:rgba(0,191,165,.15);--orca-accent-border:rgba(0,191,165,.48);--secondary-accent:#4f9cf9;--status-ok:#00c853;--status-warn:#ffb300;--status-crit:#ff5252;--font-sans:var(--orca-font,"Segoe UI",-apple-system,BlinkMacSystemFont,Roboto,Ubuntu,sans-serif);--font-mono:"Cascadia Code",Consolas,"SFMono-Regular",monospace;--shadow-soft:0 8px 24px rgba(0,0,0,.36);--radius-sm:6px;--radius-md:9px}
[data-theme=light]{color-scheme:light;--bg-app:#edf1f6;--bg-panel:#fff;--bg-card:#f5f7fb;--bg-card-hover:#eaeff6;--bg-input:#fff;--bg-viewport-top:#dce3ec;--bg-viewport-bot:#c6d0dc;--bg-hud:rgba(255,255,255,.91);--border-subtle:#d4dce5;--border-strong:#b6c2cf;--text-main:#1b222c;--text-muted:#525e6f;--text-dim:#798596;--orca-accent:#00897b;--orca-accent-hover:#00796b;--orca-accent-soft:rgba(0,137,123,.12);--orca-accent-border:rgba(0,137,123,.45);--secondary-accent:#2563eb;--status-ok:#169c46;--status-warn:#d47f00;--status-crit:#d93025}
*{box-sizing:border-box}body{margin:0;height:100vh;display:flex;flex-direction:column;background:var(--bg-app);color:var(--text-main);font:13px/1.45 var(--font-sans)}button,input,select{font:inherit;color:inherit}button,select{cursor:pointer}button{display:inline-flex;align-items:center;justify-content:center;gap:7px;border:1px solid var(--border-subtle);border-radius:var(--radius-sm);background:var(--bg-card);padding:7px 10px;line-height:1.2}button:hover:not(:disabled){background:var(--bg-card-hover);border-color:var(--border-strong)}button:active:not(:disabled){transform:translateY(1px)}button:disabled,select:disabled,input:disabled{opacity:.45;cursor:default}button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible,canvas:focus-visible{outline:2px solid var(--orca-accent-hover);outline-offset:2px}h1,h2,h3,p{margin:0}h1{font-size:19px;font-weight:650;letter-spacing:-.6px}h2{font-size:18px;font-weight:650;letter-spacing:-.4px}h3{font-size:14px;letter-spacing:-.2px}p,small,.muted{color:var(--text-muted)}small{font-size:11px}svg.ic{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round;flex:none}.iconbtn{height:30px;width:30px;padding:0}.mono,output,dd,.smallcap{font-family:var(--font-mono)}.smallcap{font-size:10px;letter-spacing:1px;text-transform:uppercase;color:var(--text-muted)}[hidden]{display:none!important}.row{display:flex;align-items:center;gap:8px}.spread{justify-content:space-between}
header{height:60px;flex:none;display:flex;align-items:center;justify-content:space-between;padding:0 20px;gap:12px;border-bottom:1px solid var(--border-subtle);background:var(--bg-panel)}.brand{display:flex;gap:11px;align-items:center}.brandmark{width:33px;height:33px;color:var(--orca-accent-hover);background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:8px;padding:4px}.brand h1 span{font-weight:400;color:var(--text-muted)}.connection{color:var(--text-muted);font-size:12px}.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--status-warn)}.dot.live{background:var(--orca-accent)}.work{display:grid;grid-template-columns:clamp(255px,22vw,344px) minmax(250px,1fr) clamp(245px,21vw,356px);min-height:0;flex:1}.side{min-height:0;display:flex;flex-direction:column;background:var(--bg-panel)}.left{border-right:1px solid var(--border-subtle)}.right{border-left:1px solid var(--border-subtle)}.scroll{overflow:auto;scrollbar-width:thin;scrollbar-color:var(--border-strong) transparent;min-height:0;flex:1}.section{padding:18px 17px;border-bottom:1px solid var(--border-subtle)}.sectionhead{display:flex;align-items:center;justify-content:space-between;gap:5px;margin-bottom:12px}.sectionhead h3{display:flex;align-items:center;gap:7px}.sectionhead h3 svg{color:var(--text-muted)}.badge{color:var(--orca-accent-hover);background:var(--orca-accent-soft);border:1px solid var(--orca-accent-border);border-radius:4px;padding:1px 5px;font:11px var(--font-mono)}.outline{background:transparent}.objects{display:grid;gap:6px}.object{display:flex;align-items:flex-start;gap:8px;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:6px;padding:9px}.object:has(input:checked){border-color:var(--orca-accent-border);background:var(--orca-accent-soft)}.object input{margin:4px 0 0;accent-color:var(--orca-accent)}.object strong,.object small{display:block;overflow-wrap:anywhere}.object small{margin-top:2px;font-family:var(--font-mono)}.object strong{font-weight:600}.section>.wide,.section>p+.row{margin-top:10px}.wide{width:100%}.segments{display:flex;padding:3px;border:1px solid var(--border-subtle);border-radius:6px;background:var(--bg-input);gap:3px}.segments button{flex:1;background:transparent;border:0;color:var(--text-muted);padding:6px 7px}.segments button[aria-pressed=true]{background:var(--orca-accent-soft);color:var(--orca-accent-hover);box-shadow:inset 0 0 0 1px var(--orca-accent-border);font-weight:600}.field{margin-top:14px}.fieldtop{display:flex;align-items:center;justify-content:space-between;gap:5px}.unit{font:10px var(--font-mono);color:var(--text-muted)}input[type=number],input[type=text],select{border:1px solid var(--border-strong);border-radius:4px;background:var(--bg-input);padding:4px 6px;min-width:0}input[type=number]{font:12px var(--font-mono);width:68px;text-align:right}input[type=range]{width:100%;height:14px;margin:5px 0 0;accent-color:var(--orca-accent-hover);cursor:pointer}.twocol{display:grid;grid-template-columns:1fr 1fr;gap:9px}.twocol label{display:grid;gap:5px;color:var(--text-muted);font-size:12px}.twocol input{width:100%;text-align:left}details summary{cursor:pointer;color:var(--text-muted);font-size:12px}details[open] summary{margin-bottom:10px}.fieldset{border:0;padding:0;margin:0;min-width:0}.chart{width:100%;height:68px;display:block;margin:12px 0 5px;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:6px}.chart .wave{fill:none;stroke:var(--orca-accent-hover);stroke-width:2;vector-effect:non-scaling-stroke}.chart .axis{stroke:var(--border-subtle);stroke-dasharray:3 4}.presets{width:100%;margin:5px 0}.presetops{display:flex;gap:5px;margin:5px 0}.presetops button{flex:1;font-size:12px}.preset-editor{display:grid;gap:6px;margin-top:8px}.preset-editor input{width:100%}
.viewport{min-height:0;min-width:0;display:flex;flex-direction:column;background:var(--bg-app)}.vhead{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:14px 16px;border-bottom:1px solid var(--border-subtle)}.vhead h2{font-size:17px}.viewtabs button{font-size:11px;white-space:nowrap}.stage{position:relative;flex:1;min-height:175px;overflow:hidden;background:radial-gradient(ellipse at 50% 39%,var(--bg-viewport-top),var(--bg-viewport-bot))}.stage canvas{width:100%;height:100%;display:block;touch-action:none;cursor:grab}.stage canvas:active{cursor:grabbing}.vbuttons{position:absolute;top:12px;right:12px;display:grid;gap:3px}.vbuttons button{background:var(--bg-hud)}.legend{position:absolute;bottom:10px;left:12px;display:flex;gap:12px;color:var(--text-muted);font:11px var(--font-mono);background:var(--bg-hud);padding:5px 7px;border-radius:4px;pointer-events:none}.swatch{display:inline-block;width:12px;height:2px;vertical-align:middle;margin-right:4px}.swatch.modified{background:var(--orca-accent-hover)}.swatch.original{background:var(--secondary-accent)}.empty{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;padding:24px;text-align:center}.empty p{max-width:310px;background:var(--bg-hud);border:1px solid var(--border-subtle);padding:16px 20px;border-radius:var(--radius-md)}.transport{padding:12px 15px;background:var(--bg-panel);border-top:1px solid var(--border-subtle)}.transport .track{flex:1;min-width:35px;margin:0}.transport .readout{font:11px var(--font-mono);color:var(--text-muted);margin-top:9px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}.transport select{font-size:11px;max-width:140px}.xyz{color:var(--text-main);white-space:pre-wrap}.layerrow{display:flex;align-items:center;justify-content:space-between;margin-top:9px;gap:5px}.transport .layerrow small{font-size:10px}.stageinfo{position:absolute;left:13px;top:13px;max-width:65%;pointer-events:none}.stageinfo strong{display:block;color:var(--text-muted);font-size:11px;font-weight:500}.stageinfo .smallcap{font-size:9px}
.state{display:flex;align-items:center;gap:8px;font-weight:600}.state .dot{background:var(--text-dim)}.state.ready .dot{background:var(--orca-accent-hover)}.state.error .dot{background:var(--status-crit)}.state.processing .dot,.state.analyzing .dot,.state.slicing_required .dot{background:var(--status-warn)}.message{margin:7px 0;font-size:12px;overflow-wrap:anywhere}.data{margin:8px 0 0;font-size:12px}.data>div{padding:6px 0;border-top:1px solid var(--border-subtle);display:flex;justify-content:space-between;gap:8px}.data dt{color:var(--text-muted)}.data dd{margin:0;text-align:right;overflow-wrap:anywhere}.flow{display:grid;gap:8px}.foot{padding:14px 16px;border-top:1px solid var(--border-subtle);background:var(--bg-panel)}.foot small{display:block;text-align:center;margin-top:6px}.positive{background:var(--orca-accent);color:white;border-color:var(--orca-accent);font-weight:650;padding:10px}.positive:hover:not(:disabled){background:var(--orca-accent-hover);border-color:var(--orca-accent-hover)}.foot .wide+.wide{margin-top:6px}.notice{padding:8px 12px;background:var(--bg-input);color:var(--status-warn);overflow-wrap:anywhere;font-size:12px}.docktabs{display:none}.path{display:block;overflow-wrap:anywhere;user-select:all;color:var(--text-muted);font:10px/1.5 var(--font-mono);margin-top:7px}.docktabs button[aria-selected=true]{border-color:var(--orca-accent-border);color:var(--orca-accent-hover);background:var(--orca-accent-soft)}
body.compact{height:auto;min-height:100vh}body.compact header{padding:0 10px;height:46px}body.compact .connection{font-size:10px}body.compact .brand{gap:6px}body.compact h1{font-size:15px}body.compact .brandmark{width:27px;height:27px}body.compact .work{display:flex;flex-direction:column}body.compact .viewport{order:-1}body.compact .stage{height:clamp(230px,33vh,360px);flex:auto}body.compact .side{border:0}body.compact .side:not(.shown){display:none}body.compact .docktabs{display:flex;gap:5px;padding:6px 10px;background:var(--bg-panel);border-bottom:1px solid var(--border-subtle)}body.compact .docktabs button{flex:1}body.compact .scroll{overflow:visible}body.compact .section{padding:13px 15px}body.compact .vhead{padding:8px 10px;flex-wrap:wrap}body.compact .vhead h2{font-size:14px}body.compact .transport{padding:8px 10px}body.compact .foot{position:sticky;bottom:0}body.compact .layerrow small{display:none}@media(max-width:580px){.connection{max-width:137px;line-height:1.15}.transport .readout{gap:6px}.vhead{flex-wrap:wrap}.viewtabs{max-width:100%}}@media(max-height:660px) and (min-width:841px){.section{padding:11px 14px}.field{margin-top:8px}header{height:48px}}
.object{align-items:center}.object .pick-object{display:block;flex:1;min-width:0;text-align:left;padding:2px 4px;background:transparent;border:1px solid transparent}.object .pick-object[aria-pressed=true]{border-left:2px solid var(--orca-accent-hover);border-radius:0;padding-left:7px}.edit-target{display:block;color:var(--orca-accent-hover);font-size:12px;margin:-4px 0 10px;overflow-wrap:anywhere}
/* Orca also injects element defaults, including a native foreground for headings. */
html[data-theme=dark]{--orca-accent:#00a896;color-scheme:dark}html[data-theme=light]{--orca-accent:#00897b;color-scheme:light}
body[data-mode]{background:var(--bg-app);color:var(--text-main);font-family:var(--font-sans)}
body h1,body h2,body h3,body label,body input,body select{color:var(--text-main)}
body select{appearance:none;-webkit-appearance:none;background-color:var(--bg-input)!important;color:var(--text-main)!important;padding-right:22px;background-image:linear-gradient(45deg,transparent 50%,var(--text-muted) 50%),linear-gradient(135deg,var(--text-muted) 50%,transparent 50%);background-position:calc(100% - 12px) 50%,calc(100% - 8px) 50%;background-size:4px 4px;background-repeat:no-repeat}
body button{color:var(--text-main);background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:var(--radius-sm);padding:7px 10px}
.panel-help{margin:8px 0;color:var(--text-muted);font-size:11px}.panel-help summary{font-size:11px}
body.compact header:has(#panel-action:not([hidden])){height:auto;min-height:46px;flex-wrap:wrap;padding-top:5px;padding-bottom:5px}
.study-modes{display:grid;grid-template-columns:1fr 1fr}.study-modes button{min-width:0;font-size:12px}.surface-mode .wave-only,.surface-mode #suggest,.surface-mode #analyze,.surface-mode #prepare-capture,.combined-mode #suggest{display:none!important}.surface-info{color:var(--text-muted);font-size:12px;margin:10px 0}.surface-mode .object:has(input:checked){background:var(--bg-input);border-color:var(--border-subtle)}.surface-mode .object:has(.pick-object[aria-pressed=true]){background:var(--bg-input);border-color:var(--border-subtle)}
</style></head>
<body data-mode="__LAYOUT__">
<header><div class="brand"><svg class="brandmark" viewBox="0 0 64 64" aria-hidden="true"><g stroke="currentColor" fill="none" stroke-width="4" stroke-linecap="round"><path id="brandwave" d="M5 25c10 0 11-16 20-16s10 18 18 18 9-14 16-14"/><use href="#brandwave" y="12"/><use href="#brandwave" y="24"/></g></svg><h1>Orca <b>Surface</b> <span>Studio</span></h1></div><div class="row"><i id="link-dot" class="dot"></i><span id="connection" class="connection"></span><button id="theme" class="iconbtn" aria-label="Alternar tema" title="Alternar tema" data-icon="sun"></button></div></header>
<nav class="docktabs" aria-label="Painel do Studio"><button id="tab-config" aria-selected="true">Configuração</button><button id="tab-review" aria-selected="false">Diagnóstico e saída</button></nav>
<main class="work"><aside class="side left shown" id="config"><div class="scroll">
<section class="section"><div class="sectionhead"><h3><i data-icon="box"></i> Objetos da mesa</h3><button class="iconbtn outline" id="refresh" aria-label="Atualizar mesa" title="Atualizar mesa" data-icon="refresh"></button></div><div id="objects" class="objects"></div><button id="analyze" class="wide"><i data-icon="scan"></i>Analisar seleção</button></section>
<section class="section"><div class="sectionhead"><h3><i data-icon="wave"></i> Parâmetros da trajetória</h3><span class="badge">mm</span></div><fieldset class="fieldset" id="params"><div class="segments study-modes" aria-label="Tipo de trajetória"><button id="mode-xy" aria-pressed="false">Onda XY</button><button id="mode-z" aria-pressed="true">Onda Z</button><button id="mode-surface" aria-pressed="false">Superfície curva</button></div><div id="primary-fields"></div><div class="field twocol wave-only"><label>Início em Z (mm)<input id="start_height_mm" type="number" min="0" step="any"></label><label>Fim em Z (mm)<input id="end_height_mm" type="number" min="0" step="any" placeholder="Até o topo"></label></div><details class="field wave-only"><summary>Ajustes avançados</summary><div id="advanced-fields"></div></details></fieldset><p id="validation" class="message" aria-live="polite" hidden></p><button class="wide outline" id="suggest"><i data-icon="sliders"></i> Aplicar sugestão do objeto</button></section>
<section class="section wave-only"><div class="sectionhead"><h3><i data-icon="library"></i> Presets</h3></div><label class="smallcap" for="presets">Perfil da onda</label><select id="presets" class="presets"></select><div class="presetops"><button id="save"><i data-icon="plus"></i> Salvar</button><button id="delete"><i data-icon="trash"></i> Excluir</button></div><form id="preset-editor" class="preset-editor" hidden><label for="preset-name">Nome do preset</label><input id="preset-name" maxlength="64" required><div class="row"><button type="submit">Confirmar</button><button type="button" id="cancel-preset">Cancelar</button></div></form></section>
</div></aside>
<section class="viewport" aria-label="Trajetória tridimensional"><div class="vhead"><h2>Trajetória 3D</h2><div class="segments viewtabs" aria-label="Visualização"><button data-view="original">Original</button><button data-view="deformed" aria-pressed="true">Com ondas</button><button data-view="compare">Comparar</button></div></div>
<div class="stage"><canvas id="canvas" tabindex="0" aria-label="Trajetória em três dimensões. Arraste para girar ou use as setas. Use mais e menos para aproximar e afastar."></canvas><div class="stageinfo"><span class="smallcap">Vista ortográfica</span><strong id="point-label"></strong></div><div class="vbuttons"><button data-icon="fit" id="fit" class="iconbtn" aria-label="Enquadrar trajetória" title="Enquadrar trajetória"></button><button data-icon="plus" id="zoom-in" class="iconbtn" aria-label="Aproximar" title="Aproximar"></button><button data-icon="minus" id="zoom-out" class="iconbtn" aria-label="Afastar" title="Afastar"></button></div><div class="empty" id="empty"><p id="empty-msg"></p></div><div class="legend" aria-hidden="true"><span id="legend-original"><i class="swatch original"></i><span id="legend-original-label">Original</span></span><span id="legend-modified"><i class="swatch modified"></i><span id="legend-modified-label">Com ondas</span></span></div></div>
<div class="transport"><div class="row"><button id="play" class="iconbtn" aria-label="Reproduzir percurso" title="Reproduzir percurso" data-icon="play"></button><input class="track" id="scrub" type="range" min="0" max="0" value="0" step="1" aria-label="Posição do bico no percurso"><output id="pct">—</output></div><div class="readout"><span>Bico (mm)</span><output class="xyz" id="xyz">X —   Y —   Z —</output></div><div class="layerrow"><label><span id="layer-label">Camada</span> <select id="layer"></select></label><small>Arraste para orbitar · role para zoom</small></div></div></section>
<aside class="side right" id="review"><div class="scroll">
<section class="section"><div class="sectionhead"><h3><i data-icon="pulse"></i> Diagnóstico</h3></div><div class="state" id="status"><i class="dot"></i><span id="status-name"></span></div><p id="message" class="message" aria-live="polite"></p><dl id="metadata" class="data"></dl></section>
<section class="section wave-only"><div class="sectionhead"><h3><i data-icon="curve"></i> Perfil analítico</h3></div><svg class="chart" viewBox="0 0 240 66" preserveAspectRatio="none" role="img" aria-label="Forma senoidal teórica nos primeiros vinte milímetros"><path class="axis" d="M0 33H240 M60 0v66 M120 0v66 M180 0v66"/><path class="wave" id="analytic-path"/></svg><div class="row spread"><small>0 mm</small><small>20 mm</small></div><dl class="data"><div><dt>Curvatura máx. estimada</dt><dd id="curvature">—</dd></div></dl></section>
<section class="section"><div class="sectionhead"><h3><i data-icon="layers"></i> Resultado</h3></div><p id="result-note" class="message"></p><dl class="data" id="metrics"></dl><span class="path" id="result-path"></span></section></div>
<footer class="foot"><div id="action-note" class="notice" hidden></div><button class="wide positive" id="generate"><i data-icon="wave"></i> Gerar G-code com ondas</button><button class="wide" id="preview"><i data-icon="open"></i> Abrir Preview no Orca</button><small id="bench-note">Estudo de bancada · impressão pelo OrcaSlicer</small></footer></aside></main>
<script id="initial-state" type="application/json">__STATE__</script>
<script>
'use strict';
const $ = id => document.getElementById(id);
const icons = {
  sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
  box:'<path d="M3 7l9-5 9 5v10l-9 5-9-5zM3 7l9 5 9-5m-9 5v10"/>',
  refresh:'<path d="M3 10a9 9 0 0115-5l3 3m0-5v5h-5M21 14a9 9 0 01-15 5l-3-3m0 5v-5h5"/>',
  scan:'<path d="M8 3H3v5m13-5h5v5M3 16v5h5m8 0h5v-5M5 12h14"/>',
  wave:'<path d="M2 12c4 0 3-7 7-7s3 14 7 14 3-7 6-7"/>',
  sliders:'<path d="M3 6h4m4 0h10M3 12h11m4 0h3M3 18h3m4 0h11M8 4v4m7 2v4m-8 2v4"/>',
  library:'<path d="M3 4h4v16H3zM10 4h4v16h-4zM16 5l3-1 4 15-3 1z"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',minus:'<path d="M5 12h14"/>',
  trash:'<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15m-8 4v7m4-7v7"/>',
  fit:'<path d="M8 3H3v5m13-5h5v5M3 16v5h5m8 0h5v-5"/><circle cx="12" cy="12" r="3"/>',
  play:'<path d="M7 4l13 8-13 8z"/>',pause:'<path d="M8 5v14m8-14v14"/>',
  pulse:'<path d="M2 12h5l3-8 4 16 3-8h5"/>',curve:'<path d="M3 3v17h18M5 16c5 0 4-11 10-11h4"/>',
  layers:'<path d="M2 8l10-5 10 5-10 5zM3 12l9 5 9-5m-18 4l9 5 9-5"/>',
  open:'<path d="M13 3h8v8m0-8L10 14M9 5H4v15h15v-5"/>'
};
function icon(name){return '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true">'+icons[name]+'</svg>'}
document.querySelectorAll('[data-icon]').forEach(e=>{e.innerHTML=icon(e.dataset.icon)});
const sineMode=node('button','','Vaso senoidal');sineMode.id='mode-combined';sineMode.setAttribute('aria-pressed','true');$('mode-xy').before(sineMode);
$('mode-z').setAttribute('aria-pressed','false');
const defaults = {mode:'combined',amplitude_mm:1,wave_count:6,z_ratio:.5,wavelength_mm:10,step_mm:.4,min_segment_mm:.15,
  tolerance_mm:.02,start_height_mm:1,end_height_mm:null,fade_layers:3,phase_deg:0,
  twist_deg_per_mm:0,corner_threshold_deg:45,max_z_speed_mm_s:5,max_z_acceleration_mm_s2:50,bench_only:true};
const builtins=(__PRESET_DATA__).map(p=>({...p,parameters:normalized(p.parameters)}));
const personalPresets=()=>(state.presets||[]).filter(p=>!builtins.some(b=>b.id===String(p.id)));
function activeBridge(){return [window.orca,window.chrome?.webview,window.webkit?.messageHandlers?.orca].find(b=>typeof b?.postMessage==='function')}
let linked=Boolean(activeBridge());
let state={},parameters={...defaults},selection=new Set(),presetId='sine-vase',pending=null;
let activeId=null,baseParameters={...defaults};
const objectParameters=new Map(),objectPresets=new Map();
let surfaceMode=false;
const surfaceByObject=new Map();
const surfaceSettings=()=>{
  const value={step_mm:.4,max_slope_deg:30,retain_native_short_edges:true,backend:'native_local',region_id:null,
    selection_mode:'paint',selection_revision:null,wall_selection:[],...surfaceByObject.get(activeId)};
  if(value.backend!=='native_local')for(const key of ['selection_mode','selection_revision','wall_selection'])delete value[key];
  return value;
};
const wallMarks=new Map();let brushRadius=6;
function surfaceError(){
  const {step_mm,max_slope_deg,backend,selection_mode,wall_selection,selection_revision}=surfaceSettings();
  if(!Number.isFinite(step_mm)||step_mm<.15||step_mm>2)return 'Use um passo entre 0,15 e 2 mm.';
  if(!Number.isFinite(max_slope_deg)||max_slope_deg<5||max_slope_deg>45)return 'Use uma inclinação entre 5° e 45°.';
  if(backend==='native_local'&&selection_mode==='paint'){
    if(selection_revision&&selection_revision!==state.revision)return 'A peça ou o perfil mudou. Limpe e selecione as áreas novamente.';
    if(!wall_selection?.length)return 'Clique na peça para escolher as áreas a suavizar. Arraste para girar.';
  }
  return '';
}
let generation=null,resultIdentity='',resultConfig='',pollTimer=0,hostSequence=-1,receivedHostState=false;
let stateStamp='',lastPoll=0;
let view='deformed',sceneTag='',playing=false,frame=0,previousTime=0,progressCarry=0;
const opened=new Set();
const numberFormat=(v,n=2)=>Number.isFinite(v)?v.toLocaleString('pt-BR',{maximumFractionDigits:n}):'—';
const effective=id=>objectParameters.get(id)||baseParameters;
const selectedParameters=()=>Object.fromEntries([...selection].map(id=>[id,{...effective(id)}]));
// Native JSON bridges may reorder dictionary keys, including nested click rays.
// Arrays retain their order: changing a ray or its coordinates still invalidates.
const stableJSON=value=>JSON.stringify(value,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)
  ?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
const signature=()=>surfaceMode
  ?stableJSON(['surface',state.revision||'',activeId,surfaceSettings()])
  :JSON.stringify(['wave',state.revision||'',state.capture?.sha256||'',
    [...selection].sort().map(id=>[id,...Object.keys(defaults).map(k=>effective(id)[k])])]);
function normalized(p){
  return {...defaults,...Object.fromEntries(Object.keys(defaults).filter(k=>p?.[k]!==undefined).map(k=>[k,p[k]])),bench_only:true};
}
function storeActive(){
  if(activeId!==null){objectParameters.set(activeId,{...parameters});objectPresets.set(activeId,presetId)}
}
function activate(id){
  activeId=id;parameters={...effective(id)};presetId=objectPresets.get(id)??(
    builtins.find(p=>Object.keys(defaults).every(k=>p.parameters[k]===parameters[k]))?.id||'');
  syncParams();
}
function node(tag,cls,content){
  const el=document.createElement(tag);
  if(cls)el.className=cls;
  if(content!==undefined)el.textContent=content;
  return el;
}
const docked=document.body.dataset.mode==='dock';
const panelAction=node('button','outline',docked?'Ocultar painel':'Abrir painel');
panelAction.id='panel-action';panelAction.hidden=true;$('theme').before(panelAction);
panelAction.onclick=()=>send(docked?'hide_panel':'open_panel');
const panelHelp=node('details','panel-help');panelHelp.hidden=true;
panelHelp.append(node('summary','','Como ocultar a aba do Studio'),
  node('p','','No gerenciador de plugins, expanda Orca Wave Studio e desmarque a página “Estúdio de Ondas Senoidais”. Mantenha a ação “Orca Wave Studio • Painel” habilitada para reabrir pelo ícone.'));
$('preview').after(panelHelp);
function send(action,extra={}){
  if(!linked)return false;
  try{const bridge=activeBridge(),obj=['surface_study','prepare_conformal','build_surface'].includes(action)
    ?{action,object_ids:[activeId],settings:action!=='surface_study'?{...surfaceSettings()}:
      {step_mm:surfaceSettings().step_mm,max_slope_deg:surfaceSettings().max_slope_deg}}
    :(action==='generate_conformal'?{action,object_ids:[activeId]}:
      {action,object_ids:[...selection],parameters:{...parameters},...extra});
    if(action==='generate'){
      obj.parameters_by_object=selectedParameters();
      obj.parameters={...effective(selection.has(activeId)?activeId:[...selection][0])};
    }
    bridge.postMessage(bridge===window.orca?obj:JSON.stringify(obj));return true}
  catch(e){notice('Falha de comunicação com o OrcaSlicer. '+e.message);return false}
}
function notice(message){$('action-note').hidden=!message;$('action-note').textContent=message}
function record(list,label,value,title=''){
  const row=node('div'),term=node('dt','',label),val=node('dd','',value);
  if(title)val.title=title;
  row.append(term,val);list.append(row);
}
function controlsBusy(){return Boolean(pending)||['processing','analyzing'].includes(state.status)}
function canCapture(){
  return Boolean(state.capture?.sha256)&&(!state.capture.revision||state.capture.revision===state.revision)
    &&!['error','slicing_required','processing','analyzing'].includes(state.status);
}
function presentResult(){
  const result=state.result,source=result?.report?.source_sha256;
  return Boolean(result?.sha256)&&state.status==='ready'&&!pending&&
    surfaceMode===(['surface','conformal'].includes(result.study_kind))&&
    (!result.revision||result.revision===state.revision)&&
    (result.workflow==='integrated'||result.study_kind==='surface'||!source||source===state.capture?.sha256)&&resultConfig===signature();
}
function valid(p=parameters){
  if(!Object.entries(p).every(([k,v])=>k==='mode'||k==='bench_only'||(k==='end_height_mm'&&v===null)||Number.isFinite(v)))return 'Preencha todos os valores numéricos.';
  if(!['xy','z','combined'].includes(p.mode)||p.amplitude_mm<0||p.wavelength_mm<1||p.wavelength_mm>50||
    p.min_segment_mm<.15||p.step_mm>2||p.tolerance_mm<=0||p.tolerance_mm>.02||p.start_height_mm<0||
    p.fade_layers<1||p.max_z_speed_mm_s<=0||p.max_z_acceleration_mm_s2<=0||
    p.corner_threshold_deg<0||p.corner_threshold_deg>180)return 'Confira os limites indicados nos campos numéricos.';
  if(p.min_segment_mm>p.step_mm)return 'O passo precisa ser maior ou igual ao segmento mínimo.';
  if(p.end_height_mm!==null&&p.end_height_mm<=p.start_height_mm)return 'O fim em Z deve ficar acima da altura inicial.';
  if(!Number.isInteger(p.fade_layers))return 'A transição precisa usar um número inteiro de camadas.';
  if(!Number.isInteger(p.wave_count)||p.wave_count<1||p.wave_count>24||p.z_ratio<=0||p.z_ratio>1)return 'Use de 1 a 24 ondas por volta e proporção Z de até 1.';
  return '';
}
function optionList(){return [...builtins,...personalPresets()]}
function addPresets(){
  const list=$('presets');list.replaceChildren(new Option('Personalizado',''));
  const group=(name,items)=>{if(!items.length)return;const el=node('optgroup');el.label=name;
    items.forEach(p=>el.append(new Option(p.name,String(p.id))));list.append(el)};
  group('Perfis de bancada',builtins);
  group('Meus presets',optionList().slice(builtins.length));
  if(!optionList().some(p=>String(p.id)===presetId))presetId='';
  list.value=presetId;
}
function loadParams(p,id=''){
  parameters=normalized(p);
  if(['z','combined'].includes(parameters.mode))parameters.twist_deg_per_mm=0;
  presetId=id;storeActive();syncParams();render();
}
function syncParams(){
  for(const [k,v] of Object.entries(parameters)){
    if($(k))$(k).value=v===null?'':String(v);
    if($('r-'+k))$('r-'+k).value=v===null?'':String(v);
  }
  $('presets').value=presetId;
  ['xy','z','combined'].forEach(m=>$('mode-'+m).setAttribute('aria-pressed',String(!surfaceMode&&parameters.mode===m)));
  $('mode-surface').setAttribute('aria-pressed',String(surfaceMode));
  if(surfaceMode)for(const [key,value] of Object.entries(surfaceSettings())){
    if(!$(key))continue;
    if($(key).type==='checkbox')$(key).checked=Boolean(value);
    else $(key).value=value??'';
    if($('r-'+key))$('r-'+key).value=value??'';
  }
  $('twist_deg_per_mm').disabled=['z','combined'].includes(parameters.mode);
}
function onParameter(k,input){
  if(surfaceMode&&(k==='step_mm'||k==='max_slope_deg')){
    surfaceByObject.set(activeId,{...surfaceSettings(),[k]:input.valueAsNumber});
    if(input.id!==k)$(k).value=input.value;
    else if($('r-'+k)&&Number.isFinite(input.valueAsNumber))$('r-'+k).value=input.value;
    render();return;
  }
  parameters[k]=input.value===''&&k==='end_height_mm'?null:input.valueAsNumber;
  if($('r-'+k)&&Number.isFinite(parameters[k]))$('r-'+k).value=parameters[k];
  if(input.id!==k)$(k).value=input.value;
  presetId='';storeActive();$('presets').value='';render();
}
function field(parent,k,label,unit,min,max,step,slider=false){
  const box=node('div','field'),top=node('div','fieldtop'),name=node('label','',label),value=node('div','row');
  name.htmlFor=k;const input=node('input');input.type='number';input.id=k;
  if(min!=null)input.min=min;if(max!=null)input.max=max;
  input.step=slider?'any':step;input.required=true;input.oninput=()=>onParameter(k,input);
  value.append(input,node('span','unit',unit));top.append(name,value);box.append(top);
  if(slider){const range=node('input');range.type='range';range.id='r-'+k;range.min=min;range.max=max??1;
    range.step=step;range.setAttribute('aria-label',label);range.oninput=()=>onParameter(k,range);box.append(range)}
  parent.append(box);
}
const primary=$('primary-fields'),advanced=$('advanced-fields');
const editTarget=node('span','edit-target');editTarget.id='edit-target';$('params').before(editTarget);
field(primary,'amplitude_mm','Amplitude','mm',0,null,.01,true);
field(primary,'wave_count','Ondas por volta','',1,24,1,true);
field(primary,'wavelength_mm','Comprimento de onda','mm',1,50,.1,true);
field(primary,'step_mm','Passo de amostragem','mm',.15,2,.01,true);
field(primary,'max_slope_deg','Limite do estudo digital','°',5,45,1,true);
const roofBox=node('div','field'),roofLabel=node('label','','Topo de referência'),roofSelect=node('select');
roofSelect.id='roof-region';roofLabel.htmlFor=roofSelect.id;
const roofMap=document.createElementNS('http://www.w3.org/2000/svg','svg');
roofMap.id='roof-map';roofMap.setAttribute('role','group');roofMap.setAttribute('aria-label','Regiões da peça vistas de cima');
roofMap.style.cssText='width:100%;height:140px;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:6px';
const roofNote=node('small');roofNote.id='roof-region-note';
roofBox.append(roofLabel,roofSelect,roofMap,roofNote);primary.append(roofBox);
roofSelect.onchange=()=>{surfaceByObject.set(activeId,{...surfaceSettings(),region_id:roofSelect.value||null});render()};
let roofMapTag='';
function roofRegions(active,disabled){
  roofBox.hidden=!surfaceMode;roofSelect.disabled=disabled;
  const rejection=state.surface_rejection?.object_id===activeId?state.surface_rejection:null;
  const catalog=state.conformal?.region_catalog||rejection?.region_catalog||active?.roof_regions,rows=catalog?.regions||[];
  const chosen=surfaceSettings().region_id||catalog?.automatic_region_id||'';
  const tag=JSON.stringify([catalog?.revision,activeId,chosen,disabled,Boolean(rejection)]);if(tag===roofMapTag)return;roofMapTag=tag;
  roofSelect.replaceChildren(new Option('Escolha automática',''));
  for(const row of rows)roofSelect.append(new Option(row.label,row.id));
  roofSelect.value=surfaceSettings().region_id||'';roofMap.replaceChildren();
  roofMap.hidden=!rows.length;
  const candidate=rows.find(r=>r.id===chosen);
  roofNote.textContent=catalog?.reason||('Topo, borda e face inferior serão avaliados juntos. '+
    (candidate?'Inclinação medida: '+numberFormat(candidate.slope_deg)+'°. ':'')+'Capacidade do cabeçote: não verificada.');
  const points=rows.flatMap(r=>r.map_triangles_xy?.flat()||[]);if(!points.length)return;
  const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),xmin=Math.min(...xs),ymin=Math.min(...ys);
  const w=Math.max(...xs)-xmin||1,h=Math.max(...ys)-ymin||1;
  roofMap.setAttribute('viewBox',[xmin-1,ymin-1,w+2,h+2].join(' '));
  for(const row of [...rows].sort((a,b)=>a.z_max_mm-b.z_max_mm)){
    const path=document.createElementNS(roofMap.namespaceURI,'path');
    path.setAttribute('d',(row.map_triangles_xy||[]).map(t=>'M'+t.map(p=>p.join(',')).join('L')+'Z').join(''));
    path.setAttribute('fill',row.id===chosen?(rejection?'#d54a4a':'#00a896'):'#496176');path.setAttribute('stroke','#c9d6e2');
    path.setAttribute('stroke-width',String(Math.max(w,h)/400));path.setAttribute('aria-label',row.label);
    path.setAttribute('role','button');path.setAttribute('tabindex',disabled?'-1':'0');
    const choose=()=>{if(disabled)return;surfaceByObject.set(activeId,{...surfaceSettings(),region_id:row.id});render()};
    path.onclick=choose;path.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();choose()}};
    const title=document.createElementNS(roofMap.namespaceURI,'title');title.textContent=row.label;path.append(title);roofMap.append(path);
  }
}
const nativeCornersBox=node('div','field'),nativeCornersLabel=node('label','row'),nativeCorners=node('input');
nativeCorners.id='retain_native_short_edges';nativeCorners.type='checkbox';
nativeCornersLabel.append(nativeCorners,node('span','','Preservar pequenas quinas'));
nativeCornersBox.append(nativeCornersLabel,node('small','','Mantém os movimentos curtos criados pelo Orca. Somente Preview.'));
primary.append(nativeCornersBox);
nativeCorners.onchange=()=>{surfaceByObject.set(activeId,{...surfaceSettings(),retain_native_short_edges:nativeCorners.checked});render()};
for(const k of ['amplitude_mm','wavelength_mm'])$(k).closest('.field').classList.add('wave-only');
const surfaceInfo=node('p','surface-info','O estudo segue a superfície superior da peça. Regiões acima da inclinação máxima ficam fora do percurso.');
primary.before(surfaceInfo);
const wallBox=node('div','field');wallBox.id='wall-selection';
wallBox.append(node('h3','','Paredes a suavizar'));
const wallModes=node('div','segments'),wallPaint=node('button','','Escolher na peça'),wallAll=node('button','','Todas compatíveis');
wallPaint.id='wall-paint';wallAll.id='wall-all';wallModes.append(wallPaint,wallAll);wallBox.append(wallModes);
const brushRow=node('label','fieldtop','Raio da área'),brushInput=node('input');
brushInput.type='number';brushInput.min='1';brushInput.max='15';brushInput.step='1';brushInput.value='6';brushInput.id='wall-radius';
brushRow.htmlFor=brushInput.id;brushRow.append(brushInput,node('span','unit','mm'));wallBox.append(brushRow);
brushInput.oninput=()=>{if(Number.isFinite(brushInput.valueAsNumber)&&brushInput.valueAsNumber>=1&&brushInput.valueAsNumber<=15)brushRadius=brushInput.valueAsNumber};
brushInput.onchange=()=>{if(!brushInput.checkValidity()||!Number.isFinite(brushInput.valueAsNumber)){brushInput.value=String(brushRadius);notice('Use um raio entre 1 e 15 mm. O último valor válido foi mantido.')}};
const wallHint=node('small','','Clique para acrescentar áreas; arraste para girar. A área inclui a espessura e pode alcançar paredes próximas. Velocidade nas áreas: 80% do perfil.'),wallList=node('div');
wallList.id='wall-areas';wallList.setAttribute('aria-live','polite');
const wallClear=node('button','outline','Limpar seleção');wallClear.id='wall-clear';
wallBox.append(wallHint,wallList,wallClear);primary.append(wallBox);
wallPaint.onclick=()=>{surfaceByObject.set(activeId,{...surfaceSettings(),selection_mode:'paint'});render()};
wallAll.onclick=()=>{surfaceByObject.set(activeId,{...surfaceSettings(),selection_mode:'all',wall_selection:[],selection_revision:null});wallMarks.delete(activeId);render()};
wallClear.onclick=()=>{surfaceByObject.set(activeId,{...surfaceSettings(),wall_selection:[],selection_revision:null});wallMarks.delete(activeId);render()};
function pickWall(ray,point){
  const settings=surfaceSettings();if(controlsBusy()||!surfaceMode||settings.backend!=='native_local'||settings.selection_mode!=='paint')return;
  if(settings.wall_selection.length>=24){notice('Use até 24 áreas. Remova uma área para acrescentar outra.');return}
  if(!brushInput.checkValidity()||!Number.isFinite(brushInput.valueAsNumber)){notice('Confira o raio da área antes de selecionar.');return}
  if(settings.selection_revision&&settings.selection_revision!==state.revision){notice('Limpe a seleção anterior antes de escolher novas áreas.');return}
  const marks=[...(wallMarks.get(activeId)||[]).slice(0,settings.wall_selection.length),{center:point,radius_mm:brushRadius}];wallMarks.set(activeId,marks);
  surfaceByObject.set(activeId,{...settings,selection_revision:state.revision,
    wall_selection:[...settings.wall_selection,{...ray,radius_mm:brushRadius}]});notice('');render();
}
field(advanced,'min_segment_mm','Segmento mínimo','mm',.15,2,'any');
field(advanced,'tolerance_mm','Tolerância','mm',.000001,.02,'any');
field(advanced,'fade_layers','Transição','cam.',1,null,1);
field(advanced,'phase_deg','Fase inicial','°',null,null,'any');
field(advanced,'z_ratio','Altura da onda / intensidade','',.01,1,.01,true);
field(advanced,'twist_deg_per_mm','Torção em XY','°/mm',null,null,'any');
field(advanced,'corner_threshold_deg','Ângulo de canto','°',0,180,'any');
field(advanced,'max_z_speed_mm_s','Velocidade máx. Z','mm/s',.000001,null,'any');
field(advanced,'max_z_acceleration_mm_s2','Aceleração máx. Z','mm/s²',.000001,null,'any');
['start_height_mm','end_height_mm'].forEach(k=>$(k).oninput=e=>onParameter(k,e.target));
['xy','z','combined'].forEach(m=>$('mode-'+m).onclick=()=>{
  surfaceMode=false;
  loadParams(m==='combined'?{...parameters,mode:m,amplitude_mm:1,wave_count:6,z_ratio:.5,end_height_mm:null}:({...parameters,mode:m}));
});
$('mode-surface').onclick=()=>{surfaceMode=true;syncParams();render()};
function analytic(){
  const combined=!surfaceMode&&parameters.mode==='combined';
  const {amplitude_mm:a,phase_deg:phase}=parameters,w=combined?20/parameters.wave_count:parameters.wavelength_mm;
  const curve=Number.isFinite(a)&&Number.isFinite(w)&&w>=1&&a>=0&&Number.isFinite(phase);
  const points=[];
  if(curve)for(let i=0;i<=360;i++){const x=i*240/360,y=33-Math.min(26,26*a/.3)*Math.sin(2*Math.PI*(20*i/360)/w+phase*Math.PI/180);
    points.push((i?'L':'M')+x.toFixed(2)+' '+y.toFixed(2))}
  $('analytic-path').setAttribute('d',points.join(''));
  const captions=$('analytic-path').closest('section').querySelectorAll('.row small');
  if(captions.length===2){captions[0].textContent=combined?'0°':'0 mm';captions[1].textContent=combined?'360° · uma volta':'20 mm'}
  $('analytic-path').closest('svg').setAttribute('aria-label',combined?'Ondulação radial teórica ao longo de uma volta':'Forma senoidal teórica nos primeiros vinte milímetros');
  $('curvature').textContent=combined?'Calculada no percurso gerado':(curve?numberFormat(a*(2*Math.PI/w)**2,4)+' mm⁻¹':'—');
}
function objects(){
  const list=$('objects');list.replaceChildren();
  if(!state.objects?.length){list.append(node('p','message','Nenhum objeto disponível nesta mesa.'));return}
  for(const obj of state.objects){
    const item=node('div','object'),input=node('input'),info=node('button','pick-object');input.type='checkbox';
    const id=String(obj.id);input.checked=selection.has(id);input.disabled=controlsBusy();input.hidden=surfaceMode;
    input.setAttribute('aria-label','Incluir '+(obj.name||id)+' na geração');
    info.disabled=controlsBusy();info.setAttribute('aria-pressed',String(id===activeId));
    info.title='Editar parâmetros de '+(obj.name||id);info.onclick=()=>{activate(id);render()};
    input.onchange=()=>{input.checked?selection.add(id):selection.delete(id);render()};
    const dims=obj.dimensions_mm||(obj.bounds?.length===2?obj.bounds[1].map((v,i)=>v-obj.bounds[0][i]):[]);
    info.append(node('strong','',obj.name||'Objeto'),node('small','','ID '+id+' · '+(obj.instances??'—')+' cópia(s)'));
    if(dims.length===3)info.append(node('small','',dims.map(n=>numberFormat(n,1)).join(' × ')+' mm'));
    item.append(input,info);list.append(item);
  }
}
const statuses={idle:'Aguardando análise',analyzing:'Analisando mesa',slicing_required:'Fatiamento necessário',
  processing:'Processando trajetória',ready:'Pronto',error:'Ação necessária'};
function diagnostics(current){
  const s=['generate','surface_study'].includes(pending)?'processing':(pending==='analyze'?'analyzing':state.status||'idle');
  $('status').className='state '+s;$('status-name').textContent=statuses[s]||s;
  if(surfaceMode&&s==='ready')$('status-name').textContent='Pronto para Preview';
  if(current&&state.result?.report?.regional_audit?.digital_approval===false){
    $('status').className='state slicing_required';$('status-name').textContent='Estudo incompleto';
  }
  $('message').textContent=pending?'Aguardando o OrcaSlicer…':state.message||'Atualize a mesa para listar os objetos disponíveis.';
  if(surfaceMode&&!state.conformal&&!pending&&['idle','slicing_required'].includes(s)){
    $('status-name').textContent='Estudo da malha';
    $('message').textContent='Escolha a peça pelo nome e estude a superfície diretamente da geometria da mesa.';
  }
  if(!surfaceMode&&parameters.mode==='combined'&&!pending&&!canCapture()&&['idle','slicing_required'].includes(s)){
    $('message').textContent='1. Preparar vaso no Orca. 2. Fatiar a placa. 3. Gerar e abrir Preview. A intensidade cresce suavemente até o topo; a base fica preservada.';
  }
  const meta=$('metadata');meta.replaceChildren();
  if(surfaceMode)record(meta,'Objeto em estudo',activeId||'—');else record(meta,'Objetos selecionados',String(selection.size));
  record(meta,'Revisão da mesa',state.revision?.slice(0,10)||'—',state.revision);
  if(!surfaceMode)record(meta,'Captura do fatiamento',state.capture?.sha256?.slice(0,10)||'—',state.capture?.sha256);
  const metrics=$('metrics');metrics.replaceChildren();$('result-path').textContent='';
  if(!current){
    $('result-note').textContent=surfaceMode?'Execute o estudo para visualizar os percursos sobre a peça.':
      (state.result?'O resultado anterior está desatualizado. Gere a trajetória para esta configuração.':'Aguardando uma trajetória processada.');
    return;
  }
  const r=state.result,rep=r.report||{};
  $('result-note').textContent=r.workflow==='integrated'?'Prévia gerada com o perfil selecionado. Conferência física do cabeçote e da deposição pendente.':r.study_kind==='conformal'?'Trajetória reconstruída a partir da cópia fatiada no Orca. Impressão indisponível.':surfaceMode?'Percurso da superfície no Studio. Deposição e impressão ainda não validadas.':
    (state.demo?'Trajetória do exemplo de bancada.':'Trajetória processada para a seleção atual.');
  record(metrics,'SHA-256',r.sha256.slice(0,12),r.sha256);
  if(surfaceMode&&r.settings?.backend==='native_local'){
    record(metrics,'Método','Contorno local do Orca');record(metrics,'Regiões','Superfícies superiores compatíveis');
    if(rep.wall_selection?.mode==='paint'){
      record(metrics,'Áreas escolhidas',rep.wall_selection.areas.length);
      record(metrics,'Velocidade nas áreas','80% do perfil');
      const angle=rep.wall_selection_audit?.maximum_motion_slope_deg;
      if(Number.isFinite(angle))record(metrics,'Maior inclinação do percurso',numberFormat(angle,1)+'°');
      if(angle>r.settings.max_slope_deg)$('result-note').textContent='Somente Preview: há movimentos mais inclinados que o limite do estudo. O arquivo não está liberado para imprimir.';
    }
    record(metrics,'Folga do cabeçote','Pendente');
    record(metrics,'Trechos com Z variável',Object.values(rep.nonplanar_extrusion_segments_by_role||{}).reduce((a,b)=>a+b,0));
  }
  if(surfaceMode&&r.settings?.backend!=='native_local'){record(metrics,'Passo do estudo',numberFormat(surfaceSettings().step_mm)+' mm');
    record(metrics,'Limite digital escolhido',numberFormat(surfaceSettings().max_slope_deg)+'°');
    record(metrics,'Folga do cabeçote','Não verificada');
    if(rep.regional_audit){
      record(metrics,'Aprovação conjunta','Incompleta · impressão bloqueada');
      for(const [face,label] of [['top','Topo'],['underside','Face inferior']]){
        const audit=rep.regional_audit.faces?.[face];
        if(audit)record(metrics,label+' · erro amostrado',numberFormat(audit.sampled_max_normal_error_mm,4)+' mm',audit.reason);
      }
      record(metrics,'Borda','Sem certificado de acabamento');
      record(metrics,'Suportes',rep.regional_audit.support?.status==='FAIL_ESTIMATE_INTERSECTION'?
        'Interseção estimada':'Folga ainda não comprovada');
    }
    if(Number.isFinite(rep.max_surface_slope_deg))record(metrics,'Inclinação máx. medida',numberFormat(rep.max_surface_slope_deg,2)+'°');
    if(Number.isFinite(rep.projected_coverage_fraction))
      record(metrics,'Cobertura projetada (est.)',numberFormat(100*rep.projected_coverage_fraction,2)+'%',
        'Fração estimada da área visível em projeção XY incluída no percurso.');
    if(Array.isArray(rep.trace_z_range_mm)&&rep.trace_z_range_mm.length===2)
      record(metrics,'Faixa de Z',rep.trace_z_range_mm.map(z=>numberFormat(z,4)).join(' – ')+' mm');
    if(Number.isFinite(rep.path_length_mm))record(metrics,'Comprimento do percurso',numberFormat(rep.path_length_mm,2)+' mm');
    if(Number.isFinite(rep.strokes))record(metrics,'Trechos independentes',numberFormat(rep.strokes));
    if(Number.isFinite(rep.segments))record(metrics,'Segmentos',numberFormat(rep.segments));
    if(rep.total_e_delta===0)record(metrics,'Extrusão comandada','0 mm');
  }
  if(Array.isArray(r.deformed_points))record(metrics,'Pontos na visualização',numberFormat(r.deformed_points.length));
  if(Array.isArray(r.layer_ids)&&!surfaceMode)record(metrics,'Camadas na visualização',numberFormat(new Set(r.layer_ids).size));
  const metricsMap={segment_count:'Segmentos gerados',max_geometric_error_mm:'Erro geométrico máx. (mm)',min_segment_mm:'Segmento mínimo (mm)',max_z_speed_mm_s:'Velocidade Z máx. estim. (mm/s)',max_z_acceleration_mm_s2:'Aceleração Z máx. estim. (mm/s²)',original_deposition_e_mm:'Filamento original (mm)',processed_deposition_e_mm:'Filamento processado (mm)'};
  for(const [key,label] of Object.entries(metricsMap)){if(Number.isFinite(rep[key]))record(metrics,label,numberFormat(rep[key],4))}
  if(Array.isArray(rep.warnings)&&rep.warnings.length)$('result-note').textContent+=' '+rep.warnings.join(' ');
  $('result-path').textContent=(r.study_kind==='surface'?r.gcode_path:r.package_path)||'';
}
class PathView {
  constructor(canvas){
    this.canvas=canvas;this.streams={};this.buffers=[];this.zoom=1;this.yaw=-.62;this.pitch=.56;
    this.center=[0,0,0];this.radius=1;this.layer='';this.cursor=0;this.light=false;this.lost=false;
    try{this.gl=canvas.getContext('webgl2',{alpha:true,antialias:true,depth:true});if(this.gl)this.init()}
    catch(e){this.error=e.message;this.gl=null}
    if(!this.gl)this.ctx=canvas.getContext('2d');
    canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();this.lost=true;render()});
    canvas.addEventListener('webglcontextrestored',()=>{this.lost=false;this.buffers=[];this.init();sceneTag='';render()});
    new ResizeObserver(()=>this.draw()).observe(canvas);
    let start=null,down=null,moved=false;
    canvas.onpointerdown=e=>{if(e.button!==0)return;start=down=[e.clientX,e.clientY];moved=false;canvas.setPointerCapture(e.pointerId)};
    canvas.onpointermove=e=>{if(start){
      if(Math.hypot(e.clientX-down[0],e.clientY-down[1])>5)moved=true;
      if(moved)this.rotate((e.clientX-start[0])*.009,(e.clientY-start[1])*.008);start=[e.clientX,e.clientY];
    }};
    canvas.onpointerup=e=>{if(down&&!moved){const hit=this.pick(e.clientX,e.clientY);if(hit)pickWall(hit.ray,hit.point)}start=down=null};
    canvas.onpointercancel=canvas.onlostpointercapture=()=>{start=down=null};
    canvas.addEventListener('wheel',e=>{e.preventDefault();this.magnify(Math.exp(-Math.sign(e.deltaY)*.12))},{passive:false});
    canvas.onkeydown=e=>{
      const moves={ArrowLeft:[-.1,0],ArrowRight:[.1,0],ArrowUp:[0,.1],ArrowDown:[0,-.1]};
      if(moves[e.key]){e.preventDefault();this.rotate(...moves[e.key])}
      if(['+','=','-'].includes(e.key)){e.preventDefault();this.magnify(e.key==='-'?.85:1.15)}
    };
  }
  init(){
    const g=this.gl,prog=g.createProgram();
    const vertex='#version 300 es\nin vec3 pos;in float shade;out float lighting;out vec3 world;uniform vec3 center;uniform vec2 angle;uniform vec3 scale;uniform float size;void main(){vec3 d=pos-center;float s=sin(angle.x),c=cos(angle.x);float horizontal=c*d.x+s*d.y;float depth=-s*d.x+c*d.y;float sp=sin(angle.y),cp=cos(angle.y);gl_Position=vec4(horizontal*scale.x,(cp*d.z+sp*depth)*scale.y,(cp*depth-sp*d.z)*scale.z,1.0);gl_PointSize=size;lighting=shade;world=pos;}';
    const fragment='#version 300 es\nprecision highp float;in float lighting;in vec3 world;uniform vec4 color;uniform bool point;uniform bool paintMesh;uniform int areaCount;uniform vec4 areas[24];out vec4 pixel;void main(){if(point&&distance(gl_PointCoord,vec2(.5))>.5)discard;vec3 ink=color.rgb;if(paintMesh){for(int i=0;i<24;i++){if(i>=areaCount)break;if(distance(world,areas[i].xyz)<=areas[i].w){ink=vec3(1.,.70,.18);break;}}}pixel=vec4(ink*lighting,color.a);}';
    for(const [type,src] of [[g.VERTEX_SHADER,vertex],[g.FRAGMENT_SHADER,fragment]]){
      const shader=g.createShader(type);g.shaderSource(shader,src);g.compileShader(shader);
      if(!g.getShaderParameter(shader,g.COMPILE_STATUS))throw Error(g.getShaderInfoLog(shader));
      g.attachShader(prog,shader);g.deleteShader(shader);
    }
    g.linkProgram(prog);if(!g.getProgramParameter(prog,g.LINK_STATUS))throw Error(g.getProgramInfoLog(prog));
    g.useProgram(prog);this.pos=g.getAttribLocation(prog,'pos');this.shade=g.getAttribLocation(prog,'shade');this.u={};
    for(const key of ['center','angle','scale','size','color','point','paintMesh','areaCount'])this.u[key]=g.getUniformLocation(prog,key);
    this.u.areas=g.getUniformLocation(prog,'areas[0]');
    g.enableVertexAttribArray(this.pos);g.enable(g.DEPTH_TEST);g.depthFunc(g.LEQUAL);
    g.enable(g.BLEND);g.blendFunc(g.SRC_ALPHA,g.ONE_MINUS_SRC_ALPHA);
  }
  get available(){return (Boolean(this.gl)||Boolean(this.ctx))&&!this.lost}
  pick(clientX,clientY){
    if(!this.mesh?.flat.length||this.layer!=='')return null;
    const rect=this.canvas.getBoundingClientRect(),w=rect.width,h=rect.height;
    const scale=(this.gl ? .425 : .42)*this.zoom*Math.min(w,h)/this.radius;
    const x=(clientX-rect.left-w/2)/scale,y=-(clientY-rect.top-h/2)/scale;
    const s=Math.sin(this.yaw),c=Math.cos(this.yaw),sp=Math.sin(this.pitch),cp=Math.cos(this.pitch);
    const direction=[-s*cp,c*cp,-sp],H=[c,s,0],V=[-s*sp,c*sp,cp];
    const origin=this.center.map((v,i)=>v+H[i]*x+V[i]*y-direction[i]*this.radius*4);
    const sub=(a,b)=>a.map((v,i)=>v-b[i]),dot=(a,b)=>a.reduce((sum,v,i)=>sum+v*b[i],0),
      cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
    let nearest=Infinity;
    for(let i=0;i<this.mesh.flat.length;i+=9){
      const a=this.mesh.flat.slice(i,i+3),b=this.mesh.flat.slice(i+3,i+6),c=this.mesh.flat.slice(i+6,i+9),
        e1=sub(b,a),e2=sub(c,a),p=cross(direction,e2),det=dot(e1,p);
      if(Math.abs(det)<1e-12)continue;
      const t=sub(origin,a),u=dot(t,p)/det,q=cross(t,e1),v=dot(direction,q)/det,d=dot(e2,q)/det;
      if(u>=0&&v>=0&&u+v<=1&&d>=0)nearest=Math.min(nearest,d);
    }
    return Number.isFinite(nearest)?{ray:{origin,direction},point:origin.map((v,i)=>v+nearest*direction[i])}:null;
  }
  selectedAreas(){
    return surfaceMode&&surfaceSettings().backend==='native_local'&&surfaceSettings().selection_mode==='paint'
      ?(presentResult()?state.result?.report?.wall_selection?.areas:(wallMarks.get(activeId)||[]).slice(0,surfaceSettings().wall_selection.length))||[]:[];
  }
  makeBuffer(data){
    if(!this.gl||this.lost)return null;
    const g=this.gl,buf=g.createBuffer();g.bindBuffer(g.ARRAY_BUFFER,buf);
    g.bufferData(g.ARRAY_BUFFER,new Float32Array(data),g.STATIC_DRAW);this.buffers.push(buf);return buf;
  }
  stream(points,layers,breaks){
    const flat=[],indices=[],groups=[],cuts=new Set(breaks||[]),byLayer=new Map();
    let group=null;
    for(let i=0;i<points.length;i++){
      const p=points[i];
      if(!Array.isArray(p)||p.length<3||!p.slice(0,3).every(Number.isFinite)){group=null;continue}
      const layer=layers&&layers[i]!=null?String(layers[i]):null;
      const index=flat.length/3;
      if(!group||group.layer!==layer||cuts.has(i)){
        group={start:index,count:0,layer};groups.push(group);
      }
      group.count++;flat.push(p[0],p[1],p[2]);indices.push(index);
      if(layer!==null){if(!byLayer.has(layer))byLayer.set(layer,[]);byLayer.get(layer).push(index)}
    }
    return {flat,indices,groups,byLayer,buffer:this.makeBuffer(flat)};
  }
  load(r){
    if(this.gl&&!this.lost)this.buffers.forEach(b=>this.gl.deleteBuffer(b));this.buffers=[];this.streams={};
    const triangles=r?.model?.objects?.filter(o=>!activeId||String(o.id)===activeId).flatMap(o=>o.triangles)||[];
    const mesh=triangles.flat(2),shades=[];
    for(const t of triangles){const [a,b,c]=t,u=b.map((v,i)=>v-a[i]),v=c.map((n,i)=>n-a[i]);
      const n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];
      const light=.42+.58*Math.abs((.3*n[0]-.4*n[1]+.86*n[2])/Math.max(1e-9,Math.hypot(...n)));
      shades.push(light,light,light)}
    this.mesh={flat:mesh,shades,buffer:this.makeBuffer(mesh),shadeBuffer:this.makeBuffer(shades)};
    for(const k of ['original','deformed']){
      const pts=r?.[k+'_points']||[],own=r?.[k+'_layer_ids'];
      const ids=own?.length===pts.length?own:(r?.layer_ids?.length===pts.length?r.layer_ids:null);
      const cuts=r?.[k+'_break_indices']??(pts.length===r?.deformed_points?.length?(r?.break_indices??r?.report?.break_indices):[]);
      this.streams[k]=this.stream(pts,ids,cuts);
    }
    this.layer='';this.cursor=0;
    const low=[Infinity,Infinity,Infinity],high=[-Infinity,-Infinity,-Infinity];
    Object.values(this.streams).forEach(s=>{for(let i=0;i<s.flat.length;i++){
      const a=i%3;low[a]=Math.min(low[a],s.flat[i]);high[a]=Math.max(high[a],s.flat[i]);
    }});
    for(let i=0;i<mesh.length;i++){const a=i%3;low[a]=Math.min(low[a],mesh[i]);high[a]=Math.max(high[a],mesh[i])}
    if(!Number.isFinite(low[0])){this.grid=null;this.draw();return}
    this.center=low.map((v,i)=>(v+high[i])/2);this.radius=Math.max(.2,Math.hypot(...low.map((v,i)=>high[i]-v))/2);
    this.sceneCenter=this.center;this.sceneRadius=this.radius;
    const target=this.radius/4,unit=10**Math.floor(Math.log10(target)),nice=[1,2,5,10].find(v=>v*unit>=target)*unit;
    const cx=Math.round(this.center[0]/nice)*nice,cy=Math.round(this.center[1]/nice)*nice;
    const floor=low[2]-.015*this.radius,extent=nice*5,lines=[];
    for(let i=-5;i<=5;i++){lines.push(cx+i*nice,cy-extent,floor,cx+i*nice,cy+extent,floor,
      cx-extent,cy+i*nice,floor,cx+extent,cy+i*nice,floor)}
    this.grid={buffer:this.makeBuffer(lines),count:lines.length/3};this.fit();
  }
  lens(){return this.streams[view==='original'?'original':'deformed']}
  active(){const s=this.lens();return s?(this.layer===''?s.indices:(s.byLayer.get(this.layer)||[])):[]}
  layers(){return [...(this.lens()?.byLayer.keys()||[])].sort((a,b)=>Number(a)-Number(b))}
  rotate(dx,dy){this.yaw+=dx;this.pitch=Math.max(-1.5,Math.min(1.5,this.pitch+dy));this.draw()}
  magnify(f){this.zoom=Math.max(.15,Math.min(100,this.zoom*f));this.draw()}
  fit(){
    this.zoom=1;this.yaw=-.62;this.pitch=.56;
    this.center=this.sceneCenter||[0,0,0];this.radius=this.sceneRadius||1;
    if(this.layer!==''){
      const low=[Infinity,Infinity,Infinity],high=[-Infinity,-Infinity,-Infinity];
      for(const s of Object.values(this.streams))for(const idx of s.byLayer.get(this.layer)||[]){
        for(let a=0;a<3;a++){const v=s.flat[idx*3+a];low[a]=Math.min(low[a],v);high[a]=Math.max(high[a],v)}
      }
      if(Number.isFinite(low[0])){
        this.center=low.map((v,i)=>(v+high[i])/2);this.radius=Math.max(.2,Math.hypot(...low.map((v,i)=>high[i]-v))/2);
      }
    }
    this.draw();
  }
  draw(){
    if(!this.available)return;
    this.drawAreas=this.selectedAreas();
    if(!this.gl){this.drawCanvas();return}
    const g=this.gl,c=this.canvas,dpr=Math.min(window.devicePixelRatio||1,2),u=this.u;
    const w=Math.max(1,Math.round(c.clientWidth*dpr)),h=Math.max(1,Math.round(c.clientHeight*dpr));
    if(c.width!==w||c.height!==h){c.width=w;c.height=h}
    g.viewport(0,0,w,h);g.clearColor(0,0,0,0);g.clear(g.COLOR_BUFFER_BIT|g.DEPTH_BUFFER_BIT);
    if(!this.grid)return;
    g.uniform3fv(u.center,this.center);g.uniform2f(u.angle,this.yaw,this.pitch);
    const scale=.85*this.zoom/this.radius;
    g.uniform3f(u.scale,scale*Math.min(1,h/w),scale*Math.min(1,w/h),.16/this.radius);
    const bind=(buf)=>{g.bindBuffer(g.ARRAY_BUFFER,buf);g.vertexAttribPointer(this.pos,3,g.FLOAT,false,0,0)};
    g.disableVertexAttribArray(this.shade);g.vertexAttrib1f(this.shade,1);
    g.uniform1i(u.paintMesh,true);g.uniform1i(u.areaCount,this.drawAreas.length);
    if(this.drawAreas.length)g.uniform4fv(u.areas,this.drawAreas.flatMap(a=>[...a.center,a.radius_mm]));
    if(this.mesh?.flat.length&&this.layer===''){
      bind(this.mesh.buffer);g.bindBuffer(g.ARRAY_BUFFER,this.mesh.shadeBuffer);
      g.enableVertexAttribArray(this.shade);g.vertexAttribPointer(this.shade,1,g.FLOAT,false,0,0);
      g.uniform1i(u.point,false);g.uniform4fv(u.color,this.light?[.57,.66,.70,.9]:[.38,.52,.57,.92]);
      g.enable(g.POLYGON_OFFSET_FILL);g.polygonOffset(1,1);g.drawArrays(g.TRIANGLES,0,this.mesh.flat.length/3);
      g.disable(g.POLYGON_OFFSET_FILL);g.disableVertexAttribArray(this.shade);g.vertexAttrib1f(this.shade,1);
    }
    g.uniform1i(u.paintMesh,false);
    g.uniform1i(u.point,false);g.uniform1f(u.size,1);bind(this.grid.buffer);
    g.uniform4fv(u.color,this.light?[.29,.36,.43,.25]:[.32,.39,.45,.35]);
    g.drawArrays(g.LINES,0,this.grid.count);
    for(const kind of (view==='compare'?['original','deformed']:[view])){
      const s=this.streams[kind];if(!s?.indices.length)continue;
      bind(s.buffer);g.uniform4fv(u.color,kind==='original'?[.31,.61,.98,view==='compare'?.68:1]:(this.light?[0,.48,.40,1]:[0,.88,.73,1]));
      for(const group of s.groups){
        if(this.layer!==''&&group.layer!==this.layer)continue;
        g.drawArrays(group.count===1?g.POINTS:g.LINE_STRIP,group.start,group.count);
      }
    }
    const idx=this.active()[this.cursor];
    if(idx!==undefined){
      bind(this.lens().buffer);g.disable(g.DEPTH_TEST);g.uniform1i(u.point,true);
      g.uniform4f(u.color,.09,.10,.12,1);g.uniform1f(u.size,11*dpr);g.drawArrays(g.POINTS,idx,1);
      g.uniform4f(u.color,1,.77,.28,1);g.uniform1f(u.size,7*dpr);g.drawArrays(g.POINTS,idx,1);g.enable(g.DEPTH_TEST);
    }
  }
  drawCanvas(){
    const c=this.canvas,g=this.ctx,w=c.width=Math.max(1,c.clientWidth),h=c.height=Math.max(1,c.clientHeight);
    g.clearRect(0,0,w,h);const scale=.42*this.zoom*Math.min(w,h)/this.radius;
    const project=p=>{const d=p.map((n,i)=>n-this.center[i]),x=Math.cos(this.yaw)*d[0]+Math.sin(this.yaw)*d[1],
      depth=-Math.sin(this.yaw)*d[0]+Math.cos(this.yaw)*d[1];
      return [w/2+x*scale,h/2-(Math.cos(this.pitch)*d[2]+Math.sin(this.pitch)*depth)*scale,
        Math.cos(this.pitch)*depth-Math.sin(this.pitch)*d[2]]};
    if(this.layer===''&&this.mesh?.flat.length){
      const faces=[];for(let i=0;i<this.mesh.flat.length;i+=9){const p=[0,3,6].map(k=>project(this.mesh.flat.slice(i+k,i+k+3)));
        faces.push({p,depth:p.reduce((sum,q)=>sum+q[2],0)/3,shade:this.mesh.shades[i/3],
          world:[0,3,6].map(k=>this.mesh.flat.slice(i+k,i+k+3))})}
      faces.sort((a,b)=>b.depth-a.depth);for(const f of faces){const t=f.shade;
        g.fillStyle=`rgb(${Math.round(90*t)},${Math.round(145*t)},${Math.round(155*t)})`;
        g.beginPath();f.p.forEach((p,i)=>i?g.lineTo(p[0],p[1]):g.moveTo(p[0],p[1]));g.closePath();g.fill();
        if(this.drawAreas.length){
          const [a,b,c]=f.world,u=b.map((v,i)=>v-a[i]),v=c.map((v,i)=>v-a[i]);
          const n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],length=Math.hypot(...n);
          if(length<1e-12)continue;for(let i=0;i<3;i++)n[i]/=length;
          const ul=Math.hypot(...u),U=u.map(x=>x/ul),V=[n[1]*U[2]-n[2]*U[1],n[2]*U[0]-n[0]*U[2],n[0]*U[1]-n[1]*U[0]];
          for(const area of this.drawAreas){
            const d=n.reduce((sum,v,i)=>sum+v*(area.center[i]-a[i]),0);
            if(Math.abs(d)>=area.radius_mm)continue;
            const r=Math.sqrt(area.radius_mm**2-d*d),center=area.center.map((v,i)=>v-d*n[i]),P=project(center),
              A=project(center.map((v,i)=>v+r*U[i])),B=project(center.map((v,i)=>v+r*V[i]));
            g.save();g.beginPath();f.p.forEach((p,i)=>i?g.lineTo(p[0],p[1]):g.moveTo(p[0],p[1]));g.closePath();g.clip();
            g.transform(A[0]-P[0],A[1]-P[1],B[0]-P[0],B[1]-P[1],P[0],P[1]);
            g.fillStyle='#edb044';g.beginPath();g.arc(0,0,1,0,2*Math.PI);g.fill();g.restore();
          }
        }
      }
    }
    for(const kind of(view==='compare'?['original','deformed']:[view])){
      const s=this.streams[kind];if(!s)continue;g.strokeStyle=kind==='original'?'#509cfb':'#00dfbb';g.lineWidth=1.2;
      for(const group of s.groups){if(this.layer!==''&&group.layer!==this.layer)continue;
        g.beginPath();for(let i=0;i<group.count;i++){const p=project(s.flat.slice((group.start+i)*3,(group.start+i)*3+3));
          i?g.lineTo(p[0],p[1]):g.moveTo(p[0],p[1])}g.stroke()}
    }
  }
}
const viewer=new PathView($('canvas'));
function cursor(){
  const seq=viewer.active(),s=viewer.lens(),n=seq.length;
  viewer.cursor=Math.max(0,Math.min(n-1,Number($('scrub').value)||0));
  $('scrub').value=viewer.cursor;$('pct').textContent=n?Math.round(viewer.cursor*100/Math.max(1,n-1))+'%':'—';
  const i=seq[viewer.cursor]*3;
  $('xyz').textContent=n?['X','Y','Z'].map((axis,a)=>axis+' '+numberFormat(s.flat[i+a],3)).join('   '):'X —   Y —   Z —';
  viewer.draw();
}
function stop(){
  playing=false;cancelAnimationFrame(frame);previousTime=0;progressCarry=0;
  $('play').innerHTML=icon('play');$('play').setAttribute('aria-label','Reproduzir percurso');$('play').title='Reproduzir percurso';
}
function timeline(){
  const n=viewer.active().length;const can=viewer.available&&n>0;
  $('scrub').max=Math.max(0,n-1);$('scrub').disabled=!can||n<2;$('play').disabled=!can||n<2;
  $('point-label').textContent=n?numberFormat(n)+' pontos no percurso':'';
  cursor();
}
function setLayers(){
  const list=$('layer'),layers=viewer.layers();
  if(!layers.includes(viewer.layer))viewer.layer='';
  list.replaceChildren(new Option(surfaceMode?'Todos':'Todas',''),...layers.map(l=>new Option((surfaceMode?'Grupo ':'Camada ')+l,l)));
  list.value=viewer.layer;list.disabled=!viewer.available||layers.length===0;
}
function playFrame(now){
  if(!playing)return;
  if(previousTime)progressCarry+=Math.min(.1,(now-previousTime)/1000)*Math.max(12,viewer.active().length/18);
  previousTime=now;const steps=Math.floor(progressCarry);
  if(steps){progressCarry-=steps;$('scrub').value=Math.min(Number($('scrub').max),viewer.cursor+steps);cursor()}
  if(viewer.cursor>=Number($('scrub').max)){stop();return}
  frame=requestAnimationFrame(playFrame);
}
$('play').onclick=()=>{
  if(playing){stop();return}
  if(viewer.cursor>=Number($('scrub').max)){$('scrub').value=0;cursor()}
  playing=true;$('play').innerHTML=icon('pause');$('play').setAttribute('aria-label','Pausar percurso');$('play').title='Pausar percurso';frame=requestAnimationFrame(playFrame);
};
$('scrub').oninput=()=>{stop();cursor()};
$('layer').onchange=e=>{stop();viewer.layer=e.target.value;viewer.fit();$('scrub').value=0;timeline()};
$('fit').onclick=()=>viewer.fit();$('zoom-in').onclick=()=>viewer.magnify(1.3);$('zoom-out').onclick=()=>viewer.magnify(1/1.3);
document.querySelectorAll('[data-view]').forEach(btn=>btn.onclick=()=>{stop();view=btn.dataset.view;setLayers();render()});
function render(){
  const busy=controlsBusy(),current=presentResult(),problem=valid();
  const combined=!surfaceMode&&parameters.mode==='combined';
  const active=(state.objects||[]).find(o=>String(o.id)===activeId);
  const invalidSelected=(state.objects||[]).find(o=>selection.has(String(o.id))&&valid(effective(String(o.id))));
  const error=surfaceMode?surfaceError():(problem||(invalidSelected?'Confira os parâmetros de '+invalidSelected.name+'.':''));
  document.body.classList.toggle('surface-mode',surfaceMode);
  document.body.classList.toggle('combined-mode',combined);
  $('wave_count').closest('.field').hidden=!combined;
  $('wavelength_mm').closest('.field').hidden=combined;
  $('z_ratio').closest('.field').hidden=!combined;
  $('end_height_mm').closest('label').hidden=combined;
  $('start_height_mm').closest('label').firstChild.textContent=combined?'Começar ondas (mm)':'Início em Z (mm)';
  const label=$('amplitude_mm').closest('.field').querySelector('label');label.textContent=combined?'Intensidade das ondas':'Amplitude';
  $('r-amplitude_mm').max=combined?5:1;
  const stepBox=$('step_mm').closest('.field'),stepParent=combined?advanced:primary;
  surfaceAdvanced.hidden=!surfaceMode;
  const localSurface=surfaceMode&&surfaceSettings().backend==='native_local';
  wallBox.hidden=!localSurface;
  const wallOptions=surfaceSettings(),painting=wallOptions.selection_mode==='paint';
  $('canvas').style.cursor=localSurface&&painting&&!busy?'crosshair':'grab';
  wallPaint.setAttribute('aria-pressed',String(painting));wallAll.setAttribute('aria-pressed',String(!painting));
  wallPaint.disabled=wallAll.disabled=brushInput.disabled=busy;brushRow.hidden=wallHint.hidden=wallList.hidden=wallClear.hidden=!painting;
  wallClear.disabled=busy||!wallOptions.wall_selection?.length;
  wallList.replaceChildren();
  (wallOptions.wall_selection||[]).forEach((area,i)=>{
    const remove=node('button','outline','Área '+(i+1)+' · '+numberFormat(area.radius_mm)+' mm ×');
    remove.setAttribute('aria-label','Remover área '+(i+1));remove.disabled=busy;
    remove.onclick=()=>{const rows=[...wallOptions.wall_selection];rows.splice(i,1);
      const marks=[...(wallMarks.get(activeId)||[])];marks.splice(i,1);wallMarks.set(activeId,marks);
      surfaceByObject.set(activeId,{...wallOptions,wall_selection:rows,selection_revision:rows.length?wallOptions.selection_revision:null});render()};wallList.append(remove);
  });
  surfaceMethod.value=surfaceSettings().backend;surfaceMethod.disabled=busy;
  const targetParent=surfaceMode?surfaceAdvanced:stepParent;
  if(stepBox.parentElement!==targetParent)targetParent.append(stepBox);
  stepBox.hidden=localSurface;
  $('max_slope_deg').closest('.field').hidden=!surfaceMode||(localSurface&&!painting);surfaceInfo.hidden=!surfaceMode;
  const stage=state.conformal?.phase,full=state.result?.study_kind==='conformal';
  roofRegions(active,busy||Boolean(stage));
  if(localSurface)roofBox.hidden=true;
  nativeCornersBox.hidden=!surfaceMode||!linked||localSurface;nativeCorners.disabled=busy||Boolean(stage);
  const conformalLabel={preparing:'Preparando cópia…',needs_open:'Abrindo cópia…',opening:'Abrindo cópia…',
    checking:'Verificando malha…',awaiting_slice:'Aguardando Fatiar no Orca',slicing:'Fatiando no Orca…',
    captured:'Gerar percurso conformal',generating:'Gerando percurso…',ready:'Percurso conformal gerado'};
  $('generate').innerHTML=icon(surfaceMode?'curve':'wave')+(surfaceMode?
    ' '+(conformalLabel[stage]||(linked?'Gerar superfície e abrir Preview':'Estudar superfície')):
    (combined?' Gerar e abrir Preview':' Gerar G-code com ondas'));
  surfaceInfo.textContent=state.conformal?(state.conformal.settings?.backend==='regional_paired'?
    'Topo e face inferior são preparados juntos, preservando a base e sem faixa plana na borda. Clique em Fatiar no Orca. Somente estudo digital.':
    'Estudo anterior: somente topo parcial; bordas planas. Não demonstra o beiral completo.'):
    (linked?(localSurface?'Clique nas áreas que deseja suavizar. O Orca calcula os contornos compatíveis; paredes verticais e faces inferiores podem continuar com camadas.':
      'Alinhamento experimental a um teto de referência. As outras regiões não seguem suas próprias curvas.'):
      'O percurso geométrico isolado é apenas uma visualização do topo; não comprova deposição.');
  $('surface-only').hidden=!surfaceMode||!linked||Boolean(stage)||localSurface;$('surface-only').disabled=!active||busy||Boolean(error);
  $('bench-note').textContent=combined?'Vaso senoidal · somente Preview · sem envio à impressora':surfaceMode?((full||stage)?'Estudo conformal · impressão indisponível':'Estudo geométrico · impressão indisponível'):'Estudo de bancada · impressão pelo OrcaSlicer';
  prep.hidden=surfaceMode||!(combined||state.capture_setup_required);prep.disabled=!linked||busy;
  prep.textContent=combined?'Preparar vaso no Orca':'Preparar captura no Orca';
  $('layer-label').textContent=surfaceMode?'Grupo de percurso':'Camada';
  document.querySelector('.readout span').textContent=surfaceMode?'Ponto (mm)':'Bico (mm)';
  $('legend-original-label').textContent=surfaceMode?'Referência':'Original';
  $('legend-modified-label').textContent=surfaceMode?'Superfície':'Com ondas';
  for(const kind of ['original','deformed'])document.querySelector('[data-view='+kind+']').textContent=$(kind==='original'?'legend-original-label':'legend-modified-label').textContent;
  editTarget.textContent=active?'Editando '+active.name+' · ID '+activeId:'Escolha uma peça para editar.';
  $('link-dot').classList.toggle('live',linked&&!state.demo);
  $('connection').textContent=linked&&!state.demo?'OrcaSlicer conectado':'Demonstração de bancada • não conectado ao Orca';
  panelAction.hidden=!linked||Boolean(state.demo);panelHelp.hidden=panelAction.hidden||docked;
  $('validation').hidden=!error;$('validation').textContent=error;
  $('refresh').disabled=!linked||busy;$('analyze').disabled=!linked||busy||!selection.size;
  $('params').disabled=busy||!active||Boolean(stage);$('presets').disabled=busy||!active;
  $('suggest').disabled=busy||!active?.suggestion;
  $('suggest').title=active?.suggestion?'Aplicar aos parâmetros de '+active.name:'O objeto ativo precisa de uma sugestão disponível';
  $('save').disabled=!linked||busy||Boolean(problem);
  $('delete').disabled=!linked||busy||!personalPresets().some(p=>String(p.id)===presetId);
  $('generate').disabled=!linked||busy||(surfaceMode?(!active||Boolean(error)):(!canCapture()||!selection.size||Boolean(invalidSelected)));
  if(stage&&stage!=='captured')$('generate').disabled=true;
  $('preview').disabled=!linked||(surfaceMode&&!full)||!current||busy||!state.result?.package_path;
  $('preview').title=surfaceMode&&!full?'Percurso da superfície disponível no visor do Studio.':'Abrir trajetória processada no OrcaSlicer';
  objects();diagnostics(current);analytic();
  profileCard.textContent=state.printer_profile?.name||'Selecione uma impressora no Orca';
  profileDetails.textContent=state.printer_profile?.issue||
    (state.printer_profile?.nozzle_mm?'Bico '+numberFormat(state.printer_profile.nozzle_mm)+' mm · camada '+numberFormat(state.printer_profile.layer_mm)+' mm · '+state.printer_profile.firmware:'O perfil acompanha a seleção feita no Orca.');
  cancelBuild.hidden=!(state.status==='processing'&&!stage);cancelBuild.disabled=false;
  const tag=[current?state.result.sha256:'model',state.model_preview?.id,activeId].join('/');
  if(sceneTag!==tag){stop();sceneTag=tag;viewer.load({...current?state.result:{},model:state.model_preview});$('scrub').value=0;setLayers()}
  else viewer.draw();
  const modes=document.querySelectorAll('[data-view]');
  for(const b of modes){
    b.setAttribute('aria-pressed',String(view===b.dataset.view));
    const counts=['original','deformed'].map(k=>viewer.streams[k]?.indices.length||0);
    b.disabled=!viewer.available||!(b.dataset.view==='compare'?counts.every(Boolean):counts[b.dataset.view==='original'?0:1]);
    if(localSurface&&b.dataset.view!=='deformed')b.disabled=true;
  }
  const n=viewer.active().length;
  $('legend-original').hidden=!n||view==='deformed';$('legend-modified').hidden=!n||view==='original';
  const hasModel=Boolean(viewer.mesh?.flat.length);
  $('empty').hidden=viewer.available&&(n>0||hasModel);
  $('empty-msg').textContent=!viewer.available?'WebGL 2 indisponível. A trajetória 3D precisa de aceleração gráfica neste visor.':
    (busy?'Analisando a trajetória atual…':(surfaceMode&&!current?'Estude a superfície da peça para visualizar seu percurso.':
    (state.result&&!current?'Configuração alterada. Gere novamente para visualizar.':
    (current?'A trajetória desta visualização não contém pontos.':'Gere uma trajetória para inspecionar o percurso do bico.'))));
  for(const id of ['fit','zoom-in','zoom-out'])$(id).disabled=!viewer.available||(!n&&!hasModel);
  timeline();
  if(hasModel&&!n)$('point-label').textContent='Modelo original · '+(busy?'calculando trajetórias…':'arraste para girar');
}
const profileBox=node('section','section'),profileCard=node('strong'),profileDetails=node('p','muted');
profileBox.append(node('h3','','Perfil selecionado no Orca'),profileCard,profileDetails);
document.querySelector('#config .section').after(profileBox);
const surfaceAdvanced=node('details','field');surfaceAdvanced.append(node('summary','','Ajustes da superfície'));
const surfaceMethod=node('select');surfaceMethod.id='surface-method';surfaceMethod.setAttribute('aria-label','Método de superfície');
for(const [id,label] of [['native_local','Acompanhar superfícies locais'],['roof_bending','Alinhar camadas a um teto (experimental)']]){
  const option=node('option','',label);option.value=id;surfaceMethod.append(option);
}
surfaceMethod.onchange=()=>{wallMarks.delete(activeId);surfaceByObject.set(activeId,{...surfaceSettings(),backend:surfaceMethod.value});render()};
surfaceAdvanced.append(surfaceMethod);
surfaceAdvanced.append($('max_slope_deg').closest('.field'),roofBox,nativeCornersBox);primary.append(surfaceAdvanced);
const cancelBuild=node('button','wide outline','Cancelar cálculo');cancelBuild.id='cancel-build';cancelBuild.hidden=true;
$('generate').after(cancelBuild);cancelBuild.onclick=()=>send('cancel_build');
const prep=node('button','wide outline','Preparar captura no Orca');prep.id='prepare-capture';prep.hidden=true;
$('analyze').after(prep);
const surfaceOnly=node('button','wide outline','Estudar apenas a superfície');surfaceOnly.id='surface-only';surfaceOnly.hidden=true;
$('generate').after(surfaceOnly);surfaceOnly.onclick=()=>request('surface_study');
function request(action){
  if(!linked||controlsBusy())return;
  notice('');pending=action;
  if(['generate','surface_study','generate_conformal','build_surface'].includes(action))generation=signature();
  render();
  if(!send(action)){pending=null;generation=null;render()}
}
$('refresh').onclick=()=>request('refresh');$('analyze').onclick=()=>request('analyze');
prep.onclick=()=>request(!surfaceMode&&parameters.mode==='combined'?'prepare_vase':'prepare_capture');$('generate').onclick=()=>request(surfaceMode?
  (state.conformal?.phase==='captured'?'generate_conformal':(state.conformal?'prepare_conformal':'build_surface')):'generate');
$('preview').onclick=()=>{if(state.result?.study_kind!=='surface'&&presentResult())send('open_preview',{sha256:state.result.sha256})};
$('suggest').onclick=()=>{
  const obj=(state.objects||[]).find(o=>String(o.id)===activeId);
  if(obj?.suggestion)loadParams({...parameters,...obj.suggestion});
};
$('presets').onchange=e=>{const preset=optionList().find(p=>String(p.id)===e.target.value);
  if(preset)loadParams(preset.parameters,String(preset.id));else{presetId='';render()}};
$('save').onclick=()=>{
  const p=personalPresets().find(p=>String(p.id)===presetId);
  $('preset-name').value=p?.name||'';$('preset-editor').hidden=false;$('preset-name').focus();
};
$('cancel-preset').onclick=()=>{$('preset-editor').hidden=true};
$('preset-editor').onsubmit=e=>{
  e.preventDefault();const name=$('preset-name').value.trim();
  if(!name){$('preset-name').focus();return}
  const found=personalPresets().find(p=>p.name===name);
  const data=found?{id:String(found.id),name}:{name};
  if(send('save_preset',data))$('preset-editor').hidden=true;
};
$('delete').onclick=()=>{const p=personalPresets().find(p=>String(p.id)===presetId);
  if(p&&window.confirm('Excluir o preset “'+p.name+'”?'))send('delete_preset',{id:String(p.id),name:p.name})};
$('theme').onclick=()=>{viewer.light=!viewer.light;document.documentElement.dataset.theme=viewer.light?'light':'dark';viewer.draw()};
function compact(){document.body.classList.toggle('compact',document.body.dataset.mode==='dock'||window.innerWidth<=840)}
window.addEventListener('resize',compact);compact();
for(const id of ['config','review'])$('tab-'+id).onclick=()=>{for(const k of ['config','review']){
  $(k).classList.toggle('shown',id===k);$('tab-'+k).setAttribute('aria-selected',String(id===k));
}};
function applyState(next){
  if(!next||typeof next!=='object'||Array.isArray(next))return;
  // Background mesh analysis temporarily publishes an empty object list.
  // Keep the last known objects disabled until the replacement arrives so
  // selections and per-object edits are not deleted between the two replies.
  if(next.status==='analyzing'&&next.revision===state.revision&&!next.objects?.length&&state.objects?.length)
    next={...next,objects:state.objects};
  if(Number.isFinite(next.sequence)&&next.sequence<hostSequence)return;
  if(Number.isFinite(next.sequence))hostSequence=next.sequence;
  // Polls advance the server sequence even when the visible data is identical.
  // Avoid rebuilding focused object buttons and preset menus on those replies.
  const stamp=JSON.stringify([next.native,next.demo,next.status,next.message,next.revision,
    next.capture?.capture_id,next.capture?.sha256,next.capture_setup_required,next.objects,
    next.presets,next.parameters,next.parameters_by_object,next.selected_object_ids,next.conformal,next.model_preview?.id,
    next.result?.sha256,next.result?.study_kind,next.result?.object_id,next.result?.settings,next.result?.package_path]);
  if(!pending&&stamp===stateStamp){state=next;schedulePoll();return}
  stateStamp=stamp;
  const first=!Object.keys(state).length,priorRev=state.revision;
  const oldIds=new Set((state.objects||[]).map(o=>String(o.id)));
  state=next;pending=null;linked=Boolean(activeBridge())&&!state.demo;notice('');
  const ids=(state.objects||[]).map(o=>String(o.id));
  selection=new Set([...selection].filter(id=>ids.includes(id)));
  if((first||!oldIds.size)&&Array.isArray(state.selected_object_ids))
    selection=new Set(state.selected_object_ids.map(String).filter(id=>ids.includes(id)));
  else if(!selection.size&&ids.length===1&&!oldIds.has(ids[0]))selection.add(ids[0]);
  if((first||!oldIds.size)&&state.parameters)baseParameters=normalized(state.parameters);
  const idSet=new Set(ids);
  for(const id of surfaceByObject.keys())if(!idSet.has(id))surfaceByObject.delete(id);
  for(const id of wallMarks.keys())if(!idSet.has(id))wallMarks.delete(id);
  for(const id of objectParameters.keys())if(!idSet.has(id)){objectParameters.delete(id);objectPresets.delete(id)}
  let loadedActive=false;
  for(const id of ids){
    const overrides=state.parameters_by_object;
    if(overrides&&Object.hasOwn(overrides,id)&&!objectParameters.has(id)){
      objectParameters.set(id,normalized({...baseParameters,...overrides[id]}));
      if(id===activeId)loadedActive=true;
    }
  }
  if(!idSet.has(activeId))activate(ids.find(id=>selection.has(id))??ids[0]??null);
  else if(loadedActive||((first||!oldIds.size)&&activeId!==null))activate(activeId);
  if(state.conformal){
    surfaceMode=true;
    const ctx=state.conformal,id=ctx.native_id||ctx.original_id;
    if(idSet.has(id)){surfaceByObject.set(id,ctx.settings);activate(id)}
  }
  if(priorRev&&priorRev!==state.revision){generation=null;resultConfig=''}
  const r=state.result;
  if(r?.sha256&&state.status==='ready'){
    const surfaceResult=['surface','conformal'].includes(r.study_kind);
    const identity=JSON.stringify([r.sha256,surfaceResult?'surface':(state.capture?.sha256||''),state.revision||'']);
    if(surfaceResult&&r.settings&&idSet.has(String(r.object_id))){
      const id=String(r.object_id),settings={step_mm:r.settings.step_mm,max_slope_deg:r.settings.max_slope_deg,
        retain_native_short_edges:Boolean(r.settings.retain_native_short_edges),
        backend:r.settings.backend||'legacy_top',region_id:r.settings.region_id??null,
        selection_mode:r.settings.selection_mode??'all',selection_revision:r.settings.selection_revision??null,
        wall_selection:r.settings.wall_selection||[]};
      if(settings.backend!=='native_local')for(const key of ['selection_mode','selection_revision','wall_selection'])delete settings[key];
      if(!resultIdentity&&!generation){
        surfaceMode=true;surfaceByObject.set(id,settings);
        if(r.report?.wall_selection?.areas)wallMarks.set(id,r.report.wall_selection.areas.map(a=>({center:a.center,radius_mm:a.radius_mm})));
        activate(id);
      }
      resultIdentity=identity;resultConfig=stableJSON(['surface',state.revision||'',id,settings]);
    }
    else if(generation){resultConfig=generation;resultIdentity=identity}
    else if(!resultIdentity||(!priorRev&&first)){resultConfig=signature();resultIdentity=identity}
    else if(identity!==resultIdentity){resultConfig='';resultIdentity=identity}
  }
  addPresets();prep.hidden=!state.capture_setup_required;prep.disabled=!linked||controlsBusy();
  render();
  if(!state.native&&!surfaceMode&&generation&&state.status==='ready'&&presentResult()&&r.package_path&&!opened.has(r.sha256)){
    opened.add(r.sha256);send('open_preview',{sha256:r.sha256});
  }
  if(!['processing','analyzing'].includes(state.status))generation=null;
  schedulePoll();
}
function schedulePoll(immediate=false){
  clearTimeout(pollTimer);
  const active=['processing','analyzing'].includes(state.status)||['generate','surface_study'].includes(pending);
  if(!linked||state.demo||(document.hidden&&!active))return;
  const delay=immediate?Math.max(0,180-(Date.now()-lastPoll)):(active?500:1500);
  pollTimer=setTimeout(()=>{
    lastPoll=Date.now();
    // Re-arm before sending. An onMessage callback can run synchronously, and
    // a lost WebView reply must not stop subsequent updates.
    pollTimer=setTimeout(()=>schedulePoll(true),4000);
    send('poll',{ui_focused:document.hasFocus()});
  },delay);
}
document.addEventListener('visibilitychange',()=>schedulePoll(!document.hidden));
window.addEventListener('focus',()=>schedulePoll(true));
window.addEventListener('pagehide',()=>clearTimeout(pollTimer));
window.addEventListener('pageshow',e=>{if(e.persisted)schedulePoll(true)});
function receive(input){
  let m=input;
  for(let depth=0;depth<3&&typeof m==='string';depth++){try{m=JSON.parse(m)}catch{return}}
  if(m?.type==='state'&&m.state){receivedHostState=true;applyState(m.state)}
}
window.orcaWaveReceive=receive;
window.addEventListener('message',e=>receive(e.data));
let wiredNative=null,wiredWebView=null;
function listen(){
  if(window.orca!==wiredNative&&typeof window.orca?.onMessage==='function'){wiredNative=window.orca;wiredNative.onMessage(receive)}
  const webview=window.chrome?.webview;
  if(webview!==wiredWebView&&typeof webview?.addEventListener==='function'){wiredWebView=webview;webview.addEventListener('message',e=>receive(e.data))}
}
listen();syncParams();applyState(JSON.parse($('initial-state').textContent));
function start(){
  let lastBridge;
  const connect=()=>{
    listen();const bridge=activeBridge();linked=Boolean(bridge)&&!state.demo;
    if(linked&&bridge!==lastBridge&&!receivedHostState&&!pending)send('refresh');
    lastBridge=bridge;render();schedulePoll();
  };
  connect();
  // Some host versions install window.orca after DOMContentLoaded.
  if(!wiredNative&&!state.demo){setTimeout(connect,80);setTimeout(connect,300);setTimeout(connect,1000)}
}
if(document.readyState==='loading')window.addEventListener('DOMContentLoaded',start,{once:true});else start();
</script></body></html>"""
