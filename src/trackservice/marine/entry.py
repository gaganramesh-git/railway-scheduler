"""The charter-entry screen — the operator's simple form to raise a new cargo
requirement. Checks feasibility (port draft, deadline), shows the cheapest option,
then commits it into the plan. Mirrors the railway depot screen.
"""

from __future__ import annotations

_PAGE = r"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Raise a Cargo Requirement</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@700;800&family=Public+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap">
<style>
:root{--bg:#eef2f5;--panel:#fff;--panel2:#f2f6f9;--rule:#d5dee5;--ink:#132029;--soft:#4a5a66;--faint:#5c6b78;
--accent:#0b6fa4;--accent2:#0d9488;--good:#268a52;--goodbg:#e2f2e9;--bad:#c23b4a;--badbg:#f7e3e5;--warn:#a9741a;--warnbg:#f6ecd7;}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Public Sans",system-ui,sans-serif;}
.wrap{max-width:560px;margin:0 auto;padding:34px 20px 60px;}
.eyebrow{font-family:"IBM Plex Mono",monospace;font-size:.7rem;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin:0 0 6px;}
h1{font-family:"Archivo",sans-serif;font-weight:800;font-size:1.6rem;margin:0 0 6px;}
.sub{color:var(--soft);font-size:.92rem;margin:0 0 20px;}
.card{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:18px 20px;box-shadow:0 6px 18px rgba(19,32,41,.05);}
label{display:block;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;color:var(--faint);margin:.85rem 0 .3rem;font-family:"IBM Plex Mono",monospace;}
select,input{width:100%;font-family:inherit;font-size:1rem;padding:.55rem .7rem;border-radius:8px;border:1px solid var(--rule);background:var(--panel2);color:var(--ink);}
.two{display:grid;grid-template-columns:1fr 1fr;gap:.8rem;}
button{width:100%;margin-top:1.3rem;font-size:1rem;font-weight:600;padding:.75rem;border-radius:10px;border:none;background:var(--accent);color:#fff;cursor:pointer;font-family:inherit;}
button:disabled{opacity:.6;cursor:wait;}
.commit{margin-top:1rem;background:var(--good);}
.result{margin-top:1.1rem;border-radius:12px;padding:1rem 1.2rem;display:none;}
.result.show{display:block;}
.result.ok{background:var(--goodbg);border:1px solid var(--good);}
.result.no{background:var(--badbg);border:1px solid var(--bad);}
.result h2{margin:0 0 .4rem;font-size:1.02rem;font-family:"Archivo",sans-serif;}
.result p{margin:.2rem 0;font-size:.9rem;color:var(--soft);}
.result .big{font-family:"IBM Plex Mono",monospace;color:var(--ink);}
.result a{color:var(--accent);font-weight:600;}
.foot{margin-top:1.3rem;font-size:.82rem;color:var(--faint);}
.foot a{color:var(--accent);}
</style>
<div class="wrap">
  <p class="eyebrow" id="eyebrow">Chartering Officer · Cargo Desk</p>
  <h1>Raise a cargo requirement</h1>
  <p class="sub">Enter a new shipment. We check it against port limits and the market, show the cheapest option, then add it to the plan.</p>
  <div class="card">
    <div class="two">
      <div><label>Origin</label><select id="origin"></select></div>
      <div><label>Discharge port</label><select id="port"></select></div>
    </div>
    <label>Commodity</label>
    <select id="commodity"><option>Coking coal</option><option>Thermal coal</option><option>Steam coal</option></select>
    <div class="two">
      <div><label>Volume (tonnes)</label>
        <select id="vol"><option>28000</option><option>30000</option><option selected>45000</option><option>55000</option><option>68000</option><option>70000</option></select></div>
      <div><label>Needed by (week)</label><select id="week"></select></div>
    </div>
    <label>Priority</label>
    <select id="priority"><option value="5">5 — plant-critical</option><option value="4">4 — important</option><option value="3">3 — routine</option></select>
    <button id="check">Check feasibility &amp; cost</button>
  </div>
  <div class="result" id="result"></div>
  <p class="foot">Chartering-desk view. The full plan is in the <a href="/">planner dashboard</a>.</p>
</div>
<script>
const ROLE = new URLSearchParams(location.search).get('role') || 'chartering-officer';
const ROLE_LABEL = {
  'chartering-officer':'Chartering Officer','procurement-mgr':'Procurement Manager',
  'logistics-head':'Logistics Head','gm-commercial':'GM (Commercial)','board':'Director / Board'};
document.getElementById('eyebrow').textContent = (ROLE_LABEL[ROLE]||'Chartering Officer') + ' · Cargo Desk';
async function boot(){
  const r=await fetch('/api/entry/options'); const d=await r.json();
  document.getElementById('origin').innerHTML=d.origins.map(o=>`<option value="${o.id}">${o.name} (${o.transit_weeks} wk transit)</option>`).join('');
  document.getElementById('port').innerHTML=d.ports.map(p=>`<option value="${p.id}">${p.name} (draft ${p.max_draft_m} m)</option>`).join('');
  const wsel=document.getElementById('week');
  for(let i=1;i<d.weeks;i++){const o=document.createElement('option');o.value=i;o.textContent='Week '+i;if(i===8)o.selected=true;wsel.appendChild(o);}
}
function body(){return {origin:origin.value, port:port.value, commodity:commodity.value,
  volume_t:parseInt(vol.value), required_by_week:parseInt(week.value), priority:parseInt(priority.value), actor:ROLE};}
document.getElementById('check').onclick=async()=>{
  const btn=document.getElementById('check'), res=document.getElementById('result');
  btn.disabled=true; btn.textContent='Checking…';
  try{
    const b=body();
    const d=await (await fetch('/api/charter/check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)})).json();
    if(d.ok){
      res.className='result show ok';
      res.innerHTML=`<h2>✓ Feasible — cheapest option</h2>
        <p>Charter a <span class="big">${d.vessel_name}</span>, depart <span class="big">week ${d.week}</span>, arrive week ${d.arrive_week}.</p>
        <p>Estimated freight: <span class="big">$${Math.round(d.cost).toLocaleString()}</span>.</p>
        <button class="commit" id="commit">✓ Add to the plan</button>`;
      document.getElementById('commit').onclick=()=>commit(b,res);
    } else {
      res.className='result show no';
      res.innerHTML=`<h2>✗ Can't ship as asked</h2><p>${d.reason}</p>`;
    }
  }catch(e){ res.className='result show no'; res.innerHTML='<h2>Could not check</h2><p>'+e.message+'</p>'; }
  finally{ btn.disabled=false; btn.textContent='Check feasibility & cost'; }
};
async function commit(b,res,cb){
  const d=await (await fetch('/api/charter/commit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)})).json();
  res.className='result show ok';
  res.innerHTML=`<h2>✓ Added to the plan (${d.id})</h2>
    <p>Chartered on a <span class="big">${d.vessel}</span>, week ${d.week}. Opening the <a href="/">planner</a>… <span id="cd">(1)</span></p>`;
  let s=1; const t=setInterval(()=>{s--;const el=document.getElementById('cd');if(el)el.textContent='('+s+')';if(s<=0){clearInterval(t);location.href='/';}},1000);
}
boot();
</script>
"""


def entry_page() -> str:
    return _PAGE
