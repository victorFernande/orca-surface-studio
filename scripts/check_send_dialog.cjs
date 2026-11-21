// Component checks, not a native Orca run; all network requests are rejected.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.WAVE_PLAYWRIGHT||'playwright');
(async()=>{
  const input=path.resolve(process.argv[2]),output=path.resolve(process.argv[3]);
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath:process.env.WAVE_BROWSER});
  const outcomes=[];
  try{
    for(const width of [660,390]){
      const page=await browser.newPage({viewport:{width,height:760}}),errors=[],requests=[];
      page.on('pageerror',e=>errors.push(e.message));
      await page.route(/^https?:/,async route=>{requests.push(route.request().url());await route.abort()});
      await page.addInitScript(()=>{window.commands=[];window.closedByUser=false;window.orca={
        onMessage:fn=>window.receive=fn,postMessage:m=>window.commands.push(m),close:()=>window.closedByUser=true}});
      await page.goto(pathToFileURL(input).href);
      // Reproduce host defaults injected after the plugin's stylesheet.
      await page.addStyleTag({content:'body{background:white;color:#303030}h1,h2,dd{color:#303030}small{color:#aaa}button{background:#008f80;color:white}'});
      assert.equal(await page.getByRole('heading',{name:'Enviar para impressora',exact:true}).count(),1);
      assert.equal(await page.locator('#send').isDisabled(),true);
      assert.equal(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor),'rgb(25, 29, 35)');
      assert.equal(await page.locator('.notice').evaluate(el=>getComputedStyle(el).color),'rgb(237, 241, 244)');
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
      await page.evaluate(()=>document.querySelector('#send').click());
      assert.deepEqual(await page.evaluate(()=>window.commands),[]);
      await page.screenshot({path:path.join(output,`dialog-${width}.png`),fullPage:true});
      await page.getByRole('button',{name:'Fechar',exact:true}).click();
      assert.equal(await page.evaluate(()=>window.closedByUser),true);
      assert.deepEqual(requests,[]);assert.deepEqual(errors,[]);
      outcomes.push({width,host_theme_readable:true,send_disabled:true,network_requests:0,errors});
      await page.close();
    }
  }finally{await browser.close()}
  const result={status:'PASS_SEND_DIALOG_COMPONENT',native_orca_controlled:false,outcomes};
  fs.writeFileSync(path.join(output,'validation.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
})().catch(e=>{console.error(e);process.exitCode=1});
