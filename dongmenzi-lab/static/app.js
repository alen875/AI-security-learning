let csrf = "";
let previewRole = "maint";
const el = id => document.getElementById(id);
function entryLink(loggedIn){const link=el("header-action");link.href=loggedIn?"#workspace":"#login-panel";link.firstChild.nodeValue=loggedIn?"我的工作空间 ":"进入平台 ";}
function notice(message){el("notice").textContent=message;}
async function api(path, options={}){
  const response=await fetch(path,{credentials:"same-origin",...options,headers:{"Content-Type":"application/json",...(csrf?{"X-CSRF-Token":csrf}:{}),...(options.headers||{})}});
  const payload=await response.json().catch(()=>({error:"invalid_response"}));
  if(!response.ok)throw new Error(payload.error||`HTTP ${response.status}`);
  return payload.data;
}
async function task(button, fn){button.disabled=true;notice("正在加载…");try{await fn();notice("完成");}catch(e){notice(`操作失败：${e.message}`);if(e.message==="login_required")showLogin();}finally{button.disabled=false;}}
function showLogin(){el("login-panel").hidden=false;el("workspace").hidden=true;csrf="";previewRole="maint";entryLink(false);}
async function refresh(){const rows=await api("/api/devices");const box=el("devices");box.replaceChildren();if(!rows.length){box.textContent="暂无可见设备";return;}for(const d of rows){const card=document.createElement("div");card.className="card";card.textContent=`${d.code} · ${d.name} · ${d.status}`;const btn=document.createElement("button");btn.textContent="查看记录";btn.onclick=()=>task(btn,async()=>{const records=await api(`/api/devices/${d.id}/records`);el("record").textContent=records.length?records.map(x=>`${x.id} ${x.code} ${x.title}`).join("\n"):"无维护记录";});card.append(btn);box.append(card);}}
async function enter(){const me=await api("/api/auth/me");csrf=me.csrf;previewRole=me.role==="maint"?"maint":"reviewer";el("identity").textContent=`当前账号：${me.username}（${me.role}）`;el("login-panel").hidden=true;el("workspace").hidden=false;el("bp-panel").hidden=false;el("bp-inspect").textContent=previewRole==="maint"?"预览普通维护报告":"预览复核报告";el("admin-panel").hidden=me.role!=="admin";el("audit-panel").hidden=!(me.role==="admin"||me.role==="reviewer");entryLink(true);await refresh();}
el("login-form").onsubmit=async e=>{e.preventDefault();const btn=e.submitter;await task(btn,async()=>{const form=new FormData(e.target);await api("/api/auth/login",{method:"POST",body:JSON.stringify(Object.fromEntries(form))});e.target.reset();await enter();});};
el("register-form").onsubmit=async e=>{e.preventDefault();const btn=e.submitter;btn.disabled=true;notice("正在注册…");try{const form=new FormData(e.target);const result=await api("/api/auth/register",{method:"POST",body:JSON.stringify(Object.fromEntries(form))});e.target.reset();notice(`账号 ${result.username} 已创建，请登录。`);}catch(error){notice(`注册失败：${error.message}`);}finally{btn.disabled=false;}};
el("logout").onclick=e=>task(e.target,async()=>{await api("/api/auth/logout",{method:"POST"});showLogin();});
el("refresh").onclick=e=>task(e.target,refresh);
el("load-record").onclick=e=>task(e.target,async()=>{const id=Number(el("record-id").value);const row=await api(`/api/records/${id}`);el("record").textContent=`${row.code} · ${row.title}\n${row.body}`;});
el("bp-inspect").onclick=e=>task(e.target,async()=>{const row=await api("/api/training/report-preview",{method:"POST",body:JSON.stringify({preview_role:previewRole})});el("bp-result").textContent=`${row.report_code} · ${row.title}\n${row.content}`;});
el("search").onclick=e=>task(e.target,async()=>{const rows=await api(`/api/training-search?q=${encodeURIComponent(el("query").value)}`);const box=el("results");box.replaceChildren();if(!rows.length){box.textContent="没有匹配的教学索引";return;}for(const r of rows){const card=document.createElement("div");card.className="card";card.textContent=`${r.code} · ${r.device_code} · ${r.title} · ${r.summary}`;box.append(card);}});
el("load-audit").onclick=e=>task(e.target,async()=>{el("audit").textContent=JSON.stringify(await api("/api/audit"),null,2);});
el("reset").onclick=e=>task(e.target,async()=>{if(!confirm("恢复虚构业务数据基线？"))return;const result=await api("/api/admin/reset",{method:"POST"});el("record").textContent=`基线已恢复：${result.after_digest}`;await refresh();});
document.querySelectorAll("[data-feature]").forEach(button=>{button.addEventListener("click",async()=>{button.disabled=true;try{const feature=encodeURIComponent(button.dataset.feature);const result=await api(`/api/portal/${feature}`);el("feature-title").textContent=result.title;el("feature-message").textContent=result.message;el("feature-dialog").showModal();}catch(error){notice(`暂时无法打开：${error.message}`);}finally{button.disabled=false;}});});
el("close-dialog").onclick=()=>el("feature-dialog").close();
el("dialog-confirm").onclick=()=>el("feature-dialog").close();
(async()=>{try{const s=await api("/api/lab/status");el("mode").textContent=`教学状态：${s.mode} · ${s.build_id}`;await enter();}catch{showLogin();}})();
