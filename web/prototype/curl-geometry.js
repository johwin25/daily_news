// Geometry is independent of the DOM, input events and article data.
export const CURL = Object.freeze({segments:32, maxRadius:54, radiusRatio:.18, threshold:12,
  directionRatio:.65, completion:.28, flickSpeed:.65, flickDistance:56, duration:440});
const dot=(a,b)=>a.x*b.x+a.y*b.y;

export function createFold(width,height,anchor,pointer) {
  const dx=anchor.x-pointer.x, dy=anchor.y-pointer.y;
  const distance=Math.hypot(dx,dy);
  const n=distance>0.01?{x:dx/distance,y:dy/distance}:{x:1,y:0};
  const t={x:-n.y,y:n.x};
  const radius=Math.min(CURL.maxRadius,Math.max(.01,distance*CURL.radiusRatio));
  const axis={x:(anchor.x+pointer.x)/2-n.x*Math.PI*radius/2,
    y:(anchor.y+pointer.y)/2-n.y*Math.PI*radius/2};
  const crease=dot(axis,n);
  const rect=[{x:0,y:0},{x:width,y:0},{x:width,y:height},{x:0,y:height}];
  return {width,height,anchor,pointer,n,t,radius,axis,crease,rect,distance};
}

export function bend(point,fold) {
  const {n,t,axis,radius}=fold;
  const offset={x:point.x-axis.x,y:point.y-axis.y};
  const s=dot(offset,n), v=dot(offset,t);
  if(s<=0) return {...point,z:0};
  const angle=Math.min(Math.PI,s/radius);
  const u=s<Math.PI*radius?radius*Math.sin(angle):-(s-Math.PI*radius);
  return {x:axis.x+t.x*v+n.x*u,y:axis.y+t.y*v+n.y*u,z:radius*(1-Math.cos(angle))};
}

// Sutherland–Hodgman clipping against the two boundaries of a material strip.
export function clipStrip(fold,low,high) {
  let points=fold.rect;
  for(const [limit,sign] of [[low,1],[high,-1]]) {
    if(!Number.isFinite(limit))continue;
    const result=[];
    for(let i=0;i<points.length;i++) {
      const a=points[i],b=points[(i+1)%points.length];
      const sa=(dot(a,fold.n)-fold.crease-limit)*sign;
      const sb=(dot(b,fold.n)-fold.crease-limit)*sign;
      if(sa>=0)result.push(a);
      if((sa>=0)!==(sb>=0)) {
        const k=sa/(sa-sb);result.push({x:a.x+(b.x-a.x)*k,y:a.y+(b.y-a.y)*k});
      }
    }
    points=result;
  }
  return points;
}

export function stripTransform(fold,s,bounds) {
  const {n,t,radius,axis}=fold;
  const theta=Math.max(0,Math.min(Math.PI,s/radius));
  const c=Math.cos(theta), sn=Math.sin(theta);
  const center={x:axis.x+n.x*s,y:axis.y+n.y*s};
  const p=bend(center,fold);
  const xx=t.x*t.x+n.x*n.x*c, xy=t.x*t.y+n.x*n.y*c;
  const yy=t.y*t.y+n.y*n.y*c, zx=n.x*sn,zy=n.y*sn;
  const bx=bounds.x-center.x,by=bounds.y-center.y;
  return {theta,matrix:[xx,xy,zx,0,xy,yy,zy,0,-n.x*sn,-n.y*sn,c,0,
    p.x+xx*bx+xy*by,p.y+xy*bx+yy*by,p.z+zx*bx+zy*by,1]};
}

export function outline(fold) {
  const points=[];
  for(let i=0;i<4;i++)for(let step=0;step<28;step++) {
    const a=fold.rect[i],b=fold.rect[(i+1)%4],k=step/28;
    points.push(bend({x:a.x+(b.x-a.x)*k,y:a.y+(b.y-a.y)*k},fold));
  }
  return points;
}

// Compensate for elevation so the projected gripped point stays under the pointer.
export function screenFold(width,height,anchor,pointer,perspective=1400) {
  let fold=createFold(width,height,anchor,pointer);
  for(let i=0;i<4;i++) {
    const scale=1-2*fold.radius/perspective;
    fold=createFold(width,height,anchor,{
      x:width/2+(pointer.x-width/2)*scale,
      y:height/2+(pointer.y-height/2)*scale});
  }
  return fold;
}
