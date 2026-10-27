import assert from 'node:assert/strict';
import {createFold,screenFold,bend,clipStrip,stripTransform,CURL} from '../curl-geometry.js';
let checks=0;
function close(a,b,message){assert.ok(Math.abs(a-b)<.015,`${message}: ${a} vs ${b}`);checks++;}
for(const direction of [1,-1])for(const [width,height] of [[375,561],[390,738],[844,316]]) {
 const anchor={x:direction===1?width:0,y:height-15};
 for(const dx of [20,90,width*.6,width*2])for(const dy of [0,-80,-height*.4]) {
  const pointer={x:anchor.x-dx*direction,y:anchor.y+dy};
  const fold=createFold(width,height,anchor,pointer),tip=bend(anchor,fold);
  close(tip.x,pointer.x,'physical tip x');close(tip.y,pointer.y,'physical tip y');
  const sf=screenFold(width,height,anchor,pointer),st=bend(anchor,sf),k=1400/(1400-st.z);
  close(width/2+(st.x-width/2)*k,pointer.x,'projected tip x');
  close(height/2+(st.y-height/2)*k,pointer.y,'projected tip y');
  for(let i=0;i<CURL.segments;i++) {
   const low=i*Math.PI*sf.radius/CURL.segments,high=(i+1)*Math.PI*sf.radius/CURL.segments;
   const polygon=clipStrip(sf,low,high);
   for(const p of polygon){assert.ok(p.x>=-.001&&p.x<=width+.001&&p.y>=-.001&&p.y<=height+.001);checks++;}
   const transform=stripTransform(sf,(low+high)/2,{x:0,y:0});assert.ok(transform.matrix.every(Number.isFinite));checks++;
  }
 }
 const horizontal=createFold(width,height,anchor,{x:anchor.x-120*direction,y:anchor.y});
 const diagonal=createFold(width,height,anchor,{x:anchor.x-120*direction,y:anchor.y-160});
 assert.notDeepEqual(horizontal.n,diagonal.n);checks++;
}
console.log(`PASS geometry: ${checks} checks (both directions, perspective grip tracking, clipping, finite matrices, Y-dependent axis)`);
