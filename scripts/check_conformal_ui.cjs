// Historical conformal-UI fixture only (before 0.15.3). Current UI: check_guided_studio_ui.cjs.
// Isolated local component test; no Orca process or printer connection.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.WAVE_PLAYWRIGHT||'playwright');

(async()=>{
  const folder=path.resolve(__dirname,'../study/evidence/benchy-roof');
  const file=path.join(folder,'studio-ui-v041.html');
  const html=fs.readFileSync(file,'utf8');
  const state=JSON.parse(html.match(/<script id="initial-state" type="application\/json">([\s\S]*?)<\/script>/)[1]);
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
    assert.equal(command.settings.retain_native_short_edges,true);
    assert.equal(command.settings.step_mm,.4);
    await page.evaluate(initial=>window.orcaWaveReceive({type:'state',state:{...initial,
      conformal:{phase:'awaiting_slice',original_id:'1',settings:{step_mm:.4,max_slope_deg:30,retain_native_short_edges:true}}}}),state);
    assert.equal(await choice.isChecked(),true);
    assert.equal(await choice.isDisabled(),true);
    await page.screenshot({path:path.join(folder,'studio-ui-v041.png')});
    assert.deepEqual(errors,[]);
    const result={status:'PASS_HEADLESS_COMPONENT',command,errors,native_orca_controlled:false,printer_contacted:false};
    fs.writeFileSync(path.join(folder,'ui-validation-v041.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
