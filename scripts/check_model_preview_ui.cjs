// Offline rendering of user-supplied fixtures; no native Orca or printer calls.
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.WAVE_PLAYWRIGHT||'playwright');
(async()=>{
  const before=path.resolve(process.argv[2]),after=path.resolve(process.argv[3]),output=path.resolve(process.argv[4]);
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath:process.env.WAVE_BROWSER});
  const cases=[];
  try{
    for(const [label,file] of [['before',before],['after',after]]){
      const page=await browser.newPage({viewport:{width:1580,height:1000}}),errors=[];
      page.on('pageerror',error=>errors.push(error.message));
      await page.route('**/*',route=>route.request().url().startsWith('file:')?route.continue():route.abort());
      await page.addInitScript(()=>{
        window.commands=[];window.orca={onMessage:f=>window.fixtureReceive=f,postMessage:message=>{
          const command=typeof message==='string'?JSON.parse(message):message;
          window.commands.push(command);
          if(command.action==='refresh')window.fixtureReceive?.({type:'state',state:JSON.parse(document.querySelector('#initial-state').textContent)});
        }};
      });
      const started=performance.now();await page.goto(pathToFileURL(file).href);
      await page.waitForFunction(()=>typeof viewer!=='undefined'&&viewer.mesh?.flat.length>0);
      const metrics=await page.evaluate(()=>{
        const bounds=state.model_preview.objects[0].bounds;
        viewer.center=bounds[0].map((v,i)=>(v+bounds[1][i])/2);
        viewer.radius=Math.hypot(...bounds[0].map((v,i)=>bounds[1][i]-v))/2;
        viewer.draw();
        return {triangles:viewer.mesh.flat.length/9,webgl:Boolean(viewer.gl),
          sourceTriangles:state.model_preview.objects[0].source_triangles,
          gpuError:viewer.gl?.getError(),buffers:viewer.buffers.length};
      });
      metrics.loadMilliseconds=performance.now()-started;
      assert(metrics.webgl,'WebGL rendering must be exercised');assert.equal(metrics.gpuError,0);
      if(label==='after')assert.equal(metrics.triangles,metrics.sourceTriangles);
      await page.locator('#canvas').screenshot({path:path.join(output,label+'.png')});
      if(label==='after'){
        const integrity=await page.evaluate(()=>{
          const source=state.model_preview,mesh=viewer.mesh,sequence=state.sequence+1;
          window.orcaWaveReceive({type:'state',state:{...state,sequence,model_preview:{id:source.id,unchanged:true}}});
          const cachePreserved=state.model_preview===source&&viewer.mesh===mesh;
          window.orcaWaveReceive({type:'state',state:{...state,sequence:sequence+1,model_preview:{id:'missing-model',unchanged:true}}});
          const missingReferenceRecovered=state.model_preview===source&&window.commands.at(-1).action==='refresh';
          window.orcaWaveReceive({type:'state',state:{...state,sequence:sequence+2,model_preview:source}});
          const c=document.querySelector('#canvas'),r=c.getBoundingClientRect(),start=performance.now();
          let hit=null;
          for(const x of [.5,.45,.55])for(const y of [.5,.6,.4])if(!hit)hit=viewer.pick(r.x+r.width*x,r.y+r.height*y);
          const pickMilliseconds=performance.now()-start;
          for(let i=0;i<12;i++)viewer.rotate(.03,-.01);
          return {cachePreserved,missingReferenceRecovered,pickable:Boolean(hit),pickMilliseconds,buffers:viewer.buffers.length,gpuError:viewer.gl.getError()};
        });
        assert(integrity.cachePreserved,'poll reference must keep geometry and GPU buffers');
        assert(integrity.missingReferenceRecovered,'unknown mesh references must request a full state');
        assert(integrity.pickable,'the full-resolution model must be pickable');
        assert.equal(integrity.buffers,metrics.buffers);assert.equal(integrity.gpuError,0);
        await page.locator('#guide-next').click();
        const sourceId=await page.evaluate(()=>state.model_preview.id);
        await page.locator('#placement-right').click();
        assert.equal(await page.evaluate(()=>surfaceSettings().placement_degrees),90);
        assert.equal(await page.evaluate(()=>state.model_preview.id),sourceId);
        assert.equal(await page.evaluate(()=>viewer.mesh.flat.length/9),metrics.sourceTriangles);
        await page.locator('#canvas').screenshot({path:path.join(output,'after-rotated.png')});
        await page.evaluate(()=>window.orcaWaveReceive({type:'state',state:{...state,sequence:state.sequence+1,objects:[],model_preview:null}}));
        assert.equal(await page.evaluate(()=>viewer.mesh.flat.length),0,'project changes must clear geometry');
        metrics.integrity=integrity;
      }
      assert.equal(await page.evaluate(()=>window.commands.some(c=>/print|upload|send_file/.test(c.action))),false);
      assert.deepEqual(errors,[]);cases.push({label,...metrics,errors});await page.close();
    }
  }finally{await browser.close()}
  const result={status:'PASS_FAITHFUL_MODEL_PREVIEW',cases,nativeOrcaControlled:false,printerContacted:false};
  fs.writeFileSync(path.join(output,'validation.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
})().catch(error=>{console.error(error);process.exitCode=1});
