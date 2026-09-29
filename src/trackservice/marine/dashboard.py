"""Self-contained HTML dashboard for the chartering plan (SIH26006)."""

from __future__ import annotations

import json

_TEMPLATE = r"""<title>Charter Planner</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700;800&family=Public+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root{--bg:#eef2f5;--panel:#fff;--panel2:#f2f6f9;--rule:#d5dee5;--ink:#132029;--soft:#546572;--faint:#8496a3;
--accent:#0b6fa4;--accent2:#0d9488;--accentbg:#dcecf5;--good:#268a52;--goodbg:#e2f2e9;--warn:#a9741a;--bad:#c23b4a;
--cape:#0b4f7a;--pana:#0b6fa4;--supra:#1f9ac0;--handy:#5cc2c2;}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Public Sans",system-ui,sans-serif;line-height:1.5;}
.wrap{max-width:1080px;margin:0 auto;padding:32px 22px 72px;}
.eyebrow{font-family:"IBM Plex Mono",monospace;font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin:0 0 6px;}
h1{font-family:"Archivo",sans-serif;font-weight:800;font-size:2rem;letter-spacing:-.02em;margin:0 0 6px;}
.sub{color:var(--soft);margin:0 0 22px;font-size:.98rem;}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:26px;}
.kpi{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:15px 14px;box-shadow:0 1px 2px rgba(19,32,41,.04),0 6px 18px rgba(19,32,41,.05);}
.kpi .n{font-family:"Archivo",sans-serif;font-weight:800;font-size:1.5rem;line-height:1;color:var(--accent);font-variant-numeric:tabular-nums;}
.kpi.good .n{color:var(--good);}
.kpi .l{font-family:"IBM Plex Mono",monospace;font-size:.62rem;letter-spacing:.06em;text-transform:uppercase;color:var(--faint);margin-top:8px;}
h2{font-family:"Archivo",sans-serif;font-size:1.12rem;margin:30px 0 4px;}
.h2sub{color:var(--faint);font-size:.82rem;margin:0 0 14px;}
.card{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:16px 18px;box-shadow:0 1px 2px rgba(19,32,41,.04),0 6px 18px rgba(19,32,41,.05);}
table{width:100%;border-collapse:collapse;font-size:.86rem;}
th{background:var(--panel2);text-align:left;padding:9px 12px;font-family:"IBM Plex Mono",monospace;font-size:.62rem;letter-spacing:.06em;text-transform:uppercase;color:var(--faint);border-bottom:1px solid var(--rule);}
td{padding:10px 12px;border-bottom:1px solid var(--rule);vertical-align:middle;}
tr:last-child td{border-bottom:none;}
.mono{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;}
.vpill{font-family:"IBM Plex Mono",monospace;font-size:.62rem;font-weight:600;padding:2px 8px;border-radius:999px;color:#fff;}
.CAPE{background:var(--cape);}.PANA{background:var(--pana);}.SUPRA{background:var(--supra);}.HANDY{background:var(--handy);color:#06201d;}
.util{height:8px;background:var(--panel2);border-radius:5px;overflow:hidden;min-width:70px;}
.util > i{display:block;height:100%;background:var(--accent2);}
.shared{font-family:"IBM Plex Mono",monospace;font-size:.6rem;font-weight:600;color:var(--good);background:var(--goodbg);padding:2px 7px;border-radius:999px;}
.cmp{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.cmp .box{border:1px solid var(--rule);border-radius:10px;padding:14px 16px;}
.cmp .box.ours{background:var(--accentbg);border-color:var(--accent);}
.cmp .lab{font-family:"IBM Plex Mono",monospace;font-size:.62rem;letter-spacing:.06em;text-transform:uppercase;color:var(--faint);}
.cmp .big{font-family:"Archivo",sans-serif;font-weight:800;font-size:1.5rem;font-variant-numeric:tabular-nums;}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:.76rem;color:var(--soft);margin:8px 0 0;}
.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;vertical-align:-1px;margin-right:5px;}
.rec{background:var(--goodbg);border:1px solid var(--good);border-radius:8px;padding:3px 9px;font-size:.72rem;color:var(--good);font-weight:600;display:inline-block;}
.verline{margin-top:18px;font-family:"IBM Plex Mono",monospace;font-size:.76rem;color:var(--soft);}
.verline .ok{color:var(--good);}
.rolebar{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;margin:0 0 16px;font-size:.85rem;}
.rolebar .lbl{color:var(--faint);font-family:"IBM Plex Mono",monospace;font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;}
.rolebar select{background:var(--panel2);color:var(--ink);border:1px solid var(--rule);border-radius:8px;padding:.35rem .55rem;font-family:inherit;}
.rolebar .perm{color:var(--soft);font-size:.82rem;}
.rolebar .entry{margin-left:auto;text-decoration:none;font-size:.8rem;font-weight:600;color:#fff;background:var(--accent);border-radius:8px;padding:.4rem .75rem;}
.chip{font-family:"IBM Plex Mono",monospace;font-size:.66rem;background:var(--panel2);border:1px solid var(--rule);border-radius:999px;padding:2px 7px;margin:1px 2px;display:inline-flex;align-items:center;gap:5px;}
.chip.manual{background:var(--goodbg);border-color:var(--good);color:var(--good);}
.chip .x{cursor:pointer;color:var(--bad);font-weight:700;}
.mbadge{font-family:"IBM Plex Mono",monospace;font-size:.6rem;font-weight:600;color:var(--good);background:var(--goodbg);padding:2px 7px;border-radius:999px;}
.entry.warn{background:var(--warn);border:none;font-family:inherit;cursor:pointer;}
.entry.alt{background:var(--accent2);border:none;font-family:inherit;cursor:pointer;}
.dpanel textarea{width:100%;min-height:120px;font-family:"IBM Plex Mono",monospace;font-size:.78rem;border:1px solid var(--rule);border-radius:8px;padding:.5rem .6rem;background:var(--panel2);color:var(--ink);}
.dpanel .tmpl{font-family:"IBM Plex Mono",monospace;font-size:.72rem;color:var(--faint);background:var(--panel2);border:1px solid var(--rule);border-radius:6px;padding:.5rem .6rem;margin:.4rem 0;white-space:pre;overflow-x:auto;}
.dpanel .okline{color:var(--good);} .dpanel .skipline{color:var(--bad);}
.dpanel h3.imp{color:var(--accent2);}
.mini{font-family:inherit;font-size:.66rem;font-weight:600;border:1px solid var(--rule);background:var(--panel);color:var(--soft);border-radius:6px;padding:2px 7px;margin:1px 2px 1px 0;cursor:pointer;}
.mini.cancel{color:var(--bad);border-color:var(--bad);}
.mini.resched{color:var(--accent);border-color:var(--accent);}
.mini:hover{filter:brightness(.97);}
.cargoline{display:flex;align-items:center;gap:4px;flex-wrap:wrap;margin:2px 0;}
.dpanel h3{font-family:"Archivo",sans-serif;font-size:1rem;margin:0 0 8px;color:var(--warn);}
.dpanel .row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:6px 0;font-size:.85rem;}
.dpanel select,.dpanel input{font-family:inherit;padding:.4rem .55rem;border:1px solid var(--rule);border-radius:8px;background:var(--panel2);color:var(--ink);}
.dpanel button{font-family:inherit;font-weight:600;border:none;border-radius:8px;padding:.45rem .8rem;cursor:pointer;color:#fff;background:var(--warn);}
.reroute{background:var(--accent)!important;font-size:.72rem;padding:.3rem .6rem!important;}
.auditwrap{margin-top:10px;}
#audit td,#audit th{font-size:.8rem;}
.deptpill{font-family:"IBM Plex Mono",monospace;font-size:.58rem;padding:1px 6px;border-radius:999px;background:var(--panel2);border:1px solid var(--rule);color:var(--soft);margin-left:6px;}
@media(max-width:820px){.kpis{grid-template-columns:repeat(2,1fr);}.cmp{grid-template-columns:1fr;}}
</style>
<div class="wrap">
  <p class="eyebrow">SIH26006 · Ministry of Steel</p>
  <h1>Charter Planner</h1>
  <p class="sub" id="sub"></p>
  <div class="rolebar" id="rolebar" style="display:none">
    <span class="lbl">Signed in as</span>
    <select id="roleSel"></select>
    <span class="perm" id="rolePerm"></span>
    <a class="entry" id="entryLink" href="/entry" style="display:none">＋ Add shipment</a>
    <button class="entry alt" id="importBtn" style="display:none">⬆ Import CSV</button>
    <button class="entry warn" id="disruptBtn" style="display:none">⚠ Declare port disruption</button>
  </div>
  <div class="card" id="importPanel" style="display:none;margin-bottom:16px"></div>
  <div class="card" id="disruptPanel" style="display:none;margin-bottom:16px"></div>
  <div class="kpis" id="kpis"></div>

  <h2>Optimised plan vs today's reactive spot procurement</h2>
  <p class="h2sub">Same cargo demand, same ports. Ours charters ahead in soft weeks and consolidates parcels; spot books each parcel alone at the deadline.</p>
  <div class="cmp" id="cmp"></div>

  <h2>Freight-rate outlook &amp; recommended entry weeks</h2>
  <p class="h2sub">Market index per vessel class over the horizon. Charter in the trough, not reactively at the deadline.</p>
  <div class="card"><div id="chart"></div><div class="legend" id="chartleg"></div></div>

  <h2>Voyage schedule</h2>
  <p class="h2sub">Each chartered voyage — vessel class, lane, weeks, load vs capacity, and consolidated parcels.</p>
  <div class="card" style="overflow-x:auto"><table id="voyages"></table></div>

  <h2>Port draft constraints</h2>
  <p class="h2sub">A vessel drawing more than a port's max draft cannot berth — the hard physical limit the optimiser respects.</p>
  <div class="card" style="overflow-x:auto"><table id="ports"></table></div>

  <h2>Audit log</h2>
  <p class="h2sub" id="auditScope">Every action is recorded. You see your own level and everyone below you.</p>
  <div class="card auditwrap" style="overflow-x:auto"><table id="audit"></table></div>

  <div class="verline" id="ver"></div>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const LIVE=__LIVE__;
const m=D.metrics, S=D.scenario;
const money=x=>'$'+Math.round(x).toLocaleString();
const mk=D.market||{};
document.getElementById('sub').innerHTML=D.problem+' — '+S.parcels.length+' cargo parcels, '+S.ports.length+' East-Coast ports, '+S.weeks+'-week horizon.'+
 (mk.date?` <span style="color:var(--faint)">Market calibrated to Baltic Exchange (BDI ${mk.BDI}, ${mk.date}).</span>`:'');

// ---------- controlled access: role hierarchy + audit visibility ----------
const ROLES=[
 {id:'chartering-officer',label:'Chartering Officer (R. Menon)',dept:'CHARTER',rank:1,tier:'desk'},
 {id:'procurement-mgr',   label:'Procurement Manager (S. Iyer)',dept:'PROC',rank:2,tier:'control'},
 {id:'logistics-head',    label:'Logistics Head / DGM (A. Banerjee)',rank:3,tier:'approve'},
 {id:'gm-commercial',     label:'GM Commercial (P. Rao)',rank:4,tier:'signoff'},
 {id:'board',             label:'Director (Finance) / Board',rank:5,tier:'oversight'},
];
function permsFor(r){switch(r.tier){
  case 'desk':return {act:true,cancel:false,edit:false,note:'Raise cargo requirements · cannot cancel or reroute booked shipments'};
  case 'control':return {act:true,cancel:true,edit:true,note:'Raise, cancel, reschedule & reroute within '+r.dept};
  case 'approve':return {act:true,cancel:true,edit:true,note:'Validate lanes & ports · cancel, reschedule, declare port disruptions'};
  case 'signoff':return {act:true,cancel:true,edit:true,note:'Sign off the plan · cancel, reschedule, reroute with a logged reason'};
  case 'oversight':return {act:false,cancel:false,edit:false,note:'View & export only — aggregate oversight'};
}}
let role=ROLES.find(r=>r.id==='gm-commercial'); let RP=permsFor(role);
function setupRoles(){
  const bar=document.getElementById('rolebar'); bar.style.display='flex';
  const sel=document.getElementById('roleSel');
  sel.innerHTML=ROLES.map(r=>`<option value="${r.id}">${r.label}</option>`).join('');
  sel.value=role.id;
  sel.onchange=()=>{role=ROLES.find(r=>r.id===sel.value);RP=permsFor(role);applyRole();};
  applyRole();
}
function applyRole(){
  document.getElementById('rolePerm').textContent=RP.note;
  const el=document.getElementById('entryLink');
  el.style.display=(LIVE && RP.act)?'':'none';
  el.href='/entry?role='+encodeURIComponent(role.id);
  const pd=document.getElementById('disruptBtn');
  if(pd) pd.style.display=(LIVE && RP.edit)?'':'none';
  const ib=document.getElementById('importBtn');
  if(ib) ib.style.display=(LIVE && RP.act)?'':'none';
  renderVoyages(); renderAudit();
}

document.getElementById('kpis').innerHTML=[
 ['good',m.cost_saved_pct+'%','Freight cost saved'],
 ['good',money(m.cost_saved),'Absolute saving'],
 ['',m.voyages_saved,'Fewer charters ('+m.ours_voyages+' vs '+m.spot_voyages+')'],
 ['',m.on_time_pct+'%','Cargo on time ('+m.ours_served+'/'+m.total_parcels+')'],
 ['',m.utilisation_pct+'%','Vessel utilisation'],
].map(k=>`<div class="kpi ${k[0]}"><div class="n">${k[1]}</div><div class="l">${k[2]}</div></div>`).join('');

document.getElementById('cmp').innerHTML=`
 <div class="box ours"><div class="lab">Optimised (this system)</div>
   <div class="big">${money(m.ours_cost)}</div>
   <div class="lab" style="margin-top:6px">${m.ours_voyages} charters · ${m.parcels_per_voyage} parcels/voyage · ${m.utilisation_pct}% full</div></div>
 <div class="box"><div class="lab">Reactive spot (today)</div>
   <div class="big">${money(m.spot_cost)}</div>
   <div class="lab" style="margin-top:6px">${m.spot_voyages} charters · 1 parcel each · booked at deadline</div></div>`;

// ---- rate chart (inline SVG) ----
const W=1000,H=190,padL=34,padB=22,padT=10;
const weeks=S.weeks, cls=S.vessels.map(v=>v.id);
const colors={CAPE:'#0b4f7a',PANA:'#0b6fa4',SUPRA:'#1f9ac0',HANDY:'#5cc2c2'};
let vals=[]; cls.forEach(c=>{for(let w=0;w<weeks;w++){vals.push(S.rate_index[c+'|'+w]);}});
const lo=Math.min(...vals)*0.98, hi=Math.max(...vals)*1.02;
const X=w=>padL+(W-padL-8)*(w/(weeks-1));
const Y=v=>padT+(H-padT-padB)*(1-(v-lo)/(hi-lo));
let svg=`<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto">`;
for(let g=0;g<=4;g++){const yy=padT+(H-padT-padB)*g/4;svg+=`<line x1="${padL}" y1="${yy}" x2="${W-8}" y2="${yy}" stroke="#e3ebf0"/>`;}
for(let w=0;w<weeks;w++){svg+=`<text x="${X(w)}" y="${H-6}" font-size="9" fill="#8496a3" text-anchor="middle" font-family="IBM Plex Mono">${w}</text>`;}
const recByV={}; D.forecast.forEach(f=>recByV[f.vessel]=f.best_week);
cls.forEach(c=>{
  let d=''; for(let w=0;w<weeks;w++){d+=(w?'L':'M')+X(w)+' '+Y(S.rate_index[c+'|'+w]);}
  svg+=`<path d="${d}" fill="none" stroke="${colors[c]}" stroke-width="2"/>`;
  const bw=recByV[c]; svg+=`<circle cx="${X(bw)}" cy="${Y(S.rate_index[c+'|'+bw])}" r="4.5" fill="${colors[c]}" stroke="#fff" stroke-width="1.5"/>`;
});
svg+=`</svg>`;
document.getElementById('chart').innerHTML=svg;
document.getElementById('chartleg').innerHTML=D.forecast.map(f=>
 `<span><i style="background:${colors[f.vessel]}"></i>${f.vessel_name}: <span class="rec">best wk ${f.best_week} (−${f.saving_pct}% vs now)</span></span>`).join('');

// ---- voyage table (cargo chips are cancellable in live mode) ----
const manualSet=new Set(D.manual_ids||[]);
function renderVoyages(){
 const vt=D.plan.voyages;
 document.getElementById('voyages').innerHTML=
 '<thead><tr><th>Voyage</th><th>Vessel</th><th>Lane</th><th>Depart→Arrive</th><th>Load</th><th>Utilisation</th><th>Cargo</th></tr></thead><tbody>'+
 vt.map(v=>{
   const chips=v.parcels.map(pid=>{
     const man=manualSet.has(pid);
     const resched=(LIVE && RP.edit)?`<button class="mini resched" onclick="rescheduleShipment('${pid}')">Reschedule</button>`:'';
     const cancel=(LIVE && RP.cancel)?`<button class="mini cancel" onclick="cancelShipment('${pid}')">Cancel</button>`:'';
     return `<div class="cargoline"><span class="chip${man?' manual':''}">${pid}${man?' ● raised':''}</span>${resched}${cancel}</div>`;
   }).join('');
   return `<tr>
   <td class="mono">${v.voyage_id}</td>
   <td><span class="vpill ${v.vessel_id}">${v.vessel}</span>${v.manual?' <span class="mbadge">raised</span>':''}</td>
   <td>${v.origin} → ${v.port}</td>
   <td class="mono">wk ${v.depart_week} → ${v.arrive_week}</td>
   <td class="mono">${v.load_t.toLocaleString()} / ${v.capacity_t.toLocaleString()} t</td>
   <td><div class="util"><i style="width:${v.utilisation_pct}%"></i></div></td>
   <td>${chips} ${v.shared?'<span class="shared">consolidated</span>':''}</td></tr>`;
 }).join('')+'</tbody>';
}
renderVoyages();

async function cancelShipment(pid){
  if(!(LIVE && RP.cancel)) return;
  const reason=prompt('Cancel shipment '+pid+' and re-plan. Reason?','buyer pulled the tender');
  if(reason===null) return;
  try{
    await fetch('/api/charter/cancel',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({parcel_id:pid, reason, actor:role.id})});
    location.reload();
  }catch(e){ alert('Cancel failed: '+e.message); }
}

async function rescheduleShipment(pid){
  if(!(LIVE && RP.edit)) return;
  const wk=prompt('Reschedule '+pid+' — new "needed by" week (0–'+(S.weeks-1)+'). '+
                  'Use an earlier week if the cargo is arriving ahead of time:');
  if(wk===null) return;
  try{
    const d=await (await fetch('/api/charter/reschedule',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({parcel_id:pid, required_by_week:parseInt(wk), actor:role.id})})).json();
    if(!d.ok){ alert(d.reason); return; }
    location.reload();
  }catch(e){ alert('Reschedule failed: '+e.message); }
}

// ---- bulk import cargo requirements from CSV (paste or file) ----
document.getElementById('importBtn').onclick=()=>{
  const el=document.getElementById('importPanel');
  if(el.style.display!=='none'){ el.style.display='none'; return; }
  el.style.display='block'; el.className='card dpanel';
  const ports=S.ports.map(p=>p.id).join('/'), origins=S.origins.map(o=>o.id).join('/');
  el.innerHTML=`<h3 class="imp">⬆ Import cargo requirements (CSV)</h3>
    <p style="font-size:.82rem;color:var(--soft);margin:.2rem 0">Columns: <b>commodity, origin, port, volume_t, required_by_week, priority</b>.
    Origins: ${origins} · Ports: ${ports}. Each row is feasibility-checked before it's added.</p>
    <div class="tmpl">commodity,origin,port,volume_t,required_by_week,priority
Coking coal,AUS,GGV,68000,9,5
Thermal coal,IDN,VZG,55000,7,4
Steam coal,MOZ,PPT,45000,10,3</div>
    <div class="row"><input type="file" id="imp-file" accept=".csv,text/csv"></div>
    <textarea id="imp-text" placeholder="…or paste CSV rows here (including the header line)"></textarea>
    <div class="row"><button id="imp-go" style="background:var(--accent2)">Validate &amp; import</button></div>
    <div id="imp-result"></div>`;
  document.getElementById('imp-file').onchange=e=>{
    const f=e.target.files[0]; if(!f) return;
    const rd=new FileReader(); rd.onload=()=>{document.getElementById('imp-text').value=rd.result;}; rd.readAsText(f);
  };
  document.getElementById('imp-go').onclick=runImport;
};
async function runImport(){
  const csv=document.getElementById('imp-text').value.trim();
  const res=document.getElementById('imp-result');
  if(!csv){ res.innerHTML='<p class="skipline">Paste CSV or choose a file first.</p>'; return; }
  res.innerHTML='<p style="color:var(--faint)">Importing…</p>';
  const d=await (await fetch('/api/charter/import-csv',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({csv, actor:role.id})})).json();
  if(!d.ok){ res.innerHTML='<p class="skipline">'+(d.reason||'import failed')+'</p>'; return; }
  let html=`<p class="okline"><b>${d.added.length} added</b>${d.skipped.length?`, <span class="skipline">${d.skipped.length} skipped</span>`:''}.</p>`;
  if(d.added.length) html+='<div class="tmpl">'+d.added.map(a=>a.id+'  '+a.summary).join('\n')+'</div>';
  if(d.skipped.length) html+='<div class="tmpl skipline">'+d.skipped.map(s=>'row '+s.row+': '+s.reason).join('\n')+'</div>';
  if(d.added.length) html+='<p>Opening the updated plan… <span id="icd">(1)</span></p>';
  res.innerHTML=html;
  if(d.added.length){let s=1;const t=setInterval(()=>{s--;const el=document.getElementById('icd');if(el)el.textContent='('+s+')';if(s<=0){clearInterval(t);location.reload();}},1000);}
}

// ---- port disruption: choose days -> notify sender -> reroute to nearest ----
document.getElementById('disruptBtn').onclick=()=>{
  const el=document.getElementById('disruptPanel');
  if(el.style.display!=='none'){ el.style.display='none'; return; }
  el.style.display='block';
  el.className='card dpanel';
  el.innerHTML=`<h3>⚠ Declare a port disruption</h3>
    <div class="row">Port
      <select id="dp-port">${S.ports.map(p=>`<option value="${p.id}">${p.name}</option>`).join('')}</select>
      from week <input id="dp-from" type="number" min="0" max="${S.weeks-1}" value="4" style="width:60px">
      for <input id="dp-days" type="number" min="1" max="60" value="14" style="width:70px"> days
      <button id="dp-go">Find affected shipments</button></div>
    <div id="dp-result"></div>`;
  document.getElementById('dp-go').onclick=runDisrupt;
};
async function runDisrupt(){
  const port=document.getElementById('dp-port').value, days=parseInt(document.getElementById('dp-days').value);
  const from_week=parseInt(document.getElementById('dp-from').value);
  const res=document.getElementById('dp-result');
  res.innerHTML='<p style="color:var(--faint)">Checking…</p>';
  const d=await (await fetch('/api/charter/port-disrupt',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({port, days, from_week, actor:role.id})})).json();
  if(!d.ok){ res.innerHTML='<p>'+(d.reason||'error')+'</p>'; return; }
  if(!d.affected.length){ res.innerHTML=`<p>${d.port} out for ~${d.weeks} week(s): <b>no shipments affected</b> in that window. Senders notified.</p>`; return; }
  res.innerHTML=`<p>${d.port} unavailable ~${d.weeks} week(s) — <b>${d.affected.length} shipment(s) affected, senders notified.</b> Choose the next-nearest port to reroute:</p>`+
    d.affected.map(a=>`<div class="row"><span class="chip">${a.parcel_id}</span> ${a.origin} · ${a.volume_t.toLocaleString()} t ·
      ${a.current_port} → <b>${a.suggested_port_name}</b>
      ${a.suggested_port?`<button class="reroute" onclick="applyReroute('${a.parcel_id}','${a.suggested_port}')">Reroute &amp; re-plan</button>`:''}</div>`).join('');
}
async function applyReroute(pid, newPort){
  const d=await (await fetch('/api/charter/reroute',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({parcel_id:pid, new_port:newPort, actor:role.id})})).json();
  if(!d.ok){ alert(d.reason||'reroute failed'); return; }
  location.reload();
}

// ---- audit log with hierarchy visibility ----
function renderAudit(){
  const au=D.audit; if(!au){document.getElementById('audit').innerHTML='';return;}
  const me=role;
  const visible=au.entries.filter(e=>{
    if(me.rank>=3) return e.rank<=me.rank;                       // approver+ sees all below
    if(me.rank===2) return e.rank<=2 && e.department===me.dept;  // control: own dept
    return e.role_id===me.id;                                    // desk: only own
  });
  document.getElementById('auditScope').textContent =
    me.rank>=3 ? 'Showing all actions at or below '+me.label.split(' (')[0]+'.'
    : me.rank===2 ? 'Showing '+me.dept+' actions up to your level.'
    : 'Showing your own actions only.';
  document.getElementById('audit').innerHTML=
   '<thead><tr><th>Time</th><th>Role</th><th>User</th><th>Action</th><th>Detail</th></tr></thead><tbody>'+
   (visible.length?visible.map(e=>`<tr>
     <td class="mono">${e.time}</td>
     <td>${e.role}${e.department?`<span class="deptpill">${e.department}</span>`:''}</td>
     <td>${e.user}</td><td>${e.action}</td><td>${e.detail}</td></tr>`).join('')
    :'<tr><td colspan="5" style="color:var(--faint)">No actions visible at your level.</td></tr>')+'</tbody>';
}

// ---- ports ----
document.getElementById('ports').innerHTML=
 '<thead><tr><th>Port</th><th>Max draft</th><th>Handling</th><th>Largest vessel it can take</th></tr></thead><tbody>'+
 S.ports.map(p=>{
   const fit=S.vessels.filter(v=>v.draft_m<=p.max_draft_m).sort((a,b)=>b.dwt-a.dwt)[0];
   return `<tr><td><b>${p.name}</b></td><td class="mono">${p.max_draft_m} m</td><td class="mono">${p.handling_tpd.toLocaleString()} t/day</td><td><span class="vpill ${fit.id}">${fit.name}</span> and smaller</td></tr>`;
 }).join('')+'</tbody>';

const ver=D.verification;
document.getElementById('ver').innerHTML=`${S.parcels.length} parcels · CP-SAT ${D.plan.proven_optimal?'proved OPTIMAL':D.plan.status} in ${D.plan.solve_seconds}s · <span class="${ver.ok?'ok':''}">${ver.ok?'✓ independently verified ('+ver.checks_run+' checks)':'✗ FAILED VERIFICATION'}</span>`;

setupRoles();
</script>
"""


def build_html(report: dict, live: bool = False) -> str:
    return (_TEMPLATE
            .replace("__DATA__", json.dumps(report))
            .replace("__LIVE__", "true" if live else "false"))
