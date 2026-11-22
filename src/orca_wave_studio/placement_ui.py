"""Placement controls; a head sketch is explicitly not print qualification."""
MARKUP = r'''
<section class="section" id="placement-tools" hidden>
<h3>Posição da cópia na mesa</h3>
<p class="message">Gire a peça antes de estudar. O resultado será fatiado nessa orientação.</p>
<div class="row"><button id="placement-left" type="button">−90°</button><input id="placement-degrees" type="number" min="0" max="359" step="15" value="0" aria-label="Rotação da cópia em Z, graus"><button id="placement-right" type="button">+90°</button></div>
<small>Giro em Z, sem alterar o tamanho. Confira depois no Preview.</small>
<details id="head-map-editor"><summary>Mapear cabeçote desta impressora</summary>
<p class="message">Vista de cima, com a ponta do bico no centro. Desenhe cada parte ou informe seus limites em mm. Trás é +Y da mesa; direita é +X.</p>
<svg id="head-map-view" viewBox="-70 -70 140 140" role="img" aria-label="Mapa do cabeçote relativo à ponta do bico" style="width:100%;height:180px;background:var(--bg-input);touch-action:none"></svg>
<label>Parte<input id="head-map-name" value="Carcaça traseira" maxlength="60"></label>
<div class="field twocol"><label>X mínimo<input id="head-map-x_min" type="number" step="0.1"></label><label>X máximo<input id="head-map-x_max" type="number" step="0.1"></label><label>Y mínimo<input id="head-map-y_min" type="number" step="0.1"></label><label>Y máximo<input id="head-map-y_max" type="number" step="0.1"></label></div>
<label>Altura da parte acima da ponta do bico (mm)<input id="head-map-clearance_z" type="number" min="0.01" step="0.1"></label>
<button id="head-map-add" class="wide" type="button">Adicionar parte ao mapa</button><div id="head-map-parts"></div>
<button id="head-map-save" class="wide" type="button">Salvar mapa desta impressora</button>
<p id="head-map-note" class="message">Mapa visual parcial. Ainda não verifica colisões nem libera impressão.</p>
</details></section>
'''

SCRIPT = r'''
let headMapKey=null,headMapParts=[];
const headMapFields=['x_min','x_max','y_min','y_max','clearance_z'];
function placementModel(model){
  const angle=surfaceMode?(surfaceSettings().placement_degrees||0):0;
  if(!angle||!model)return model;
  const a=angle*Math.PI/180,c=Math.cos(a),s=Math.sin(a);
  return {...model,objects:model.objects.map(o=>{
    if(String(o.id)!==activeId)return o;
    const x=(o.bounds[0][0]+o.bounds[1][0])/2,y=(o.bounds[0][1]+o.bounds[1][1])/2;
    return {...o,triangles:o.triangles.map(t=>t.map(p=>[x+c*(p[0]-x)-s*(p[1]-y),y+s*(p[0]-x)+c*(p[1]-y),p[2]]))};
  })};
}
function changePlacement(value){
  if(!Number.isFinite(value)||controlsBusy()||!activeId)return;
  const angle=((value%360)+360)%360,choices=surfaceSettings();
  surfaceByObject.set(activeId,{...choices,placement_degrees:angle,wall_selection:[],selection_revision:null});
  wallMarks.delete(activeId);resultConfig='';sceneTag='';
  if(guidedMode)guideStep=2;
  render();notice('Orientação atualizada. Se usar pintura, selecione as áreas nesta posição.');
}
$('placement-left').onclick=()=>changePlacement((surfaceSettings().placement_degrees||0)-90);
$('placement-right').onclick=()=>changePlacement((surfaceSettings().placement_degrees||0)+90);
$('placement-degrees').onchange=e=>changePlacement(Number(e.target.value));
function drawHeadMap(){
  const svg=$('head-map-view');svg.replaceChildren();
  const put=(tag,attrs,text)=>{const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));if(text)e.textContent=text;svg.append(e);return e};
  put('path',{d:'M-65 0H65M0-65V65',stroke:'#738092','stroke-width':'.5'});
  for(const part of headMapParts){
    const rect=put('rect',{x:part.x_min,y:-part.y_max,width:part.x_max-part.x_min,height:part.y_max-part.y_min,fill:'#ba82f5','fill-opacity':'.4',stroke:'#ba82f5','stroke-width':'.8'});
    const title=document.createElementNS(svg.namespaceURI,'title');title.textContent=part.name;rect.append(title);
  }
  put('circle',{cx:0,cy:0,r:2,fill:'#00bfa5'});
  put('text',{x:3,y:7,fill:'#9aa4b4','font-size':5},'Bico');
  put('text',{x:3,y:-61,fill:'#9aa4b4','font-size':5},'Trás +Y');
  put('text',{x:25,y:65,fill:'#9aa4b4','font-size':5},'Frente −Y');
  const list=$('head-map-parts');list.replaceChildren();
  headMapParts.forEach((p,i)=>{const row=node('div','row'),label=node('small','',p.name+' · '+p.clearance_z+' mm'),remove=node('button','','Remover');remove.type='button';remove.onclick=()=>{headMapParts.splice(i,1);drawHeadMap()};row.append(label,remove);list.append(row)});
}
let headMapStart=null;
function headMapPoint(e){const svg=$('head-map-view'),p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;const q=p.matrixTransform(svg.getScreenCTM().inverse());return [q.x,-q.y]}
$('head-map-view').onpointerdown=e=>{if(e.button!==0||controlsBusy())return;headMapStart=headMapPoint(e);e.currentTarget.setPointerCapture(e.pointerId)};
$('head-map-view').onpointerup=e=>{
  if(!headMapStart)return;const end=headMapPoint(e),start=headMapStart;headMapStart=null;
  if(Math.hypot(end[0]-start[0],end[1]-start[1])<1)return;
  for(const [key,value] of Object.entries({x_min:Math.min(start[0],end[0]),x_max:Math.max(start[0],end[0]),y_min:Math.min(start[1],end[1]),y_max:Math.max(start[1],end[1])}))$('head-map-'+key).value=value.toFixed(1);
};
$('head-map-view').onpointercancel=()=>headMapStart=null;
$('head-map-add').onclick=()=>{
  if(controlsBusy())return;
  const part={name:$('head-map-name').value.trim()};
  for(const key of headMapFields){const input=$('head-map-'+key);if(input.value.trim()===''){notice('Informe todas as medidas desta parte.');return}part[key]=Number(input.value)}
  if(!part.name||headMapParts.length>=12||headMapFields.some(k=>!Number.isFinite(part[k])||Math.abs(part[k])>300)||part.x_min>=part.x_max||part.y_min>=part.y_max||part.clearance_z<=0){notice('Confira os limites e a altura desta parte.');return}
  headMapParts.push(part);drawHeadMap();
};
$('head-map-save').onclick=()=>{if(!controlsBusy()&&headMapKey)send('save_head_map',{profile_key:headMapKey,components:headMapParts})};
function renderPlacement(active,busy,current){
  $('placement-tools').hidden=!surfaceMode||!active||(guidedMode&&guideStep!==2);
  $('placement-degrees').value=surfaceSettings().placement_degrees||0;
  for(const id of ['placement-left','placement-right','placement-degrees','head-map-add','head-map-save'])$(id).disabled=busy||!active;
  const map=state.head_map;
  if((map?.profile_key||null)!==headMapKey){headMapKey=map?.profile_key||null;headMapParts=structuredClone(map?.components||[]);for(const key of headMapFields)$('head-map-'+key).value='';drawHeadMap()}
  $('head-map-save').disabled=busy||!headMapKey;
  $('head-map-note').textContent=headMapKey?'Mapa visual parcial para '+map.identity.printer_name+'. Ainda não verifica colisões nem libera impressão.':'Escolha o perfil da impressora no Orca para salvar o mapa.';
}
'''
