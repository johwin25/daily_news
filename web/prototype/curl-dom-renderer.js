import {CURL,screenFold,clipStrip,stripTransform,outline} from './curl-geometry.js';
const SVG='http://www.w3.org/2000/svg';
const svgElement=(tag,attrs={})=>{const el=document.createElementNS(SVG,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);return el;};

/** A DOM-backed cylindrical paper mesh. No rasterization or external textures. */
export class DOMCurlRenderer {
  constructor(host) {
    this.host=host;
    this.shadow=svgElement('svg',{'class':'curl-shadow','aria-hidden':'true'});
    const defs=svgElement('defs'),filter=svgElement('filter',{id:'paper-shadow',x:'-100%',y:'-100%',width:'300%',height:'300%'});
    filter.append(svgElement('feGaussianBlur',{stdDeviation:7}));defs.append(filter);
    this.path=svgElement('path',{fill:'#24190e',opacity:'.22',filter:'url(#paper-shadow)'});
    this.shadow.append(defs,this.path);host.before(this.shadow);
    this.strips=[];
  }
  prepare(source,width,height) {
    this.clear();this.width=width;this.height=height;
    const scrollTop=source.querySelector('.summary')?.scrollTop||0;
    this.shadow.setAttribute('viewBox',`0 0 ${width} ${height}`);
    for(let i=0;i<CURL.segments+2;i++) {
      const strip=document.createElement('div');strip.className='curl-strip';
      const front=document.createElement('div');front.className='curl-front';
      // Only the static part and first half-cylinder can face the reader.
      if(i<=CURL.segments/2) {
        const clone=source.cloneNode(true);clone.hidden=false;clone.inert=true;
        clone.removeAttribute('id');clone.querySelectorAll('[id]').forEach(el=>el.removeAttribute('id'));
        clone.querySelectorAll('button,a,[tabindex]').forEach(el=>el.tabIndex=-1);
        clone.style.width=`${width}px`;clone.style.height=`${height}px`;
        front.append(clone);
      }
      const shade=document.createElement('div');shade.className='curl-shading';front.append(shade);
      const back=document.createElement('div');back.className='curl-back';
      strip.append(front,back);this.host.append(strip);this.strips.push({strip,front,shade,back});
    }
    if(scrollTop)this.host.querySelectorAll('.summary').forEach(summary=>{summary.scrollTop=scrollTop;});
    this.host.classList.add('active');this.shadow.classList.add('active');
  }
  render(anchor,pointer) {
    const f=screenFold(this.width,this.height,anchor,pointer);
    const arc=Math.PI*f.radius, step=arc/CURL.segments;
    this.host.dataset.normal=`${f.n.x.toFixed(4)},${f.n.y.toFixed(4)}`;
    this.host.dataset.radius=f.radius.toFixed(3);
    for(let i=0;i<this.strips.length;i++) {
      const low=i===0?-Infinity:(i-1)*step;
      const high=i===this.strips.length-1?Infinity:i*step;
      // A fraction of a pixel overlap hides anti-aliased seams between facets.
      const points=clipStrip(f,low-1.2,high+1.2);
      const {strip,front,shade,back}=this.strips[i];
      if(points.length<3){strip.hidden=true;continue;}strip.hidden=false;
      const x=Math.min(...points.map(p=>p.x)),y=Math.min(...points.map(p=>p.y));
      const w=Math.max(...points.map(p=>p.x))-x,h=Math.max(...points.map(p=>p.y))-y;
      const middle=i===0?Math.min(0,high):i===this.strips.length-1?Math.max(arc,low):(low+high)/2;
      const {theta,matrix}=stripTransform(f,middle,{x,y});
      strip.style.width=`${w}px`;strip.style.height=`${h}px`;
      strip.style.transform=`matrix3d(${matrix.join(',')})`;
      const polygon=`polygon(${points.map(p=>`${p.x-x}px ${p.y-y}px`).join(',')})`;
      front.style.clipPath=polygon;back.style.clipPath=polygon;
      const clone=front.querySelector('.page');if(clone){clone.style.left=`${-x}px`;clone.style.top=`${-y}px`;}
      // Back face is blank warm paper; no mirrored or illegible article text.
      const color=angle=>{const light=Math.sin(Math.max(0,Math.min(Math.PI,angle)));return `rgb(${245-40*light} ${235-43*light} ${215-48*light})`;};
      const gradientAngle=Math.atan2(f.n.x,-f.n.y)*180/Math.PI;
      // Continuous per-strip lighting avoids a stack of visibly flat shaded cards.
      back.style.backgroundImage=`linear-gradient(${gradientAngle}deg,${color(theta-Math.PI/CURL.segments/2)},${color(theta+Math.PI/CURL.segments/2)})`;
      shade.style.background=`rgba(34,22,10,${.20*Math.sin(theta)})`;
      strip.style.zIndex=String(Math.round(100+Math.sin(theta/2)*100));
    }
    // Project the curled perimeter into the same perspective as the DOM mesh.
    const d=1400,cx=this.width/2,cy=this.height/2;
    const perimeter=outline(f).map(p=>{const k=d/(d-p.z);return `${cx+(p.x-cx)*k+f.radius*.10},${cy+(p.y-cy)*k+f.radius*.18}`;});
    this.path.setAttribute('d',`M${perimeter.join(' L')}Z`);
    this.path.setAttribute('opacity',String(Math.min(.26,f.distance/300)));
  }
  clear(){this.host.replaceChildren();this.host.classList.remove('active');this.shadow.classList.remove('active');this.strips=[];delete this.host.dataset.normal;delete this.host.dataset.radius;}
  destroy(){this.clear();this.shadow.remove();}
}
