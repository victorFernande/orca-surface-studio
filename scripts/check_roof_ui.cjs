// Isolated browser component fixture: no Orca window, profile or printer.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.WAVE_PLAYWRIGHT||'playwright');
const {createHash}=require('node:crypto');

(async()=>{
  const folder=path.resolve(__dirname,'../study/evidence/roof-study/ui');
  const file=path.join(folder,'studio-regional.html');
  const state=JSON.parse(fs.readFileSync(file,'utf8').match(/<script id="initial-state" type="application\/json">([\s\S]*?)<\/script>/)[1]);
  const browser=await chromium.launch({headless:true,executablePath:process.env.WAVE_BROWSER});
  const errors=[];
  try{
    const page=await browser.newPage({viewport:{width:1440,height:960}});
    page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(initial=>{
      window.testMessages=[];
      window.orca={onMessage:fn=>window.testReceive=fn,postMessage:message=>{
        const data=typeof message==='string'?JSON.parse(message):message;
        window.testMessages.push(data);
        if(['refresh','poll'].includes(data.action))window.testReceive?.({type:'state',state:initial});
      }};
    },state);
    await page.goto(pathToFileURL(file).href);
    await page.getByRole('button',{name:'Superfície curva',exact:true}).click();
    const choice=page.getByRole('checkbox',{name:'Preservar pequenas quinas',exact:true});
    assert.equal(await choice.isChecked(),false);
    await choice.check();
    await page.getByRole('button',{name:'Preparar fatiamento conformal',exact:true}).click();
    const command=await page.evaluate(()=>window.testMessages.findLast(m=>m.action==='prepare_conformal'));
    assert.equal(command.settings.backend,'regional_paired');
    assert.equal(command.settings.retain_native_short_edges,true);
    assert.equal(command.settings.region_id,null);
    assert.match(await page.locator('#roof-region-note').innerText(),/25.*Cabeçote|25.*cabeçote/);
    // A manual pick changes only the reference region; paired faces stay coupled.
    await page.evaluate(initial=>window.orcaWaveReceive({type:'state',state:{...initial,sequence:500}}),state);
    const manualId=state.objects[0].roof_regions.regions[0].id;
    await page.locator('#roof-region').selectOption(manualId);
    await page.getByRole('button',{name:'Preparar fatiamento conformal',exact:true}).click();
    const corrected=await page.evaluate(()=>window.testMessages.findLast(m=>m.action==='prepare_conformal'));
    assert.equal(corrected.settings.region_id,manualId);
    const settings=corrected.settings;
    await page.evaluate(({initial,settings})=>window.orcaWaveReceive({type:'state',state:{...initial,sequence:501,
      status:'ready',capture:{sha256:'source',revision:initial.revision},
      conformal:{phase:'ready',original_id:'1',native_id:'1',settings,region_catalog:initial.objects[0].roof_regions},
      result:{sha256:'processed',study_kind:'conformal',object_id:'1',revision:initial.revision,settings,
        package_path:'component-fixture-only.gcode.3mf',original_points:[],deformed_points:[],
        layer_ids:[],report:{source_sha256:'source',print_allowed:false,
          regional_audit:{digital_approval:false,faces:{top:{sampled_max_normal_error_mm:.09,reason:'Amostrado'},
            underside:{sampled_max_normal_error_mm:.09,reason:'Amostrado'}},support:{status:'NOT_CERTIFIED'}}}}}}),{initial:state,settings});
    assert.equal(await page.getByRole('button',{name:'Abrir Preview no Orca',exact:true}).isEnabled(),true);
    assert.match(await page.locator('#result-note').innerText(),/Impressão indisponível/);
    assert.match(await page.locator('#metrics').innerText(),/Incompleta/);
    assert.equal(await choice.isDisabled(),true);
    assert.equal(await page.locator('#roof-region').isDisabled(),true);
    assert.deepEqual(errors,[]);
    await page.screenshot({path:path.join(folder,'studio-regional.png')});
    const result={status:'PASS_HEADLESS_COMPONENT',command,corrected,errors,
      native_orca_controlled:false,printer_contacted:false,fixture_result_is_not_native_preview:true,
      studio_html_sha256:createHash('sha256').update(fs.readFileSync(file)).digest('hex'),
      studio_ui_source_sha256:createHash('sha256').update(fs.readFileSync(path.resolve(__dirname,'../src/orca_wave_studio/studio_ui.py'))).digest('hex')};
    fs.writeFileSync(path.join(folder,'ui-validation.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
