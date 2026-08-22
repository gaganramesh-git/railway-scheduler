"""Render the solved report as one self-contained HTML file.

The JSON is embedded, so the file opens with no server and no network. No
localStorage/sessionStorage is used. The 'before' (greedy) and 'after' (CP-SAT)
plans are both real solver output baked into the page; the emergency toggle
swaps to the pre-computed re-optimised plan.
"""

from __future__ import annotations

import json

_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Track Service — Maintenance Block Scheduler</title>
<style>
:root {
  --bg:#0f1419; --panel:#171d24; --panel2:#1e262f; --rule:#2a343e;
  --ink:#e6ecf1; --ink-soft:#9aa8b4; --ink-faint:#6b7885;
  --accent:#4fd1c5; --accent-dim:#1f3d3a;
  --p3:#546b82; --p4:#c98a2b; --p5:#d1495b;
  --good:#3fb56b; --bad:#d1495b; --new:#4fd1c5;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font-family:var(--sans); font-size:15px; line-height:1.5; }
.wrap { max-width:1180px; margin:0 auto; padding:2rem 1.5rem 5rem; }
header { border-bottom:1px solid var(--rule); padding-bottom:1.4rem; margin-bottom:1.6rem; }
.eyebrow { font-family:var(--mono); font-size:.7rem; letter-spacing:.16em; text-transform:uppercase; color:var(--accent); margin:0 0 .5rem; }
h1 { margin:0; font-size:1.9rem; letter-spacing:-.02em; }
.sub { color:var(--ink-soft); margin:.4rem 0 0; max-width:60ch; }

.kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:.8rem; margin:1.6rem 0; }
.kpi { background:var(--panel); border:1px solid var(--rule); border-radius:8px; padding:.9rem 1rem; }
.kpi .n { font-size:1.6rem; font-weight:700; font-variant-numeric:tabular-nums; }
.kpi .l { font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; color:var(--ink-faint); margin-top:.15rem; }
.kpi .d { font-size:.75rem; color:var(--accent); margin-top:.3rem; }

.controls { display:flex; flex-wrap:wrap; gap:.6rem; align-items:center; margin:1.4rem 0 1rem; }
button { font-family:var(--sans); font-size:.85rem; padding:.5rem .9rem; border-radius:7px; border:1px solid var(--rule); background:var(--panel2); color:var(--ink); cursor:pointer; transition:background .12s,border-color .12s; }
button:hover { border-color:var(--accent); }
button.active { background:var(--accent); color:#06201d; border-color:var(--accent); font-weight:600; }
button.emg { border-color:var(--p5); color:#f0a6b0; }
button.emg.on { background:var(--p5); color:#fff; }
.tabs { display:flex; gap:.35rem; flex-wrap:wrap; }
.spacer { flex:1; }

.diff { display:none; background:var(--accent-dim); border:1px solid var(--accent); border-radius:8px; padding:.7rem 1rem; margin-bottom:1rem; font-size:.85rem; }
.diff.show { display:block; }

.legend { display:flex; gap:1rem; flex-wrap:wrap; font-size:.75rem; color:var(--ink-soft); margin:.6rem 0 1.2rem; }
.legend span { display:inline-flex; align-items:center; gap:.35rem; }
.sw { width:12px; height:12px; border-radius:3px; display:inline-block; }

.gantt { background:var(--panel); border:1px solid var(--rule); border-radius:10px; padding:1rem; overflow-x:auto; }
.lane { display:grid; grid-template-columns:180px 1fr; gap:.5rem; align-items:center; margin-bottom:.4rem; min-width:640px; }
.lane-label { font-size:.8rem; color:var(--ink-soft); }
.lane-label .traffic { font-size:.68rem; color:var(--ink-faint); }
.track { position:relative; height:34px; background:var(--panel2); border-radius:5px; overflow:hidden; }
.track.nowindow { background:repeating-linear-gradient(45deg,#151b21,#151b21 6px,#11161b 6px,#11161b 12px); }
.track .window { position:absolute; top:0; bottom:0; background:#131a20; border-left:1px dashed var(--rule); border-right:1px dashed var(--rule); }
.block { position:absolute; top:3px; bottom:3px; border-radius:4px; padding:0 .4rem; font-size:.7rem; color:#fff; display:flex; align-items:center; overflow:hidden; white-space:nowrap; cursor:default; box-shadow:0 1px 3px rgba(0,0,0,.4); }
.block.p3 { background:var(--p3); } .block.p4 { background:var(--p4); } .block.p5 { background:var(--p5); }
.block.newly { outline:2px solid var(--new); outline-offset:-2px; }
.block.bumped { opacity:.28; text-decoration:line-through; }
.axis { display:grid; grid-template-columns:180px 1fr; gap:.5rem; margin-top:.3rem; min-width:640px; }
.axis .ticks { position:relative; height:16px; font-size:.62rem; color:var(--ink-faint); }
.axis .ticks span { position:absolute; transform:translateX(-50%); }

.panels { display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-top:1.4rem; }
@media (max-width:820px){ .panels{ grid-template-columns:1fr; } }
.card { background:var(--panel); border:1px solid var(--rule); border-radius:10px; padding:1.1rem 1.2rem; }
.card h2 { margin:0 0 .8rem; font-size:.8rem; text-transform:uppercase; letter-spacing:.1em; color:var(--ink-faint); }
.row { border-bottom:1px solid var(--rule); padding:.6rem 0; font-size:.85rem; }
.row:last-child { border-bottom:none; }
.row .id { font-family:var(--mono); color:var(--accent); font-size:.78rem; }
.row .why { color:var(--ink-soft); font-size:.8rem; margin-top:.15rem; }
.tag { font-family:var(--mono); font-size:.64rem; padding:.1rem .35rem; border-radius:3px; background:var(--panel2); color:var(--ink-soft); margin-left:.3rem; }
.tag.crew { color:#f0a6b0; } .tag.equipment { color:#c98a2b; } .tag.window { color:#9aa8b4; }
.prov { font-size:.75rem; color:var(--accent); margin-top:.4rem; }
.empty { color:var(--ink-faint); font-size:.82rem; font-style:italic; }
footer { margin-top:2rem; color:var(--ink-faint); font-size:.75rem; }

.tt { position:fixed; pointer-events:none; background:#000; border:1px solid var(--rule); border-radius:6px; padding:.5rem .65rem; font-size:.75rem; max-width:240px; opacity:0; transition:opacity .1s; z-index:50; }
.tt .tt-id { font-family:var(--mono); color:var(--accent); }
.tt dl { margin:.3rem 0 0; display:grid; grid-template-columns:auto 1fr; gap:.1rem .5rem; }
.tt dt { color:var(--ink-faint); } .tt dd { margin:0; }

.livepanel { display:none; background:var(--panel); border:1px solid var(--p5); border-radius:10px; padding:1.1rem 1.2rem; margin:0 0 1.2rem; }
.livepanel.show { display:block; }
.live-title { font-size:.78rem; text-transform:uppercase; letter-spacing:.1em; color:#f0a6b0; margin-bottom:.9rem; }
.live-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:.7rem; }
.live-grid label { display:flex; flex-direction:column; gap:.25rem; font-size:.72rem; color:var(--ink-faint); text-transform:uppercase; letter-spacing:.05em; }
.live-grid select, .live-grid input { font-family:var(--sans); font-size:.85rem; padding:.4rem .5rem; border-radius:6px; border:1px solid var(--rule); background:var(--panel2); color:var(--ink); }
.live-actions { display:flex; align-items:center; gap:.8rem; margin-top:1rem; }
button.solve { border-color:var(--p5); background:var(--p5); color:#fff; font-weight:600; }
button.solve:disabled { opacity:.5; cursor:wait; }
#solveMsg { font-size:.8rem; color:var(--accent); }
.applybtn { font-family:var(--sans); font-size:.68rem; font-weight:600; padding:.18rem .55rem; margin-left:.4rem; border-radius:5px; border:1px solid var(--accent); background:transparent; color:var(--accent); cursor:pointer; vertical-align:middle; }
.applybtn:hover { background:var(--accent); color:#06201d; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Track Service</h1>
    <p class="sub">Detects conflicts across engineering windows, optimises the block plan for priority, proves why unscheduled work didn't fit, and proposes alternatives. CP-SAT vs a real first-come-first-served baseline.</p>
  </header>

  <div class="kpis" id="kpis"></div>

  <div class="diff" id="diff"></div>

  <div class="controls">
    <div class="tabs" id="nightTabs"></div>
    <div class="spacer"></div>
    <button id="viewOpt" class="active">Optimised (CP-SAT)</button>
    <button id="viewGreedy">Before (greedy FCFS)</button>
    <button id="emgBtn" class="emg">⚠ Inject emergency</button>
    <button id="liveBtn" class="emg" style="display:none">✦ Custom emergency (live)</button>
  </div>

  <div class="livepanel" id="livepanel">
    <div class="live-title">Author an emergency — the solver places it live</div>
    <div class="live-grid">
      <label>Section<select id="f-section"></select></label>
      <label>Night<select id="f-night"></select></label>
      <label>Duration (h)<input id="f-dur" type="number" min="1" max="6" step="0.5" value="2.5"></label>
      <label>Crew<select id="f-crew">
        <option value="p-way">p-way</option><option value="signalling">signalling</option>
        <option value="ohe">ohe</option><option value="bridge">bridge</option></select></label>
      <label>Crew size<input id="f-crewsize" type="number" min="1" max="4" value="2"></label>
      <label>Equipment<select id="f-equip">
        <option value="none">none</option><option value="road-railer">road-railer</option>
        <option value="tamping-machine">tamping-machine</option><option value="ballast-cleaner">ballast-cleaner</option>
        <option value="rail-grinder">rail-grinder</option><option value="tower-wagon">tower-wagon</option></select></label>
    </div>
    <div class="live-actions">
      <button id="solveBtn" class="solve">Solve it →</button>
      <span id="solveMsg"></span>
    </div>
  </div>

  <div class="legend">
    <span><i class="sw" style="background:var(--p5)"></i> Urgent (wt 5)</span>
    <span><i class="sw" style="background:var(--p4)"></i> Important (wt 4)</span>
    <span><i class="sw" style="background:var(--p3)"></i> Routine (wt 3)</span>
    <span><i class="sw" style="background:var(--new)"></i> Newly placed</span>
    <span><i class="sw" style="background:var(--panel2)"></i> Available block</span>
  </div>

  <div class="gantt" id="gantt"></div>

  <div class="panels">
    <div class="card">
      <h2>Conflict report — why work didn't fit</h2>
      <div id="conflicts"></div>
      <p class="prov">Each reason is verified by relaxing that one resource and re-solving — shown, not guessed.</p>
    </div>
    <div class="card">
      <h2>Proposed alternatives</h2>
      <div id="alternatives"></div>
    </div>
  </div>

  <footer id="foot"></footer>
</div>

<div class="tt" id="tooltip"></div>

<script id="data" type="application/json">__DATA__</script>
<script>
const BASE = JSON.parse(document.getElementById('data').textContent);  // pristine plan, never mutated
let DATA = BASE;
const LIVE = __LIVE__;
let state = { view:'opt', night:0, emergency:false };

const TICK_MIN = 30, DAY_START = 22*60;
const clock = t => { const m=DAY_START+t*30; return String(Math.floor(m/60)%24).padStart(2,'0')+':'+String(m%60).padStart(2,'0'); };

function activeScenario(){ return state.emergency ? DATA.emergency.scenario : DATA.scenario; }
function activeSchedule(){
  if (state.emergency) return DATA.emergency.schedule;
  return state.view==='opt' ? DATA.optimal : DATA.greedy;
}
function maxTick(){ return Math.max(...DATA.scenario.windows.map(w=>w.end), 12); }

function reqMap(sc){ const m={}; sc.requests.forEach(r=>m[r.id]=r); return m; }

function renderKpis(){
  const om=DATA.metrics.optimal, gm=DATA.metrics.greedy;
  const wtGap=om.priority_weight-gm.priority_weight, schGap=om.scheduled-gm.scheduled;
  document.getElementById('kpis').innerHTML = `
    <div class="kpi"><div class="n">${om.scheduled}/${om.total_requests}</div><div class="l">Scheduled (CP-SAT)</div><div class="d">greedy: ${gm.scheduled}</div></div>
    <div class="kpi"><div class="n">${om.priority_weight}</div><div class="l">Priority weight</div><div class="d">+${wtGap} vs greedy</div></div>
    <div class="kpi"><div class="n">${om.window_utilisation_pct}%</div><div class="l">Window utilisation</div><div class="d">greedy: ${gm.window_utilisation_pct}%</div></div>
    <div class="kpi"><div class="n">${om.solve_seconds}s</div><div class="l">Solve time</div><div class="d">${om.proven_optimal?'OPTIMAL — proven':om.status}</div></div>`;
}

function renderTabs(){
  const el=document.getElementById('nightTabs'); el.innerHTML='';
  for(let n=0;n<DATA.scenario.nights;n++){
    const b=document.createElement('button');
    b.textContent='Night '+(n+1);
    if(n===state.night) b.classList.add('active');
    b.onclick=()=>{ state.night=n; render(); };
    el.appendChild(b);
  }
}

function renderGantt(){
  const sc=activeScenario(), sch=activeSchedule(), rm=reqMap(sc), n=state.night;
  const mx=maxTick(), g=document.getElementById('gantt');
  const bumped = state.emergency ? new Set(DATA.emergency.bumped) : new Set();
  const baseIds = new Set(DATA.optimal.assignments.map(a=>a.id));
  g.innerHTML='';

  sc.sections.forEach(section=>{
    const win = sc.windows.find(w=>w.section===section.id && w.night===n);
    const lane=document.createElement('div'); lane.className='lane';
    lane.innerHTML=`<div class="lane-label">${section.name}<div class="traffic">${section.id} · ${section.traffic} trains/night</div></div>`;
    const track=document.createElement('div'); track.className='track'+(win?'':' nowindow');
    if(win){
      const w=document.createElement('div'); w.className='window';
      w.style.left=(100*win.start/mx)+'%'; w.style.width=(100*(win.end-win.start)/mx)+'%';
      track.appendChild(w);
    }
    sch.assignments.filter(a=>rm[a.id] && rm[a.id].section===section.id && a.night===n).forEach(a=>{
      const r=rm[a.id];
      const b=document.createElement('div');
      b.className='block p'+r.priority + (state.emergency && !baseIds.has(a.id)?' newly':'');
      b.style.left=(100*a.start/mx)+'%'; b.style.width=(100*(a.end-a.start)/mx)+'%';
      b.textContent=r.id+' '+r.title;
      attachTip(b,r,a);
      track.appendChild(b);
    });
    lane.appendChild(track); g.appendChild(lane);
  });

  // time axis
  const axis=document.createElement('div'); axis.className='axis';
  let ticks='<div></div><div class="ticks">';
  for(let t=0;t<=mx;t+=2) ticks+=`<span style="left:${100*t/mx}%">${clock(t)}</span>`;
  ticks+='</div>'; axis.innerHTML=ticks; g.appendChild(axis);
}

function attachTip(el,r,a){
  el.addEventListener('mousemove',e=>{
    const tt=document.getElementById('tooltip');
    tt.innerHTML=`<div class="tt-id">${r.id}</div>${r.title}
      <dl><dt>section</dt><dd>${r.section}</dd>
      <dt>time</dt><dd>${a.start_clock}–${a.end_clock}</dd>
      <dt>crew</dt><dd>${r.crew} ×${r.crew_size}</dd>
      <dt>equip</dt><dd>${r.equipment}</dd>
      <dt>priority</dt><dd>${r.priority}</dd></dl>`;
    tt.style.opacity=1; tt.style.left=Math.min(e.clientX+14,innerWidth-250)+'px'; tt.style.top=(e.clientY+14)+'px';
  });
  el.addEventListener('mouseleave',()=>document.getElementById('tooltip').style.opacity=0);
}

function renderConflicts(){
  const el=document.getElementById('conflicts');
  const rm=reqMap(DATA.scenario);
  const exps=DATA.explanations;
  if(!exps.length){ el.innerHTML='<p class="empty">Every request was scheduled — no conflicts.</p>'; return; }
  el.innerHTML=exps.map(e=>{
    const r=rm[e.request_id]||{title:'',priority:''};
    const tags=e.binding.map(b=>`<span class="tag ${b}">${b}</span>`).join('');
    return `<div class="row"><span class="id">${e.request_id}</span> ${r.title} ${tags}
      <div class="why">${e.detail}</div></div>`;
  }).join('');
}

function renderAlternatives(){
  const el=document.getElementById('alternatives');
  const alts=DATA.alternatives.filter(a=>a);
  if(!alts.length){ el.innerHTML='<p class="empty">Nothing to propose — all work placed.</p>'; return; }
  el.innerHTML=alts.map(a=>{
    const applyBtn = (LIVE && a.feasible)
      ? `<button class="applybtn" onclick="applyAlt('${a.request_id}')">Apply →</button>` : '';
    return `<div class="row"><span class="id">${a.request_id}</span>
      ${a.feasible?`<span class="tag">${a.weight_cost<=0?'no net loss':'−'+a.weight_cost+' wt'}</span>`:'<span class="tag crew">infeasible</span>'}
      ${applyBtn}
      <div class="why">${a.note}</div></div>`;
  }).join('');
}

let pinned=[];   // cumulative jobs the planner has applied
async function applyAlt(id){
  const el=document.getElementById('alternatives');
  el.style.opacity=.5;
  const candidate=[...pinned, id];
  try{
    const res=await fetch('/api/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ids:candidate})});
    if(!res.ok) throw new Error('HTTP '+res.status);
    const rep=await res.json(), e=rep.emergency;
    // A pin is sticky: only commit if EVERY pinned job is honoured together.
    const allHonoured = candidate.every(x=>e.pinned_scheduled.includes(x));
    if(!allHonoured){
      alert('Cannot pin '+id+' on top of the current pins — no single plan fits them all. Keeping the previous plan.');
      return;                       // keep the old plan untouched
    }
    DATA=rep; pinned=candidate.slice();
    state.emergency=true; state.view='opt';
    state.night=e.request.night;
    render();
  }catch(e){ alert('Apply failed: '+e.message); }
  finally{ el.style.opacity=1; }
}

function renderDiff(){
  const d=document.getElementById('diff');
  if(!state.emergency){ d.classList.remove('show'); return; }
  const e=DATA.emergency;
  d.classList.add('show');
  const applied = e.kind==='applied';
  let lead;
  if(applied){
    const n=(e.pinned_scheduled||[]).length;
    const pinNote = n>1 ? ` — ${n} jobs now pinned` : '';
    lead = `<strong>✓ Applied ${e.request.id} ${e.request.title}</strong> on ${e.request.section}, night ${e.request.night+1}${pinNote}.`;
  } else {
    lead = `<strong>⚠ ${e.request.title}</strong> injected on ${e.request.section}, night ${e.request.night+1}.`;
  }
  d.innerHTML=`${lead}
    Re-solved in ${e.schedule.solve_seconds}s — bumped <strong>${e.bumped.join(', ')||'nothing'}</strong>.
    Priority weight ${e.weight_before} → ${e.weight_after}.`;
}

function render(){
  renderKpis(); renderTabs(); renderGantt(); renderConflicts(); renderAlternatives(); renderDiff();
  document.getElementById('viewOpt').classList.toggle('active', state.view==='opt' && !state.emergency);
  document.getElementById('viewGreedy').classList.toggle('active', state.view==='greedy' && !state.emergency);
  document.getElementById('emgBtn').classList.toggle('on', state.emergency);
  const om=DATA.metrics.optimal;
  document.getElementById('foot').textContent=
    `Seed ${DATA.scenario.seed} · ${DATA.scenario.requests.length} requests · ${DATA.scenario.nights} nights · `+
    `CP-SAT ${om.proven_optimal?'proved OPTIMAL':om.status} in ${om.solve_seconds}s. Regenerate: trackservice run --seed N`;
}

// Returning to a base view restores the pristine plan in full — Gantt, conflicts,
// AND the alternatives list — and clears every pin.
document.getElementById('viewOpt').onclick=()=>{ DATA=BASE; pinned=[]; state.view='opt'; state.emergency=false; render(); };
document.getElementById('viewGreedy').onclick=()=>{ DATA=BASE; pinned=[]; state.view='greedy'; state.emergency=false; render(); };
document.getElementById('emgBtn').onclick=()=>{
  if(!state.emergency){ DATA=BASE; pinned=[]; state.emergency=true; state.view='opt'; }  // always the scripted emergency, from a clean plan
  else { state.emergency=false; }
  render();
};

// --- live mode: author an emergency and let the server solve it -------------
function setupLive(){
  document.getElementById('liveBtn').style.display='';
  const sec=document.getElementById('f-section'), nt=document.getElementById('f-night');
  DATA.scenario.sections.forEach(s=>{ const o=document.createElement('option'); o.value=s.id; o.textContent=s.id+' — '+s.name; sec.appendChild(o); });
  sec.value='SEC-H';
  for(let n=0;n<DATA.scenario.nights;n++){ const o=document.createElement('option'); o.value=n; o.textContent='Night '+(n+1); nt.appendChild(o); }

  document.getElementById('liveBtn').onclick=()=>{
    document.getElementById('livepanel').classList.toggle('show');
  };

  document.getElementById('solveBtn').onclick=async()=>{
    const btn=document.getElementById('solveBtn'), msg=document.getElementById('solveMsg');
    btn.disabled=true; msg.textContent='Solving…';
    const body={
      section:document.getElementById('f-section').value,
      night:parseInt(document.getElementById('f-night').value,10),
      duration_h:parseFloat(document.getElementById('f-dur').value),
      crew:document.getElementById('f-crew').value,
      crew_size:parseInt(document.getElementById('f-crewsize').value,10),
      equipment:document.getElementById('f-equip').value,
      priority:5, title:'EMERGENCY (live)'
    };
    try{
      const t0=performance.now();
      const res=await fetch('/api/solve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      if(!res.ok) throw new Error('HTTP '+res.status);
      DATA=await res.json();
      state.emergency=true; state.view='opt';
      state.night=DATA.emergency.request.night;
      render();
      msg.textContent=`Solved live in ${DATA.emergency.schedule.solve_seconds}s (round-trip ${((performance.now()-t0)/1000).toFixed(2)}s).`;
    }catch(e){ msg.textContent='Solve failed: '+e.message; }
    finally{ btn.disabled=false; }
  };
}

if(LIVE) setupLive();
render();
</script>
</body>
</html>
"""


def build_html(report: dict, live: bool = False) -> str:
    return (
        _TEMPLATE
        .replace("__DATA__", json.dumps(report))
        .replace("__LIVE__", "true" if live else "false")
    )


def render_dashboard(report: dict, path: str) -> None:
    """Write the static (baked-in) dashboard — no live solving."""
    with open(path, "w") as f:
        f.write(build_html(report, live=False))
