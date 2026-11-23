// Offline component test; no native Orca control or printer contact.
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.WAVE_PLAYWRIGHT||'playwright');

(async()=>{
  const folder=path.resolve(process.argv[2]);
  const packs=Object.fromEntries(fs.readdirSync(path.resolve('src/orca_wave_studio/locales'))
    .filter(f=>f.endsWith('.json')).map(f=>{const p=JSON.parse(fs.readFileSync(path.join('src/orca_wave_studio/locales',f),'utf8'));return [p.code,p]}));
  const browser=await chromium.launch({headless:true,executablePath:process.env.WAVE_BROWSER});
  const outcomes=[];
  try{
    for(const file of ['model.html','dock.html']){
      const html=fs.readFileSync(path.join(folder,file),'utf8');
      const initial=JSON.parse(html.match(/<script id="initial-state" type="application\/json">([\s\S]*?)<\/script>/)[1]);
      const settings={step_mm:.4,max_slope_deg:30,retain_native_short_edges:true,backend:'continuous_layers',region_id:null,
        selection_mode:'all',selection_revision:null,wall_selection:[]};
      const result={sha256:'b'.repeat(64),study_kind:'surface',workflow:'integrated',object_id:String(initial.objects[0].id),
        revision:initial.revision,settings,report:{print_allowed:false,warp:{transition_kernel:'cubic_spline_phase_v1',reference_certificate_version:2}}};
      const host={...initial,result,status:'ready',language:'pt',sequence:1};
      let sequence=1;
      const page=await browser.newPage({viewport:{width:file==='dock.html'?390:1580,height:1000}}),errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      await page.exposeFunction('mockHost',command=>{
        if(command.action==='set_language')host.language=command.language;
        return {...host,sequence:++sequence};
      });
      await page.addInitScript(()=>{
        window.commands=[];
        window.orca={onMessage:fn=>window.hostReceive=fn,postMessage:async m=>{
          const command=typeof m==='string'?JSON.parse(m):m;window.commands.push(command);
          if(['poll','refresh','set_language'].includes(command.action)){
            const state=await window.mockHost(command);window.hostReceive?.({type:'state',state});
          }
        }};
      });
      await page.goto(pathToFileURL(path.join(folder,file)).href);
      await page.waitForFunction(()=>document.body.dataset.guideStep==='4');
      assert.equal(await page.locator('#guide-next').isEnabled(),true,'a restored current result can reopen Preview');
      assert.equal(await page.locator('#language option').count(),7);
      for(const [code,pack] of Object.entries(packs)){
        await page.selectOption('#language',code);
        await page.waitForFunction(code=>language===code&&state.language===code,code);
        assert.equal(await page.locator('#warning-title').innerText(),pack.translations.warning_title);
        assert.equal(await page.locator('#warning-body').innerText(),pack.translations.warning_body);
        assert.equal(await page.locator('#guide-warning').innerText(),pack.translations.warning_preview);
        assert.equal(await page.locator('html').getAttribute('lang'),code);
        assert.equal(await page.locator('#guide-next').isEnabled(),true,'language choice must preserve the current study');
        assert.equal(await page.evaluate(()=>presentResult()),true);
        // Reload gets the persisted language from the host, as does a second page/dock.
        await page.reload();
        await page.waitForFunction(code=>state.language===code&&document.querySelector('#language').value===code,code);
        assert.equal(await page.locator('#warning-title').innerText(),pack.translations.warning_title);
        host.result.report.bead_deposition={below_profile_minimum_occurrences:1};
        await page.evaluate(state=>window.orcaWaveReceive({type:'state',state}),{...host,sequence:++sequence});
        assert.equal(await page.locator('#guide-warning').innerText(),pack.translations.warning_bead);
        delete host.result.report.bead_deposition;
        await page.evaluate(state=>window.orcaWaveReceive({type:'state',state}),{...host,sequence:++sequence});
        // A hidden desktop tab still consumes host language changes when reopened.
        assert.equal(await page.locator('#guide-warning').innerText(),pack.translations.warning_preview);
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
        if(['pt','ja'].includes(code))await page.screenshot({path:path.join(folder,`${file}-${code}.png`),fullPage:true});
      }
      assert.equal(await page.locator('#guide-toggle,#mode-xy,#mode-z,#presets,#generate,#preview').count(),0);
      assert.equal(await page.evaluate(()=>window.commands.some(c=>/print|upload|send_file/.test(c.action))),false);
      assert.deepEqual(errors,[]);outcomes.push({file,languages:Object.keys(packs),restored_result:true,persistence:true,errors});
      await page.close();
    }
  }finally{await browser.close()}
  const report={status:'PASS_WARNING_LANGUAGES',native_orca_controlled:false,printer_contacted:false,outcomes};
  fs.writeFileSync(path.join(folder,'languages-validation.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1});
