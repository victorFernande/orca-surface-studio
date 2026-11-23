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
      const curve=page.locator('#curve-height-number'),curveRange=page.locator('#curve-height-range');
      assert.equal(await curve.isVisible(),true);assert.equal(await curve.inputValue(),'5');
      for(const input of [curve,curveRange]){
        assert.equal(await input.getAttribute('min'),'0.1');assert.equal(await input.getAttribute('max'),'5');
        assert.equal(await input.getAttribute('step'),'0.1');
      }
      for(const invalid of ['0','5.1','0.15']){
        await curve.fill(invalid);assert.equal(await page.locator('#guide-next').isDisabled(),true);
        await page.locator('.pick-object').first().click();assert.equal(await step(),'1','cannot hide an invalid height by selecting the same object');
      }
      await curve.fill('0.1');assert.equal(await curveRange.inputValue(),'0.1');
      assert.equal(await page.locator('#guide-next').isEnabled(),true);
      await curve.fill('4.9');await curve.press('ArrowUp');assert.equal(await curve.inputValue(),'5');
      await curve.blur();
      await page.locator('#canvas').scrollIntoViewIfNeeded();let target=await hit();assert.ok(target);
      await page.mouse.click(target.x,target.y);
      assert.equal(await page.evaluate(()=>surfaceSettings().wall_selection.length),0,'step 1 must not paint');
      await page.screenshot({path:path.join(output,`${width}-${fallback}-1-model.png`),fullPage:true});
      await page.locator('.pick-object').first().click();assert.equal(await step(),'2');
      assert.equal(await page.locator('#wall-all').getAttribute('aria-pressed'),'true');
      await page.locator('#wall-paint').click();
      assert.equal(await page.locator('#guide-next').isDisabled(),true);
      await page.locator('#canvas').scrollIntoViewIfNeeded();target=await hit();await page.mouse.click(target.x,target.y);
      assert.equal(await page.locator('#guide-next').isEnabled(),true);
      await page.screenshot({path:path.join(output,`${width}-${fallback}-2-areas.png`),fullPage:true});
      await page.locator('#guide-next').click();assert.equal(await step(),'3');
      assert.equal(await page.locator('#guide-next').innerText(),'Calculando…');
      assert.equal(await page.locator('#wall-selection').isVisible(),false);
      const build=await page.evaluate(()=>window.commands.findLast(m=>m.action==='build_surface'));
      assert.equal(build.open_preview,false);assert.equal(build.settings.wall_selection.length,1);
      assert.equal(await page.evaluate(()=>window.commands.some(m=>m.action==='open_preview')),false);
      assert.equal(await page.locator('#guide-next').isDisabled(),true);
      // A delayed reply to an earlier poll must not unlock the new command.
      await page.evaluate(state=>window.orcaWaveReceive({type:'state',state:{...state,sequence:19}}),state);
      assert.equal(await page.locator('#guide-next').isDisabled(),true);
      await page.evaluate(()=>document.querySelector('#guide-next').click());
      await page.evaluate(state=>window.orcaWaveReceive({type:'state',state:{...state,sequence:20,
        build_client_request_id:window.commands.findLast(m=>m.action==='build_surface').client_request_id,
        status:'processing',message:'Refinando as camadas…',calculation:{phase:'Refinando as camadas…',elapsed_seconds:73}}}),state);
      assert.equal(await page.locator('#guide-progress').isVisible(),true);
      assert.match(await page.locator('#guide-progress').innerText(),/1 min 13 s/);
      assert.equal(await page.locator('#cancel-build').isVisible(),true);
      assert.equal(await page.evaluate(()=>window.commands.filter(m=>m.action==='build_surface').length),1);
      await page.screenshot({path:path.join(output,`${width}-${fallback}-3-calculation.png`),fullPage:true});
      const result=structuredClone(fixture);result.object_id=String(state.objects[0].id);
      result.revision=state.revision;result.settings=build.settings;
      await page.evaluate(({state,result})=>window.orcaWaveReceive({type:'state',state:{...state,
        build_client_request_id:window.commands.findLast(m=>m.action==='build_surface').client_request_id,
        sequence:30,status:'ready',result,message:'Estudo concluído.'}}),{state,result});
      assert.equal(await step(),'4');assert.equal(await page.locator('#guide-next').innerText(),'Ver no Preview do Orca');
      assert.equal(await page.locator('#guide-warning').isVisible(),true);
      assert.equal(await page.evaluate(()=>window.commands.some(m=>m.action==='open_preview')),false);
      await page.screenshot({path:path.join(output,`${width}-${fallback}-4-result.png`),fullPage:true});
      await page.locator('#guide-next').click();
      const transfer=await page.evaluate(()=>window.commands.findLast(m=>m.action==='open_preview'));
      assert.equal(transfer.sha256,result.sha256);
      assert.equal(await page.evaluate(()=>window.commands.some(m=>/print|upload|send_file/.test(m.action))),false);
      await page.locator('#guide-back').click();
      assert.equal(await step(),'2');await page.getByRole('button',{name:'Remover área 1',exact:true}).click();
      assert.equal(await page.locator('#guide-next').isDisabled(),true);
      assert.equal(await page.locator('#guide-step-4').isDisabled(),true);
      // Whole-model coverage must be reachable without opening advanced options.
      assert.equal(await page.locator('#wall-all').isVisible(),true);
      await page.locator('#wall-all').click();
      assert.equal(await page.locator('#guide-next').isEnabled(),true);
      assert.equal(await page.locator('#wall-radius').isVisible(),false);
      assert.equal(await page.locator('#guide-toggle,#mode-xy,#mode-z,#mode-combined,#presets,#generate,#preview').count(),0);
      await page.locator('#guide-back').click();assert.equal(await step(),'1');
      await page.locator('#guide-next').click();assert.equal(await step(),'2');
      assert.equal(await page.locator('#wall-all').getAttribute('aria-pressed'),'true');
      await page.locator('#guide-next').click();
      const whole=await page.evaluate(()=>window.commands.findLast(m=>m.action==='build_surface'));
      assert.equal(whole.open_preview,false);assert.equal(whole.settings.selection_mode,'all');
      assert.equal(whole.settings.backend,'continuous_layers');
      assert.equal(whole.settings.max_curve_height_mm,5);
      assert.equal(whole.settings.adaptation_strength,undefined);
      assert.deepEqual(whole.settings.wall_selection,[]);
      const wholeResult=structuredClone(result);wholeResult.settings=whole.settings;
      wholeResult.report.wall_selection={mode:'all',areas:[],wall_speed_factor:1};
      wholeResult.report.warp={...wholeResult.report.warp,transition_kernel:'cubic_spline_phase_v1',reference_certificate_version:2};
      wholeResult.report.bead_deposition={model:'logical_pitch_finite_bead_v1',minimum_supported_height_mm:.04,
        maximum_supported_height_mm:.25,below_profile_minimum_occurrences:1};
      await page.evaluate(({state,result})=>window.orcaWaveReceive({type:'state',state:{...state,
        build_client_request_id:window.commands.findLast(m=>m.action==='build_surface').client_request_id,
        sequence:35,status:'ready',result,message:'Estudo da peça inteira concluído.'}}),{state,result:wholeResult});
      assert.equal(await step(),'4');
      assert.match(await page.locator('#guide-summary').innerText(),/Peça inteira/);
      assert.match(await page.locator('#guide-summary').innerText(),/Velocidades do perfil selecionado/);
      assert.match(await page.locator('#guide-summary').innerText(),/Altura efetiva do cordão/);
      assert.match(await page.locator('#guide-warning').innerText(),/abaixo da altura mínima/);
      await page.locator('#send-review').click();
      assert.equal(await page.evaluate(()=>window.commands.findLast(m=>m.action==='open_send_dialog').sha256),wholeResult.sha256);
      assert.equal(await page.evaluate(()=>window.commands.some(m=>m.action==='send_file')),false);
      await page.locator('#guide-send').click();
      assert.equal(await page.evaluate(()=>window.commands.findLast(m=>m.action==='open_send_dialog').sha256),wholeResult.sha256);
      // Returning to unchanged areas uses the existing result without another build.
      const builds=await page.evaluate(()=>window.commands.filter(m=>m.action==='build_surface').length);
      await page.locator('#guide-back').click();
      assert.equal(await step(),'2');
      assert.equal(await page.locator('#guide-next').innerText(),'Ver resultado já calculado');
      await page.locator('#guide-next').click();assert.equal(await step(),'4');
      assert.equal(await page.evaluate(()=>window.commands.filter(m=>m.action==='build_surface').length),builds);
      await page.locator('#guide-step-1').click();
      await curve.fill('4.9');assert.equal(await page.evaluate(()=>presentResult()),false,'curve changes invalidate the result');
      await curve.fill('5');await curve.blur();assert.equal(await page.evaluate(()=>presentResult()),true);
      await page.locator('#guide-next').click();await page.locator('#guide-next').click();
      const oldKernel=structuredClone(wholeResult);oldKernel.report.warp.transition_kernel='hermite_c1_xyz_v4';
      await page.evaluate(({state,result})=>window.orcaWaveReceive({type:'state',state:{...state,
        sequence:36,status:'ready',result}}),{state,result:oldKernel});
      assert.equal(await page.evaluate(()=>presentResult()),false,'an older transition kernel is stale');
      await page.evaluate(state=>window.orcaWaveReceive({type:'state',state:{...state,sequence:40,
        revision:'changed-project',result:null}}),state);
      assert.equal(await step(),'1');
      await page.locator('#guide-next').click();await page.locator('#wall-all').click();await page.locator('#guide-next').click();
      await page.evaluate(state=>window.orcaWaveReceive({type:'state',state:{...state,sequence:41,
        build_client_request_id:window.commands.findLast(m=>m.action==='build_surface').client_request_id,
        revision:'changed-project',status:'error',message:'BEAD_HEIGHT: 0.29 > 0.28',result:null}}),state);
      assert.equal(await step(),'3');assert.match(await page.locator('#guide-help').innerText(),/área menor/);
      assert.equal(await page.locator('#guide-next').innerText(),'Tentar novamente');
      await page.locator('#guide-next').click();
      assert.equal(await page.locator('#guide-next').isDisabled(),true);
      await page.evaluate(state=>window.orcaWaveReceive({type:'state',state:{...state,sequence:42,
        objects:[],model_preview:null,status:'idle',send_preview_available:true,result:null,revision:'preview-only'}}),state);
      assert.match(await page.locator('#guide-help').innerText(),/G-code aberto no Preview/);
      assert.match(await page.locator('#empty-msg').innerText(),/trajetória já está no Preview/);
      assert.equal(await page.locator('#guide-send').isVisible(),true);
      await page.locator('#guide-send').click();
      assert.equal(await page.evaluate(()=>window.commands.some(m=>m.action==='send_file')),false);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),true,'no horizontal overflow');
      assert.deepEqual(errors,[]);outcomes.push({fallback,width,height,errors,four_steps:true,
        curve_height_range_mm:[.1,5],curve_height_step_mm:.1,curve_height_default_mm:5,
        invalid_curve_height_blocks_next:true,curve_height_change_invalidates_result:true,
        study_does_not_open_orca:true,explicit_transfer_only:true,stale_selection_invalidated:true,
        whole_model_in_guided_step:true,legacy_layout_removed:true,scope_survives_guided_navigation:true,
        single_calculate_click:true,visible_progress:true,unchanged_result_reused:true,error_retry:true,sliced_only_send_review:true});
      await page.close();
    }
  }finally{await browser.close()}
  const report={status:'PASS_GUIDED_COMPONENT',native_orca_controlled:false,printer_contacted:false,outcomes};
  fs.writeFileSync(path.join(output,'validation.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1});
