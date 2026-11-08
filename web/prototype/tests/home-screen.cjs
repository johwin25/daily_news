const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {existsSync}=require('node:fs');
const path=require('node:path');
const server=spawn('python',['-m','http.server','8877','--bind','127.0.0.1','--directory',path.resolve(__dirname,'../..')],{stdio:'ignore'});
const delay=ms=>new Promise(r=>setTimeout(r,ms));
let browser;
(async()=>{try {
 for(let i=0;i<50;i++){try{if((await fetch('http://127.0.0.1:8877/prototype/')).ok)break;}catch{}await delay(100);}
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||(existsSync('/usr/bin/chromium')?'/usr/bin/chromium':undefined),args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 const page=await context.newPage();await page.goto('http://127.0.0.1:8877/prototype/');
 const result=await page.evaluate(async()=>{
  const url=document.querySelector('link[rel="manifest"]').href;
  const response=await fetch(url);if(!response.ok)throw Error('Manifest missing');
  const data=await response.json();
  const icon=document.querySelector('link[rel="apple-touch-icon"]').href;
  const iconResponse=await fetch(icon);
  return {data,start:new URL(data.start_url,url).pathname,scope:new URL(data.scope,url).pathname,
   appleTitle:document.querySelector('meta[name="apple-mobile-web-app-title"]').content,
   appleCapable:document.querySelector('meta[name="apple-mobile-web-app-capable"]').content,
   iconStatus:iconResponse.status,iconPath:new URL(icon).pathname};
 });
 assert.equal(result.data.display,'standalone');assert.equal(result.start,'/prototype/');assert.equal(result.scope,'/prototype/');
 assert.equal(result.appleCapable,'yes');assert.equal(result.appleTitle,'Daily News 2.0');assert.equal(result.iconStatus,200);assert.equal(result.iconPath,'/app-icon.png');
 assert.equal(context.serviceWorkers().length,0);
 console.log('PASS: 8 Home Screen metadata checks; standalone scope, start URL, Apple title/capability, original icon, no service worker');
 }finally{if(browser)await browser.close();server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
