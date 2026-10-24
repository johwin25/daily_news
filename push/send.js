const webpush=require("web-push");
const keys=["PUSH_WORKER_URL","PUSH_ADMIN_TOKEN","VAPID_PUBLIC_KEY","VAPID_PRIVATE_KEY","VAPID_SUBJECT"];
if(keys.some(k=>!process.env[k])){console.log("Push not configured; skipping.");process.exit(0);}
const base=process.env.PUSH_WORKER_URL.replace(/\/$/,"");
if(!/^https:\/\//.test(base))throw Error("Push Worker URL must use HTTPS");
webpush.setVapidDetails(process.env.VAPID_SUBJECT,process.env.VAPID_PUBLIC_KEY,process.env.VAPID_PRIVATE_KEY);
(async()=>{
 const response=await fetch(base+"/admin/subscriptions",{headers:{Authorization:"Bearer "+process.env.PUSH_ADMIN_TOKEN}});
 if(!response.ok)throw Error("Subscription retrieval failed");
 const data=await response.json();
 if(!data.complete)throw Error("Subscriber pagination required");
 let delivered=0,expired=0,failed=0;
 for(const sub of data.subscriptions){
   try{
     await webpush.sendNotification(sub,JSON.stringify({title:"The Morning Edition",body:"Fresh off the press. Your daily briefing is here.",url:"https://johwin25.github.io/daily_news/"}),{TTL:3600});
     delivered++;
   }catch(e){
     if([404,410].includes(e.statusCode)){
       await fetch(base+"/admin/remove",{method:"POST",headers:{Authorization:"Bearer "+process.env.PUSH_ADMIN_TOKEN,"Content-Type":"application/json"},body:JSON.stringify({endpoint:sub.endpoint})});
       expired++;
     }else failed++;
   }
 }
 console.log("Push result: delivered",delivered,"expired",expired,"failed",failed);
 if(failed)process.exitCode=1;
})().catch(e=>{console.error(e.message);process.exitCode=1;});
