const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const {existsSync}=require('node:fs');
const path=require('node:path');
const {spawn}=require('node:child_process');
const root=path.resolve(__dirname,'../..'), artifacts=process.env.ARTIFACTS||'/tmp/daily-news-v2-screenshots';
const server=spawn('python',['-m','http.server','8765','--bind','127.0.0.1','--directory',root],{stdio:'ignore'});
const delay=ms=>new Promise(r=>setTimeout(r,ms));
let browser,checks=0;
function check(value,message){assert.ok(value,message);checks++;}
async function count(page,n){await page.waitForFunction(n=>document.querySelector('#counter').textContent.startsWith(String(n).padStart(2,'0')),n);check(true,`story ${n}`);}
async function pointer(page,dx,{cancel=false,dy=0}={}){
 await page.evaluate(({dx,dy,cancel})=>{
  const el=document.querySelector('#reader'),y=el.getBoundingClientRect().top+70,x=dx<0?innerWidth-30:30;
  const send=(type,px,py)=>el.dispatchEvent(new PointerEvent(type,{bubbles:true,pointerId:81,pointerType:'touch',isPrimary:true,button:0,clientX:px,clientY:py}));
  // Synthetic events do not create a browser active pointer; stub only capture for this test.
  const original=el.setPointerCapture;el.setPointerCapture=()=>{};
  send('pointerdown',x,y);send('pointermove',x+dx,y+dy);send(cancel?'pointercancel':'pointerup',x+dx,y+dy);el.setPointerCapture=original;
 },{dx,dy,cancel});await delay(550);
}
async function touch(page,from,to){const c=await page.context().newCDPSession(page);await c.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:from[0],y:from[1]}]});for(let i=1;i<=12;i++){await c.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:from[0]+(to[0]-from[0])*i/12,y:from[1]+(to[1]-from[1])*i/12}]});await delay(12);}await c.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await c.detach();await delay(550);}
async function layout(page){const result=await page.evaluate(()=>{
 const page=document.querySelector('#pages>.page:not([hidden])'),read=page.querySelector('.read').getBoundingClientRect(),reader=document.querySelector('#reader').getBoundingClientRect();
 return {overflow:document.documentElement.scrollWidth>innerWidth,readVisible:read.top>=reader.top&&read.bottom<=reader.bottom+1,images:[...document.images].filter(i=>!i.closest('#turn')).every(i=>i.complete&&i.naturalWidth>0)};
});check(!result.overflow,'no horizontal overflow');check(result.readVisible,'read controls visible');check(result.images,'local photos loaded');}
(async()=>{try{
 await fs.mkdir(artifacts,{recursive:true});for(let i=0;i<50;i++){try{if((await fetch('http://127.0.0.1:8765/prototype/')).ok)break;}catch{}await delay(100);}
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||(existsSync('/usr/bin/chromium')?'/usr/bin/chromium':undefined),headless:true,args:['--no-sandbox']});
 for(const [width,height] of [[375,667],[390,844],[430,932],[844,390]]){
  const context=await browser.newContext({viewport:{width,height},isMobile:true,hasTouch:true,deviceScaleFactor:1});const page=await context.newPage();page.setDefaultTimeout(8000);const requests=[];page.on('request',r=>requests.push(r.url()));const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  await page.goto('http://127.0.0.1:8765/prototype/');await page.waitForFunction(()=>[...document.images].every(i=>i.complete));await count(page,1);await layout(page);
  check(await page.locator('#previous').isDisabled(),'first boundary disabled');await pointer(page,180);await count(page,1);
  await page.screenshot({path:`${artifacts}/${width}x${height}-cover.png`});
  const card=page.locator('#pages>.page').nth(0),read=card.locator('.read'),summary=card.locator('.summary');
  await read.click();check(await read.getAttribute('aria-expanded')==='true','expanded');await layout(page);
  check(await summary.evaluate(e=>e.scrollHeight>e.clientHeight),'summary has scrollable content');
  await summary.evaluate(e=>e.scrollTop=e.scrollHeight);check(await summary.evaluate(e=>e.scrollTop>0),'summary scrolls');check(await read.isVisible(),'collapse remains visible');
  await page.screenshot({path:`${artifacts}/${width}x${height}-expanded.png`});await read.click();check(await summary.isHidden(),'collapsed');
  await pointer(page,-22);await count(page,1);await pointer(page,-180,{cancel:true});await count(page,1);check(await page.locator('#turn').getAttribute('class')!=='active','cancel restores turn');
  await pointer(page,15,{dy:130});await count(page,1);
  // Browser touch emulation: Chromium dispatches genuine browser touch/pointer routing.
  await touch(page,[width-35,125],[35,125]);await count(page,2);
  await touch(page,[35,125],[width-35,125]);await count(page,1);
  await page.keyboard.press('ArrowRight');await count(page,2);await delay(550);
  await page.keyboard.press('ArrowLeft');await count(page,1);await delay(550);
  await page.evaluate(()=>{for(let i=0;i<10;i++)document.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));});await delay(550);await count(page,2);
  await page.evaluate(()=>{const el=document.querySelector('#reader');const original=el.setPointerCapture;el.setPointerCapture=()=>{};for(let i=0;i<8;i++){for(const [type,x] of [['pointerdown',300],['pointermove',70],['pointerup',70]])el.dispatchEvent(new PointerEvent(type,{bubbles:true,pointerId:90+i,isPrimary:true,button:0,clientX:x,clientY:140}));}el.setPointerCapture=original;});await delay(550);await count(page,3);await page.keyboard.press('ArrowRight');await delay(550);await count(page,4);
  check(await page.locator('#next').isDisabled(),'last boundary disabled');await pointer(page,-180);await count(page,4);
  await page.locator('#reader').focus();await page.keyboard.press('Tab');check(await page.evaluate(()=>document.activeElement.matches('.read')),'keyboard focuses visible read control');await page.keyboard.press('Enter');check(await page.locator('#pages>.page').nth(3).locator('.read').getAttribute('aria-expanded')==='true','keyboard expands');
  check((await context.serviceWorkers()).length===0,'no service worker');check(requests.every(url=>url.startsWith('http://127.0.0.1:8765/')),'no external or live news requests');check(errors.length===0,`no console/page errors: ${errors}`);await context.close();console.log(`PASS ${width}×${height}`);
 }
 const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,reducedMotion:'reduce'});const page=await context.newPage();await page.goto('http://127.0.0.1:8765/prototype/');await page.keyboard.press('ArrowRight');await count(page,2);check(await page.locator('#turn').evaluate(e=>getComputedStyle(e).display==='none'),'reduced motion has no curl');await pointer(page,-220);await count(page,3);await context.close();
 const touchContext=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});const tp=await touchContext.newPage();await tp.goto('http://127.0.0.1:8765/prototype/');await tp.locator('#pages>.page').nth(0).locator('.read').click();const box=await tp.locator('#summary-0').boundingBox();await touch(tp,[box.x+box.width/2,box.y+box.height-15],[box.x+box.width/2,box.y+15]);check(await tp.locator('#summary-0').evaluate(e=>e.scrollTop>0),'browser touch scrolls summary');await count(tp,1);
 // Capture an actual mid-turn frame, then cancellation from browser touch stream.
 await tp.locator('#pages>.page').nth(0).locator('.read').click();const cd=await touchContext.newCDPSession(tp);await cd.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:355,y:160}]});await cd.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:200,y:160}]});await delay(80);await tp.screenshot({path:`${artifacts}/page-turn.png`});check(await tp.locator('#turn').evaluate(e=>e.classList.contains('active')&&getComputedStyle(e).transform!=='none'),'curl uses perspective transform');await cd.send('Input.dispatchTouchEvent',{type:'touchCancel',touchPoints:[]});await delay(550);await count(tp,1);await tp.locator('#pages>.page').nth(0).locator('.read').click();await tp.setViewportSize({width:844,height:390});await layout(tp);await tp.setViewportSize({width:390,height:844});await layout(tp);await touchContext.close();
 const failed=await browser.newContext({viewport:{width:375,height:667}});const fp=await failed.newPage();await fp.route('**/assets/*',r=>r.abort());await fp.goto('http://127.0.0.1:8765/prototype/');await fp.locator('#pages>.page').nth(0).locator('.fallback').waitFor({state:'visible'});check(await fp.locator('h1').first().isVisible(),'image failure retains headline');await fp.locator('#pages>.page').nth(0).locator('.read').click();check(await fp.locator('#summary-0').isVisible(),'image failure still permits reading');await fp.locator('#pages>.page').nth(0).locator('.read').click();await fp.screenshot({path:`${artifacts}/image-failure.png`});await failed.close();
 console.log(`PASS ${checks} assertions; screenshots: ${artifacts}`);
 }finally{if(browser)await browser.close();server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
