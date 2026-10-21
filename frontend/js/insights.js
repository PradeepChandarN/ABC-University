(function(){
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const inr=n=>'₹'+Number(n||0).toLocaleString('en-IN');
const col=p=>p>=75?'var(--green)':p>=55?'var(--gold)':'var(--red)';
const PAL=['#14213d','#c2410c','#1f6f5c','#b7791f','#2c4a7c'];
const grow=()=>requestAnimationFrame(()=>requestAnimationFrame(()=>{
  document.querySelectorAll('[data-w]').forEach(e=>e.style.width=e.dataset.w+'%');
  document.querySelectorAll('[data-h]').forEach(e=>e.style.height=e.dataset.h+'%');}));
const bar=(p,c)=>`<div class="track"><div class="fill" style="background:${c||col(p)}" data-w="${Math.max(0,Math.min(100,p||0))}"></div></div>`;

async function api(u){const r=await fetch(u);if(!r.ok)throw new Error((await r.json()).detail||r.statusText);return r.json();}

function donut(title,data){
  const t=data.reduce((a,d)=>a+d.n,0)||1,R=42,C=2*Math.PI*R;let off=0;
  const arcs=data.map((d,i)=>{const l=d.n/t*C,s=`<circle r="${R}" cx="60" cy="60" fill="none" stroke="${PAL[i%5]}" stroke-width="18" stroke-dasharray="${l} ${C-l}" stroke-dashoffset="${-off}"/>`;off+=l;return s}).join('');
  return `<div class="donut"><svg viewBox="0 0 120 120">${arcs}</svg>${title}<div class="legend">${data.map((d,i)=>`<span><i style="background:${PAL[i%5]}"></i>${esc(d.label)} ${d.n}</span>`).join('')}</div></div>`;
}

function headlines(d){
  const L=[],k=d.kpis,top=d.leaderboard[0],low=d.attendance[0];
  const cs=d.courses.filter(c=>c.avg_score!=null),bestC=cs[0],worstC=cs[cs.length-1];
  const dd=d.departments.filter(x=>x.avg_score!=null).sort((a,b)=>b.avg_score-a.avg_score);
  const weakPass=[...d.courses].filter(c=>c.pass_rate!=null).sort((a,b)=>a.pass_rate-b.pass_rate)[0];
  const lowAtt=d.attendance.filter(a=>a.pct<75).length;
  if(top)L.push(`<strong>${esc(top.name)}</strong> leads the university with a normalised score of <strong>${top.score}%</strong> (${esc(top.dept)}, year ${top.year}).`);
  if(dd.length>1)L.push(`<strong>${esc(dd[0].name)}</strong> has the strongest department average at <strong>${dd[0].avg_score}%</strong>; ${esc(dd[dd.length-1].name)} trails at ${dd[dd.length-1].avg_score}%.`);
  if(bestC&&worstC)L.push(`<strong>${esc(bestC.name)}</strong> is the highest-scoring course (${bestC.avg_score}%), while <strong>${esc(worstC.name)}</strong> is the toughest at ${worstC.avg_score}%.`);
  if(weakPass&&weakPass.pass_rate<100)L.push(`<span class="bad"><strong>${esc(weakPass.name)}</strong> has the lowest pass rate: only <strong>${weakPass.pass_rate}%</strong> of assessments passed.</span>`);
  if(low)L.push(`<span class="bad"><strong>${lowAtt}</strong> of ${d.attendance.length} course attendance records fall below 75%. The lowest is <strong>${esc(low.name)}</strong> in ${esc(low.course)} at ${low.pct}%.</span>`);
  if(d.at_risk.length)L.push(`<span class="bad"><strong>${d.at_risk.length}</strong> students are on the watchlist for low scores, failed assessments or poor attendance.</span>`);
  L.push(`Active scholarships distribute <strong>${inr(k.scholarship_active)}</strong>; <strong>${k.hostel_residents}</strong> of ${k.students} students live in hostel.`);
  $('headlines').innerHTML=L.map((t,i)=>`<li${t.startsWith('<span class="bad">')?' class="bad"':''}><i>${String(i+1).padStart(2,'0')}</i><span>${t}</span></li>`).join('');
}

function render(d){
  const k=d.kpis;
  $('kpis').innerHTML=[[k.students,'Students'],[k.faculty,'Faculty'],[k.courses,'Courses'],[k.avg_score+'<sub>%</sub>','Avg score'],[k.pass_rate+'<sub>%</sub>','Pass rate'],[k.avg_attendance+'<sub>%</sub>','Avg attendance'],[inr(k.scholarship_active),'Active aid'],[k.hostel_residents,'In hostel']]
    .map(([v,l])=>`<div class="kpi"><b>${v}</b><span>${l}</span></div>`).join('');
  headlines(d);
  $('depts').innerHTML=d.departments.map(x=>`<div class="card"><h4>${esc(x.name)}</h4><p class="hod">HOD · ${esc(x.hod||'—')}</p>
    <div class="stats"><div><b>${x.students}</b><span>students</span></div><div><b>${x.faculty}</b><span>faculty</span></div><div><b>${x.courses}</b><span>courses</span></div></div>
    ${bar(x.avg_score,'var(--ink)')}<small style="font:12px 'JetBrains Mono';color:var(--mute)">avg score ${x.avg_score??'—'}%</small></div>`).join('');
  $('courseBars').innerHTML=d.courses.map(c=>`<div class="row"><div class="lbl"><b>${esc(c.name)}</b><small>${esc(c.faculty||'Unassigned')} · ${c.enrolled} enrolled</small></div>
    <div class="track" style="height:14px"><div class="fill" style="background:var(--ink)" data-w="${c.avg_score||0}"></div>${c.pass_rate!=null?`<span class="mk" style="left:${c.pass_rate}%" title="Pass rate ${c.pass_rate}%"></span>`:''}</div><div class="val">${c.avg_score??'—'}%</div></div>`).join('')
    +`<p style="margin-top:8px;font:12px 'JetBrains Mono';color:var(--mute)"><span style="color:var(--red)">▍</span> red marker = pass rate of that course</p>`;
  const mx=Math.max(...d.grade_bands.map(b=>b.n),1);
  $('bands').innerHTML=d.grade_bands.map(b=>`<div class="col"><div data-h="${b.n/mx*80}"><b>${b.n}</b></div><span>${esc(b.band.replace('  ','\n'))}</span></div>`).join('');
  $('types').innerHTML=d.by_type.map(t=>`<div class="mini"><span>${esc(t.type)}</span>${bar(t.avg_score)}<span class="val">${t.avg_score}</span></div>`).join('');
  $('mix').innerHTML=donut('Gender',d.mix.gender)+donut('Level',d.mix.level)+donut('Year',d.mix.year)+donut('Faculty',d.mix.faculty_type);
  $('att').innerHTML=d.attendance.map(a=>`<div class="att${a.pct<75?' low':''}" onclick="document.dispatchEvent(new CustomEvent('open',{detail:${a.id}}))"><b>${a.pct}%</b><div>${esc(a.name)}</div><small>${esc(a.course)}</small></div>`).join('');
  $('top').innerHTML=d.leaderboard.slice(0,5).map(s=>`<li data-id="${s.id}"><span><b>${esc(s.name)}</b><small>${esc(s.dept)} · year ${s.year}</small></span><b class="s">${s.score}</b></li>`).join('');
  $('wl').textContent=d.at_risk.length+' flagged';
  $('risk').innerHTML=d.at_risk.map(s=>`<div class="risk" data-id="${s.id}"><div><b class="n">${esc(s.name)}</b><div class="chips">${s.score<50?'<span class="chip">low score</span>':''}${s.attendance<75?'<span class="chip">attendance '+s.attendance+'%</span>':''}${s.fails>0?`<span class="chip">${s.fails} fail${s.fails>1?'s':''}</span>`:''}</div></div><b style="font:700 20px Fraunces">${s.score??'—'}</b></div>`).join('')||'<p>No students flagged.</p>';
  $('schol').innerHTML=`<div class="big">${inr(d.scholarships.reduce((a,s)=>a+s.amount,0))}</div>`+d.scholarships.map(s=>`<div class="item"><span class="chip ${s.status==='Active'?'ok':s.status==='Pending'?'gold':''}">${esc(s.status)}</span> ${s.n} awards · ${inr(s.amount)}</div>`).join('');
  $('intern').innerHTML=d.internships.map(i=>`<div class="item"><b>${esc(i.company)}</b><small>${esc(i.name)} · ${i.weeks} weeks</small></div>`).join('');
  $('res').innerHTML=d.research.map(r=>`<div class="item"><b>${esc(r.title)}</b><small>${esc(r.student)} guided by ${esc(r.guide)} · <span class="chip ${r.status==='Completed'?'ok':'gold'}">${esc(r.status)}</span></small></div>`).join('');
  const mc=Math.max(...d.workload.map(w=>w.credits),1);
  $('load').innerHTML=d.workload.map(w=>`<div class="row"><div class="lbl"><b>${esc(w.name)}</b><small>${esc(w.designation||'')}</small></div>${bar(w.credits/mc*100,'var(--blue)')}<div class="val">${w.credits} cr</div></div>`).join('');
  $('names').innerHTML=d.leaderboard.map(s=>`<option value="${s.id} · ${esc(s.name)}">`).join('');
  grow();
}

async function openStudent(id){
  const box=$('profile');box.className='profile';box.innerHTML='Loading…';
  try{
    const p=await api('/api/insights/student/'+id),s=p.profile;
    const avg=p.results.length?(p.results.reduce((a,r)=>a+r.pct,0)/p.results.length).toFixed(1):'—';
    box.innerHTML=`<div class="phead"><div><h3>${esc(s.student_name)}</h3><p>#${s.student_id} · ${esc(s.program_name)} (${esc(s.program_level)}) · ${esc(s.dept_name)} · Year ${s.year_of_study}<br>${esc(s.email||'')} · ${esc(s.contact_number||'')}</p></div><div class="sc"><b>${avg}${avg!=='—'?'%':''}</b><span>normalised score</span></div></div>
    <div class="pgrid"><div class="panel"><h3>Marks</h3>${p.results.map(r=>`<div class="mini" style="grid-template-columns:1fr 90px 60px"><span>${esc(r.course)}<small style="display:block;color:var(--mute)">${esc(r.type)}</small></span>${bar(r.pct)}<span class="val">${r.marks}/${r.max}</span></div>`).join('')||'No results'}</div>
    <div class="panel"><h3>Attendance</h3>${p.attendance.map(a=>`<div class="mini" style="grid-template-columns:1fr 90px 50px"><span>${esc(a.course)}</span>${bar(a.pct)}<span class="val">${a.pct}%</span></div>`).join('')||'No records'}
    <h3 style="margin-top:20px">Enrolled in</h3>${p.courses.map(c=>`<span class="chip gold" style="margin:0 4px 4px 0;display:inline-block">${esc(c.name)} · S${c.semester}</span>`).join('')||'—'}</div>
    <div class="panel"><h3>Support &amp; career</h3>
    ${p.scholarships.map(x=>`<div class="item"><b>${esc(x.name)}</b> <span class="chip ${x.status==='Active'?'ok':'gold'}">${esc(x.status)}</span><small>${inr(x.amount)} · ${esc(x.criteria||'')}</small></div>`).join('')}
    ${p.hostel.map(h=>`<div class="item"><b>${esc(h.name)}</b><small>Room ${esc(h.room)}</small></div>`).join('')}
    ${p.internships.map(i=>`<div class="item"><b>Internship · ${esc(i.company)}</b><small>${i.weeks} weeks · ${esc(i.start||'')} → ${esc(i.end||'')}</small></div>`).join('')}
    ${p.research.map(r=>`<div class="item"><b>${esc(r.title)}</b><small>${esc(r.status)} · ${esc(r.guide)}</small></div>`).join('')}
    ${(p.scholarships.length+p.hostel.length+p.internships.length+p.research.length)?'':'<p style="color:var(--mute)">No scholarship, hostel, internship or research records.</p>'}</div></div>`;
    grow();box.scrollIntoView({behavior:'smooth',block:'nearest'});
  }catch(e){box.className='profile empty';box.textContent='Could not load student: '+e.message;}
}
const jump=id=>{openStudent(id);$('student360').scrollIntoView({behavior:'smooth'})};
document.addEventListener('open',e=>jump(e.detail));
document.addEventListener('click',e=>{const r=e.target.closest('[data-id]');if(r)jump(r.dataset.id)});
$('q').addEventListener('change',e=>{const m=e.target.value.match(/^\d+/);if(m)openStudent(m[0])});
$('today').textContent=new Date().toLocaleDateString('en-IN',{weekday:'long',day:'numeric',month:'long',year:'numeric'});
api('/api/insights').then(render).catch(e=>{$('headlines').innerHTML='<li><i>!</i><span>Could not load insights: '+esc(e.message)+'</span></li>'});
})();
