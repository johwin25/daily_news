import {CURL} from './curl-geometry.js';
import {CurlRenderer} from './curl-renderer.js';

/** Input + settling controller; article data and rendering remain separate. */
export class CurlNavigation {
  constructor({reader,host,cards,previous,next,onChange}) {
    Object.assign(this,{reader,cards,previous,next,onChange});
    this.index=0;this.state='idle';this.gesture=null;this.frame=0;
    this.renderer=new CurlRenderer(host);this.reduced=matchMedia('(prefers-reduced-motion: reduce)');
    this.events=new AbortController();const signal=this.events.signal;
    const on=(el,name,fn)=>el.addEventListener(name,fn,{signal});
    on(reader,'click',e=>{if(e.target.closest('.read'))this.warm();});
    on(reader,'pointerdown',e=>this.down(e));on(reader,'pointermove',e=>this.move(e));
    on(reader,'pointerup',e=>this.finish(e));on(reader,'pointercancel',e=>this.finish(e,true));
    on(reader,'lostpointercapture',e=>this.finish(e,true));
    on(previous,'click',()=>this.go(-1));on(next,'click',()=>this.go(1));
    on(document,'keydown',e=>{if(e.altKey||e.ctrlKey||e.metaKey)return;
      if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();this.go(e.key==='ArrowRight'?1:-1);}
      if(e.key==='Escape')this.cancel();});
    on(window,'blur',()=>this.cancel());on(window,'resize',()=>this.reset());
    on(this.reduced,'change',()=>this.reset());
    on(document,'visibilitychange',()=>{if(document.hidden)this.reset();});
    on(window,'pagehide',e=>e.persisted?this.reset():this.destroy());this.update();
  }
  update(){this.cards.forEach((card,i)=>{card.hidden=i!==this.index;card.inert=i!==this.index;});this.previous.disabled=this.index===0;this.next.disabled=this.index===this.cards.length-1;this.onChange(this.index);this.reader.dataset.state=this.state;this.warm();}
  warm(){const b=this.reader.getBoundingClientRect();this.renderer.warm(this.cards[this.index],b.width,b.height);}
  valid(direction){return this.index+direction>=0&&this.index+direction<this.cards.length;}
  prepare(g){
    if(this.reduced.matches)return;
    this.renderer.prepare(this.cards[this.index],g.width,g.height);
    this.cards[this.index].hidden=true;this.cards[this.index+g.direction].hidden=false;
    this.reader.classList.add('turning');
  }
  down(e){
    if(this.state!=='idle'||!e.isPrimary||e.button!==0||e.target.closest('button,a,.summary'))return;
    const bounds=this.reader.getBoundingClientRect();
    this.gesture={id:e.pointerId,startX:e.clientX-bounds.left,startY:e.clientY-bounds.top,
      bounds,width:bounds.width,height:bounds.height,lastX:e.clientX,lastTime:e.timeStamp,velocity:0,progress:0};
    this.state='tracking';this.reader.dataset.state=this.state;
    this.reader.setPointerCapture(e.pointerId);
  }
  move(e){
    const g=this.gesture;if(!g||g.id!==e.pointerId)return;
    const x=e.clientX-g.bounds.left,y=e.clientY-g.bounds.top;
    const dx=x-g.startX,dy=y-g.startY;
    if(this.state==='tracking') {
      if(Math.max(Math.abs(dx),Math.abs(dy))<CURL.threshold)return;
      if(Math.abs(dx)<Math.abs(dy)*CURL.directionRatio){this.release(g);this.gesture=null;this.state='idle';this.update();return;}
      g.direction=dx<0?1:-1;
      if(!this.valid(g.direction)){this.release(g);this.gesture=null;this.state='idle';this.update();return;}
      g.anchor={x:g.direction>0?g.width:0,y:g.startY};
      this.state='dragging';this.reader.dataset.state=this.state;this.prepare(g);
    }
    if(this.state!=='dragging')return;
    const now=e.timeStamp,dt=now-g.lastTime;
    if(dt>0)g.velocity=.25*g.velocity+.75*((g.lastX-e.clientX)*g.direction/dt);
    g.lastX=e.clientX;g.lastTime=now;
    const travel=Math.max(0,-dx*g.direction);
    g.progress=travel/g.width;
    g.pointer={x:g.anchor.x-travel*g.direction,y:g.anchor.y+dy};
    // One render per animation frame; pointer events never force repeated layout.
    if(!this.reduced.matches&&!this.frame)this.frame=requestAnimationFrame(()=>{this.frame=0;if(this.gesture===g)this.renderer.render(g.anchor,g.pointer);});
  }
  release(g){if(this.reader.hasPointerCapture(g.id))this.reader.releasePointerCapture(g.id);}
  finish(e,cancelled=false){
    const g=this.gesture;if(!g||g.id!==e.pointerId)return;
    this.gesture=null;this.release(g);cancelAnimationFrame(this.frame);this.frame=0;
    if(this.state!=='dragging'){this.state='idle';this.update();return;}
    const fresh=performance.now()-g.lastTime<100;
    const flick=fresh&&g.velocity>CURL.flickSpeed&&g.progress*g.width>CURL.flickDistance;
    const reversed=fresh&&g.velocity<-.3&&g.progress<.55;
    const complete=!cancelled&&!reversed&&(g.progress>CURL.completion||flick);
    this.settle(g,complete);
  }
  settle(g,complete){
    if(this.reduced.matches){if(complete)this.index+=g.direction;this.clean();return;}
    this.state=complete?'settling-complete':'settling-cancel';this.reader.dataset.state=this.state;
    const from=g.pointer||{...g.anchor};
    const to=complete?{x:g.direction>0?-g.width*1.4:g.width*2.4,y:g.anchor.y}:{...g.anchor};
    const start=performance.now(),duration=complete?CURL.duration:300;
    const tick=now=>{const t=Math.min(1,(now-start)/duration),ease=1-Math.pow(1-t,3);
      this.renderer.render(g.anchor,{x:from.x+(to.x-from.x)*ease,y:from.y+(to.y-from.y)*ease});
      if(t<1)this.frame=requestAnimationFrame(tick);else{if(complete)this.index+=g.direction;this.clean();}};
    this.frame=requestAnimationFrame(tick);
  }
  go(direction){
    if(this.state!=='idle'||!this.valid(direction))return;
    this.reader.focus({preventScroll:true});
    const bounds=this.reader.getBoundingClientRect(),g={direction,width:bounds.width,height:bounds.height};
    g.anchor={x:direction>0?g.width:0,y:g.height*.9};g.pointer={x:g.anchor.x-direction*2,y:g.anchor.y};
    this.prepare(g);this.settle(g,true);
  }
  cancel(){if(this.gesture)this.finish({pointerId:this.gesture.id},true);else if(this.state!=='idle')this.reset();}
  clean(){cancelAnimationFrame(this.frame);this.frame=0;this.renderer.clear();this.reader.classList.remove('turning');this.state='idle';this.update();}
  reset(){const g=this.gesture;this.gesture=null;if(g)this.release(g);this.clean();}
  destroy(){this.reset();this.events.abort();this.renderer.destroy();}
}
