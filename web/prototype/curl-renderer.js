import {CURL,screenFold,bend,clipStrip,outline} from './curl-geometry.js';
import {DOMCurlRenderer} from './curl-dom-renderer.js';

const vertex=`
attribute vec3 position;
attribute vec2 uv;
attribute float angle;
uniform vec2 size;
varying vec2 vUV;
varying float vAngle;
void main(){
 vec2 projected=(position.xy-size*.5)*(1400.0/(1400.0-position.z))+size*.5;
 gl_Position=vec4(projected.x/size.x*2.0-1.0,1.0-projected.y/size.y*2.0,-position.z/300.0,1.0);
 vUV=uv;vAngle=angle;
}`;
const fragment=`
precision mediump float;
uniform sampler2D face;
varying vec2 vUV;
varying float vAngle;
void main(){
 float curve=sin(vAngle);
 if(gl_FrontFacing){
  vec4 color=texture2D(face,vUV);
  gl_FragColor=vec4(color.rgb*(1.0-.20*curve),color.a);
 }else{
  vec3 paper=vec3(.961,.922,.843)-vec3(.15,.16,.18)*curve;
  float grain=sin(gl_FragCoord.y*2.0+sin(gl_FragCoord.x))*.002;
  gl_FragColor=vec4(paper+grain,1.0);
 }
}`;

/** One WebGL draw call bends a cached article texture; native DOM mesh is fallback. */
export class CurlRenderer {
  constructor(host) {
    this.host=host;this.dom=new DOMCurlRenderer(host);this.cache=new WeakMap();
    this.canvas=document.createElement('canvas');this.canvas.className='curl-canvas';
    this.canvas.setAttribute('aria-hidden','true');
    try {
      const gl=this.canvas.getContext('webgl',{alpha:true,antialias:true,preserveDrawingBuffer:true,premultipliedAlpha:false});
      if(!gl)throw new Error('WebGL unavailable');this.gl=gl;
      const compile=(kind,source)=>{const s=gl.createShader(kind);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error('Shader unavailable');return s;};
      this.program=gl.createProgram();this.shaders=[compile(gl.VERTEX_SHADER,vertex),compile(gl.FRAGMENT_SHADER,fragment)];
      this.shaders.forEach(s=>gl.attachShader(this.program,s));gl.linkProgram(this.program);
      if(!gl.getProgramParameter(this.program,gl.LINK_STATUS))throw new Error('Shader link unavailable');
      this.buffer=gl.createBuffer();this.texture=gl.createTexture();
      this.attributes=['position','uv','angle'].map(name=>gl.getAttribLocation(this.program,name));
      this.sizeUniform=gl.getUniformLocation(this.program,'size');
      this.faceUniform=gl.getUniformLocation(this.program,'face');
      gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.frontFace(gl.CW);
    } catch {this.gl=null;}
    this.canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();this.gl=null;
      if(this.mode==='webgl'&&this.source){this.mode='dom';this.dom.prepare(this.source,this.width,this.height);this.host.dataset.renderer='dom';}});
  }
  key(source,width,height){return `${width}:${height}:${source.classList.contains('expanded')}:${source.querySelector('.summary')?.scrollTop||0}`;}
  async warm(source,width,height) {
    if(!this.gl||!window.htmlToImage)return;
    const key=this.key(source,width,height),old=this.cache.get(source);
    if(old?.key===key)return old.promise;
    const entry={key,canvas:null,promise:null};this.cache.set(source,entry);this.host.dataset.snapshot='pending';
    entry.promise=(async()=>{
      let stage;
      try {
        await Promise.all([...source.querySelectorAll('img')].map(img=>img.decode().catch(()=>{})));
        stage=document.createElement('div');stage.className='snapshot-stage';stage.inert=true;
        Object.assign(stage.style,{position:'fixed',left:'-20000px',top:'0',width:`${width}px`,height:`${height}px`,pointerEvents:'none'});
        const clone=source.cloneNode(true);clone.hidden=false;clone.inert=true;
        clone.removeAttribute('id');clone.querySelectorAll('[id]').forEach(el=>el.removeAttribute('id'));
        Object.assign(clone.style,{width:`${width}px`,height:`${height}px`,left:'0',top:'0',inset:'auto'});
        stage.append(clone);document.body.append(stage);
        const original=source.querySelector('.summary'),summary=clone.querySelector('.summary');if(original&&summary)summary.scrollTop=original.scrollTop;
        const canvas=await window.htmlToImage.toCanvas(clone,{width,height,pixelRatio:Math.min(1.5,devicePixelRatio||1),skipFonts:true,
          filter:node=>!(node instanceof HTMLImageElement&&node.hidden)});
        if(this.cache.get(source)===entry){entry.canvas=canvas;this.host.dataset.snapshot='ready';}
      } catch {if(this.cache.get(source)===entry)this.host.dataset.snapshot='fallback';}
      finally {stage?.remove();}
    })();
    return entry.promise;
  }
  prepare(source,width,height) {
    this.clear();this.source=source;this.width=width;this.height=height;
    const entry=this.cache.get(source);
    if(!this.gl||!entry?.canvas||entry.key!==this.key(source,width,height)) {
      this.mode='dom';this.host.dataset.renderer='dom';this.dom.prepare(source,width,height);return;
    }
    try {
      const gl=this.gl,ratio=Math.min(1.5,devicePixelRatio||1);
      this.canvas.width=Math.round(width*ratio);this.canvas.height=Math.round(height*ratio);
      gl.viewport(0,0,this.canvas.width,this.canvas.height);gl.useProgram(this.program);
      gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,this.texture);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
      gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,entry.canvas);
      gl.uniform2f(this.sizeUniform,width,height);gl.uniform1i(this.faceUniform,0);
      this.host.append(this.canvas);this.host.classList.add('active');
      this.dom.shadow.setAttribute('viewBox',`0 0 ${width} ${height}`);this.dom.shadow.classList.add('active');
      this.mode='webgl';this.host.dataset.renderer='webgl';
    } catch {this.mode='dom';this.host.dataset.renderer='dom';this.dom.prepare(source,width,height);}
  }
  render(anchor,pointer) {
    if(this.mode!=='webgl'){this.dom.render(anchor,pointer);return;}
    const f=screenFold(this.width,this.height,anchor,pointer),vertices=[];
    const arc=Math.PI*f.radius,segments=64,step=arc/segments;
    const push=point=>{const p=bend(point,f),s=(point.x-f.axis.x)*f.n.x+(point.y-f.axis.y)*f.n.y;
      vertices.push(p.x,p.y,p.z,point.x/f.width,point.y/f.height,Math.max(0,Math.min(Math.PI,s/f.radius)));};
    for(let i=0;i<segments+2;i++){
      const polygon=clipStrip(f,i===0?-Infinity:(i-1)*step,i===segments+1?Infinity:i*step);
      for(let j=1;j<polygon.length-1;j++){push(polygon[0]);push(polygon[j]);push(polygon[j+1]);}
    }
    const gl=this.gl;gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
    gl.bindBuffer(gl.ARRAY_BUFFER,this.buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(vertices),gl.DYNAMIC_DRAW);
    for(let i=0;i<3;i++){gl.enableVertexAttribArray(this.attributes[i]);gl.vertexAttribPointer(this.attributes[i],i===0?3:i===1?2:1,gl.FLOAT,false,24,i===0?0:i===1?12:20);}
    gl.drawArrays(gl.TRIANGLES,0,vertices.length/6);
    this.host.dataset.normal=`${f.n.x.toFixed(4)},${f.n.y.toFixed(4)}`;this.host.dataset.radius=f.radius.toFixed(3);
    this.host.dataset.vertices=String(vertices.length/6);
    const d=1400,cx=f.width/2,cy=f.height/2;
    const points=outline(f).map(p=>{const k=d/(d-p.z);return `${cx+(p.x-cx)*k+f.radius*.1},${cy+(p.y-cy)*k+f.radius*.18}`;});
    this.dom.path.setAttribute('d',`M${points.join(' L')}Z`);this.dom.path.setAttribute('opacity',String(Math.min(.26,f.distance/300)));
  }
  clear(){this.dom.clear();this.mode=null;this.source=null;}
  destroy(){this.clear();this.cache=new WeakMap();if(this.gl){this.gl.deleteTexture(this.texture);this.gl.deleteBuffer(this.buffer);this.gl.deleteProgram(this.program);this.shaders.forEach(s=>this.gl.deleteShader(s));}this.dom.destroy();}
}
