// Local component test only; does not control Orca or contact a printer.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.WAVE_PLAYWRIGHT||'playwright');

(async()=>{
  const input=path.resolve(process.argv[2]),output=path.resolve(process.argv[3]);
  const html=fs.readFileSync(input,'utf8');
  const state=JSON.parse(html.match(/<script id="initial-state" type="application\/json">([\s\S]*?)<\/script>/)[1]);
  const fixture=JSON.parse(fs.readFileSync(process.argv[4],'utf8'));
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath:process.env.WAVE_BROWSER});
  const outcomes=[];
  try{
    for(const [fallback,width,height] of [[false,1580,1000],[true,1580,1000],[false,390,844]]){
      const page=await browser.newPage({viewport:{width,height}}),errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      await page.addInitScript(({state,fallback})=>{
        if(fallback){const get=HTMLCanvasElement.prototype.getContext;
          HTMLCanvasElement.prototype.getContext=function(kind,...args){return kind==='webgl2'?null:get.call(this,kind,...args)}}
        window.commands=[];window.orca={onMessage:fn=>window.hostReceive=fn,postMessage:m=>{
          const data=typeof m==='string'?JSON.parse(m):m;window.commands.push(data);
          if(data.action==='refresh')window.hostReceive?.({type:'state',state});
        }};
      },{state,fallback});
      await page.goto(pathToFileURL(input).href);
      const step=()=>page.locator('body').getAttribute('data-guide-step');
      const hit=()=>page.evaluate(()=>{
        const c=document.querySelector('#canvas'),r=c.getBoundingClientRect();
        for(let y=r.top+r.height*.2;y<r.bottom-r.height*.15;y+=8)
          for(let x=r.left+r.width*.2;x<r.right-r.width*.15;x+=8)
            if(viewer.pick(x,y))return {x,y};return null;
      });
      assert.equal(await step(),'1');assert.equal(await page.locator('#wall-selection').isVisible(),false);
      await page.locator('#canvas').scrollIntoViewIfNeeded();let target=await hit();assert.ok(target);
      await page.mouse.click(target.x,target.y);
      assert.equal(await page.evaluate(()=>surfaceSettings().wall_selection.length),0,'step 1 must not paint');
      await page.screenshot({path:path.join(output,`${width}-${fallback}-1-model.png`),fullPage:true});
      await page.locator('#guide-next').click();assert.equal(await step(),'2');
      assert.equal(await page.locator('#wall-all').getAttribute('aria-pressed'),'true');
      await page.locator('#wall-paint').click();
      assert.equal(await page.locator('#guide-next').isDisabled(),true);
      await page.locator('#canvas').scrollIntoViewIfNeeded();target=await hit();await page.mouse.click(target.x,target.y);
      assert.equal(await page.locator('#guide-next').isEnabled(),true);
      await page.screenshot({path:path.join(output,`${width}-${fallback}-2-areas.png`),fullPage:true});
      await page.locator('#guide-next').click();assert.equal(await step(),'3');
      assert.equal(await page.locator('#guide-next').innerText(),'Estudar movimento');
      assert.equal(await page.locator('#wall-selection').isVisible(),false);
      await page.locator('#guide-next').click();
      const build=await page.evaluate(()=>window.commands.findLast(m=>m.action==='build_surface'));
      assert.equal(build.open_preview,false);assert.equal(build.settings.wall_selection.length,1);
      assert.equal(await page.evaluate(()=>window.commands.some(m=>m.action==='open_preview')),false);
      assert.equal(await page.locator('#guide-next').isDisabled(),true);
      const result=structuredClone(fixture);result.object_id=String(state.objects[0].id);
      result.revision=state.revision;result.settings=build.settings;
      await page.evaluate(({state,result})=>window.orcaWaveReceive({type:'state',state:{...state,
        sequence:30,status:'ready',result,message:'Estudo concluído.'}}),{state,result});
      assert.equal(await step(),'4');assert.equal(await page.locator('#guide-next').innerText(),'Mandar para a bandeja');
      assert.equal(await page.locator('#guide-warning').isVisible(),true);
      assert.equal(await page.evaluate(()=>window.commands.some(m=>m.action==='open_preview')),false);
      await page.screenshot({path:path.join(output,`${width}-${fallback}-4-result.png`),fullPage:true});
      await page.locator('#guide-next').click();
      const transfer=await page.evaluate(()=>window.commands.findLast(m=>m.action==='open_preview'));
      assert.equal(transfer.sha256,result.sha256);
      assert.equal(await page.evaluate(()=>window.commands.some(m=>/print|upload|send_file/.test(m.action))),false);
      await page.locator('#guide-back').click();await page.locator('#guide-back').click();
      assert.equal(await step(),'2');await page.getByRole('button',{name:'Remover área 1',exact:true}).click();
      assert.equal(await page.locator('#guide-next').isDisabled(),true);
      assert.equal(await page.locator('#guide-step-4').isDisabled(),true);
      // Whole-model coverage must be reachable without opening advanced options.
      assert.equal(await page.locator('#wall-all').isVisible(),true);
      await page.locator('#wall-all').click();
      assert.equal(await page.locator('#guide-next').isEnabled(),true);
      assert.equal(await page.locator('#wall-radius').isVisible(),false);
      await page.locator('#guide-toggle').click();await page.locator('#guide-toggle').click();
      await page.locator('#guide-next').click();assert.equal(await step(),'2');
      assert.equal(await page.locator('#wall-all').getAttribute('aria-pressed'),'true');
      await page.locator('#guide-next').click();await page.locator('#guide-next').click();
      const whole=await page.evaluate(()=>window.commands.findLast(m=>m.action==='build_surface'));
      assert.equal(whole.open_preview,false);assert.equal(whole.settings.selection_mode,'all');
      assert.equal(whole.settings.backend,'continuous_layers');
      assert.equal(whole.settings.adaptation_strength,undefined);
      assert.deepEqual(whole.settings.wall_selection,[]);
      const wholeResult=structuredClone(result);wholeResult.settings=whole.settings;
      wholeResult.report.wall_selection={mode:'all',areas:[],wall_speed_factor:1};
      wholeResult.report.warp={...wholeResult.report.warp,transition_kernel:'cubic_spline_phase_v1',reference_certificate_version:2};
      wholeResult.report.bead_deposition={model:'logical_pitch_finite_bead_v1',minimum_supported_height_mm:.04,
        maximum_supported_height_mm:.25,below_profile_minimum_occurrences:1};
      await page.evaluate(({state,result})=>window.orcaWaveReceive({type:'state',state:{...state,
        sequence:35,status:'ready',result,message:'Estudo da peça inteira concluído.'}}),{state,result:wholeResult});
      assert.equal(await step(),'4');
      assert.match(await page.locator('#guide-summary').innerText(),/Peça inteira/);
      assert.match(await page.locator('#guide-summary').innerText(),/Velocidades do perfil selecionado/);
      assert.match(await page.locator('#guide-summary').innerText(),/Altura efetiva do cordão/);
      assert.match(await page.locator('#guide-warning').innerText(),/abaixo da altura mínima/);
      await page.locator('#send-review').click();
      assert.equal(await page.evaluate(()=>window.commands.findLast(m=>m.action==='open_send_dialog').sha256),wholeResult.sha256);
      assert.equal(await page.evaluate(()=>window.commands.some(m=>m.action==='send_file')),false);
      const oldKernel=structuredClone(wholeResult);oldKernel.report.warp.transition_kernel='hermite_c1_xyz_v4';
      await page.evaluate(({state,result})=>window.orcaWaveReceive({type:'state',state:{...state,
        sequence:36,status:'ready',result}}),{state,result:oldKernel});
      assert.equal(await page.evaluate(()=>presentResult()),false,'an older transition kernel is stale');
      await page.evaluate(state=>window.orcaWaveReceive({type:'state',state:{...state,sequence:40,
        revision:'changed-project',result:null}}),state);
      assert.equal(await step(),'1');
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),true,'no horizontal overflow');
      assert.deepEqual(errors,[]);outcomes.push({fallback,width,height,errors,four_steps:true,
        study_does_not_open_orca:true,explicit_transfer_only:true,stale_selection_invalidated:true,
        whole_model_in_guided_step:true,scope_survives_advanced_toggle:true});
      await page.close();
    }
  }finally{await browser.close()}
  const report={status:'PASS_GUIDED_COMPONENT',native_orca_controlled:false,printer_contacted:false,outcomes};
  fs.writeFileSync(path.join(output,'validation.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1});
