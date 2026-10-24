// Cloudflare Worker. Bind KV as SUBSCRIPTIONS; secret ADMIN_TOKEN; VAPID_PUBLIC_KEY as variable.
// Never publish subscription endpoints or administrator secrets in GitHub Pages.
const ALLOWED_ORIGIN="https://johwin25.github.io";
const cors={"Access-Control-Allow-Origin":ALLOWED_ORIGIN,"Access-Control-Allow-Methods":"GET,POST,DELETE,OPTIONS","Access-Control-Allow-Headers":"Content-Type,Authorization","Vary":"Origin"};
const reply=(obj,status=200)=>new Response(JSON.stringify(obj),{status,headers:{...cors,"Content-Type":"application/json","Cache-Control":"no-store"}});
async function keyFor(endpoint){const d=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(endpoint));return "sub:"+Array.from(new Uint8Array(d),b=>b.toString(16).padStart(2,"0")).join("");}
function valid(s){
 if(!s||typeof s.endpoint!=="string"||s.endpoint.length>2048||!s.keys||typeof s.keys.p256dh!=="string"||typeof s.keys.auth!=="string")return false;
 let u;try{u=new URL(s.endpoint);}catch{return false;}
 // Restrict to known push provider domains; no arbitrary server fetches.
 return u.protocol==="https:" && /^(?:[a-z0-9-]+\.)*(?:push\.apple\.com|push\.services\.mozilla\.com|fcm\.googleapis\.com|notify\.windows\.com)$/.test(u.hostname)
 && s.keys.p256dh.length>=40&&s.keys.p256dh.length<=150&&s.keys.auth.length>=10&&s.keys.auth.length<=80;
}
export default {async fetch(req,env){
 const url=new URL(req.url),origin=req.headers.get("Origin");
 if(req.method==="OPTIONS")return origin===ALLOWED_ORIGIN?new Response(null,{headers:cors}):reply({error:"forbidden"},403);
 if(url.pathname==="/config"&&req.method==="GET")return reply({publicKey:env.VAPID_PUBLIC_KEY||""});
 if(url.pathname==="/subscribe"&&req.method==="POST"){
   if(origin!==ALLOWED_ORIGIN)return reply({error:"forbidden"},403);
   if(!req.headers.get("Content-Type")?.startsWith("application/json"))return reply({error:"content_type"},415);
   let s;try{if(Number(req.headers.get("Content-Length")||0)>4096)return reply({error:"too_large"},413);s=await req.json();}catch{return reply({error:"invalid_json"},400);}
   if(!valid(s))return reply({error:"invalid_subscription"},400);
   await env.SUBSCRIPTIONS.put(await keyFor(s.endpoint),JSON.stringify({endpoint:s.endpoint,keys:{p256dh:s.keys.p256dh,auth:s.keys.auth}}),{expirationTtl:7776000});
   return reply({ok:true});
 }
 if(url.pathname==="/unsubscribe"&&req.method==="POST"){
   if(origin!==ALLOWED_ORIGIN)return reply({error:"forbidden"},403);
   const b=await req.json().catch(()=>({}));
   if(typeof b.endpoint!=="string"||b.endpoint.length>2048)return reply({error:"invalid_endpoint"},400);
   // Client can remove its own record; requires exact unguessable subscription endpoint.
   await env.SUBSCRIPTIONS.delete(await keyFor(b.endpoint));return reply({ok:true});
 }
 if(url.pathname.startsWith("/admin/")){
   if(!env.ADMIN_TOKEN||req.headers.get("Authorization")!=="Bearer "+env.ADMIN_TOKEN)return reply({error:"unauthorized"},401);
   if(url.pathname==="/admin/subscriptions"&&req.method==="GET"){
     const listed=await env.SUBSCRIPTIONS.list({prefix:"sub:",limit:1000});
     const rows=await Promise.all(listed.keys.map(k=>env.SUBSCRIPTIONS.get(k.name)));
     return reply({subscriptions:rows.filter(Boolean).map(x=>JSON.parse(x)),complete:listed.list_complete});
   }
   if(url.pathname==="/admin/remove"&&req.method==="POST"){
     const b=await req.json().catch(()=>({}));
     if(typeof b.endpoint!=="string"||b.endpoint.length>2048)return reply({error:"invalid"},400);
     await env.SUBSCRIPTIONS.delete(await keyFor(b.endpoint));return reply({ok:true});
   }
 }
 return reply({error:"not_found"},404);
}};
