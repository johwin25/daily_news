const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const {existsSync}=require('node:fs');
const path=require('node:path');
const {spawn}=require('node:child_process');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const root=path.resolve(__dirname,'../..'),artifacts=process.env.ARTIFACTS||'/tmp/daily-news-v2-screenshots';
const server=spawn('python',['-m','http.server','8766','--bind','127.0.0.1','--directory',root],{stdio:'ignore'});
let browser,checks=0;
const check=(v,message)=>{assert.ok(v,message);checks++;};
async function stable(p,n){await p.waitForFunction(n=>document.querySelector('#reader').dataset.state==='idle'&&document.querySelector('#counter').textContent.startsWith(String(n).padStart(2,'0')),n);checks++;}
(async()=>{try {
 await fs.mkdir(artifacts,{recursive:true});for(let i=0;i<50;i++){try{if((await fetch('http://127.0.0.1:8766/prototype/')).ok)break;}catch{}await delay(100);}
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||(existsSync('/usr/bin/chromium')?'/usr/bin/chromium':undefined),args:['--no-sandbox']});
 const p=await browser.newPage({viewport:{width:390,height:844}});p.setDefaultTimeout(8000);
 const errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto('http://127.0.0.1:8766/prototype/');await p.waitForFunction(()=>[...document.images].every(i=>i.complete));await p.waitForFunction(()=>document.querySelector('#turn').dataset.snapshot==='ready');
 const bounds=await p.locator('#reader').boundingBox(),x=380,y=bounds.y+bounds.height-12;
 await p.mouse.move(x,y);await p.mouse.down();await p.mouse.move(220,y-110,{steps:10});await delay(50);
 check(await p.locator('#reader').getAttribute('data-state')==='dragging','desktop drag live before release');
 const first=await p.locator('#turn').getAttribute('data-normal');
 check(await p.locator('#turn').getAttribute('data-renderer')==='webgl','cached article uses WebGL surface');
 check(Number(await p.locator('#turn').getAttribute('data-vertices'))>100,'curved surface contains tessellated vertices');
 check(await p.locator('#pages>.page').nth(1).isVisible(),'next article exposed before release');
 await p.screenshot({path:`${artifacts}/curl-mouse-shallow.png`});
 await p.mouse.move(220,y-240,{steps:10});await delay(50);
 check(first!==await p.locator('#turn').getAttribute('data-normal'),'same X and changed Y rotates fold geometry');
 await p.screenshot({path:`${artifacts}/curl-mouse-diagonal.png`});
 // Reverse all the way back, pause to remove any flick velocity, then release.
 await p.mouse.move(369,y-3,{steps:16});await delay(150);await p.mouse.up();await stable(p,1);
 check(await p.locator('#turn').evaluate(el=>!el.children.length),'cancel clears mesh resources');
 await p.mouse.move(x,y);await p.mouse.down();await p.mouse.move(200,y-180,{steps:12});await p.mouse.up();await stable(p,2);
 await p.mouse.move(10,y);await p.mouse.down();await p.mouse.move(190,y-210,{steps:12});await delay(50);
 await p.screenshot({path:`${artifacts}/curl-backward.png`});await p.mouse.up();await stable(p,1);
 // Short slow drag must cancel; same travel as a fast flick must commit exactly once.
 await p.mouse.move(x,y);await p.mouse.down();await p.mouse.move(305,y-10,{steps:5});await delay(150);await p.mouse.up();await stable(p,1);
 await p.mouse.move(x,y);await p.mouse.down();await p.mouse.move(305,y-10);await p.mouse.up();await stable(p,2);
 await p.mouse.move(x,y);await p.mouse.down();await p.mouse.move(200,y-150,{steps:10});await p.keyboard.press('Escape');await stable(p,2);await p.mouse.up();
 // Beginning inside a summary protects native scrolling even for horizontal input.
 const read=p.locator('#pages>.page').nth(1).locator('.read');await read.click();
 const summary=await p.locator('#summary-1').boundingBox();await p.mouse.move(summary.x+summary.width*.8,summary.y+20);await p.mouse.down();await p.mouse.move(summary.x+15,summary.y+30,{steps:6});await p.mouse.up();await stable(p,2);await read.click();
 // Orientation interruption resolves to the original page and releases resources.
 await p.mouse.move(x,y);await p.mouse.down();await p.mouse.move(200,y-140,{steps:10});await p.setViewportSize({width:844,height:390});await p.mouse.up();await stable(p,2);check(await p.locator('#turn').evaluate(el=>!el.children.length),'resize cleans active drag');
 await p.setViewportSize({width:390,height:844});await p.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));await p.keyboard.press('ArrowLeft');await stable(p,1);
 // Frame timing measured in this headless environment, not a claim about iPhone FPS.
 await p.mouse.move(x,y);await p.mouse.down();await p.mouse.move(280,y-100,{steps:5});
 await p.evaluate(()=>{window.frameTimes=[];window.lastFrame=performance.now();window.sample=true;function tick(t){window.frameTimes.push(t-window.lastFrame);window.lastFrame=t;if(window.sample)requestAnimationFrame(tick);}requestAnimationFrame(tick);});
 for(let i=0;i<40;i++)await p.mouse.move(280-i*2,y-100-i*2);
 const times=await p.evaluate(()=>{window.sample=false;return window.frameTimes.slice(1).sort((a,b)=>a-b);});
 check(times.length>20,'frame timing samples collected');
 await fs.writeFile(`${artifacts}/curl-frame-timing.json`,JSON.stringify({environment:'Headless Chromium; not iPhone hardware',frames:times.length,median:times[Math.floor(times.length*.5)],p95:times[Math.floor(times.length*.95)]},null,2));
 await p.keyboard.press('Escape');await p.mouse.up();await stable(p,1);check(errors.length===0,`no JavaScript errors: ${errors}`);
 await p.close();
 // Browser touch emulation on the bottom-right grip, including a steep diagonal.
 const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});const tp=await context.newPage();tp.setDefaultTimeout(8000);await tp.goto('http://127.0.0.1:8766/prototype/');await tp.waitForFunction(()=>document.querySelector('#turn').dataset.snapshot==='ready');
 const c=await context.newCDPSession(tp);await c.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});
 for(let i=1;i<=16;i++){await c.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x-170*i/16,y:y-245*i/16}]});await delay(12);}
 check(await tp.locator('#reader').getAttribute('data-state')==='dragging','steep diagonal browser touch remains captured');
 await tp.screenshot({path:`${artifacts}/curl-touch-diagonal.png`});await c.send('Input.dispatchTouchEvent',{type:'touchCancel',touchPoints:[]});await stable(tp,1);
 check(await tp.locator('#turn').evaluate(el=>!el.children.length),'touch cancel cleans mesh');await context.close();
 // No-WebGL browsers retain a curved DOM mesh rather than falling back to a rigid flip.
 const fallbackContext=await browser.newContext({viewport:{width:390,height:844}});
 await fallbackContext.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...args){return kind==='webgl'?null:original.call(this,kind,...args);};});
 const fp=await fallbackContext.newPage();fp.setDefaultTimeout(8000);await fp.goto('http://127.0.0.1:8766/prototype/');
 await fp.mouse.move(x,y);await fp.mouse.down();await fp.mouse.move(220,y-210,{steps:10});
 check(await fp.locator('#turn').getAttribute('data-renderer')==='dom','WebGL unavailable selects curved DOM fallback');
 check(await fp.locator('.curl-strip').count()>30,'fallback uses a material mesh');await fp.screenshot({path:`${artifacts}/curl-fallback.png`});
 await fp.keyboard.press('Escape');await fp.mouse.up();await stable(fp,1);await fallbackContext.close();
 // Graphics context loss during a held drag also degrades without losing navigation.
 const lossContext=await browser.newContext({viewport:{width:390,height:844}});const lp=await lossContext.newPage();lp.setDefaultTimeout(8000);await lp.goto('http://127.0.0.1:8766/prototype/');
 await lp.waitForFunction(()=>document.querySelector('#turn').dataset.snapshot==='ready');
 await lp.mouse.move(x,y);await lp.mouse.down();await lp.mouse.move(230,y-140,{steps:10});
 const canLose=await lp.locator('.curl-canvas').evaluate(canvas=>{const extension=canvas.getContext('webgl').getExtension('WEBGL_lose_context');if(!extension)return false;extension.loseContext();return true;});
 check(canLose,'browser context-loss extension available');await lp.waitForFunction(()=>document.querySelector('#turn').dataset.renderer==='dom');
 await lp.mouse.move(210,y-160);await lp.keyboard.press('Escape');await lp.mouse.up();await stable(lp,1);await lossContext.close();
 console.log(`PASS curl: ${checks} assertions; mouse, Y tracking, reversal, distance/velocity, interruption, touch corner, frame samples`);
} finally {if(browser)await browser.close();server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
