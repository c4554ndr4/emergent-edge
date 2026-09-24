const DATA_PATH = "./data/case_graph_data.json";
const DEMO_PATH = "./data/pipeline_demo_data.json";
const PIPELINE_PAGE = "pipeline.html";
const EXPANDED = false;
const els = {svg: document.getElementById("caseSvg"), detail: document.getElementById("detailPanel"), mapGuide: document.getElementById("mapGuide"), legend: document.getElementById("patternLegend"), colorBy: document.getElementById("colorBy"), showPatterns: document.getElementById("showPatterns"), resetZoom: document.getElementById("resetZoomBtn")};
const state = {data:null, display:{}, demoIds:new Set(), selected:null, pattern:null, hovered:null, labels:[], zoom:{scale:1,tx:0,ty:0}};
const LIABILITY_COLORS = {
  duty_of_care: "#f59e0b",
  product_safety: "#ef4444",
  regulatory: "#8b5cf6",
  brand_trust: "#38bdf8",
  privacy: "#14b8a6",
  fraud_enablement: "#fb7185",
  ip: "#a78bfa",
  default: "#94a3b8",
};

function humanize(v) {
  return String(v || "").replaceAll("_", " ").replace(/\s+/g, " ").trim();
}

function short(v, n = 24) {
  const t = String(v || "");
  return t.length > n ? `${t.slice(0, n - 1)}…` : t;
}

function make(tag, attrs = {}) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, String(v));
  return el;
}

function colorForPatternId(key) {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  return `hsl(${h % 360} 68% 58%)`;
}

function colorForCase(c) {
  if (els.colorBy.value === "liability") {
    return LIABILITY_COLORS[c.major_liability] || LIABILITY_COLORS.default;
  }
  const key = c.predicted_pattern_id || "none";
  return colorForPatternId(key);
}

function colorForPattern(patternId) {
  if (els.colorBy.value === "liability") {
    const first = state.data.cases.find((c) => c.predicted_pattern_id === patternId);
    return first ? colorForCase(first) : LIABILITY_COLORS.default;
  }
  return colorForPatternId(patternId);
}

function starPoints(cx, cy, outerR = 8.8, innerR = 4.4) {
  const pts = [];
  for (let i = 0; i < 10; i++) {
    const angle = -Math.PI / 2 + (i * Math.PI) / 5;
    const r = i % 2 === 0 ? outerR : innerR;
    pts.push(`${cx + Math.cos(angle) * r},${cy + Math.sin(angle) * r}`);
  }
  return pts.join(" ");
}

function patternAnchor(patternId) {
  const key = patternId || "none";
  let h = 2166136261;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  const u = ((h >>> 0) % 1000000) / 1000000;
  const v = (((h >>> 1) >>> 0) % 1000000) / 1000000;
  const angle = u * Math.PI * 2;
  const radius = 0.45 + v * 0.4; // [0.45, 0.85]
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
}

function hybridPos(c) {
  const rawX = Number(c.x || 0);
  const rawY = Number(c.y || 0);
  const a = patternAnchor(c.predicted_pattern_id);
  const w = 0; // Raw embedding only.
  return {
    x: (1 - w) * rawX + w * a.x,
    y: (1 - w) * rawY + w * a.y,
  };
}

function applyTransform(view) {
  view.setAttribute("transform", `translate(${state.zoom.tx} ${state.zoom.ty}) scale(${state.zoom.scale})`);
}

function svgPoint(evt) {
  const pt = els.svg.createSVGPoint();
  pt.x = evt.clientX;
  pt.y = evt.clientY;
  const ctm = els.svg.getScreenCTM();
  if (!ctm) return { x: 0, y: 0 };
  const p = pt.matrixTransform(ctm.inverse());
  return { x: p.x, y: p.y };
}

function wireZoom(view) {
  applyTransform(view);
    updateLabels();
  els.svg.onwheel = (evt) => {
    evt.preventDefault();
    const a = svgPoint(evt);
    const f = evt.deltaY < 0 ? 1.1 : 0.9;
    const ns = Math.max(0.6, Math.min(8, state.zoom.scale * f));
    const r = ns / state.zoom.scale;
    state.zoom.tx = a.x - (a.x - state.zoom.tx) * r;
    state.zoom.ty = a.y - (a.y - state.zoom.ty) * r;
    state.zoom.scale = ns;
    applyTransform(view);
    updateLabels();
  };
  let drag = false;
  let last = { x: 0, y: 0 };
  els.svg.onmousedown = (evt) => { drag = true; last = svgPoint(evt); };
  els.svg.onmousemove = (evt) => {
    if (!drag) return;
    const p = svgPoint(evt);
    state.zoom.tx += p.x - last.x;
    state.zoom.ty += p.y - last.y;
    last = p;
    applyTransform(view);
    updateLabels();
  };
  els.svg.onmouseup = () => { drag = false; };
  els.svg.onmouseleave = () => { drag = false; };
}


const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const prose = value => Array.isArray(value) ? value.join("; ") : value || "";
const caseTitle = c => state.display.cases?.[c.case_id]?.title || humanize(c.title || c.case_id);
const patternTitle = id => { const p = state.display.patterns?.[id] || {}; return p.display_title || p.title || state.data.patterns[id]?.display_title || humanize(state.data.patterns[id]?.label || id); };
function safeUrl(value) { try { const u = new URL(value); return ["http:","https:"].includes(u.protocol) ? u.href : ""; } catch { return ""; } }
function patternMarkup(id, compact=false) {
  const p = state.data.patterns[id] || {}, d = state.display.patterns?.[id] || {};
  const criteria = `<p><strong>Qualifies:</strong> ${esc(prose(d.qualifies || p.required_signals) || "No criteria recorded.")}</p><p><strong>Boundary:</strong> ${esc(prose(d.boundary || p.boundary_notes || p.insufficient_signals) || "No boundary recorded.")}</p>`;
  return `<h3>${esc(patternTitle(id))}</h3><p>${esc(d.summary || p.summary)}</p>${compact ? `<details><summary>Pattern criteria</summary>${criteria}</details>` : criteria}`;
}
function selectPattern(id) {
  state.pattern = state.pattern === id ? null : id;
  if (state.pattern) {
    els.detail.innerHTML = `<p class="detail-eyebrow">Pattern · ${state.data.cases.filter(c=>c.predicted_pattern_id===id).length} cases</p>${patternMarkup(id)}`;
  } else if(state.selected) renderDetail(state.selected);
  render();
}
function renderLegend() {
  if (!els.legend) return;
  const activePattern=document.activeElement?.dataset?.pattern;
  els.legend.replaceChildren();
  const count = document.createElement("p"); count.className="legend-count"; count.textContent=`${state.data.cases.length} cases · ${Object.keys(state.data.patterns).length} patterns`; els.legend.append(count);
  for(const id of Object.keys(state.data.patterns)) {
    const b=document.createElement("button"); b.type="button"; b.dataset.pattern=id; b.className="pattern-legend-button"; b.setAttribute("aria-pressed",String(state.pattern===id));
    const swatch=document.createElement("span"); swatch.className="pattern-swatch"; swatch.style.background=colorForPattern(id); swatch.setAttribute("aria-hidden","true");
    const label=document.createElement("span"); label.textContent=patternTitle(id);
    const n=document.createElement("span"); n.className="pattern-count"; n.textContent=String(state.data.cases.filter(c=>c.predicted_pattern_id===id).length);
    b.append(swatch,label,n); b.addEventListener("click",()=>selectPattern(id)); els.legend.append(b);
    if(activePattern===id)b.focus();
  }
}
function renderDetail(c) {
  const d=state.display.cases?.[c.case_id] || {}, id=c.predicted_pattern_id;
  els.detail.scrollTop = 0;
  if (document.getElementById("casePicker")) document.getElementById("casePicker").value = c.case_id;
  const quotes=[...new Set((c.evidence_spans || []).map(e=>e.quote).filter(Boolean))].slice(0,3);
  const url=safeUrl(c.source_url);
  const recorded={reviewed_mechanism:d.mechanism,reviewed_outcome:d.outcome,assignment_score:c.predicted_pattern_score, retrieval_hits:c.top_patterns, source_id:c.source_id, ai_written:{extent:c.llm_written_extent,verdict:c.llm_written_verdict,confidence:c.llm_written_confidence},core_dimensions:c.core_dimensions,impact_pathways:c.impact_pathways,provider_liability_assessment:c.provider_liability_assessment,decision_closest_pattern:c.decision_closest_pattern,decision_suspected_pattern:c.decision_suspected_pattern};
  if(!Object.values(recorded.ai_written).some(v=>v!=null))delete recorded.ai_written;
  els.detail.innerHTML=`<p class="detail-eyebrow">Case${d.source_type ? " · "+esc(d.source_type):""}</p><h2>${esc(caseTitle(c))}</h2>    <div class="detail-links">${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">Open source ↗</a>`:""}${state.demoIds.has(c.case_id) ? `<a href="${PIPELINE_PAGE}?case=${encodeURIComponent(c.case_id)}">View pipeline example →</a>`:""}</div><p>${esc(d.summary || c.summary)}</p>
    ${d.notes ? `<p class="small"><strong>Review note:</strong> ${esc(prose(d.notes))}</p>`:""}
    <h3>Evidence</h3>${quotes.length ? quotes.map(q=>`<blockquote>${esc(q)}</blockquote>`).join("") : '<p class="small">No extracted quotes available.</p>'}
    ${id ? `<section class="linked-pattern"><p class="detail-eyebrow">Linked pattern</p>${patternMarkup(id,true)}<button type="button" class="highlight-pattern">Highlight pattern</button></section>`:""}

    <details class="recorded-analysis"><summary>Recorded analysis</summary><p class="small">Historical model output; these labels and scores may differ from the edited case description.</p><pre>${esc(JSON.stringify(recorded,null,2))}</pre></details>`;
  els.detail.querySelector(".highlight-pattern")?.addEventListener("click",()=>selectPattern(id));
}
function interactive(node,title,key,action) {
  node.setAttribute("tabindex","0"); node.setAttribute("role","button"); node.setAttribute("aria-label",title); node.dataset.key=key;
  const tip=make("title"); tip.textContent=title; node.append(tip);
  node.addEventListener("click",action);
  node.addEventListener("keydown",e=>{if(e.key==="Enter" || e.key===" "){e.preventDefault(); action(); els.svg.querySelector(`[data-key="${CSS.escape(key)}"]`)?.focus();}});
  for(const event of ["mouseenter","focus"]) node.addEventListener(event,()=>{state.hovered=key; updateLabels();});
  for(const event of ["mouseleave","blur"]) node.addEventListener(event,()=>{state.hovered=null;updateLabels();});
}
function updateLabels() {
  const used=[];
  const sorted=[...state.labels].sort((a,b)=>Number(b.priority())-Number(a.priority()));
  for(const l of sorted) {
    const important=l.priority(), z=state.zoom.scale;
    const fit = Math.min(1, Math.max(0.3, els.svg.getBoundingClientRect().width / 980));
    const box={x:l.x,y:l.y-13/z,w:Math.min(l.text.length,34)*7/(z*fit),h:17/(z*fit)};
    const overlap=used.some(b=>box.x<b.x+b.w && box.x+box.w>b.x && box.y<b.y+b.h && box.y+box.h>b.y);
    const visible=important || (!l.dim && !overlap && (z>1.5 || used.length<(fit<0.6?4:13)));
    l.el.style.display=visible ? "" : "none";
    l.el.textContent=important ? l.text : short(l.text,34);
    l.el.style.fontSize=`${11/(z*fit)}px`;
    if(visible) used.push(box);
  }
}
function render() {
  const focusKey=document.activeElement?.dataset?.key;
  els.svg.replaceChildren(); state.labels=[];
  const w=980,h=560,pad=48,view=make("g"); els.svg.append(view);
  const xMap=v=>pad+((Number(v)+1)/2)*(w-pad*2), yMap=v=>h-pad-((Number(v)+1)/2)*(h-pad*2);
  const grid=make("g",{opacity:0.45});
  for(let i=0;i<=8;i++){ const x=pad+(w-pad*2)*i/8,y=pad+(h-pad*2)*i/8;grid.append(make("line",{x1:x,y1:pad,x2:x,y2:h-pad,stroke:"#2a3a50"}),make("line",{x1:pad,y1:y,x2:w-pad,y2:y,stroke:"#2a3a50"})); }view.append(grid);
  const groups=new Map();
  for(const c of state.data.cases){const id=c.predicted_pattern_id || "other";if(!groups.has(id))groups.set(id,[]);groups.get(id).push({x:xMap(c.x),y:yMap(c.y)});}
  for(const [id,pts] of groups){if(pts.length<2)continue;const cx=pts.reduce((a,p)=>a+p.x,0)/pts.length,cy=pts.reduce((a,p)=>a+p.y,0)/pts.length,r=Math.max(24,Math.sqrt(pts.reduce((a,p)=>a+(p.x-cx)**2+(p.y-cy)**2,0)/pts.length)*1.8);view.append(make("circle",{cx,cy,r,fill:"#5aa7ff20",stroke:"#5aa7ff66","stroke-width":1.2,opacity:state.pattern&&state.pattern!==id?0.2:1}));}
  const label=(x,y,text,key,priority,dim)=>{const el=make("text",{x,y,class:"node-label map-readable-label"});el.textContent=text;view.append(el);state.labels.push({el,x,y,text,key,priority,dim});};
  if(els.showPatterns.checked)for(const [id,p] of Object.entries(state.data.patterns)){
    const px=xMap(p.x||0),py=yMap(p.y||0),dim=!!state.pattern&&state.pattern!==id;
    if(state.pattern===id)view.append(make("circle",{cx:px,cy:py,r:13,fill:"none",stroke:"#fff","stroke-width":2,class:"selection-ring"}));
    const node=make("polygon",{points:starPoints(px,py),fill:colorForPattern(id),stroke:"#f8fafc","stroke-width":1.4,opacity:dim?0.18:0.92,class:"pattern-node"});
    interactive(node,patternTitle(id),`pattern:${id}`,()=>selectPattern(id));view.append(node);
    label(px+11,py+4,patternTitle(id),`pattern:${id}`,()=>state.pattern===id||state.hovered===`pattern:${id}`,dim);
  }
  for(const c of state.data.cases){const cx=xMap(c.x),cy=yMap(c.y),sel=state.selected?.case_id===c.case_id,dim=!!state.pattern&&c.predicted_pattern_id!==state.pattern;
    const node=make("circle",{cx,cy,r:sel?8.8:EXPANDED?6.8:7,fill:colorForCase(c),stroke:sel?"#f8fafc":"#dbeafe","stroke-width":sel?2.5:EXPANDED?1.6:1.8,class:"node",opacity:dim?0.18:1});
    interactive(node,caseTitle(c),c.case_id,()=>{state.selected=c;state.pattern=null;const url=new URL(location.href);url.searchParams.set("case",c.case_id);history.replaceState(null,"",url);renderDetail(c);render();});view.append(node);
    label(cx+(EXPANDED?8:9),cy-(EXPANDED?7:8),caseTitle(c),c.case_id,()=>state.hovered===c.case_id||(!dim&&sel),dim);
  }
  wireZoom(view); renderLegend();
  if(focusKey)els.svg.querySelector(`[data-key="${CSS.escape(focusKey)}"]`)?.focus();
}
async function optionalJson(path){try{const r=await fetch(path);return r.ok?await r.json():{};}catch{return {};}}
async function load(){
  const [res,display,demo]=await Promise.all([fetch(DATA_PATH),optionalJson("./data/display_content.json"),optionalJson(DEMO_PATH)]);
  if(!res.ok)throw new Error("The case map could not load. Please reload to try again.");
  state.data=await res.json();state.display=display;state.demoIds=new Set((demo.samples||[]).map(s=>s.case_id));
  const picker = document.getElementById("casePicker");
  if (picker) {
    picker.replaceChildren(...state.data.cases.map(c=>{const option=document.createElement("option");option.value=c.case_id;option.textContent=caseTitle(c);return option;}));
    picker.addEventListener("change",()=>{const c=state.data.cases.find(item=>item.case_id===picker.value);if(c){state.selected=c;state.pattern=null;const url=new URL(location.href);url.searchParams.set("case",c.case_id);history.replaceState(null,"",url);renderDetail(c);render();}});
  }
  const requested = new URLSearchParams(location.search).get("case");
  state.selected=state.data.cases.find(c=>c.case_id===requested)||state.data.cases[0]||null;
  if(state.selected)renderDetail(state.selected);render();
}
els.colorBy.addEventListener("change",render);els.showPatterns.addEventListener("change",render);els.resetZoom.addEventListener("click",()=>{state.zoom={scale:1,tx:0,ty:0};render();});
window.addEventListener("resize",()=>{if(state.data)updateLabels();});
load().catch(e=>{els.detail.textContent=e.message;console.error(e);});
