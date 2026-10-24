(() => {
const button=document.getElementById("notification-toggle");
const status=document.getElementById("push-status");
const base=(window.DAILY_NEWS_PUSH_ENDPOINT||"").replace(/\/$/,"");
function show(message){status.textContent=message;}
function decodeKey(str){const base64=str.replace(/-/g,"+").replace(/_/g,"/");const binary=atob(base64.padEnd(Math.ceil(base64.length/4)*4,"="));return Uint8Array.from(binary,c=>c.charCodeAt(0));}
async function ready(){
 if(!base){show("Notifications are not configured yet.");button.disabled=true;return;}
 if(!("serviceWorker" in navigator)||!("PushManager" in window)||!("Notification" in window)){show("This device does not support Web Push.");button.disabled=true;return;}
 const reg=await navigator.serviceWorker.ready;
 const existing=await reg.pushManager.getSubscription();
 button.textContent=existing?"Disable notifications":"Enable notifications";
 show(existing?"Notifications enabled on this device.":"You can opt in to daily alerts.");
}
button.addEventListener("click",async()=>{
 button.disabled=true;
 try{
  const reg=await navigator.serviceWorker.ready;
  const existing=await reg.pushManager.getSubscription();
  if(existing){
    const response=await fetch(base+"/unsubscribe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({endpoint:existing.endpoint})});
    if(!response.ok)throw Error("Unsubscribe service unavailable");
    await existing.unsubscribe();show("Notifications disabled.");button.textContent="Enable notifications";return;
  }
  if(Notification.permission==="denied")throw Error("Notifications blocked in device settings");
  const permission=await Notification.requestPermission();
  if(permission!=="granted")throw Error("Notification permission not granted");
  const res=await fetch(base+"/config",{cache:"no-store"});
  if(!res.ok)throw Error("Push configuration unavailable");
  const {publicKey}=await res.json();
  if(!publicKey)throw Error("Push public key not configured");
  const subscription=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:decodeKey(publicKey)});
  const stored=await fetch(base+"/subscribe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(subscription)});
  if(!stored.ok){await subscription.unsubscribe();throw Error("Push registration failed");}
  button.textContent="Disable notifications";show("Notifications enabled. A test push can now be sent from the backend.");
 }catch(err){show(err.message||"Could not enable notifications.");}
 finally{button.disabled=false;}
});
ready().catch(()=>show("Push status unavailable."));
})();
