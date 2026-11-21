// Headless component check. Never connects to Orca or a printer.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.env.WAVE_PLAYWRIGHT || 'playwright');

(async () => {
  const folder=path.resolve(__dirname,'../study/evidence/sine-vase');
  const html=fs.readFileSync(path.join(folder,'studio.html'),'utf8');
  const state=JSON.parse(html.match(/<script id="initial-state" type="application\/json">([\s\S]*?)<\/script>/)[1]);
  const browser=await chromium.launch({headless:true,executablePath:process.env.WAVE_BROWSER});
  const errors=[];
  try {
    const page=await browser.newPage({viewport:{width:1440,height:960}});
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(pathToFileURL(path.join(folder,'studio.html')).href);
    await page.getByRole('button',{name:'Vaso senoidal',exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Vaso senoidal',exact:true}).getAttribute('aria-pressed'),'true');
    assert.ok(await page.getByRole('spinbutton',{name:'Intensidade das ondas',exact:true}).isVisible());
    assert.ok(await page.getByRole('spinbutton',{name:'Ondas por volta',exact:true}).isVisible());
    assert.ok(!await page.getByRole('spinbutton',{name:'Comprimento de onda',exact:true}).isVisible());
    const layers=await page.locator('#layer option').evaluateAll(items=>items.map(i=>i.value).filter(Boolean));
    await page.locator('#layer').selectOption(layers.at(-1));
    const zRange=await page.evaluate(()=>{
      const indices=viewer.active(); const points=viewer.lens().flat;
      const zs=indices.map(i=>points[i*3+2]);return [Math.min(...zs),Math.max(...zs)];
    });
    assert.ok(zRange[1]-zRange[0]>1.4);
    await page.screenshot({path:path.join(folder,'studio-top-layer.png')});
    await page.locator('#layer').selectOption('');
    await page.getByRole('button',{name:'Enquadrar trajetória',exact:true}).click();
    await page.screenshot({path:path.join(folder,'studio-full.png')});
    await page.close();

    const live=await browser.newPage({viewport:{width:1440,height:960}});
    live.on('pageerror',e=>errors.push(e.message));
    await live.addInitScript(initial=>{
      window.testMessages=[];
      const state={...initial,demo:false,native:true,capture_setup_required:false};
      window.orca={onMessage:fn=>window.testReceive=fn,postMessage:message=>{
        const data=typeof message==='string'?JSON.parse(message):message;
        window.testMessages.push(data);
        if(['refresh','poll'].includes(data.action))window.testReceive?.({type:'state',state});
      }};
    },state);
    await live.goto(pathToFileURL(path.join(folder,'studio.html')).href);
    await live.evaluate(initial=>window.orcaWaveReceive({type:'state',state:{...initial,demo:false,native:true}}),state);
    await live.getByRole('spinbutton',{name:'Intensidade das ondas',exact:true}).fill('2');
    await live.getByRole('spinbutton',{name:'Ondas por volta',exact:true}).fill('8');
    await live.evaluate(initial=>{
      const current={...initial,demo:false,native:true,revision:'new-config',capture:{...initial.capture,revision:'new-config'}};
      window.orcaWaveReceive({type:'state',state:{...current,status:'analyzing',objects:[]}});
      window.orcaWaveReceive({type:'state',state:current});
    },state);
    assert.equal(await live.getByRole('spinbutton',{name:'Intensidade das ondas',exact:true}).inputValue(),'2');
    assert.equal(await live.getByRole('spinbutton',{name:'Ondas por volta',exact:true}).inputValue(),'8');
    await live.getByRole('button',{name:'Gerar e abrir Preview',exact:true}).click();
    const command=await live.evaluate(()=>window.testMessages.findLast(m=>m.action==='generate'));
    assert.equal(command.parameters_by_object['100'].mode,'combined');
    assert.equal(command.parameters_by_object['100'].amplitude_mm,2);
    assert.equal(command.parameters_by_object['100'].wave_count,8);
    await live.close();

    const dock=await browser.newPage({viewport:{width:430,height:850}});
    dock.on('pageerror',e=>errors.push(e.message));
    await dock.setContent(html.replace('data-mode="page"','data-mode="dock"'));
    await dock.getByRole('spinbutton',{name:'Ondas por volta',exact:true}).waitFor();
    await dock.screenshot({path:path.join(folder,'studio-dock.png')});
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(folder,'ui-checks.json'),JSON.stringify({status:'PASS_HEADLESS',z_range_top_layer_mm:zRange,
      outgoing_generation:command,errors,native_orca_controlled:false,printer_contacted:false},null,2));
    console.log(JSON.stringify({status:'PASS_HEADLESS',z_range_top_layer_mm:zRange,errors}));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1});
