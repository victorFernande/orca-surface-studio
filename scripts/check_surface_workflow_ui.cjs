// Own local HTML component test. No native Orca control or printer/network IO.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.WAVE_PLAYWRIGHT||'playwright');

(async()=>{
  const input=path.resolve(process.argv[2]||'study/evidence/active-profile-benchy/studio-mesh.html');
  const output=path.resolve(process.argv[3]||'study/evidence/active-profile-benchy/ui');fs.mkdirSync(output,{recursive:true});
  const html=fs.readFileSync(input,'utf8');
  const state=JSON.parse(html.match(/<script id="initial-state" type="application\/json">([\s\S]*?)<\/script>/)[1]);
  const browser=await chromium.launch({headless:true,executablePath:process.env.WAVE_BROWSER});
  const results=[];
  try{
    for(const fallback of [false,true]){
      const page=await browser.newPage({viewport:{width:1580,height:1000}});const errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      await page.addInitScript(({state,fallback})=>{
        if(fallback){const original=HTMLCanvasElement.prototype.getContext;
          HTMLCanvasElement.prototype.getContext=function(kind,...args){return kind==='webgl2'?null:original.call(this,kind,...args)}}
        window.commands=[];window.orca={onMessage:fn=>window.hostReceive=fn,postMessage:m=>{
          const data=typeof m==='string'?JSON.parse(m):m;window.commands.push(data);
          if(data.action==='refresh')window.hostReceive?.({type:'state',state});
        }};
      },{state,fallback});
      await page.goto(pathToFileURL(input).href);
      await page.getByRole('button',{name:'Superfície curva',exact:true}).click();
      await page.getByRole('button',{name:'Enquadrar trajetória',exact:true}).click();
      assert.equal(await page.locator('#empty').isVisible(),false);
      assert.equal(await page.getByText(state.printer_profile.name,{exact:true}).count(),1);
      assert.ok(await page.evaluate(()=>viewer.mesh.flat.length>0));
      assert.equal(await page.locator('#generate').isDisabled(),true);
      const target=await page.evaluate(()=>{
        const c=document.querySelector('#canvas'),r=c.getBoundingClientRect();
        for(let y=r.top+r.height*.25;y<r.bottom-r.height*.2;y+=12)
          for(let x=r.left+r.width*.2;x<r.right-r.width*.2;x+=12)
            if(viewer.pick(x,y))return {x,y};
        return null;
      });
      assert.ok(target,'model must be pickable');await page.mouse.click(target.x,target.y);
      assert.equal(await page.getByRole('button',{name:'Remover área 1',exact:true}).count(),1);
      assert.equal(await page.locator('#generate').isEnabled(),true);
      await page.mouse.move(target.x,target.y);await page.mouse.down();
      await page.mouse.move(target.x+24,target.y+8,{steps:5});await page.mouse.up();
      assert.equal(await page.getByRole('button',{name:/Remover área/}).count(),1,'orbit must not paint');
      await page.locator('#generate').click();
      const painted=await page.evaluate(()=>window.commands.findLast(c=>c.action==='build_surface'));
      assert.equal(painted.settings.selection_mode,'paint');
      assert.equal(painted.settings.selection_revision,state.revision);
      assert.equal(painted.settings.wall_selection.length,1);
      assert.ok(painted.settings.wall_selection[0].direction.every(Number.isFinite));
      await page.evaluate(state=>window.orcaWaveReceive({type:'state',state:{...state,sequence:30}}),state);
      await page.screenshot({path:path.join(output,fallback?'selected-software.png':'selected-webgl.png')});
      if(process.argv[5]){
        // Exercise the render/handshake with an actual report, translated to
        // this UI fixture's single click. This is not a native integration run.
        const result=JSON.parse(fs.readFileSync(process.argv[5],'utf8'));
        result.object_id='1';result.revision=state.revision;
        // Match native dictionary serialization, including nested ray key order.
        const reorder=v=>Array.isArray(v)?v.map(reorder):v&&typeof v==='object'
          ?Object.fromEntries(Object.keys(v).sort().map(k=>[k,reorder(v[k])])):v;
        result.settings=reorder(painted.settings);
        result.report.wall_selection.areas=result.report.wall_selection.areas.slice(0,1);
        await page.evaluate(({state,result})=>window.orcaWaveReceive({type:'state',state:{...state,
          sequence:31,status:'ready',result,message:'Somente Preview.'}}),{state,result});
        assert.equal(await page.locator('#preview').isEnabled(),true,'painted result signature must match');
        assert.match(await page.locator('#result-note').innerText(),/não está liberado para imprimir/);
        assert.equal(await page.getByText('Maior inclinação do percurso',{exact:true}).count(),1);
        await page.evaluate(state=>window.orcaWaveReceive({type:'state',state:{...state,sequence:32}}),state);
      }
      await page.getByRole('button',{name:'Remover área 1',exact:true}).click();
      assert.equal(await page.locator('#generate').isDisabled(),true);
      await page.getByRole('button',{name:'Todas compatíveis',exact:true}).click();
      await page.screenshot({path:path.join(output,fallback?'mesh-software.png':'mesh-webgl.png')});
      await page.getByRole('button',{name:'Gerar superfície e abrir Preview',exact:true}).click();
      const command=await page.evaluate(()=>window.commands.findLast(c=>c.action==='build_surface'));
      assert.equal(command.settings.backend,'native_local');assert.deepEqual(command.object_ids,['1']);
      if(process.argv[4]){
        const result=JSON.parse(fs.readFileSync(process.argv[4],'utf8'));
        result.object_id='1';result.revision=state.revision;result.settings=command.settings;
        await page.evaluate(({state,result})=>window.orcaWaveReceive({type:'state',state:{...state,
          sequence:49,status:'ready',result,message:'Candidato local gerado; impressão pendente.'}}),{state,result});
        assert.equal(await page.getByText('Contorno local do Orca',{exact:true}).count(),1);
        assert.equal(await page.getByRole('button',{name:'Comparar',exact:true}).isEnabled(),false);
        assert.ok(await page.evaluate(()=>viewer.streams.deformed.indices.length>0));
        await page.screenshot({path:path.join(output,fallback?'local-result-software.png':'local-result-webgl.png')});
      }
      // A rejected calculation must keep the real model visible and navigable.
      await page.evaluate(state=>window.orcaWaveReceive({type:'state',state:{...state,sequence:50,status:'error',
        message:'Teste: configuração incompatível.'}}),state);
      assert.equal(await page.locator('#empty').isVisible(),false);
      assert.equal(await page.getByRole('button',{name:'Aproximar',exact:true}).isEnabled(),true);
      await page.screenshot({path:path.join(output,fallback?'error-software.png':'error-webgl.png')});
      // A project change clears the old geometry rather than retaining a coupon.
      await page.evaluate(()=>window.orcaWaveReceive({type:'state',state:{native:true,sequence:51,
        revision:'new-empty-project',status:'slicing_required',objects:[],model_preview:null}}));
      assert.equal(await page.evaluate(()=>viewer.mesh.flat.length),0);
      assert.deepEqual(errors,[]);results.push({fallback,errors,model_visible_before_calculation:true,
        model_visible_after_error:true,stale_model_cleared:true,command});await page.close();
    }
  }finally{await browser.close()}
  const result={status:'PASS_HEADLESS_COMPONENT',native_orca_controlled:false,printer_contacted:false,results};
  fs.writeFileSync(path.join(output,'validation.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
})().catch(e=>{console.error(e);process.exitCode=1});
