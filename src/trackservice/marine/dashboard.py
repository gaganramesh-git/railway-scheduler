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
@media(max-width:820px){.kpis{grid-template-columns:repeat(2,1fr);}.cmp{grid-template-columns:1fr;}}
</style>
<div class="wrap">
  <p class="eyebrow">SIH26006 · Ministry of Steel</p>
  <h1>Charter Planner</h1>
  <p class="sub" id="sub"></p>
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

  <div class="verline" id="ver"></div>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const m=D.metrics, S=D.scenario;
const money=x=>'$'+Math.round(x).toLocaleString();
document.getElementById('sub').textContent=D.problem+' — '+S.parcels.length+' cargo parcels, '+S.ports.length+' East-Coast ports, '+S.weeks+'-week horizon.';

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

// ---- voyage table ----
const vt=D.plan.voyages;
document.getElementById('voyages').innerHTML=
 '<thead><tr><th>Voyage</th><th>Vessel</th><th>Lane</th><th>Depart→Arrive</th><th>Load</th><th>Utilisation</th><th>Parcels</th></tr></thead><tbody>'+
 vt.map(v=>`<tr>
   <td class="mono">${v.voyage_id}</td>
   <td><span class="vpill ${v.vessel_id}">${v.vessel}</span></td>
   <td>${v.origin} → ${v.port}</td>
   <td class="mono">wk ${v.depart_week} → ${v.arrive_week}</td>
   <td class="mono">${v.load_t.toLocaleString()} / ${v.capacity_t.toLocaleString()} t</td>
   <td><div class="util"><i style="width:${v.utilisation_pct}%"></i></div></td>
   <td>${v.parcels.length} ${v.shared?'<span class="shared">consolidated</span>':''}</td></tr>`).join('')+'</tbody>';

// ---- ports ----
document.getElementById('ports').innerHTML=
 '<thead><tr><th>Port</th><th>Max draft</th><th>Handling</th><th>Largest vessel it can take</th></tr></thead><tbody>'+
 S.ports.map(p=>{
   const fit=S.vessels.filter(v=>v.draft_m<=p.max_draft_m).sort((a,b)=>b.dwt-a.dwt)[0];
   return `<tr><td><b>${p.name}</b></td><td class="mono">${p.max_draft_m} m</td><td class="mono">${p.handling_tpd.toLocaleString()} t/day</td><td><span class="vpill ${fit.id}">${fit.name}</span> and smaller</td></tr>`;
 }).join('')+'</tbody>';

const ver=D.verification;
document.getElementById('ver').innerHTML=`${S.parcels.length} parcels · CP-SAT ${D.plan.proven_optimal?'proved OPTIMAL':D.plan.status} in ${D.plan.solve_seconds}s · <span class="${ver.ok?'ok':''}">${ver.ok?'✓ independently verified ('+ver.checks_run+' checks)':'✗ FAILED VERIFICATION'}</span>`;
</script>
"""


def build_html(report: dict) -> str:
    return _TEMPLATE.replace("__DATA__", json.dumps(report))
