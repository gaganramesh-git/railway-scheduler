"""The Depot Incharge screen — the simple view for the person in the field.

This is the role whose expertise is track, signalling or traction, not software.
So the screen mirrors the block programme they already know: same vocabulary,
same reason codes, minimal typing, one button. It answers one question — "will
tonight's job fit, and if not, why?" — in their language, not in optimiser terms.
Every advanced capability (sweeps, proofs, the full Gantt) lives in the planner
view, not here.
"""

from __future__ import annotations

_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Depot Incharge — Block Demand</title>
<style>
:root{ --bg:#eef1f5; --panel:#ffffff; --panel2:#f1f4f8; --rule:#d8dfe7; --ink:#1b2430;
  --ink-soft:#566473; --ink-faint:#8391a0; --accent:#0d9488; --accent-dim:#d7efec; --good:#2f9e5c; --bad:#cf4655; --warn:#b7841f;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; --mono:ui-monospace,Menlo,monospace; }
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);}
.wrap{max-width:560px;margin:0 auto;padding:2rem 1.25rem 4rem;}
.eyebrow{font-family:var(--mono);font-size:.68rem;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin:0 0 .3rem;}
h1{margin:0;font-size:1.5rem;}
.sub{color:var(--ink-soft);font-size:.9rem;margin:.35rem 0 1.4rem;}
.card{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:1.3rem 1.4rem;}
label{display:block;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-faint);margin:.9rem 0 .3rem;}
select,input{width:100%;font-family:var(--sans);font-size:1rem;padding:.6rem .7rem;border-radius:8px;border:1px solid var(--rule);background:var(--panel2);color:var(--ink);}
.two{display:grid;grid-template-columns:1fr 1fr;gap:.8rem;}
button{width:100%;margin-top:1.3rem;font-size:1rem;font-weight:600;padding:.8rem;border-radius:10px;border:none;background:var(--accent);color:#ffffff;cursor:pointer;}
button:disabled{opacity:.5;cursor:wait;}
.result{margin-top:1.2rem;border-radius:12px;padding:1.1rem 1.2rem;display:none;}
.result.show{display:block;}
.result.ok{background:#e7f5ec;border:1px solid var(--good);}
.result.no{background:#fbe9eb;border:1px solid var(--bad);}
.result.warn{background:#faf1dc;border:1px solid var(--warn);}
.result h2{margin:0 0 .4rem;font-size:1.05rem;}
.result p{margin:.2rem 0;font-size:.9rem;color:var(--ink-soft);}
.result .big{font-family:var(--mono);color:var(--ink);font-size:1rem;}
.commit{margin-top:1rem;background:var(--good);color:#fff;}
.commit:disabled{opacity:.6;}
.result a{color:var(--accent);font-weight:600;}
.foot{margin-top:1.4rem;font-size:.8rem;color:var(--ink-faint);}
.foot a{color:var(--accent);}
</style>
</head>
<body>
<div class="wrap">
  <p class="eyebrow">Depot Incharge · SSE / JE</p>
  <h1>Raise a block demand</h1>
  <p class="sub">Pick tonight's work. We check it against the whole corridor and tell you if it fits — before you forward it.</p>

  <div class="card">
    <label>Department</label>
    <select id="dept">
      <option value="ENGG">Engineering (P.Way)</option>
      <option value="TRD">Traction Distribution (OHE)</option>
      <option value="SNT">Signal &amp; Telecom</option>
    </select>

    <label>Section</label>
    <select id="section"></select>

    <div class="two">
      <div><label>Reason code</label><select id="reason"></select></div>
      <div><label>Duration</label>
        <select id="dur"><option value="1.5">1.5 h</option><option value="2">2 h</option>
          <option value="2.5" selected>2.5 h</option><option value="3">3 h</option><option value="4">4 h</option></select></div>
    </div>

    <div class="two">
      <div><label>Machine</label><select id="equip"></select></div>
      <div><label>Needed by (night)</label>
        <select id="night"><option value="1">Night 1</option><option value="2">Night 2</option>
          <option value="3" selected>Night 3</option><option value="4">Night 4</option>
          <option value="5">Night 5</option><option value="6">Night 6</option><option value="7">Night 7</option></select></div>
    </div>

    <button id="check">Check &amp; add to plan</button>
  </div>

  <div class="result" id="result"></div>

  <p class="foot">This is the field-engineer view. The full corridor plan is in the <a href="/">planner dashboard</a>.</p>
</div>

<script>
const DEPT_CREW={ENGG:'p-way',TRD:'ohe',SNT:'signalling'};
const DEPT_REASON={ENGG:['ETMW','EOMT','ERRL'],TRD:['POWER'],SNT:['OTHR']};
const DEPT_EQUIP={ENGG:['none','tamping-machine','ballast-cleaner','rail-grinder','road-railer'],TRD:['tower-wagon'],SNT:['none']};
let SECTIONS=[];

// Who's raising this demand — passed from the dashboard role bar (?role=sse-trd).
const ROLE = new URLSearchParams(location.search).get('role') || 'sse-pway';
const ROLE_DEPT = {'sse-pway':'ENGG','sse-trd':'TRD','sse-snt':'SNT'};

async function boot(){
  const r=await fetch('/api/depot/sections'); const data=await r.json();
  SECTIONS=data.sections; const nights=data.nights||7;
  const sel=document.getElementById('section');
  sel.innerHTML=SECTIONS.map(s=>`<option value="${s.id}">${s.id} — ${s.name} (${s.traffic} trains/night)</option>`).join('');
  const nsel=document.getElementById('night'); const def=Math.min(3,nights);
  nsel.innerHTML='';
  for(let i=1;i<=nights;i++){ const o=document.createElement('option'); o.value=i; o.textContent='Night '+i; if(i===def)o.selected=true; nsel.appendChild(o); }
  const dept=ROLE_DEPT[ROLE];
  if(dept){ document.getElementById('dept').value=dept; }
  syncDept();
}
function syncDept(){
  const d=document.getElementById('dept').value;
  document.getElementById('reason').innerHTML=DEPT_REASON[d].map(x=>`<option>${x}</option>`).join('');
  document.getElementById('equip').innerHTML=DEPT_EQUIP[d].map(x=>`<option>${x}</option>`).join('');
}
document.getElementById('dept').onchange=syncDept;

document.getElementById('check').onclick=async()=>{
  const btn=document.getElementById('check'), res=document.getElementById('result');
  btn.disabled=true; btn.textContent='Checking…';
  const dept=document.getElementById('dept').value;
  const body={ department:dept, crew:DEPT_CREW[dept], section:document.getElementById('section').value,
    reason_code:document.getElementById('reason').value, duration_h:parseFloat(document.getElementById('dur').value),
    equipment:document.getElementById('equip').value, night:parseInt(document.getElementById('night').value,10),
    actor:ROLE };
  try{
    const r=await fetch('/api/depot/check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const d=await r.json();
    res.className='result show '+(d.ok?'ok':(d.fits_by_bumping?'warn':'no'));
    const commit=`<button id="commit" class="commit">✓ Commit to plan</button>`;
    if(d.ok){
      res.innerHTML=`<h2>✓ Fits — ready to commit</h2>
        <p>Would schedule on <span class="big">Night ${d.night}, ${d.start}–${d.end}</span> on ${body.section}.</p>
        <p>No conflict with other departments' work that night.</p>${commit}`;
    } else if(d.fits_by_bumping){
      res.innerHTML=`<h2>⚠ Fits only by moving other work</h2>
        <p>It can go on <span class="big">Night ${d.night}</span>, but it would displace ${d.bumped.join(', ')}.</p>
        <p>Commit anyway and the planner will see the trade — or pick another night.</p>${commit}`;
    } else {
      res.innerHTML=`<h2>✗ Won't fit as asked</h2>
        <p>${d.reason}</p>${d.suggestion?`<p><strong>Try:</strong> ${d.suggestion}</p>`:''}`;
    }
    const cb=document.getElementById('commit');
    if(cb) cb.onclick=()=>commitDemand(body,cb,res);
  }catch(e){ res.className='result show no'; res.innerHTML='<h2>Could not check</h2><p>'+e.message+'</p>'; }
  finally{ btn.disabled=false; btn.textContent='Check & add to plan'; }
};

async function commitDemand(body,cb,res){
  cb.disabled=true; cb.textContent='Committing…';
  try{
    cb.textContent='Placing in the plan…';
    const r=await fetch('/api/depot/commit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const d=await r.json();
    res.className='result show ok';
    const night=d.night||body.night;
    const url='/?night='+night;
    res.innerHTML=`<h2>✓ Committed to the plan (${d.id})</h2>
      <p>Pinned on <span class="big">Night ${night}</span>. Opening the planner on that night —
      your block shows outlined as newly raised. <span id="cd">(1)</span></p>`;
    let s=1; const t=setInterval(()=>{ s--; const el=document.getElementById('cd');
      if(el) el.textContent='('+s+')'; if(s<=0){ clearInterval(t); location.href=url; } },1000);
  }catch(e){ cb.disabled=false; cb.textContent='✓ Commit to plan'; }
}
boot();
</script>
</body>
</html>
"""


def depot_page() -> str:
    return _PAGE
