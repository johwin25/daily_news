/*
MIT License

Copyright (c) 2019 Simon Lightfoot

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

*/
// Curl deformation adapted from fluttercommunity/page_turn by Simon Lightfoot.
// MIT license: see ../THIRD_PARTY_NOTICES.md. DOM strips replace Canvas image capture.
export class PageTurn {
  constructor(root, pages) {
    if (!pages.length) throw new Error('At least one page is required');
    this.root = root; this.pages = pages; this.index = 0;
    this.motion = matchMedia('(prefers-reduced-motion: reduce)');
    this.abort = new AbortController(); const options = {signal: this.abort.signal};
    root.classList.add('page-turn'); root.tabIndex = 0;
    root.setAttribute('aria-label', 'Articles; use left and right arrow keys to turn pages');
    root.replaceChildren(...pages); this.show();
    root.addEventListener('pointerdown', e => this.down(e), options);
    root.addEventListener('pointermove', e => this.move(e), options);
    root.addEventListener('pointerup', e => this.end(e), options);
    root.addEventListener('pointercancel', e => this.end(e, true), options);
    root.addEventListener('lostpointercapture', e => this.end(e, true), options);
    root.addEventListener('keydown', e => {
      if (e.target.closest('button,a,input,textarea,[contenteditable]')) return;
      if (['ArrowLeft','ArrowRight'].includes(e.key)) {e.preventDefault(); this.turn(e.key === 'ArrowRight' ? 1 : -1);}
    }, options);
    this.resize = new ResizeObserver(() => {if(this.drag || this.busy) this.reset();});
    this.resize.observe(root);
  }
  show() {
    this.pages.forEach((p,i) => {p.hidden = i !== this.index; p.inert = i !== this.index;});
    this.root.dataset.index = this.index;
  }
  down(e) {
    if (this.busy || this.drag || !e.isPrimary || e.button !== 0 || e.target.closest('button,a,.summary')) return;
    this.drag = {id:e.pointerId, x:e.clientX, y:e.clientY, p:0, direction:0};
  }
  move(e) {
    const d = this.drag; if (!d || d.id !== e.pointerId) return;
    const dx = e.clientX-d.x, dy=e.clientY-d.y;
    if (!d.direction) {
      if (Math.max(Math.abs(dx),Math.abs(dy)) < 10) return;
      if (Math.abs(dy) > Math.abs(dx)) {this.drag=null;return;}
      d.direction = dx < 0 ? 1 : -1;
      if (this.index+d.direction < 0 || this.index+d.direction >= this.pages.length) {this.drag=null;return;}
      this.root.setPointerCapture(e.pointerId); this.prepare(d.direction);
    }
    const rect=this.root.getBoundingClientRect();
    d.p=Math.max(0,Math.min(1,-dx*d.direction/rect.width));
    d.yRatio=Math.max(0,Math.min(1,(e.clientY-rect.top)/rect.height));
    this.paint(d.p,d.yRatio); e.preventDefault();
  }
  prepare(direction) {
    this.direction=direction; this.pages[this.index+direction].hidden=false;
    this.pages[this.index].style.visibility='hidden';
    this.layer=document.createElement('div'); this.layer.className='curl-layer'; this.layer.inert=true; this.layer.setAttribute('aria-hidden','true');
    this.strips=[];
    if (!this.motion.matches) for(let i=0;i<40;i++) {
      const strip=document.createElement('div'); strip.className='curl-strip';
      const clone=this.pages[this.index].cloneNode(true); clone.hidden=false;clone.style.visibility='';
      clone.removeAttribute('id'); clone.querySelectorAll('[id]').forEach(n=>n.removeAttribute('id'));
      clone.style.width=this.root.clientWidth+'px'; clone.style.height=this.root.clientHeight+'px';
      clone.style.left= -i*this.root.clientWidth/40+'px';
      strip.append(clone); this.layer.append(strip); this.strips.push(strip);
    }
    this.root.append(this.layer);
  }
  paint(p,y=.5) {
    this.root.dataset.progress=p.toFixed(3);
    if(this.motion.matches) return;
    const w=this.root.clientWidth, h=this.root.clientHeight;
    // Upstream's sinusoidal strip deformation; added pointer-height bias and mirrored reverse turn.
    const radius=.18*Math.sin(Math.PI*p), movement=p*1.2;
    this.strips.forEach((strip,i)=> {
      const xf=i/40, v=radius*(Math.sin(2*Math.PI*(xf-p))+1.1);
      const bend=h*radius*p*v;
      const x=this.direction===1 ? (xf*(1-radius)-movement)*w : (xf*(1-radius)+movement+radius)*w;
      strip.style.width=w/40+1+'px';strip.style.height=h+'px';
      strip.style.transform=`translate(${x}px,${-bend*2*y}px) scale(${1-radius},${1+bend*2/h})`;
      strip.style.filter=`brightness(${1-.32*Math.abs(Math.sin(Math.PI*(xf-p)))*Math.sin(Math.PI*p)})`;
    });
    this.layer.style.filter=`drop-shadow(${this.direction*12}px 4px ${8+24*Math.sin(Math.PI*p)}px #0006)`;
  }
  end(e,cancel=false) {
    const d=this.drag;if(!d || d.id!==e.pointerId)return; this.drag=null;
    if(d.direction)this.settle(cancel?0:(d.p>=.28?1:0),d.p,d.yRatio);
  }
  settle(target,from=0,y=.5) {
    this.busy=true;const start=performance.now(); const duration=this.motion.matches?0:280;
    const tick=now=>{
      const t=duration?Math.min(1,(now-start)/duration):1;
      this.paint(from+(target-from)*(1-(1-t)**3),y);
      if(t<1)this.frame=requestAnimationFrame(tick);
      else {if(target)this.index+=this.direction;this.reset();this.root.dispatchEvent(new CustomEvent('pagechange',{detail:{index:this.index}}));}
    };this.frame=requestAnimationFrame(tick);
  }
  turn(direction) {
    if(this.busy||this.drag||this.index+direction<0||this.index+direction>=this.pages.length)return;
    this.prepare(direction);this.settle(1);
  }
  reset() {
    cancelAnimationFrame(this.frame);this.layer?.remove();this.layer=null;this.drag=null;this.busy=false;
    this.pages.forEach(p=>p.style.visibility='');this.root.dataset.progress='0';this.show();
  }
  destroy() {this.reset();this.abort.abort();this.resize.disconnect();}
}
