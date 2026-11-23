// Component checks, not a native Orca run; all network requests are rejected.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.WAVE_PLAYWRIGHT||'playwright');
(async()=>{
  const input=path.resolve(process.argv[2]),output=path.resolve(process.argv[3]);
  const scenarios=fs.statSync(input).isDirectory()?[
    {file:path.join(input,'blocked.html'),allowed:false},{file:path.join(input,'allowed.html'),allowed:true}
  ]:[{file:input,allowed:false}];
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath:process.env.WAVE_BROWSER});
  const outcomes=[];
  try{
    for(const scenario of scenarios)for(const width of [700,390]){
      const page=await browser.newPage({viewport:{width,height:760}}),errors=[],requests=[];
      page.on('pageerror',e=>errors.push(e.message));
      await page.route(/^https?:/,async route=>{requests.push(route.request().url());await route.abort()});
      await page.addInitScript(()=>{window.commands=[];window.closedByUser=false;window.orca={
        onMessage:fn=>window.receive=fn,postMessage:m=>window.commands.push(m),close:()=>window.closedByUser=true}});
      await page.goto(pathToFileURL(scenario.file).href);
      // Reproduce host defaults injected after the plugin's stylesheet.
      await page.addStyleTag({content:'body{background:white;color:#303030}h1,h2,dd{color:#303030}small{color:#aaa}button{background:#008f80;color:white}'});
      assert.equal(await page.getByRole('heading',{name:'Enviar para impressora',exact:true}).count(),1);
      assert.equal(await page.locator('#send').isDisabled(),!scenario.allowed);
      assert.equal(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor),'rgb(25, 29, 35)');
      assert.equal(await page.getByRole('alert').count(),1);
      assert.equal(await page.locator('.risk-warning').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(255, 240, 173)');
      assert.equal(await page.locator('.risk-warning').evaluate(el=>getComputedStyle(el).color),'rgb(60, 41, 0)');
      assert.ok(await page.locator('#risk-title').evaluate(el=>parseFloat(getComputedStyle(el).fontSize))>=20);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
      await page.screenshot({path:path.join(output,`dialog-${scenario.allowed?'allowed':'blocked'}-${width}.png`),fullPage:true});
      await page.evaluate(()=>document.querySelector('#send').click());
      await page.evaluate(()=>document.querySelector('#send').click());
      const commands=await page.evaluate(()=>window.commands);
      assert.equal(commands.length,scenario.allowed?1:0);
      if(scenario.allowed){
        assert.deepEqual(commands[0],{action:'send_file',risk_acknowledged:true,confirmation_token:'component-test-token'});
        await page.evaluate(()=>window.receive({message:'Erro de teste; confira o receptor antes de tentar novamente.'}));
        assert.equal(await page.locator('#send').isDisabled(),true,'no automatic retry after uncertainty');
      }
      await page.getByRole('button',{name:'Cancelar',exact:true}).click();
      assert.equal(await page.evaluate(()=>window.closedByUser),true);
      assert.deepEqual(requests,[]);assert.deepEqual(errors,[]);
      outcomes.push({width,host_theme_readable:true,technical_checks_allowed:scenario.allowed,
        yellow_warning:true,confirmation_commands:commands.length,network_requests:0,errors});
      await page.close();
    }
  }finally{await browser.close()}
  const result={status:'PASS_SEND_DIALOG_COMPONENT',native_orca_controlled:false,outcomes};
  fs.writeFileSync(path.join(output,'validation.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
})().catch(e=>{console.error(e);process.exitCode=1});
