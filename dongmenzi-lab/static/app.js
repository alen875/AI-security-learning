let csrf = "";
const el = id => document.getElementById(id);
function notice(message){el("notice").textContent=message;}
async function api(path, options={}){
  const response=await fetch(path,{credentials:"same-origin",...options,headers:{"Content-Type":"application/json",...(csrf?{"X-CSRF-Token":csrf}:{}),...(options.headers||{})}});
  const payload=await response.json().catch(()=>({error:"invalid_response"}));
  if(!response.ok)throw new Error(payload.error||`HTTP ${response.status}`);
  return payload.data;
}
async function task(button, fn){button.disabled=true;notice("正在加载…");try{await fn();notice("完成");}catch(e){notice(`操作失败：${e.message}`);if(e.message==="login_required")showLogin();}finally{button.disabled=false;}}
function showLogin(){el("login-panel").hidden=false;el("workspace").hidden=true;csrf="";}
async function refresh(){const rows=await api("/api/devices");const box=el("devices");box.replaceChildren();if(!rows.length){box.textContent="暂无可见设备";return;}for(const d of rows){const card=document.createElement("div");card.className="card";card.textContent=`${d.code} · ${d.name} · ${d.status}`;const btn=document.createElement("button");btn.textContent="查看记录";btn.onclick=()=>task(btn,async()=>{const records=await api(`/api/devices/${d.id}/records`);el("record").textContent=records.length?records.map(x=>`${x.id} ${x.code} ${x.title}`).join("\n"):"无维护记录";});card.append(btn);box.append(card);}}
async function enter(){const me=await api("/api/auth/me");csrf=me.csrf;el("identity").textContent=`当前账号：${me.username}（${me.role}）`;el("login-panel").hidden=true;el("workspace").hidden=false;el("bp-panel").hidden=me.role!=="maint";el("admin-panel").hidden=me.role!=="admin";el("audit-panel").hidden=!(me.role==="admin"||me.role==="reviewer");await refresh();}
el("login-form").onsubmit=async e=>{e.preventDefault();const btn=e.submitter;await task(btn,async()=>{const form=new FormData(e.target);await api("/api/auth/login",{method:"POST",body:JSON.stringify(Object.fromEntries(form))});e.target.reset();await enter();});};
el("logout").onclick=e=>task(e.target,async()=>{await api("/api/auth/logout",{method:"POST"});showLogin();});
el("refresh").onclick=e=>task(e.target,refresh);
el("load-record").onclick=e=>task(e.target,async()=>{const id=Number(el("record-id").value);const row=await api(`/api/records/${id}`);el("record").textContent=`${row.code} · ${row.title}\n${row.body}`;});
el("bp-inspect").onclick=e=>task(e.target,async()=>{const row=await api("/api/training/report-preview",{method:"POST",body:JSON.stringify({preview_role:"maint"})});el("bp-result").textContent=`${row.report_code} · ${row.title}\n${row.content}`;});
el("search").onclick=e=>task(e.target,async()=>{const rows=await api(`/api/training-search?q=${encodeURIComponent(el("query").value)}`);const box=el("results");box.replaceChildren();if(!rows.length){box.textContent="没有匹配的教学索引";return;}for(const r of rows){const card=document.createElement("div");card.className="card";card.textContent=`${r.code} · ${r.device_code} · ${r.title} · ${r.summary}`;box.append(card);}});
el("load-audit").onclick=e=>task(e.target,async()=>{el("audit").textContent=JSON.stringify(await api("/api/audit"),null,2);});
el("reset").onclick=e=>task(e.target,async()=>{if(!confirm("恢复虚构业务数据基线？"))return;const result=await api("/api/admin/reset",{method:"POST"});el("record").textContent=`基线已恢复：${result.after_digest}`;await refresh();});
(async()=>{try{const s=await api("/api/lab/status");el("mode").textContent=`教学状态：${s.mode} · ${s.build_id}`;await enter();}catch{showLogin();}})();
