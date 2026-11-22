// Local component exercise only; never contacts Orca or a printer.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.WAVE_PLAYWRIGHT||'playwright');
(async()=>{
  const input=path.resolve(process.argv[2]),output=path.resolve(process.argv[3]);
  const html=fs.readFileSync(input,'utf8');
  const state=JSON.parse(html.match(/<script id="initial-state" type="application\/json">([\s\S]*?)<\/script>/)[1]);
  state.head_map={profile_key:'fixture-A',identity:{printer_name:'Fixture A',nozzle_mm:.4},components:[],print_allowed:false};
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath:process.env.WAVE_BROWSER});
  const outcomes=[];
  try{
    for(const width of [1580,390]){
      const page=await browser.newPage({viewport:{width,height:1000}}),errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      await page.addInitScript(state=>{
        window.commands=[];window.orca={onMessage:f=>window.receiveState=f,postMessage:m=>{
          const data=typeof m==='string'?JSON.parse(m):m;window.commands.push(data);
          if(data.action==='refresh')window.receiveState?.({type:'state',state});
        }};
      },state);
      await page.goto(pathToFileURL(input).href);
      assert.equal(await page.locator('#safety-warning').isVisible(),true);
      assert.match(await page.locator('#safety-warning').innerText(),/Use at your own risk/);
      await page.locator('#guide-next').click();
      assert.equal(await page.locator('#placement-tools').isVisible(),true);
      const source=await page.evaluate(()=>JSON.stringify(state.model_preview));
      await page.locator('#placement-right').click();
      assert.equal(await page.locator('#placement-degrees').inputValue(),'90');
      assert.equal(await page.evaluate(()=>surfaceSettings().placement_degrees),90);
      assert.equal(await page.evaluate(()=>JSON.stringify(state.model_preview)),source);
      assert.equal(await page.evaluate(()=>placementModel(state.model_preview).objects[0].triangles[0][0][2]===state.model_preview.objects[0].triangles[0][0][2]),true);
      assert.notEqual(await page.evaluate(()=>JSON.stringify(placementModel(state.model_preview))),source);
      await page.locator('#head-map-editor summary').click();
      assert.equal(await page.locator('#head-map-clearance_z').inputValue(),'');
      await page.screenshot({path:path.join(output,`placement-map-empty-${width}.png`),fullPage:true});
      for(const [key,value] of Object.entries({x_min:-12,x_max:8,y_min:10,y_max:45,clearance_z:3}))
        await page.locator('#head-map-'+key).fill(String(value));
      await page.locator('#head-map-add').click();
      assert.equal(await page.locator('#head-map-parts').getByText('Carcaça traseira · 3 mm').count(),1);
      await page.locator('#head-map-save').click();
      const save=await page.evaluate(()=>window.commands.findLast(c=>c.action==='save_head_map'));
      assert.equal(save.profile_key,'fixture-A');assert.equal(save.components[0].y_min,10);
      await page.screenshot({path:path.join(output,`placement-map-${width}.png`),fullPage:true});
      await page.locator('#guide-next').click();await page.locator('#guide-next').click();
      const build=await page.evaluate(()=>window.commands.findLast(c=>c.action==='build_surface'));
      assert.equal(build.settings.placement_degrees,90);assert.equal(build.open_preview,false);
      assert.equal(await page.evaluate(()=>window.commands.some(c=>/print|upload|send_file/.test(c.action))),false);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
      assert.deepEqual(errors,[]);outcomes.push({width,rotation_sent:90,map_separate_from_printing:true,errors});await page.close();
    }
  }finally{await browser.close()}
  const result={status:'PASS_PLACEMENT_COMPONENT',native_orca_controlled:false,printer_contacted:false,outcomes};
  fs.writeFileSync(path.join(output,'validation.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
})().catch(e=>{console.error(e);process.exitCode=1});
