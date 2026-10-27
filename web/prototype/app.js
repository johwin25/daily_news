'use strict';
// Entirely local, fictional editorial fixtures. No production data, permissions or SW.
const stories = [
 {section:'01 / SCIENCE',topic:'A wider perspective',headline:'A universe still waiting to be read.',caption:'The next great discovery might be hiding in the spaces between what we already know.',image:'space.jpg',alt:'Thousands of distant galaxies in the Hubble eXtreme Deep Field',credit:'NASA / ESA / XDF team · Public domain',source:'https://hubblesite.org/contents/news-releases/2012/news-2012-37',paragraphs:[
 'This fictional sample imagines a new generation of open observatories: places where researchers and curious readers explore the same view of the night sky. It is a design demonstration, not a report of a new discovery.',
 'A deep-field photograph is a remarkable kind of time capsule. Light from distant galaxies travels for billions of years before reaching a telescope. A small patch of darkness can contain more structure than our eyes could ever reveal on their own.',
 'In this imagined programme, small teams would be able to compare observations, revisit older data and publish their questions alongside their results. The useful story would be the process: how an unexpected signal becomes a hypothesis, and how a hypothesis survives careful testing.',
 'There is no single image that tells the whole story. Different instruments reveal different wavelengths, and researchers must distinguish an interesting pattern from an error in the measurement. Independent checks are part of discovery, rather than an obstacle to it.',
 'For readers, the invitation is simple: look slowly. The photograph here is an archival illustration, not evidence for the fictional programme described above. All four stories in this edition are sample copy written to explore the reading experience.']},
 {section:'02 / EXPLORATION',topic:'The long view',headline:'What we take with us, beyond Earth.',caption:'Behind every launch is a quieter story of people, preparation and patience.',image:'rocket.jpg',alt:'Falcon 9 launching DSCOVR at dusk, with a bright plume',credit:'SpaceX · Public domain',source:'https://www.flickr.com/photos/spacexphotos/16511594820/',paragraphs:[
 'This fictional briefing imagines a public exhibition about the work behind a space mission. It is sample editorial copy, not an announcement of a launch or a new mission.',
 'A rocket leaves the ground in seconds, but its journey begins much earlier. Engineers check instruments, rehearse decisions and document small changes. The most important work is often invisible in the final photograph.',
 'The imagined exhibition would follow a mission through its many disciplines, from materials and navigation to the people listening for its first signal. Visitors could explore the trade-offs that make complex systems possible.',
 'Repetition matters. Teams test individual parts before testing them together, and a delay can be evidence that a careful process is working. An impressive picture should never stand in for an explanation of that process.',
 'The archival photograph shows the 2015 DSCOVR launch. It illustrates the theme only. This prototype does not report live launch information or offer operational guidance.']},
 {section:'03 / PEOPLE',topic:'An extraordinary ordinary day',headline:'The human side of a distant horizon.',caption:'An imagined portrait series puts the people behind exploration back in the frame.',image:'astronaut.png',alt:'Archival NASA portrait of astronaut Eileen Collins in an orange flight suit',position:'center 25%',credit:'NASA · Eileen Collins portrait · Public domain',source:'https://flic.kr/p/r9qvLn',paragraphs:[
 'This fictional sample describes an imagined oral-history collection about life in scientific teams. The archival portrait of Eileen Collins is illustrative; she has not participated in or endorsed this fictional project.',
 'We often remember the milestone and forget the routine. An oral history can make room for both: the moment everyone watched and the many days when the work was simply practice, learning and collaboration.',
 'The imagined collection would ask people about the first question that drew them to their field, the mentors who helped them stay, and the habits that make difficult decisions manageable.',
 'No single biography represents a whole profession. The point of a collection would be to hear different experiences, including the roles that are rarely visible in public photographs.',
 'This is a sample reading experience. Its text is invented, its photograph is archival, and it makes no claim about a current interview or event.']},
 {section:'04 / EVERYDAY LIFE',topic:'A slower morning',headline:'A little room for the everyday.',caption:'An imagined neighbourhood project asks what happens when we make time to sit together.',image:'coffee.png',alt:'Overhead photograph of a cup of coffee on a wooden table',credit:'Rachel Michetti / Pikolo Espresso Bar · CC0',source:'https://github.com/scikit-image/scikit-image/blob/v0.19.3/skimage/data/_fetchers.py#L935-L951',paragraphs:[
 'This fictional sample imagines a neighbourhood reading table: a place to share a newspaper, linger over a cup and start a conversation. No real project or business opening is being reported.',
 'The proposed table would have no programme beyond a few spare chairs and a selection of reading material. People could bring a question, exchange a recommendation or simply spend a quiet morning in company.',
 'Public places can be measured in many ways. A seat, a little shade and enough time to feel welcome may matter just as much as the shape of a building. The imagined project begins with these modest details.',
 'A good shared space also needs care. Accessibility, noise, cost and the needs of neighbours would all shape how the table worked. A warm idea is only a starting point for those practical conversations.',
 'The photograph is an illustration by Rachel Michetti, released under CC0. Like the other stories here, this is invented sample copy for the prototype, not live news.']}
];
const reader=document.querySelector('#reader'), pages=document.querySelector('#pages'), turn=document.querySelector('#turn');
const counter=document.querySelector('#counter'), previous=document.querySelector('#previous'), next=document.querySelector('#next');
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
let index=0, busy=false, gesture=null, frame=0, animation=null;
function element(tag,cls,text){const el=document.createElement(tag);if(cls)el.className=cls;if(text)el.textContent=text;return el;}
const cards=stories.map((s,i)=>{
 const card=element('article','page');card.setAttribute('aria-roledescription','slide');card.setAttribute('aria-label',`${i+1} of ${stories.length}: ${s.headline}`);card.style.setProperty('--position',s.position||'center');
 const fallback=element('div','fallback','The picture can wait.');fallback.hidden=true;fallback.append(element('small','','Illustration unavailable · the story is still here'));
 const img=element('img','photograph');img.alt=s.alt;img.src=`./assets/${s.image}`;img.decoding='async';img.addEventListener('error',()=>{img.hidden=true;fallback.hidden=false;});
 const top=element('div','topline');top.append(element('span','',s.section),element('span','','SAMPLE STORY'));
 const copy=element('section','copy');copy.append(element('p','kicker',s.topic.toUpperCase()),element('h1','',s.headline),element('p','caption',s.caption));
 const summary=element('div','summary');summary.id=`summary-${i}`;summary.hidden=true;summary.tabIndex=0;summary.setAttribute('role','region');summary.setAttribute('aria-label','Longer sample summary');s.paragraphs.forEach(p=>summary.append(element('p','',p)));
 const read=element('button','read','Read more +');read.type='button';read.setAttribute('aria-expanded','false');read.setAttribute('aria-controls',summary.id);
 read.addEventListener('click',()=>{const open=summary.hidden;summary.hidden=!open;card.classList.toggle('expanded',open);read.setAttribute('aria-expanded',String(open));read.textContent=open?'Read less −':'Read more +';});
 const credit=element('p','credit','Illustrative archive image · ');const link=element('a','',s.credit);link.href=s.source;link.target='_blank';link.rel='noopener noreferrer';credit.append(link);
 copy.append(summary,read,credit);card.append(fallback,img,top,copy);pages.append(card);return card;
});
function update(){cards.forEach((c,i)=>{c.hidden=i!==index;c.inert=i!==index;});counter.textContent=`${String(index+1).padStart(2,'0')} / 04 · Swipe to turn`;previous.disabled=index===0;next.disabled=index===stories.length-1;}
function clean(){cancelAnimationFrame(frame);turn.classList.remove('active');turn.querySelector('.page')?.remove();turn.style.transform='';reader.classList.remove('turning');reader.style.setProperty('--shade',0);update();busy=false;animation=null;}
function prepare(direction){
 const outgoing=direction>0?index:index-1;const clone=cards[outgoing].cloneNode(true);clone.hidden=false;clone.inert=true;clone.removeAttribute('aria-label');clone.querySelectorAll('[id]').forEach(el=>el.removeAttribute('id'));turn.prepend(clone);
 cards[index].hidden=direction>0;cards[index+direction].hidden=false;turn.classList.add('active');reader.classList.add('turning');
}
function paint(progress,direction){const amount=direction>0?progress:1-progress;turn.style.transform=`rotateY(${-112*amount}deg) rotateZ(${-1.4*Math.sin(amount*Math.PI)}deg)`;reader.style.setProperty('--shade',String(.22*Math.sin(progress*Math.PI)));}
function settle(direction,from,commit){
 busy=true;const to=commit?1:0,start=performance.now(),duration=Math.max(120,Math.abs(to-from)*460);
 animation={direction,commit};
 function tick(now){const t=Math.min(1,(now-start)/duration),ease=1-Math.pow(1-t,3);paint(from+(to-from)*ease,direction);if(t<1)frame=requestAnimationFrame(tick);else{if(commit)index+=direction;clean();}}
 frame=requestAnimationFrame(tick);
}
function go(direction){if(busy||gesture||index+direction<0||index+direction>=cards.length)return;reader.focus({preventScroll:true});if(reduced.matches){index+=direction;update();return;}prepare(direction);paint(0,direction);settle(direction,0,true);}
previous.addEventListener('click',()=>go(-1));next.addEventListener('click',()=>go(1));
reader.setAttribute('aria-describedby','instructions');
document.addEventListener('keydown',e=>{if(e.altKey||e.ctrlKey||e.metaKey)return;if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();go(e.key==='ArrowRight'?1:-1);}if(e.key==='Escape'&&gesture)cancel();});
reader.addEventListener('pointerdown',e=>{if(!e.isPrimary||e.button!==0||busy||gesture||e.target.closest('button,a'))return;gesture={id:e.pointerId,x:e.clientX,y:e.clientY,mode:null,direction:0,progress:0};reader.setPointerCapture(e.pointerId);});
reader.addEventListener('pointermove',e=>{
 const g=gesture;if(!g||g.id!==e.pointerId)return;const dx=e.clientX-g.x,dy=e.clientY-g.y;
 if(!g.mode){if(Math.max(Math.abs(dx),Math.abs(dy))<12)return;g.mode=Math.abs(dx)>Math.abs(dy)*1.3?'horizontal':'vertical';if(g.mode==='horizontal'){g.direction=dx<0?1:-1;if(index+g.direction<0||index+g.direction>=cards.length){g.mode='boundary';return;}if(!reduced.matches)prepare(g.direction);}}
 if(g.mode!=='horizontal')return;g.progress=Math.max(0,Math.min(.99,Math.abs(Math.min(0,dx*g.direction))/reader.clientWidth));if(!reduced.matches)paint(g.progress,g.direction);
});
function finish(e,cancelled=false){const g=gesture;if(!g||g.id!==e.pointerId)return;gesture=null;if(reader.hasPointerCapture(g.id))reader.releasePointerCapture(g.id);if(g.mode!=='horizontal')return;const commit=!cancelled&&g.progress>.18;if(reduced.matches){if(commit)index+=g.direction;update();}else settle(g.direction,g.progress,commit);}
function cancel(){if(gesture)finish({pointerId:gesture.id},true);}
reader.addEventListener('pointerup',e=>finish(e));reader.addEventListener('pointercancel',e=>finish(e,true));reader.addEventListener('lostpointercapture',e=>finish(e,true));
window.addEventListener('blur',cancel);window.addEventListener('resize',()=>{cancel();if(animation){if(animation.commit)index+=animation.direction;clean();}});
reduced.addEventListener('change',()=>{cancel();if(animation){if(animation.commit)index+=animation.direction;clean();}});
update();
