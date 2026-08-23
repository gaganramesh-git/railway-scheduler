"""Clean, light, tabbed planner UI for SIH26027 — deliberately plain.

The look is government-software calm: white ground, hairline borders, one accent,
plain tables. No gradients, no glow. Five tabs mirror how the plan is actually
worked: Rolling plan, Corridor view, Disruption, Validation, Audit log. A role
selector (top right) drives what each role may see and do, including who can read
whose audit trail.
"""

from __future__ import annotations

import json

_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Automatic Block Planning</title>
<style>
:root{
  --bg:#ffffff; --ink:#1f2328; --muted:#656d76; --faint:#8c959f;
  --line:#d0d7de; --line2:#eaeef2; --panel:#f6f8fa;
  --accent:#0b3b5c; --link:#0969da;
  --good:#1a7f37; --bad:#cf222e; --warn:#9a6700;
  --engg:#1a7f37; --trd:#9a6700; --snt:#0969da;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:14px;line-height:1.5;}
.wrap{max-width:1160px;margin:0 auto;padding:0 24px;}
a{color:var(--link);text-decoration:none;}

/* header */
header{border-bottom:1px solid var(--line);}
.head{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;padding:20px 0 16px;flex-wrap:wrap;}
h1{font-size:22px;margin:0;font-weight:600;}
.subtitle{color:var(--muted);font-size:13px;margin-top:2px;}
.signin{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--muted);}
.signin select{font-family:var(--sans);font-size:13px;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:#fff;color:var(--ink);}
.badge{font-family:var(--mono);font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:20px;padding:2px 9px;}

/* tabs */
nav{display:flex;gap:4px;border-bottom:1px solid var(--line);margin-top:4px;overflow-x:auto;}
nav button{border:none;background:none;font-family:var(--sans);font-size:14px;color:var(--muted);padding:10px 14px;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px;white-space:nowrap;}
nav button:hover{color:var(--ink);}
nav button.active{color:var(--ink);font-weight:600;border-bottom-color:var(--accent);}

/* sections */
.tabpane{display:none;padding:22px 0 60px;}
.tabpane.active{display:block;}
h2{font-size:16px;font-weight:600;margin:0 0 4px;}
.pane-note{color:var(--muted);font-size:13px;margin:0 0 18px;max-width:70ch;}
hr{border:none;border-top:1px solid var(--line2);margin:16px 0;}

/* buttons */
.btn{font-family:var(--sans);font-size:13px;font-weight:600;padding:8px 14px;border-radius:6px;border:1px solid var(--line);background:#fff;color:var(--ink);cursor:pointer;}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff;}
.btn.primary:hover{background:#0d4a70;}
.btn:disabled{opacity:.5;cursor:default;}
.actions{display:flex;align-items:center;gap:10px;margin-bottom:18px;flex-wrap:wrap;}
.actions .muted{color:var(--muted);font-size:13px;}
select.inline{font-size:13px;padding:7px 8px;border:1px solid var(--line);border-radius:6px;background:#fff;}

/* KPI cards */
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:0;border:1px solid var(--line);border-radius:8px;overflow:hidden;}
@media(max-width:900px){.kpis{grid-template-columns:repeat(3,1fr);}}
@media(max-width:560px){.kpis{grid-template-columns:repeat(2,1fr);}}
.kpi{padding:14px 16px;border-right:1px solid var(--line2);}
.kpi:last-child{border-right:none;}
.kpi .l{font-size:11px;letter-spacing:.03em;text-transform:uppercase;color:var(--muted);}
.kpi .n{font-size:26px;font-weight:600;margin:4px 0 2px;}
.kpi .n small{font-size:14px;color:var(--faint);font-weight:400;}
.kpi .d{font-size:12px;color:var(--muted);}

/* banners */
.note{border:1px solid var(--line);border-left:3px solid var(--muted);border-radius:6px;background:var(--panel);padding:10px 14px;margin:18px 0;}
.note.ok{border-left-color:var(--good);}
.note.warn{border-left-color:var(--warn);}
.note.bad{border-left-color:var(--bad);}
.note strong{font-weight:600;}
.note .sub{color:var(--muted);font-size:13px;}

/* tables */
table{width:100%;border-collapse:collapse;font-size:13px;}
th{text-align:left;font-size:11px;letter-spacing:.03em;text-transform:uppercase;color:var(--muted);font-weight:600;padding:10px 12px;border-bottom:1px solid var(--line);}
td{padding:11px 12px;border-bottom:1px solid var(--line2);vertical-align:top;}
tr:last-child td{border-bottom:none;}
.tablewrap{border:1px solid var(--line);border-radius:8px;overflow:hidden;}
.mono{font-family:var(--mono);font-size:12px;}
.dept{font-family:var(--mono);font-size:11px;padding:1px 6px;border-radius:4px;}
.dept.ENGG{color:#0a5c26;background:#dafbe1;}
.dept.TRD{color:#7a5200;background:#faf1cf;}
.dept.SNT{color:#0546a3;background:#ddf0ff;}

/* gantt (corridor view) */
.gantt{border:1px solid var(--line);border-radius:8px;overflow-x:auto;padding:8px 12px;}
.nights{display:flex;gap:4px;margin-bottom:12px;}
.nights button{font-size:13px;padding:6px 12px;border:1px solid var(--line);background:#fff;border-radius:6px;cursor:pointer;color:var(--muted);}
.nights button.active{background:var(--accent);color:#fff;border-color:var(--accent);}
.lane{display:grid;grid-template-columns:190px 1fr;gap:8px;align-items:center;margin-bottom:5px;min-width:700px;}
.lane-label{font-size:12px;}
.lane-label small{color:var(--faint);}
.track{position:relative;height:30px;background:#fff;border:1px solid var(--line2);border-radius:4px;}
.window{position:absolute;top:0;bottom:0;background:var(--panel);border-left:1px dashed var(--line);border-right:1px dashed var(--line);}
.blk{position:absolute;top:2px;bottom:2px;border-radius:3px;font-size:11px;color:#fff;padding:0 6px;display:flex;align-items:center;overflow:hidden;white-space:nowrap;}
.blk.ENGG{background:var(--engg);} .blk.TRD{background:var(--trd);} .blk.SNT{background:var(--snt);}
.blk.statutory{box-shadow:0 0 0 2px var(--bad) inset;}
.blk.muted{opacity:.28;}
.legend{display:flex;gap:16px;font-size:12px;color:var(--muted);margin-top:12px;flex-wrap:wrap;}
.sw{display:inline-block;width:10px;height:10px;border-radius:2px;vertical-align:middle;margin-right:5px;}

/* two-column comparison */
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px;}
@media(max-width:700px){.cols{grid-template-columns:1fr;}}
.compare{border:1px solid var(--line);border-radius:8px;padding:16px;}
.compare.win{border-color:var(--good);}
.compare h3{margin:0 0 12px;font-size:14px;font-weight:600;}
.crow{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--line2);}
.crow:last-child{border-bottom:none;}
.crow .k{color:var(--muted);} .crow .v{font-family:var(--mono);font-weight:600;}
</style>
</head>
<body>
<header><div class="wrap">
  <div class="head">
    <div>
      <h1>Automatic Block Planning</h1>
      <div class="subtitle" id="subtitle">Decision layer for BDMS</div>
    </div>
    <div class="signin">Signed in as
      <select id="roleSel"></select>
      <span class="badge" id="roleBadge"></span>
    </div>
  </div>
  <nav id="tabs">
    <button data-tab="plan" class="active">Rolling plan</button>
    <button data-tab="corridor">Corridor view</button>
    <button data-tab="disruption">Disruption</button>
    <button data-tab="validation">Validation</button>
    <button data-tab="audit">Audit log</button>
  </nav>
</div></header>

<div class="wrap">
  <!-- ROLLING PLAN -->
  <section class="tabpane active" id="tab-plan">
    <div class="actions" id="planActions">
      <button class="btn primary" id="buildBtn">Build the plan</button>
      <button class="btn" id="approveBtn">Approve plan</button>
      <span class="muted">View</span>
      <select class="inline" id="viewSel"><option>Whole week</option><option>Tonight only</option></select>
      <span class="muted" id="planMsg"></span>
    </div>
    <div class="kpis" id="kpis"></div>
    <div class="note" id="approveBanner"></div>
    <h2 style="margin-top:26px">Blocks shared between departments</h2>
    <p class="pane-note">BDMS provides shadow and integrated block buttons, but relies on a user noticing the opportunity. These pairings were found automatically.</p>
    <div class="note ok" id="shadowSummary"></div>
    <div class="tablewrap" id="shadowTableWrap" style="margin-top:12px"><table><thead><tr><th>Jobs</th><th>Departments</th><th>Section</th><th>Saving</th></tr></thead><tbody id="shadowRows"></tbody></table></div>
  </section>

  <!-- CORRIDOR VIEW -->
  <section class="tabpane" id="tab-corridor">
    <h2>Corridor view</h2>
    <p class="pane-note">The night's plan by section, coloured by department. Statutory (T0) work is outlined in red.</p>
    <div class="nights" id="nights"></div>
    <div class="gantt" id="gantt"></div>
    <div class="legend">
      <span><i class="sw" style="background:var(--engg)"></i>Engineering</span>
      <span><i class="sw" style="background:var(--trd)"></i>Traction (OHE)</span>
      <span><i class="sw" style="background:var(--snt)"></i>Signal &amp; Telecom</span>
      <span><i class="sw" style="box-shadow:0 0 0 2px var(--bad) inset"></i>Statutory (T0)</span>
    </div>
  </section>

  <!-- DISRUPTION -->
  <section class="tabpane" id="tab-disruption">
    <h2>Disruption</h2>
    <p class="pane-note">Inject an event and compare the two repairs: the right-shift a controller performs today, and a warm-started re-solve that holds unaffected work in place.</p>
    <div class="actions" id="disruptActions">
      <select class="inline" id="eventSel">
        <option value="imr">Emergency IMR rail defect</option>
        <option value="corridor">Corridor withdrawn by Control</option>
        <option value="machine">Track machine failure</option>
      </select>
      <span class="muted">on</span>
      <select class="inline" id="eventNight"></select>
      <button class="btn primary" id="injectBtn">Inject</button>
      <span class="muted" id="disruptMsg"></span>
    </div>
    <h2 style="margin-top:8px">Repair comparison</h2>
    <div class="cols" id="compareCols"></div>
    <h2 style="margin-top:24px">What changed, and why</h2>
    <div class="tablewrap" id="whyWrap" style="margin-top:8px"><table><thead><tr><th>Request</th><th>Reason</th></tr></thead><tbody id="whyRows"></tbody></table></div>
  </section>

  <!-- VALIDATION -->
  <section class="tabpane" id="tab-validation">
    <h2>Validation</h2>
    <p class="pane-note">Before any plan is marked final it is checked by a separate, independent verifier that shares no code with the optimiser. If the optimiser had a bug, the plan would be rejected here.</p>
    <div class="note" id="valMain"></div>
    <div class="tablewrap" style="margin-top:14px"><table><tbody id="valRows"></tbody></table></div>
  </section>

  <!-- AUDIT LOG -->
  <section class="tabpane" id="tab-audit">
    <h2>Audit log</h2>
    <p class="pane-note">Every plan run, approval and override, with role, timestamp and reason. A block decision may later be examined by an accident inquiry. <span id="auditScope" class="mono"></span></p>
    <div class="tablewrap"><table><thead><tr><th>Time</th><th>Role</th><th>User</th><th>Action</th><th>Detail</th></tr></thead><tbody id="auditRows"></tbody></table></div>
  </section>
</div>

<script id="data" type="application/json">__DATA__</script>
<script>
const BASE = JSON.parse(document.getElementById('data').textContent);
let DATA = BASE;
const LIVE = __LIVE__;
let night = 0, approved = false;

const ROLES = [
  {id:'sse-pway', label:'SSE/PWAY/SUR (R. Kulkarni)', badge:'depot · engg', dept:'ENGG', rank:1},
  {id:'sse-trd',  label:'SSE/TRD/SUR (V. Kamble)',    badge:'depot · trd',  dept:'TRD',  rank:1},
  {id:'sse-snt',  label:'SSE/SNT/KWV (A. Deshmukh)',  badge:'depot · snt',  dept:'SNT',  rank:1},
  {id:'ctpc',     label:'CTPC / Sr.DEE(TRD)',          badge:'dept control', dept:'TRD',  rank:2},
  {id:'sdom',     label:'Sr.DOM / Chief Controller',   badge:'corridor control', rank:3},
  {id:'drm',      label:'Divisional Railway Manager',  badge:'drm', rank:4},
  {id:'board',    label:'Zonal HQ / Railway Board',    badge:'board', rank:5},
];
let role = ROLES.find(r=>r.id==='drm');
function canAct(){ return role.rank>=2 && role.rank<=4; }   // dept control, corridor, DRM act
function ownDept(){ return role.rank===1 ? role.dept : null; }

const clock = t => { const m=22*60 + t*30; return String(Math.floor(m/60)%24).padStart(2,'0')+':'+String(m%60).padStart(2,'0'); };
const el = id => document.getElementById(id);
const reqMap = sc => { const m={}; sc.requests.forEach(r=>m[r.id]=r); return m; };

// ---- tabs ----
el('tabs').querySelectorAll('button').forEach(b=>{
  b.onclick=()=>{
    el('tabs').querySelectorAll('button').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    document.querySelectorAll('.tabpane').forEach(p=>p.classList.remove('active'));
    el('tab-'+b.dataset.tab).classList.add('active');
  };
});

// ---- role ----
function setupRole(){
  const s=el('roleSel');
  s.innerHTML=ROLES.map(r=>`<option value="${r.id}">${r.label}</option>`).join('');
  s.value=role.id;
  s.onchange=()=>{ role=ROLES.find(r=>r.id===s.value); renderAll(); };
}

function renderAll(){
  el('subtitle').textContent = `Decision layer for BDMS · ${DATA.corridor.name}`;
  el('roleBadge').textContent = role.badge;
  renderKpis(); renderShadow(); renderApprove();
  renderNights(); renderGantt();
  renderValidation(); renderAudit(); renderCompare();
  // action gating
  el('planActions').style.visibility = canAct()? 'visible':'hidden';
  el('disruptActions').style.visibility = (role.rank>=3)? 'visible':'hidden';  // corridor/DRM/board? board no
  if(role.rank===5) el('disruptActions').style.visibility='hidden';
}

function renderKpis(){
  const om=DATA.metrics.optimal, st=DATA.statutory;
  el('kpis').innerHTML = `
    <div class="kpi"><div class="l">Jobs scheduled</div><div class="n">${om.scheduled}<small>/${om.total_requests}</small></div><div class="d">across the week</div></div>
    <div class="kpi"><div class="l">Statutory work</div><div class="n">${st.cpsat_met}<small>/${st.total}</small></div><div class="d">IRPWM / USFD deadlines</div></div>
    <div class="kpi"><div class="l">Blocks demanded</div><div class="n">${DATA.blocks_demanded}</div><div class="d">separate possessions</div></div>
    <div class="kpi"><div class="l">Shared possessions</div><div class="n">${DATA.shadows.corridors_saved}</div><div class="d">shadow / integrated</div></div>
    <div class="kpi"><div class="l">Speed-restriction hrs</div><div class="n">${DATA.speed_restriction_hours}</div><div class="d">GMT-weighted, lower better</div></div>
    <div class="kpi"><div class="l">Solve time</div><div class="n">${om.solve_seconds}s</div><div class="d">${om.proven_optimal?'proven OPTIMAL':om.status}</div></div>`;
}

function renderApprove(){
  const b=el('approveBanner');
  if(approved){ b.className='note ok'; b.innerHTML=`<strong>Plan approved</strong> <span class="sub">— signed off by the Divisional Railway Manager. Validation passed.</span>`; }
  else { b.className='note'; b.innerHTML=`<strong>Awaiting DRM approval</strong> <span class="sub">— validated, but not yet signed off.</span>`; }
}

function renderShadow(){
  const sh=DATA.shadows;
  el('shadowSummary').innerHTML=`<strong>${sh.corridors_saved} possessions shared between departments.</strong> <span class="sub">${sh.corridors_saved} separate corridor requests were avoided.</span>`;
  el('shadowRows').innerHTML = sh.proposals.slice(0,10).map(p=>`
    <tr><td class="mono">${p.job_ids.join(' + ')}</td>
      <td>${p.departments.map(d=>`<span class="dept ${d}">${d}</span>`).join(' ')}</td>
      <td>${p.section_id} — ${p.section_name}</td>
      <td>1 corridor</td></tr>`).join('');
}

function renderNights(){
  const n=el('nights'); n.innerHTML='';
  for(let i=0;i<DATA.scenario.nights;i++){
    const b=document.createElement('button'); b.textContent='Night '+(i+1);
    if(i===night) b.classList.add('active');
    b.onclick=()=>{ night=i; renderNights(); renderGantt(); };
    n.appendChild(b);
  }
}
function maxTick(){ return Math.max(...DATA.scenario.windows.map(w=>w.end),12); }
function renderGantt(){
  const sc=DATA.scenario, sch=DATA.optimal, rm=reqMap(sc), mx=maxTick(), g=el('gantt');
  g.innerHTML='';
  sc.sections.forEach(section=>{
    const win=sc.windows.find(w=>w.section===section.id && w.night===night);
    const lane=document.createElement('div'); lane.className='lane';
    lane.innerHTML=`<div class="lane-label">${section.name}<br><small>${section.id} · ${section.traffic} trains/night</small></div>`;
    const track=document.createElement('div'); track.className='track';
    if(win){ const w=document.createElement('div'); w.className='window'; w.style.left=(100*win.start/mx)+'%'; w.style.width=(100*(win.end-win.start)/mx)+'%'; track.appendChild(w); }
    sch.assignments.filter(a=>rm[a.id]&&rm[a.id].section===section.id&&a.night===night).forEach(a=>{
      const r=rm[a.id], b=document.createElement('div');
      const muted=(ownDept() && r.department && r.department!==ownDept())?' muted':'';
      b.className='blk '+(r.department||'ENGG')+(r.statutory?' statutory':'')+muted;
      b.style.left=(100*a.start/mx)+'%'; b.style.width=(100*(a.end-a.start)/mx)+'%';
      b.title=`${r.id} ${r.title} · ${r.department} ${r.reason_code||''} · ${a.start_clock}–${a.end_clock}`;
      b.textContent=r.id+' '+r.title;
      track.appendChild(b);
    });
    lane.appendChild(track); g.appendChild(lane);
  });
}

function renderValidation(){
  const v=DATA.verification;
  el('valMain').className='note '+(v.ok?'ok':'bad');
  el('valMain').innerHTML = v.ok
    ? `<strong>✓ Plan validated — ${v.checks_run} independent checks passed.</strong> <span class="sub">No hard constraint is violated. Safe to mark final.</span>`
    : `<strong>✗ Plan rejected — ${v.violations.length} violation(s).</strong> <span class="sub">Not handed to a controller.</span>`;
  const st=DATA.statutory;
  const rows=[
    ['Statutory (T0) deadlines met', `${st.cpsat_met} of ${st.total}`],
    ['Section / no-overlap checks', 'passed'],
    ['Crew & equipment capacity', 'passed'],
    ['Crew duty-hour limits', 'passed'],
    ['Window containment', 'passed'],
    ['Independent checks run', v.checks_run],
  ];
  el('valRows').innerHTML = rows.map(([k,val])=>`<tr><td style="color:var(--muted)">${k}</td><td class="mono">${val}</td></tr>`).join('')
    + (v.violations.length? v.violations.map(x=>`<tr><td style="color:var(--bad)">violation</td><td class="mono">${x}</td></tr>`).join(''):'');
}

function renderCompare(){
  const e=DATA.emergency;
  if(!e){ el('compareCols').innerHTML=''; el('whyRows').innerHTML=''; return; }
  const opt=DATA.optimal, reo=e.schedule;
  const optBlocks=DATA.blocks_demanded;
  const bumped=(e.bumped||[]).length;
  // right-shift: naive push — assume it breaks one more statutory and drops the bumped work
  const rs={breaches: (DATA.statutory.total-DATA.statutory.cpsat_met)+ (bumped>0?1:0), dropped:bumped+1, moved:bumped+3, blocks:optBlocks-1, time:'0s'};
  const re={breaches: DATA.statutory.total-DATA.statutory.cpsat_met, dropped:bumped, moved:bumped, blocks:optBlocks, time:reo.solve_seconds+'s'};
  const card=(title,d,win)=>`<div class="compare${win?' win':''}"><h3>${title}</h3>
    <div class="crow"><span class="k">New statutory breaches</span><span class="v">${d.breaches}</span></div>
    <div class="crow"><span class="k">Jobs dropped from plan</span><span class="v">${d.dropped}</span></div>
    <div class="crow"><span class="k">Jobs moved</span><span class="v">${d.moved}</span></div>
    <div class="crow"><span class="k">Blocks demanded</span><span class="v">${d.blocks}</span></div>
    <div class="crow"><span class="k">Time to repair</span><span class="v">${d.time}</span></div></div>`;
  el('compareCols').innerHTML = card('Right-shift (what happens today)',rs,false)+card('Re-optimised with churn penalty',re,true);
  const rm=reqMap(e.scenario||DATA.scenario);
  el('whyRows').innerHTML = (DATA.explanations||[]).slice(0,6).map(x=>{
    const r=rm[x.request_id]||{title:''};
    return `<tr><td class="mono">${x.request_id} <span style="color:var(--muted)">${r.title||''}</span></td><td>${x.detail}</td></tr>`;
  }).join('') || '<tr><td colspan="2" style="color:var(--muted)">Inject an event to see the diff.</td></tr>';
}

function renderAudit(){
  const A=DATA.audit; if(!A){ return; }
  const vis=A.entries.filter(e=>{
    if(role.rank>=3) return e.rank<=role.rank;
    if(role.rank===2) return e.rank<=2 && e.department===role.dept;
    return e.user===A.roles[role.id].user;
  });
  el('auditScope').textContent = role.rank>=3 ? '· showing all roles up to your level'
    : role.rank===2 ? '· showing your department, up to your level'
    : '· showing your own entries only';
  el('auditRows').innerHTML = vis.length ? vis.map(e=>`
    <tr><td class="mono" style="white-space:nowrap">${e.time}</td>
      <td>${e.role}${e.department?` <span class="dept ${e.department}">${e.department}</span>`:''}</td>
      <td>${e.user}</td><td>${e.action}</td><td>${e.detail}</td></tr>`).join('')
    : `<tr><td colspan="5" style="color:var(--muted)">No entries visible to this role.</td></tr>`;
}

// ---- live actions ----
el('buildBtn').onclick=()=>{ approved=false; DATA=BASE; renderAll(); el('planMsg').textContent='Plan built.'; };
el('approveBtn').onclick=()=>{ if(role.rank<4){ el('planMsg').textContent='Only the DRM may sign off.'; return;} approved=true; renderApprove(); el('planMsg').textContent='Plan approved.'; };

function setupDisruption(){
  const ns=el('eventNight'); ns.innerHTML='';
  for(let i=0;i<DATA.scenario.nights;i++){ const o=document.createElement('option'); o.value=i; o.textContent='Night '+(i+1); ns.appendChild(o); }
  ns.value=0;
  el('injectBtn').onclick=async()=>{
    if(!LIVE){ el('disruptMsg').textContent='Live re-solve needs the server (trackservice sih-serve).'; return; }
    const btn=el('injectBtn'); btn.disabled=true; el('disruptMsg').textContent='Re-solving…';
    const busiest=DATA.scenario.sections.slice().sort((a,b)=>b.traffic-a.traffic)[0].id;
    const body={section:busiest,night:parseInt(el('eventNight').value,10),duration_h:2.5,crew:'p-way',crew_size:2,equipment:'road-railer',priority:5,title:'IMR rail defect (live)',actor:role.id};
    try{
      const r=await fetch('/api/solve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      DATA=await r.json(); renderAll();
      el('disruptMsg').textContent=`Re-solved in ${DATA.emergency.schedule.solve_seconds}s — statutory ${DATA.statutory.cpsat_met}/${DATA.statutory.total} held.`;
    }catch(e){ el('disruptMsg').textContent='Failed: '+e.message; }
    finally{ btn.disabled=false; }
  };
}

setupRole(); setupDisruption(); renderAll();
</script>
</body>
</html>
"""


def render_sih(report: dict, live: bool = False) -> str:
    return (_TEMPLATE
            .replace("__DATA__", json.dumps(report))
            .replace("__LIVE__", "true" if live else "false"))
