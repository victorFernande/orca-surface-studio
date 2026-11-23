"""Offline WebView document shared by the Orca page, dock and bench viewer."""
from __future__ import annotations

import json

from .branding import ICON_SVG
from .language_packs import load_language_packs
from .placement_ui import MARKUP as PLACEMENT_MARKUP,SCRIPT as PLACEMENT_SCRIPT
from .model_preview_ui import SCRIPT as MODEL_PREVIEW_SCRIPT


def get_studio_html(initial_state: dict | None = None, *, dock: bool = False) -> str:
    payload = json.dumps(initial_state or {}, ensure_ascii=False, allow_nan=False)
    # The state is data inside a script element. Its contents must never end the element.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    catalogs = json.dumps(load_language_packs()[0], ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")
    return (_HTML.replace("__LAYOUT__", "dock" if dock else "page")
            .replace("__BRAND_ICON__", ICON_SVG.replace('<svg ', '<svg class="brandmark" role="img" aria-label="Trajetória subindo a 30 graus" ', 1))
            .replace("__PLACEMENT_MARKUP__",PLACEMENT_MARKUP).replace("__PLACEMENT_SCRIPT__",PLACEMENT_SCRIPT)
            .replace("__MODEL_PREVIEW_SCRIPT__",MODEL_PREVIEW_SCRIPT)
            .replace("__LANGUAGE_PACKS__", catalogs).replace("__STATE__", payload))


_HTML = r"""<!doctype html>
<html lang="pt-BR" data-theme="dark"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Orca Surface Studio</title>
<style>
:root{color-scheme:dark;--bg-app:#15171b;--bg-panel:#1d2026;--bg-card:#242830;--bg-card-hover:#2b303a;--bg-input:#16181d;--bg-viewport-top:#222731;--bg-viewport-bot:#111318;--bg-hud:rgba(23,26,33,.88);--border-subtle:#313641;--border-strong:#434b5a;--text-main:#eef2f7;--text-muted:#9aa4b4;--text-dim:#6d7788;--orca-accent:#00a896;--orca-accent-hover:#00bfa5;--orca-accent-soft:rgba(0,191,165,.15);--orca-accent-border:rgba(0,191,165,.48);--secondary-accent:#4f9cf9;--status-ok:#00c853;--status-warn:#ffb300;--status-crit:#ff5252;--font-sans:var(--orca-font,"Segoe UI",-apple-system,BlinkMacSystemFont,Roboto,Ubuntu,sans-serif);--font-mono:"Cascadia Code",Consolas,"SFMono-Regular",monospace;--shadow-soft:0 8px 24px rgba(0,0,0,.36);--radius-sm:6px;--radius-md:9px}
[data-theme=light]{color-scheme:light;--bg-app:#edf1f6;--bg-panel:#fff;--bg-card:#f5f7fb;--bg-card-hover:#eaeff6;--bg-input:#fff;--bg-viewport-top:#dce3ec;--bg-viewport-bot:#c6d0dc;--bg-hud:rgba(255,255,255,.91);--border-subtle:#d4dce5;--border-strong:#b6c2cf;--text-main:#1b222c;--text-muted:#525e6f;--text-dim:#798596;--orca-accent:#00897b;--orca-accent-hover:#00796b;--orca-accent-soft:rgba(0,137,123,.12);--orca-accent-border:rgba(0,137,123,.45);--secondary-accent:#2563eb;--status-ok:#169c46;--status-warn:#d47f00;--status-crit:#d93025}
*{box-sizing:border-box}body{margin:0;height:100vh;display:flex;flex-direction:column;background:var(--bg-app);color:var(--text-main);font:13px/1.45 var(--font-sans)}button,input,select{font:inherit;color:inherit}button,select{cursor:pointer}button{display:inline-flex;align-items:center;justify-content:center;gap:7px;border:1px solid var(--border-subtle);border-radius:var(--radius-sm);background:var(--bg-card);padding:7px 10px;line-height:1.2}button:hover:not(:disabled){background:var(--bg-card-hover);border-color:var(--border-strong)}button:active:not(:disabled){transform:translateY(1px)}button:disabled,select:disabled,input:disabled{opacity:.45;cursor:default}button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible,canvas:focus-visible{outline:2px solid var(--orca-accent-hover);outline-offset:2px}h1,h2,h3,p{margin:0}h1{font-size:19px;font-weight:650;letter-spacing:-.6px}h2{font-size:18px;font-weight:650;letter-spacing:-.4px}h3{font-size:14px;letter-spacing:-.2px}p,small,.muted{color:var(--text-muted)}small{font-size:11px}svg.ic{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round;flex:none}.iconbtn{height:30px;width:30px;padding:0}.mono,output,dd,.smallcap{font-family:var(--font-mono)}.smallcap{font-size:10px;letter-spacing:1px;text-transform:uppercase;color:var(--text-muted)}[hidden]{display:none!important}.row{display:flex;align-items:center;gap:8px}.spread{justify-content:space-between}
header{height:60px;flex:none;display:flex;align-items:center;justify-content:space-between;padding:0 20px;gap:12px;border-bottom:1px solid var(--border-subtle);background:var(--bg-panel)}.brand{display:flex;gap:11px;align-items:center}.brandmark{width:36px;height:36px;color:var(--orca-accent-hover);background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:8px;padding:0}.brand h1 span{font-weight:400;color:var(--text-muted)}.connection{color:var(--text-muted);font-size:12px}.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--status-warn)}.dot.live{background:var(--orca-accent)}.work{display:grid;grid-template-columns:clamp(255px,22vw,344px) minmax(250px,1fr) clamp(245px,21vw,356px);min-height:0;flex:1}.side{min-height:0;display:flex;flex-direction:column;background:var(--bg-panel)}.left{border-right:1px solid var(--border-subtle)}.right{border-left:1px solid var(--border-subtle)}.scroll{overflow:auto;scrollbar-width:thin;scrollbar-color:var(--border-strong) transparent;min-height:0;flex:1}.section{padding:18px 17px;border-bottom:1px solid var(--border-subtle)}.sectionhead{display:flex;align-items:center;justify-content:space-between;gap:5px;margin-bottom:12px}.sectionhead h3{display:flex;align-items:center;gap:7px}.sectionhead h3 svg{color:var(--text-muted)}.badge{color:var(--orca-accent-hover);background:var(--orca-accent-soft);border:1px solid var(--orca-accent-border);border-radius:4px;padding:1px 5px;font:11px var(--font-mono)}.outline{background:transparent}.objects{display:grid;gap:6px}.object{display:flex;align-items:flex-start;gap:8px;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:6px;padding:9px}.object:has(input:checked){border-color:var(--orca-accent-border);background:var(--orca-accent-soft)}.object input{margin:4px 0 0;accent-color:var(--orca-accent)}.object strong,.object small{display:block;overflow-wrap:anywhere}.object small{margin-top:2px;font-family:var(--font-mono)}.object strong{font-weight:600}.section>.wide,.section>p+.row{margin-top:10px}.wide{width:100%}.segments{display:flex;padding:3px;border:1px solid var(--border-subtle);border-radius:6px;background:var(--bg-input);gap:3px}.segments button{flex:1;background:transparent;border:0;color:var(--text-muted);padding:6px 7px}.segments button[aria-pressed=true]{background:var(--orca-accent-soft);color:var(--orca-accent-hover);box-shadow:inset 0 0 0 1px var(--orca-accent-border);font-weight:600}.field{margin-top:14px}.fieldtop{display:flex;align-items:center;justify-content:space-between;gap:5px}.unit{font:10px var(--font-mono);color:var(--text-muted)}input[type=number],input[type=text],select{border:1px solid var(--border-strong);border-radius:4px;background:var(--bg-input);padding:4px 6px;min-width:0}input[type=number]{font:12px var(--font-mono);width:68px;text-align:right}input[type=range]{width:100%;height:14px;margin:5px 0 0;accent-color:var(--orca-accent-hover);cursor:pointer}.twocol{display:grid;grid-template-columns:1fr 1fr;gap:9px}.twocol label{display:grid;gap:5px;color:var(--text-muted);font-size:12px}.twocol input{width:100%;text-align:left}details summary{cursor:pointer;color:var(--text-muted);font-size:12px}details[open] summary{margin-bottom:10px}.fieldset{border:0;padding:0;margin:0;min-width:0}.chart{width:100%;height:68px;display:block;margin:12px 0 5px;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:6px}.chart .wave{fill:none;stroke:var(--orca-accent-hover);stroke-width:2;vector-effect:non-scaling-stroke}.chart .axis{stroke:var(--border-subtle);stroke-dasharray:3 4}.presets{width:100%;margin:5px 0}.presetops{display:flex;gap:5px;margin:5px 0}.presetops button{flex:1;font-size:12px}.preset-editor{display:grid;gap:6px;margin-top:8px}.preset-editor input{width:100%}
.viewport{min-height:0;min-width:0;display:flex;flex-direction:column;background:var(--bg-app)}.vhead{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:14px 16px;border-bottom:1px solid var(--border-subtle)}.vhead h2{font-size:17px}.viewtabs button{font-size:11px;white-space:nowrap}.stage{position:relative;flex:1;min-height:175px;overflow:hidden;background:radial-gradient(ellipse at 50% 39%,var(--bg-viewport-top),var(--bg-viewport-bot))}.stage canvas{width:100%;height:100%;display:block;touch-action:none;cursor:grab}.stage canvas:active{cursor:grabbing}.vbuttons{position:absolute;top:12px;right:12px;display:grid;gap:3px}.vbuttons button{background:var(--bg-hud)}.legend{position:absolute;bottom:10px;left:12px;display:flex;gap:12px;color:var(--text-muted);font:11px var(--font-mono);background:var(--bg-hud);padding:5px 7px;border-radius:4px;pointer-events:none}.swatch{display:inline-block;width:12px;height:2px;vertical-align:middle;margin-right:4px}.swatch.modified{background:var(--orca-accent-hover)}.swatch.original{background:var(--secondary-accent)}.empty{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;padding:24px;text-align:center}.empty p{max-width:310px;background:var(--bg-hud);border:1px solid var(--border-subtle);padding:16px 20px;border-radius:var(--radius-md)}.transport{padding:12px 15px;background:var(--bg-panel);border-top:1px solid var(--border-subtle)}.transport .track{flex:1;min-width:35px;margin:0}.transport .readout{font:11px var(--font-mono);color:var(--text-muted);margin-top:9px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}.transport select{font-size:11px;max-width:140px}.xyz{color:var(--text-main);white-space:pre-wrap}.layerrow{display:flex;align-items:center;justify-content:space-between;margin-top:9px;gap:5px}.transport .layerrow small{font-size:10px}.stageinfo{position:absolute;left:13px;top:13px;max-width:65%;pointer-events:none}.stageinfo strong{display:block;color:var(--text-muted);font-size:11px;font-weight:500}.stageinfo .smallcap{font-size:9px}
.state{display:flex;align-items:center;gap:8px;font-weight:600}.state .dot{background:var(--text-dim)}.state.ready .dot{background:var(--orca-accent-hover)}.state.error .dot{background:var(--status-crit)}.state.processing .dot,.state.analyzing .dot,.state.slicing_required .dot{background:var(--status-warn)}.message{margin:7px 0;font-size:12px;overflow-wrap:anywhere}.data{margin:8px 0 0;font-size:12px}.data>div{padding:6px 0;border-top:1px solid var(--border-subtle);display:flex;justify-content:space-between;gap:8px}.data dt{color:var(--text-muted)}.data dd{margin:0;text-align:right;overflow-wrap:anywhere}.flow{display:grid;gap:8px}.foot{padding:14px 16px;border-top:1px solid var(--border-subtle);background:var(--bg-panel)}.foot small{display:block;text-align:center;margin-top:6px}.positive{background:var(--orca-accent);color:white;border-color:var(--orca-accent);font-weight:650;padding:10px}.positive:hover:not(:disabled){background:var(--orca-accent-hover);border-color:var(--orca-accent-hover)}.foot .wide+.wide{margin-top:6px}.notice{padding:8px 12px;background:var(--bg-input);color:var(--status-warn);overflow-wrap:anywhere;font-size:12px}.docktabs{display:none}.path{display:block;overflow-wrap:anywhere;user-select:all;color:var(--text-muted);font:10px/1.5 var(--font-mono);margin-top:7px}.docktabs button[aria-selected=true]{border-color:var(--orca-accent-border);color:var(--orca-accent-hover);background:var(--orca-accent-soft)}
body.compact{height:auto;min-height:100vh}body.compact header{padding:0 10px;height:46px}body.compact .connection{font-size:10px}body.compact .brand{gap:6px}body.compact h1{font-size:15px}body.compact .brandmark{width:27px;height:27px}body.compact .work{display:flex;flex-direction:column}body.compact .viewport{order:-1}body.compact .stage{height:clamp(230px,33vh,360px);flex:auto}body.compact .side{border:0}body.compact .side:not(.shown){display:none}body.compact .docktabs{display:flex;gap:5px;padding:6px 10px;background:var(--bg-panel);border-bottom:1px solid var(--border-subtle)}body.compact .docktabs button{flex:1}body.compact .scroll{overflow:visible}body.compact .section{padding:13px 15px}body.compact .vhead{padding:8px 10px;flex-wrap:wrap}body.compact .vhead h2{font-size:14px}body.compact .transport{padding:8px 10px}body.compact .foot{position:sticky;bottom:0}body.compact .layerrow small{display:none}@media(max-width:580px){.connection{max-width:137px;line-height:1.15}.transport .readout{gap:6px}.vhead{flex-wrap:wrap}.viewtabs{max-width:100%}}@media(max-height:660px) and (min-width:841px){.section{padding:11px 14px}.field{margin-top:8px}header{height:48px}}
.object{align-items:center}.object .pick-object{display:block;flex:1;min-width:0;text-align:left;padding:2px 4px;background:transparent;border:1px solid transparent}.object .pick-object[aria-pressed=true]{border-left:2px solid var(--orca-accent-hover);border-radius:0;padding-left:7px}.edit-target{display:block;color:var(--orca-accent-hover);font-size:12px;margin:-4px 0 10px;overflow-wrap:anywhere}
.guide-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;padding:12px 18px;border-bottom:1px solid var(--border-subtle);background:var(--bg-panel)}.guide-steps button{justify-content:flex-start;text-align:left;padding:10px 12px;color:var(--text-muted);background:transparent}.guide-steps b{display:inline-grid;place-items:center;width:25px;height:25px;border:1px solid var(--border-strong);border-radius:50%;flex:none}.guide-steps [aria-current=step]{border-color:var(--orca-accent-border);background:var(--orca-accent-soft);color:var(--text-main)}.guide-steps [aria-current=step] b{background:var(--orca-accent);border-color:var(--orca-accent);color:white}.guide-controls{display:grid;gap:8px}.guide-controls small{text-align:left}.guide-help h2{margin-bottom:9px}.guide-help p{line-height:1.65}.guide-summary strong{display:block;margin-top:7px;overflow-wrap:anywhere}.guide-warning{padding:10px;border-left:3px solid var(--status-warn);background:var(--bg-input);color:var(--text-muted);margin-top:15px}.guided .object small:first-of-type{display:none}.guided .study-modes,.guided .edit-target,.guided .surface-info,.guided #suggest,.guided #analyze,.guided .viewtabs,.guided #generate,.guided #preview,.guided #bench-note,.guided .panel-help,.guided #metadata,.guided #result-path{display:none!important}.guided #wall-selection>h3{display:none}.guided #wall-selection{margin-top:0}.guided[data-guide-step="1"] #area-section,.guided[data-guide-step="1"] #guide-summary,.guided[data-guide-step="2"] #model-section,.guided[data-guide-step="2"] #guide-summary{display:none}.guided[data-guide-step="3"] #model-section,.guided[data-guide-step="3"] #area-section,.guided[data-guide-step="4"] #model-section,.guided[data-guide-step="4"] #area-section{display:none}.guided #guide-back{background:transparent}.guided #guide-next{min-height:42px}.guided #guide-details{margin:0 16px 16px}.guided #guide-details>summary{padding:8px 0}.guided .vhead h2{font-size:16px}.guided[data-study-ready="false"] .transport{display:none}.guided.compact .connection{display:none}.guided.compact .side:not(.shown){display:flex}.guided .docktabs{display:none!important}.guided.compact header{gap:5px}.guided.compact .brand h1{font-size:13px}.guided #profile-card{padding-top:13px;padding-bottom:13px}.guided #guide-help{min-height:180px}@media(max-width:840px){.guide-steps{grid-template-columns:repeat(2,minmax(0,1fr));padding:8px;gap:5px}.guide-steps button{font-size:12px;padding:7px}.guide-steps b{width:22px;height:22px}.guided #guide-help{min-height:0}}
/* Orca also injects element defaults, including a native foreground for headings. */
html[data-theme=dark]{--orca-accent:#00a896;color-scheme:dark}html[data-theme=light]{--orca-accent:#00897b;color-scheme:light}
body[data-mode]{background:var(--bg-app);color:var(--text-main);font-family:var(--font-sans)}
body h1,body h2,body h3,body label,body input,body select{color:var(--text-main)}
body select{appearance:none;-webkit-appearance:none;background-color:var(--bg-input)!important;color:var(--text-main)!important;padding-right:22px;background-image:linear-gradient(45deg,transparent 50%,var(--text-muted) 50%),linear-gradient(135deg,var(--text-muted) 50%,transparent 50%);background-position:calc(100% - 12px) 50%,calc(100% - 8px) 50%;background-size:4px 4px;background-repeat:no-repeat}
body button{color:var(--text-main);background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:var(--radius-sm);padding:7px 10px}
.panel-help{margin:8px 0;color:var(--text-muted);font-size:11px}.panel-help summary{font-size:11px}
body.compact header:has(#panel-action:not([hidden])){height:auto;min-height:46px;flex-wrap:wrap;padding-top:5px;padding-bottom:5px}
.study-modes{display:grid;grid-template-columns:1fr 1fr}.study-modes button{min-width:0;font-size:12px}.surface-mode .wave-only,.surface-mode #suggest,.surface-mode #analyze,.surface-mode #prepare-capture,.combined-mode #suggest{display:none!important}.surface-info{color:var(--text-muted);font-size:12px;margin:10px 0}.surface-mode .object:has(input:checked){background:var(--bg-input);border-color:var(--border-subtle)}.surface-mode .object:has(.pick-object[aria-pressed=true]){background:var(--bg-input);border-color:var(--border-subtle)}
.safety-warning{flex-shrink:0;padding:8px 16px;background:#382b13;color:#ffdd91;border-bottom:1px solid #8a661f;font-size:12px;overflow-wrap:anywhere}#placement-tools .row input{min-width:0;width:72px}#placement-tools label{display:block;margin:7px 0;color:var(--text-muted);font-size:12px}#placement-tools input{display:block;width:100%;padding:6px;background:var(--bg-input);border:1px solid var(--border-strong);border-radius:var(--radius-sm)}#head-map-editor{margin-top:12px}
.guided.compact .work,.guided.compact .side,.guided.compact .scroll{flex:none}.guided.compact .foot{position:static}#language{max-width:125px}
</style></head>
<body class="guided surface-mode" data-mode="__LAYOUT__">
<div class="safety-warning" role="alert" id="safety-warning"><strong id="warning-title">AVISO — Use por sua conta e risco.</strong> <span id="warning-body">Não imprima sem supervisão até ter 100% de certeza de que as trajetórias são seguras para sua impressora.</span></div>
<header><div class="brand">__BRAND_ICON__<h1>Orca <b>Surface</b> <span>Studio</span></h1></div><div class="row"><i id="link-dot" class="dot"></i><span id="connection" class="connection"></span><button id="theme" class="iconbtn" aria-label="Alternar tema" title="Alternar tema" data-icon="sun"></button></div></header>
<main class="work"><aside class="side left shown" id="config"><div class="scroll">
__PLACEMENT_MARKUP__
<section class="section"><div class="sectionhead"><h3><i data-icon="box"></i> Objetos da mesa</h3><button class="iconbtn outline" id="refresh" aria-label="Atualizar mesa" title="Atualizar mesa" data-icon="refresh"></button></div><div id="objects" class="objects"></div></section>
<section class="section"><div class="sectionhead"><h3><i data-icon="wave"></i> Parâmetros da trajetória</h3><span class="badge">mm</span></div><fieldset class="fieldset" id="params"><div id="primary-fields"></div></fieldset><p id="validation" class="message" aria-live="polite" hidden></p></section>
</div></aside>
<section class="viewport" aria-label="Trajetória tridimensional"><div class="vhead"><h2>Trajetória 3D</h2></div>
<div class="stage"><canvas id="canvas" tabindex="0" aria-label="Trajetória em três dimensões. Arraste para girar ou use as setas. Use mais e menos para aproximar e afastar."></canvas><div class="stageinfo"><span class="smallcap">Vista ortográfica</span><strong id="point-label"></strong></div><div class="vbuttons"><button data-icon="fit" id="fit" class="iconbtn" aria-label="Enquadrar trajetória" title="Enquadrar trajetória"></button><button data-icon="plus" id="zoom-in" class="iconbtn" aria-label="Aproximar" title="Aproximar"></button><button data-icon="minus" id="zoom-out" class="iconbtn" aria-label="Afastar" title="Afastar"></button></div><div class="empty" id="empty"><p id="empty-msg"></p></div><div class="legend" aria-hidden="true"><span id="legend-original"><i class="swatch original"></i><span id="legend-original-label">Original</span></span><span id="legend-modified"><i class="swatch modified"></i><span id="legend-modified-label">Com ondas</span></span></div></div>
<div class="transport"><div class="row"><button id="play" class="iconbtn" aria-label="Reproduzir percurso" title="Reproduzir percurso" data-icon="play"></button><input class="track" id="scrub" type="range" min="0" max="0" value="0" step="1" aria-label="Posição do bico no percurso"><output id="pct">—</output></div><div class="readout"><span>Bico (mm)</span><output class="xyz" id="xyz">X —   Y —   Z —</output></div><div class="layerrow"><label><span id="layer-label">Camada</span> <select id="layer"></select></label><small>Arraste para orbitar · role para zoom</small></div></div></section>
<aside class="side right" id="review"><div class="scroll">
<section class="section"><div class="sectionhead"><h3><i data-icon="pulse"></i> Diagnóstico</h3></div><div class="state" id="status"><i class="dot"></i><span id="status-name"></span></div><p id="message" class="message" aria-live="polite"></p><dl id="metadata" class="data"></dl></section>
<section class="section"><div class="sectionhead"><h3><i data-icon="layers"></i> Resultado</h3></div><p id="result-note" class="message"></p><dl class="data" id="metrics"></dl><span class="path" id="result-path"></span></section></div>
<footer class="foot" id="study-actions"><div id="action-note" class="notice" hidden></div></footer></aside></main>
<script id="initial-state" type="application/json">__STATE__</script>
<script>
'use strict';
const $ = id => document.getElementById(id);
const languagePacks=__LANGUAGE_PACKS__;
let language='pt';
function resolveLanguage(value){
  let code=String(value||'pt').toLowerCase().replaceAll('_','-');
  while(code){if(Object.hasOwn(languagePacks,code))return code;code=code.includes('-')?code.slice(0,code.lastIndexOf('-')):''}
  return 'en';
}
function warning(key){return languagePacks[language]?.translations[key]||languagePacks.en.translations[key]}
function renderLanguage(){
  $('language').value=language;document.documentElement.lang=language;
  document.documentElement.dir=languagePacks[language].direction;
  $('warning-title').textContent=warning('warning_title');$('warning-body').textContent=warning('warning_body');
  $('language').setAttribute('aria-label',warning('language'));$('language').title=warning('language');
}
const languageSelect=document.createElement('select');languageSelect.id='language';
for(const [code,pack] of Object.entries(languagePacks))languageSelect.append(new Option(pack.native_name,code));
$('theme').before(languageSelect);
languageSelect.onchange=()=>{language=resolveLanguage(languageSelect.value);render();send('set_language',{language})};

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
function activeBridge(){return [window.orca,window.chrome?.webview,window.webkit?.messageHandlers?.orca].find(b=>typeof b?.postMessage==='function')}
let linked=Boolean(activeBridge());
let state={},selection=new Set(),pending=null,activeId=null,pendingBuildId=null;
const surfaceMode=true,guidedMode=true;
let guideStep=1,guideModelId=null,guideAwaitStudy=false;
const surfaceByObject=new Map();
const surfaceSettings=()=>{
  const value={step_mm:.4,max_slope_deg:30,retain_native_short_edges:true,backend:'continuous_layers',region_id:null,
    selection_mode:'all',selection_revision:null,wall_selection:[],...surfaceByObject.get(activeId)};
  // A rejected reduced-adaptation trial must not become the guided default.
  delete value.adaptation_strength;
  if(!value.placement_degrees)delete value.placement_degrees;
  if(!['native_local','continuous_layers'].includes(value.backend))for(const key of ['selection_mode','selection_revision','wall_selection'])delete value[key];
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
const numberFormat=(v,n=2)=>Number.isFinite(v)?v.toLocaleString('pt-BR',{maximumFractionDigits:n}):'—';
// Native JSON bridges may reorder dictionary keys, including nested click rays.
// Arrays retain their order: changing a ray or its coordinates still invalidates.
const stableJSON=value=>JSON.stringify(value,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)
  ?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
const signature=()=>stableJSON(['surface',state.revision||'',activeId,surfaceSettings()]);
function activate(id){
  if(id!==activeId){guideStep=1;guideModelId=null;guideAwaitStudy=false}
  activeId=id;
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
function send(action,extra={}){
  if(!linked)return false;
  try{const bridge=activeBridge(),obj={action,...(action==='build_surface'?{object_ids:[activeId],settings:{...surfaceSettings()}}:{}),...extra};
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
function presentResult(){
  const result=state.result,source=result?.report?.source_sha256;
  if(result?.settings?.backend==='continuous_layers'&&
     (result.report?.warp?.transition_kernel!=='cubic_spline_phase_v1'||result.report?.warp?.reference_certificate_version!==2))return false;
  return Boolean(result?.sha256)&&state.status==='ready'&&!pending&&
    surfaceMode===(['surface','conformal'].includes(result.study_kind))&&
    (!result.revision||result.revision===state.revision)&&
    (result.workflow==='integrated'||result.study_kind==='surface'||!source||source===state.capture?.sha256)&&resultConfig===signature();
}
const primary=$('primary-fields');
const wallBox=node('div','field');wallBox.id='wall-selection';
wallBox.append(node('h3','','Paredes a suavizar'));
const wallModes=node('div','segments'),wallPaint=node('button','','Pintar áreas'),wallAll=node('button','','Peça inteira');
wallPaint.id='wall-paint';wallAll.id='wall-all';wallModes.append(wallPaint,wallAll);wallBox.append(wallModes);
const brushRow=node('label','fieldtop','Raio da área'),brushInput=node('input');
brushInput.type='number';brushInput.min='1';brushInput.max='15';brushInput.step='1';brushInput.value='6';brushInput.id='wall-radius';
brushRow.htmlFor=brushInput.id;brushRow.append(brushInput,node('span','unit','mm'));wallBox.append(brushRow);
brushInput.oninput=()=>{if(Number.isFinite(brushInput.valueAsNumber)&&brushInput.valueAsNumber>=1&&brushInput.valueAsNumber<=15)brushRadius=brushInput.valueAsNumber};
brushInput.onchange=()=>{if(!brushInput.checkValidity()||!Number.isFinite(brushInput.valueAsNumber)){brushInput.value=String(brushRadius);notice('Use um raio entre 1 e 15 mm. O último valor válido foi mantido.')}};
const wallHint=node('small','','Clique para acrescentar áreas; arraste para girar. A área inclui a espessura e pode alcançar paredes próximas. Velocidade nas áreas: 80% do perfil.'),wallList=node('div');
wallList.id='wall-areas';wallList.setAttribute('aria-live','polite');
const wallClear=node('button','outline','Limpar seleção');wallClear.id='wall-clear';
const wallAllHint=node('small','','Alinha as camadas ao teto e às bordas compatíveis da peça inteira. Esse cálculo pode levar vários minutos. Para limitar a região, escolha Pintar áreas.');wallBox.append(wallHint,wallAllHint,wallList,wallClear);primary.append(wallBox);
wallPaint.onclick=()=>{surfaceByObject.set(activeId,{...surfaceSettings(),backend:'native_local',selection_mode:'paint'});render()};
wallAll.onclick=()=>{surfaceByObject.set(activeId,{...surfaceSettings(),backend:'continuous_layers',selection_mode:'all',wall_selection:[],selection_revision:null});wallMarks.delete(activeId);render()};
wallClear.onclick=()=>{surfaceByObject.set(activeId,{...surfaceSettings(),wall_selection:[],selection_revision:null});wallMarks.delete(activeId);render()};
function pickWall(ray,point){
  if(guidedMode&&guideStep!==2)return;
  const settings=surfaceSettings();if(controlsBusy()||!surfaceMode||settings.backend!=='native_local'||settings.selection_mode!=='paint')return;
  if(settings.wall_selection.length>=24){notice('Use até 24 áreas. Remova uma área para acrescentar outra.');return}
  if(!brushInput.checkValidity()||!Number.isFinite(brushInput.valueAsNumber)){notice('Confira o raio da área antes de selecionar.');return}
  if(settings.selection_revision&&settings.selection_revision!==state.revision){notice('Limpe a seleção anterior antes de escolher novas áreas.');return}
  const marks=[...(wallMarks.get(activeId)||[]).slice(0,settings.wall_selection.length),{center:point,radius_mm:brushRadius}];wallMarks.set(activeId,marks);
  surfaceByObject.set(activeId,{...settings,selection_revision:state.revision,
    wall_selection:[...settings.wall_selection,{...ray,radius_mm:brushRadius}]});notice('');render();
}
function objects(){
  const list=$('objects');list.replaceChildren();
  if(!state.objects?.length){list.append(node('p','message','Nenhum objeto disponível nesta mesa.'));return}
  for(const obj of state.objects){
    const item=node('div','object'),info=node('button','pick-object');
    const id=String(obj.id);
    info.disabled=controlsBusy();info.setAttribute('aria-pressed',String(id===activeId));
    info.title='Escolher áreas de '+(obj.name||id);info.onclick=()=>{
      activate(id);guideModelId=id;guideStep=2;render()
    };
    const dims=obj.dimensions_mm||(obj.bounds?.length===2?obj.bounds[1].map((v,i)=>v-obj.bounds[0][i]):[]);
    info.append(node('strong','',obj.name||'Objeto'),node('small','','ID '+id+' · '+(obj.instances??'—')+' cópia(s)'));
    if(dims.length===3)info.append(node('small','',dims.map(n=>numberFormat(n,1)).join(' × ')+' mm'));
    item.append(info);list.append(item);
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
  const meta=$('metadata');meta.replaceChildren();
  if(surfaceMode)record(meta,'Objeto em estudo',activeId||'—');else record(meta,'Objetos selecionados',String(selection.size));
  record(meta,'Revisão da mesa',state.revision?.slice(0,10)||'—',state.revision);
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
  if(surfaceMode&&['native_local','continuous_layers'].includes(r.settings?.backend)){
    record(metrics,'Método',r.settings?.backend==='continuous_layers'?'Camadas contínuas':'Contorno local do Orca');record(metrics,'Regiões','Superfícies superiores compatíveis');
    if(rep.wall_selection?.mode==='paint'){
      record(metrics,'Áreas escolhidas',rep.wall_selection.areas.length);
      record(metrics,'Velocidade nas áreas','80% do perfil');
      const angle=rep.motion_slope_review?.maximum_deg??rep.wall_selection_audit?.maximum_motion_slope_deg;
      if(Number.isFinite(angle))record(metrics,'Maior inclinação do percurso',numberFormat(angle,1)+'°');
      if(angle>r.settings.max_slope_deg)$('result-note').textContent='Somente Preview: há movimentos mais inclinados que o limite do estudo. O arquivo não está liberado para imprimir.';
    }
    if(rep.wall_selection?.mode==='all'){
      record(metrics,'Abrangência','Peça inteira · superfícies compatíveis');
      record(metrics,'Maior inclinação do percurso',numberFormat(rep.motion_slope_review?.maximum_deg,1)+'°');
    }
    if(rep.contour_coverage){
      record(metrics,'Deposições ajustadas em Z',rep.contour_coverage.adjusted_deposition_segments);
      record(metrics,'Camadas com ajuste em Z',rep.contour_coverage.affected_layer_count);
      record(metrics,'Acabamento sem degraus','Não certificado');
    }
    if(rep.finishing){
      record(metrics,'Camadas de acabamento',numberFormat(rep.finishing.finishing_layer_mm,3)+' mm');
      record(metrics,'Amostragem vertical',numberFormat(rep.finishing.sampling_reduction_percent,0)+'% menor que a nominal');
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
__MODEL_PREVIEW_SCRIPT__
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
    const nearest=displayRayDistance(this.mesh.flat,origin,direction);
    return nearest!==null?{ray:{origin,direction},point:origin.map((v,i)=>v+nearest*direction[i])}:null;
  }

  selectedAreas(){
    return surfaceMode&&surfaceSettings().backend==='native_local'&&surfaceSettings().selection_mode==='paint'
      ?(presentResult()?state.result?.report?.wall_selection?.areas:(wallMarks.get(activeId)||[]).slice(0,surfaceSettings().wall_selection.length))||[]:[];
  }
  makeBuffer(data){
    if(!this.gl||this.lost)return null;
    const g=this.gl,buf=g.createBuffer();g.bindBuffer(g.ARRAY_BUFFER,buf);
    g.bufferData(g.ARRAY_BUFFER,data instanceof Float32Array?data:new Float32Array(data),g.STATIC_DRAW);this.buffers.push(buf);return buf;
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
    const {flat:mesh,shades}=displaySurface(r?.model?.objects?.filter(o=>!activeId||String(o.id)===activeId)||[]);
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
      g.uniform1i(u.point,false);g.uniform4fv(u.color,this.light?[.57,.66,.70,1]:[.38,.52,.57,1]);
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
function render(){
  renderLanguage();
  const busy=controlsBusy(),current=presentResult();
  const active=(state.objects||[]).find(o=>String(o.id)===activeId);
  document.body.classList.add('surface-mode');
  wallBox.hidden=false;
  const wallOptions=surfaceSettings(),painting=wallOptions.selection_mode==='paint';
  $('canvas').style.cursor=painting&&!busy&&guideStep===2?'crosshair':'grab';
  wallPaint.setAttribute('aria-pressed',String(painting));wallAll.setAttribute('aria-pressed',String(!painting));
  wallPaint.disabled=wallAll.disabled=brushInput.disabled=busy;brushRow.hidden=wallHint.hidden=wallList.hidden=wallClear.hidden=!painting;
  wallAllHint.hidden=painting;wallClear.disabled=busy||!wallOptions.wall_selection?.length;
  wallList.replaceChildren();
  (wallOptions.wall_selection||[]).forEach((area,i)=>{
    const remove=node('button','outline','Área '+(i+1)+' · '+numberFormat(area.radius_mm)+' mm ×');
    remove.setAttribute('aria-label','Remover área '+(i+1));remove.disabled=busy;
    remove.onclick=()=>{const rows=[...wallOptions.wall_selection];rows.splice(i,1);
      const marks=[...(wallMarks.get(activeId)||[])];marks.splice(i,1);wallMarks.set(activeId,marks);
      surfaceByObject.set(activeId,{...wallOptions,wall_selection:rows,selection_revision:rows.length?wallOptions.selection_revision:null});render()};wallList.append(remove);
  });
  const stage=state.conformal?.phase;
  $('layer-label').textContent='Grupo de percurso';
  document.querySelector('.readout span').textContent='Ponto (mm)';
  $('legend-original-label').textContent='Referência';
  $('legend-modified-label').textContent='Superfície';
  $('link-dot').classList.toggle('live',linked&&!state.demo);
  $('connection').textContent=linked&&!state.demo?'OrcaSlicer conectado':'Demonstração de bancada • não conectado ao Orca';
  panelAction.hidden=!linked||Boolean(state.demo);
  $('refresh').disabled=!linked||busy;
  $('params').disabled=busy||!active||Boolean(stage);
  objects();diagnostics(current);
  profileCard.textContent=state.printer_profile?.name||'Selecione uma impressora no Orca';
  profileDetails.textContent=state.printer_profile?.issue||
    (state.printer_profile?.nozzle_mm?'Bico '+numberFormat(state.printer_profile.nozzle_mm)+' mm · camada '+numberFormat(state.printer_profile.layer_mm)+' mm · '+state.printer_profile.firmware:'O perfil acompanha a seleção feita no Orca.');
  cancelBuild.hidden=!(state.status==='processing'&&!stage);cancelBuild.disabled=false;
  renderPlacement(active,busy,current);
  const tag=[current?state.result.sha256:'model',state.model_preview?.id,activeId,surfaceSettings().placement_degrees||0].join('/');
  if(sceneTag!==tag){stop();sceneTag=tag;viewer.load({...current?state.result:{},model:placementModel(state.model_preview)});$('scrub').value=0;setLayers()}
  else viewer.draw();
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
  if(hasModel&&!n)$('point-label').textContent=(surfaceSettings().placement_degrees?'Cópia girada '+surfaceSettings().placement_degrees+'°':'Modelo')+' · '+(busy?'calculando trajetórias…':'arraste para mudar a vista');
  renderGuide(active,current,busy);
}
const profileBox=node('section','section'),profileCard=node('strong'),profileDetails=node('p','muted');
profileBox.append(node('h3','','Perfil selecionado no Orca'),profileCard,profileDetails);
document.querySelector('#config .section').after(profileBox);
const cancelBuild=node('button','wide outline','Cancelar cálculo');cancelBuild.id='cancel-build';cancelBuild.hidden=true;
$('study-actions').append(cancelBuild);cancelBuild.onclick=()=>send('cancel_build');
function request(action,extra={}){
  if(!linked||controlsBusy())return;
  notice('');pending=action;
  if(action==='build_surface'){
    pendingBuildId=globalThis.crypto?.randomUUID?.()||Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
    extra={...extra,client_request_id:pendingBuildId};
  }
  if(['generate','surface_study','generate_conformal','build_surface'].includes(action))generation=signature();
  render();
  if(!send(action,extra)){pending=null;pendingBuildId=null;generation=null;render()}
}
$('refresh').onclick=()=>request('refresh');
$('theme').onclick=()=>{viewer.light=!viewer.light;document.documentElement.dataset.theme=viewer.light?'light':'dark';viewer.draw()};
function compact(){document.body.classList.toggle('compact',document.body.dataset.mode==='dock'||window.innerWidth<=840)}
window.addEventListener('resize',compact);compact();
const guideSteps=node('nav','guide-steps');guideSteps.id='guide-steps';guideSteps.setAttribute('aria-label','Passos do estudo');
const guideLabels=['Modelo','Áreas a suavizar','Cálculo','Preview e envio'];
const guideStepButtons=guideLabels.map((label,i)=>{
  const b=node('button');b.id='guide-step-'+(i+1);b.setAttribute('aria-label','Passo '+(i+1)+': '+label);
  b.append(node('b','',String(i+1)),node('span','',label));
  b.onclick=()=>{if(i+1<=guideStep&&!controlsBusy()){guideStep=i+1;guideAwaitStudy=false;render()}};
  guideSteps.append(b);return b;
});document.querySelector('header').after(guideSteps);
const sendReviewButton=node('button','outline','Conferir envio');sendReviewButton.id='send-review';$('theme').before(sendReviewButton);
sendReviewButton.setAttribute('aria-label','Conferir envio para impressora');sendReviewButton.title='Abrir a conferência de envio sem iniciar impressão';
sendReviewButton.onclick=()=>send('open_send_dialog',state.result?.sha256?{sha256:state.result.sha256}:{});
$('objects').closest('section').id='model-section';$('params').closest('section').id='area-section';profileBox.id='profile-card';
const guideSummary=node('section','section guide-summary');guideSummary.id='guide-summary';
guideSummary.append(node('h3','','Seu estudo'));const guideModelName=node('strong'),guideAreaCount=node('p','message'),guideFinish=node('p','message'),guideSpeed=node('small');guideSummary.append(guideModelName,guideAreaCount,guideFinish,guideSpeed);profileBox.after(guideSummary);
const guideHelp=node('section','section guide-help');guideHelp.id='guide-help';
const guideHeading=node('h2'),guideText=node('p'),guideWarning=node('p','guide-warning');guideWarning.id='guide-warning';guideHelp.append(guideHeading,guideText,guideWarning);
const guideProgress=node('div','guide-progress');guideProgress.id='guide-progress';guideProgress.setAttribute('role','status');
const guidePhase=node('p'),guideElapsed=node('small');guideProgress.append(guidePhase,guideElapsed);guideHelp.append(guideProgress);
const guideSelection=node('p');guideSelection.id='guide-selection';guideSelection.setAttribute('aria-live','polite');guideHelp.append(guideSelection);
const reviewScroll=document.querySelector('#review>.scroll');reviewScroll.prepend(guideHelp);
const guideDetails=node('details');guideDetails.id='guide-details';guideDetails.append(node('summary','','Detalhes do estudo'));
guideDetails.append($('status').closest('section'),$('metrics').closest('section'));reviewScroll.append(guideDetails);
const guideControls=node('div','guide-controls'),guideNext=node('button','wide positive'),guideBack=node('button','wide outline','Voltar'),guideFootNote=node('small');
const guideSend=node('button','wide outline','Conferir envio');guideSend.id='guide-send';guideSend.onclick=()=>sendReviewButton.click();
guideControls.id='guide-controls';guideNext.id='guide-next';guideBack.id='guide-back';guideFootNote.id='guide-foot-note';guideControls.append(guideNext,guideSend,guideBack,guideFootNote);$('study-actions').prepend(guideControls);
guideBack.onclick=()=>{if(!controlsBusy()){guideStep=guideStep===4?2:Math.max(1,guideStep-1);guideAwaitStudy=false;render()}};
guideNext.onclick=()=>{
  if(guideNext.disabled)return;
  if(guideStep===1){guideModelId=activeId;guideStep=2;render()}
  else if(guideStep===2||guideStep===3){
    if(presentResult()){guideStep=4;render();return}
    guideStep=3;guideAwaitStudy=true;request('build_surface',{open_preview:false})
  }
  else if(presentResult())send('open_preview',{sha256:state.result.sha256});
};
function renderGuide(active,current,busy){
  sendReviewButton.hidden=!(state.native&&(state.send_preview_available||current));
  sendReviewButton.disabled=busy;
  sendReviewButton.textContent='Conferir envio';
  const on=guidedMode&&surfaceMode;document.body.classList.toggle('guided',on);
  guideSteps.hidden=guideControls.hidden=guideHelp.hidden=guideSummary.hidden=!on;
  $('model-section').querySelector('h3').textContent=on?'Modelos na bandeja':'Objetos da mesa';
  $('area-section').querySelector('h3').textContent=on?'Áreas da peça':'Parâmetros da trajetória';
  guideDetails.hidden=on?guideStep<3:false;
  if(current&&!busy&&(guideAwaitStudy||guideStep===3||guideModelId===null)){guideModelId=activeId;guideStep=4;guideAwaitStudy=false}
  if(state.status==='error'&&!pending)guideAwaitStudy=false;
  if(guideStep>1&&guideModelId!==activeId){guideStep=1;guideAwaitStudy=false}
  if(guideStep===4&&!current){guideStep=3;guideAwaitStudy=false}
  document.body.dataset.guideStep=String(guideStep);
  document.body.dataset.studyReady=String(current);
  guideDetails.hidden=guideStep<3;
  guideStepButtons.forEach((button,i)=>{button.disabled=busy||i+1>guideStep;button.toggleAttribute('aria-current',i+1===guideStep);if(i+1===guideStep)button.setAttribute('aria-current','step')});
  const previewOnly=!active&&state.send_preview_available;
  guideHeading.textContent=previewOnly?'G-code aberto no Preview':guideLabels[guideStep-1];
  const choices=surfaceSettings(),areaCount=choices.wall_selection?.length||0,
    count=choices.selection_mode==='all'?'Peça inteira · superfícies compatíveis':areaCount+(areaCount===1?' área selecionada':' áreas selecionadas');
  guideModelName.textContent=active?.name||'Escolha um modelo';guideAreaCount.textContent=count;guideSpeed.textContent=choices.selection_mode==='all'?'Velocidades do perfil selecionado.':'Velocidade nas áreas: 80% do perfil.';
  const finish=current?state.result?.report?.finishing:null;
  const beads=current?state.result?.report?.bead_deposition:null;
  guideFinish.textContent=beads?.maximum_supported_height_mm?'Altura efetiva do cordão: '+numberFormat(beads.minimum_supported_height_mm,3)+'–'+numberFormat(beads.maximum_supported_height_mm,3)+' mm. Material calculado automaticamente.':finish&&choices.backend==='continuous_layers'?'Camadas alinhadas às superfícies da peça.':finish?'Acabamento: camadas de '+numberFormat(finish.finishing_layer_mm,3)+' mm nas faixas escolhidas.':'Acabamento ajustado automaticamente ao perfil.';
  guideText.textContent=previewOnly?'Este arquivo já está fatiado. Use Conferir envio para revisar a impressora e as verificações pendentes. Para mudar as áreas, abra o projeto original.':
    guideStep===1?(active?'Clique no modelo da lista para escolher suas áreas. Se ele já está destacado, use Escolher áreas.':'Adicione um modelo à placa do Orca e clique em Atualizar.'):
    guideStep===2?(choices.selection_mode==='all'?'Peça inteira selecionada. Para limitar o cálculo, escolha Pintar áreas e clique na peça.':'Clique nas áreas que quer suavizar. As marcas mostram o que será calculado. Arraste para girar.'):
    guideStep===3?(busy?'Pode acompanhar o cálculo aqui. O modelo original será preservado.':state.status==='error'?friendlyStudyError(state.message):'O cálculo foi interrompido. Tente novamente ou volte para ajustar as áreas.'):
    state.result?.native_preview?'Resultado aberto no Preview do Orca. Confira o movimento antes do envio.':'Confira o movimento com ▶ e abra o Preview do Orca. Depois use Conferir envio.';
  guideProgress.hidden=guideStep!==3||!busy;
  guidePhase.textContent=pendingBuildId?'Preparando o cálculo no Orca…':state.calculation?.phase||state.message||'Preparando o cálculo…';
  const seconds=state.calculation?.elapsed_seconds;
  guideElapsed.textContent=Number.isFinite(seconds)?'Tempo decorrido: '+Math.floor(seconds/60)+' min '+seconds%60+' s · você pode cancelar abaixo.':'Aguardando o Orca…';
  guideSelection.hidden=guideStep!==2;
  guideSelection.textContent=surfaceError()||count+' · pronto para calcular.';
  guideWarning.hidden=guideStep!==4||Boolean(state.result?.report?.print_allowed);
  guideWarning.textContent=warning(beads?.below_profile_minimum_occurrences?'warning_bead':'warning_preview');
  guideNext.textContent=guideStep===1?'Escolher áreas':guideStep===2?(current?'Ver resultado já calculado':'Calcular e preparar Preview'):guideStep===3?(busy?'Calculando…':'Tentar novamente'):'Ver no Preview do Orca';
  guideNext.disabled=!linked||busy||!active||(guideStep===2&&Boolean(surfaceError()))||(guideStep===3&&Boolean(surfaceError()))||(guideStep===4&&!current);
  guideBack.hidden=guideStep===1;guideBack.disabled=busy;
  guideSend.hidden=!(previewOnly||guideStep===4&&current&&state.native);guideSend.disabled=busy;
  guideNext.hidden=previewOnly;
  guideFootNote.textContent=guideStep===2?(choices.selection_mode==='all'?'Peça inteira exige mais cálculo. O perfil do Orca será usado automaticamente.':'Seleção pronta? Um clique calcula e prepara o resultado.'):guideStep===3?'Nenhum arquivo é enviado à impressora durante o cálculo.':guideStep===4?'Conferir envio abre a revisão. A impressão exige uma ação separada.':'';
  $('action-note').hidden=!$('action-note').textContent;
  $('validation').hidden=true;
  document.querySelector('.vhead h2').textContent=guideStep<3?'Seu modelo':'Movimento da peça';
}
function friendlyStudyError(message=''){
  if(/BEAD_HEIGHT|altura.*(?:cordão|mínima)|espaçamento/i.test(message))return 'O espaçamento ficou fora dos limites do perfil. Volte e escolha uma área menor para testar. O original foi preservado; veja o motivo em Detalhes do estudo.';
  if(/cancelad/i.test(message))return 'Cálculo cancelado. Você pode tentar novamente ou voltar para ajustar as áreas.';
  if(/permiss|access|acesso|audit/i.test(message))return 'O cálculo precisa de uma autorização no Orca. Confira a janela de permissão e tente novamente.';
  return 'Não foi possível concluir o cálculo. Volte para conferir as áreas e o perfil. O motivo completo está em Detalhes do estudo.';
}
function applyState(next){
  if(!next||typeof next!=='object'||Array.isArray(next))return;
  // Background mesh analysis temporarily publishes an empty object list.
  // Keep the last known objects disabled until the replacement arrives so
  // selections and per-object edits are not deleted between the two replies.
  if(next.status==='analyzing'&&next.revision===state.revision&&!next.objects?.length&&state.objects?.length)
    next={...next,objects:state.objects};
  if(Number.isFinite(next.sequence)&&next.sequence<hostSequence)return;
  if(next.model_preview?.unchanged){
    if(next.model_preview.id!==state.model_preview?.id||!state.model_preview?.objects){send('refresh');return}
    next={...next,model_preview:state.model_preview};
  }
  if(Number.isFinite(next.sequence))hostSequence=next.sequence;
  // Polls advance the server sequence even when the visible data is identical.
  // Avoid rebuilding focused object buttons and preset menus on those replies.
  const stamp=JSON.stringify([next.native,next.demo,next.status,next.message,next.revision,
    next.capture?.capture_id,next.capture?.sha256,next.capture_setup_required,next.objects,
    next.language,next.selected_object_ids,next.conformal,next.model_preview?.id,
    next.result?.sha256,next.result?.study_kind,next.result?.object_id,next.result?.settings,next.result?.package_path,
    next.result?.report?.print_allowed,next.result?.report?.bead_deposition?.below_profile_minimum_occurrences,
    next.send_preview_available,next.head_map,next.calculation,next.build_client_request_id]);
  if(!pending&&stamp===stateStamp){state=next;schedulePoll();return}
  stateStamp=stamp;
  const first=!Object.keys(state).length,priorRev=state.revision;
  const oldIds=new Set((state.objects||[]).map(o=>String(o.id)));
  const waitingForBuild=pendingBuildId&&next.build_client_request_id!==pendingBuildId&&next.status!=='processing'&&priorRev===next.revision;
  if(!waitingForBuild){pending=null;pendingBuildId=null}
  state=next;language=resolveLanguage(next.language||language);linked=Boolean(activeBridge())&&!state.demo;notice('');
  const ids=(state.objects||[]).map(o=>String(o.id));
  selection=new Set([...selection].filter(id=>ids.includes(id)));
  if((first||!oldIds.size)&&Array.isArray(state.selected_object_ids))
    selection=new Set(state.selected_object_ids.map(String).filter(id=>ids.includes(id)));
  else if(!selection.size&&ids.length===1&&!oldIds.has(ids[0]))selection.add(ids[0]);
  const idSet=new Set(ids);
  for(const id of surfaceByObject.keys())if(!idSet.has(id))surfaceByObject.delete(id);
  for(const id of wallMarks.keys())if(!idSet.has(id))wallMarks.delete(id);
  if(!idSet.has(activeId))activate(ids.find(id=>selection.has(id))??ids[0]??null);
  if(state.conformal){
    const ctx=state.conformal,id=ctx.native_id||ctx.original_id;
    if(idSet.has(id)){surfaceByObject.set(id,ctx.settings);activate(id)}
  }
  if(priorRev&&priorRev!==state.revision){
    generation=null;resultConfig='';guideStep=1;guideModelId=null;guideAwaitStudy=false;
    if(guidedMode){surfaceByObject.clear();wallMarks.clear()}
  }
  const r=state.result;
  if(r?.sha256&&state.status==='ready'){
    const surfaceResult=['surface','conformal'].includes(r.study_kind);
    const identity=JSON.stringify([r.sha256,surfaceResult?'surface':(state.capture?.sha256||''),state.revision||'']);
    if(surfaceResult&&r.settings&&idSet.has(String(r.object_id))){
      const id=String(r.object_id),settings={step_mm:r.settings.step_mm,max_slope_deg:r.settings.max_slope_deg,
        retain_native_short_edges:Boolean(r.settings.retain_native_short_edges),
        backend:r.settings.backend||'legacy_top',region_id:r.settings.region_id??null,
        selection_mode:r.settings.selection_mode??'all',selection_revision:r.settings.selection_revision??null,
        wall_selection:r.settings.wall_selection||[],...(r.settings.placement_degrees?{placement_degrees:r.settings.placement_degrees}:{})};
      if(settings.backend==='native_local'&&settings.selection_mode==='all')settings.backend='continuous_layers';
      if(!['native_local','continuous_layers'].includes(settings.backend))for(const key of ['selection_mode','selection_revision','wall_selection'])delete settings[key];
      if(!resultIdentity&&!generation){
        surfaceByObject.set(id,settings);
        if(r.report?.wall_selection?.areas)wallMarks.set(id,r.report.wall_selection.areas.map(a=>({center:a.center,radius_mm:a.radius_mm})));
        activate(id);
      }
      resultIdentity=identity;resultConfig=stableJSON(['surface',state.revision||'',id,settings]);
    }
    else if(generation){resultConfig=generation;resultIdentity=identity}
    else if(!resultIdentity||(!priorRev&&first)){resultConfig=signature();resultIdentity=identity}
    else if(identity!==resultIdentity){resultConfig='';resultIdentity=identity}
  }
  render();
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
    send('poll',{ui_focused:document.hasFocus(),model_preview_id:state.model_preview?.id});
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
__PLACEMENT_SCRIPT__
listen();applyState(JSON.parse($('initial-state').textContent));
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
