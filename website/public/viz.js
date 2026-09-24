const DATA_PATH = "./data/case_graph_data.json";

const els = {
  metrics: document.getElementById("metrics"),
  svg: document.getElementById("caseSvg"),
  detail: document.getElementById("detailPanel"),
  mapGuide: document.getElementById("mapGuide"),
  cardDrafts: document.getElementById("cardDrafts"),
  colorBy: document.getElementById("colorBy"),
  showPatterns: document.getElementById("showPatterns"),
  resetZoom: document.getElementById("resetZoomBtn"),
};

const state = { data: null, selected: null, zoom: { scale: 1, tx: 0, ty: 0 } };
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

function renderMetrics() {
  const d = state.data;
  const cards = [
    ["Cases", d.meta.case_count],
    ["Patterns", d.meta.pattern_count],
    ["Embedding Model", d.meta.embedding_model],
    ["Assignment", d.meta.assignment || "Decision + retrieval with embedding fallback"],
  ];
  els.metrics.innerHTML = cards.map(([k, v]) => `<article class="metric"><div class="k">${k}</div><div class="v">${v}</div></article>`).join("");
}

function assignmentSummary(c) {
  if (c.decision_closest_pattern) return "Judge decision with closest existing pattern";
  if (c.decision_suspected_pattern) return "Judge/watchlist suspicion, then mapped to display pattern";
  if (c.predicted_pattern_id) return "Display assignment from pattern retrieval / embedding fallback";
  return "No pattern assignment available";
}

function generalObservationDraft(c) {
  const parts = [
    c.summary || "",
    `Observed mechanism: ${humanize((c.core_dimensions || {}).mechanism_of_effect || "unknown")}.`,
    `Main consequence: ${humanize((c.core_dimensions || {}).real_world_consequence || "unknown")}.`,
  ].filter(Boolean);
  return parts.join(" ");
}

function generalEvidenceDraft(c) {
  const spans = (c.evidence_spans || []).slice(0, 2);
  if (!spans.length) return "No quoted evidence extracted yet.";
  return spans.map((e) => `${humanize(e.dimension)}: ${e.quote}`).join(" ");
}

function generalRiskDraft(c) {
  const liability = humanize(c.major_liability || "unknown");
  const impact = (c.impact_pathways || []).slice(0, 2).map(humanize);
  const tail = impact.length ? `Likely pathways: ${impact.join("; ")}.` : "";
  return `Why monitor: this case may indicate ${liability} exposure or a recurring risky interaction pattern. ${tail}`.trim();
}

function renderGuide() {
  els.mapGuide.innerHTML = `
    <h2>How To Read This Map</h2>
    <div class="guide-block">
      <p class="small">This is a similarity map of stored case cards, not a literal risk ranking. Nearby cases are closer in embedding space based on their extracted summaries and evidence.</p>
    </div>
    <div class="guide-grid">
      <div class="guide-item">
        <div class="guide-visual">
          <span class="dot dot-case"></span>
        </div>
        <div>
          <div class="legend-title">Case Node</div>
          <p class="small">A circle is a sourced case card. Click one to inspect the summary, evidence, and linked pattern.</p>
        </div>
      </div>
      <div class="guide-item">
        <div class="guide-visual">
          <span class="star-chip">★</span>
        </div>
        <div>
          <div class="legend-title">Pattern Node</div>
          <p class="small">A star is a pattern card. Turn on <strong>Show pattern cards</strong> to overlay them on the map.</p>
        </div>
      </div>
      <div class="guide-item">
        <div class="guide-visual">
          <span class="swatch-line"></span>
        </div>
        <div>
          <div class="legend-title">Cluster Halo</div>
          <p class="small">The faint halo shows a loose neighborhood of cases that currently share the same displayed pattern assignment.</p>
        </div>
      </div>
      <div class="guide-item">
        <div class="guide-visual">
          <span class="color-chip liability-chip">Liability</span>
        </div>
        <div>
          <div class="legend-title">Color Modes</div>
          <p class="small"><strong>Assigned Pattern</strong> colors by displayed pattern. <strong>Major Liability</strong> colors by the current risk label field in the dataset.</p>
        </div>
      </div>
    </div>
    <div class="guide-block">
      <div class="legend-title">Interpretation Notes</div>
      <ul class="list compact-list">
        <li>The axes are projection coordinates, not named dimensions.</li>
        <li>Pattern placement is visual context only; it does not prove causality.</li>
        <li>Assignment provenance is shown in the detail panel for each case.</li>
      </ul>
    </div>
  `;
}

function renderDraftCards() {
  const samples = (state.data?.cases || []).slice(0, 3);
  els.cardDrafts.innerHTML = `
    <h2>Draft General Case-Card Framing</h2>
    <p class="small">These are draft templates for making case cards read more generally and evidence-first, without assuming a specific taxonomy like spiralism or companionship.</p>
    ${samples.map((c) => `
      <div class="draft-card">
        <div class="draft-title">${humanize(c.title)}</div>
        <div class="draft-label">Observation</div>
        <p class="small">${generalObservationDraft(c)}</p>
        <div class="draft-label">Evidence</div>
        <p class="small">${generalEvidenceDraft(c)}</p>
        <div class="draft-label">Why It Matters</div>
        <p class="small">${generalRiskDraft(c)}</p>
      </div>
    `).join("")}
  `;
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
  };
  els.svg.onmouseup = () => { drag = false; };
  els.svg.onmouseleave = () => { drag = false; };
}

function renderDetail(c) {
  const dimFromCanonical = (key) => {
    const t = String(c.canonical_text || "");
    const m = t.match(new RegExp(`^${key}:\\s*(.+)$`, "m"));
    return m ? m[1].trim() : "";
  };
  const dim = (key) => {
    const cd = c.core_dimensions || {};
    const direct = cd[key];
    if (direct != null && String(direct).trim()) return String(direct);
    const fromCanonical = dimFromCanonical(key);
    return fromCanonical || "unknown";
  };

  const extentMap = {
    full: "fully AI-written",
    partial: "partially AI-written",
    none: "not AI-written",
    unknown: "uncertain",
  };
  const verdictMap = {
    llm_like: "AI-like writing style",
    human_like: "human-like writing style",
    unknown: "mixed/uncertain style",
  };
  const conf = Number(c.llm_written_confidence || 0);
  const confPct = ((conf <= 1 ? conf : conf / 100) * 100).toFixed(0);
  const extentLabel = extentMap[String(c.llm_written_extent || "unknown")] || "uncertain";
  const verdictLabel = verdictMap[String(c.llm_written_verdict || "unknown")] || "mixed/uncertain style";
  const p = state.data.patterns[c.predicted_pattern_id];
  const provenance = assignmentSummary(c);
  const top = (c.top_patterns || [])
    .map((x) => `<li>${humanize(x.label || x.pattern_id)} <span class="sub">${x.score.toFixed(3)}</span></li>`)
    .join("");
  const evidence = (c.evidence_spans || [])
    .slice(0, 4)
    .map((e) => `<li><strong>${humanize(e.dimension)}</strong>: ${e.quote || ""}</li>`)
    .join("");
  const impact = (c.impact_pathways || []).map((x) => `<li>${x}</li>`).join("");
  const li = (c.provider_liability_assessment || [])
    .map((x) => `<li><strong>${humanize(x.liability_type)}</strong> (${x.risk_level})</li>`)
    .join("");
  const coreSnapshot = [
    ["Organizing Principle", dim("organizing_principle")],
    ["Mechanism of Effect", dim("mechanism_of_effect")],
    ["Stance", dim("stance")],
    ["Real-World Consequence", dim("real_world_consequence")],
    ["Coordination Level", dim("coordination_level")],
  ]
    .map(([k, v]) => `<li><strong>${k}:</strong> ${humanize(v)}</li>`)
    .join("");
  const targetFraming = [
    ["Target of Effect", dim("target_of_effect")],
    ["Relationship Framing", dim("relationship_framing")],
    ["Agency Attribution", dim("agency_attribution")],
  ]
    .map(([k, v]) => `<li><strong>${k}:</strong> ${humanize(v)}</li>`)
    .join("");
  const diffusionRitual = [
    ["Spread Signal", dim("diffusion_stage")],
    ["Repeatability / Scripted Use", dim("ritualization_level")],
    ["User-AI Identity Blending", dim("identity_co_construction")],
  ]
    .map(([k, v]) => `<li><strong>${k}:</strong> ${humanize(v)}</li>`)
    .join("");
  const generalDraft = `
    <div class="pattern-focus draft-focus">
      <h3>Generalized Draft Case Card</h3>
      <p class="small"><strong>Observation:</strong> ${generalObservationDraft(c)}</p>
      <p class="small"><strong>Evidence:</strong> ${generalEvidenceDraft(c)}</p>
      <p class="small"><strong>Why It Matters:</strong> ${generalRiskDraft(c)}</p>
    </div>
  `;

  els.detail.innerHTML = `
    <h3>${humanize(c.title)}</h3>
    <p class="sub">${c.summary || ""}</p>
    ${c.source_url ? `<a class="source-link" href="${c.source_url}" target="_blank" rel="noopener noreferrer">Open source post</a>` : ""}
    <dl class="kv">
      <dt>Assigned Pattern</dt><dd>${humanize(c.predicted_pattern_label || c.predicted_pattern_id)}</dd>
      <dt>Pattern Score</dt><dd>${(c.predicted_pattern_score || 0).toFixed(3)}</dd>
      <dt>Major Liability</dt><dd>${humanize(c.major_liability)}</dd>
      <dt>AI-Written</dt><dd>${extentLabel} (${verdictLabel}, ${confPct}% confidence)</dd>
      <dt>Source</dt><dd>${humanize(c.source_id || "unknown")}</dd>
      <dt>Assignment Provenance</dt><dd>${provenance}</dd>
    </dl>
    ${generalDraft}
    <h3>Evidence Highlights</h3>
    <ul class="list">${evidence || "<li>No extracted evidence spans.</li>"}</ul>
    <h3>Core Snapshot</h3>
    <ul class="list">${coreSnapshot}</ul>
    <h3>Target + Relationship Context</h3>
    <ul class="list">${targetFraming}</ul>
    <h3>Spread + Repeatability Signal</h3>
    <ul class="list">${diffusionRitual}</ul>
    <h3>Impact Pathways</h3>
    <ul class="list">${impact || "<li>No impact pathways listed.</li>"}</ul>
    <h3>Top Pattern Matches</h3>
    <ul class="list">${top || "<li>None</li>"}</ul>
    <div class="pattern-focus">
      <h3>Linked Pattern Card</h3>
      ${p ? `<p class="small"><strong>${humanize(p.label || p.pattern_id)}</strong><br>${p.summary || ""}</p>
      <p class="small"><strong>Required:</strong> ${(p.required_signals || []).map(humanize).join("; ") || "None"}</p>
      <p class="small"><strong>Insufficient:</strong> ${(p.insufficient_signals || []).map(humanize).join("; ") || "None"}</p>
      <p class="small"><strong>Boundary:</strong> ${(p.boundary_notes || []).map(humanize).join("; ") || "None"}</p>` : `<p class="small">Pattern card unavailable.</p>`}
    </div>
    <h3>Model Provider Liability</h3>
    <ul class="list">${li || "<li>None</li>"}</ul>
  `;
}

function render() {
  const svg = els.svg;
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  const w = 980;
  const h = 560;
  const pad = 48;
  const view = make("g");
  svg.appendChild(view);

  const grid = make("g", { opacity: 0.45 });
  for (let i = 0; i <= 8; i++) {
    const x = pad + ((w - pad * 2) * i) / 8;
    const y = pad + ((h - pad * 2) * i) / 8;
    grid.appendChild(make("line", { x1: x, y1: pad, x2: x, y2: h - pad, stroke: "#2a3a50" }));
    grid.appendChild(make("line", { x1: pad, y1: y, x2: w - pad, y2: y, stroke: "#2a3a50" }));
  }
  view.appendChild(grid);

  const xMap = (v) => pad + ((Number(v) + 1) / 2) * (w - pad * 2);
  const yMap = (v) => h - pad - ((Number(v) + 1) / 2) * (h - pad * 2);

  if (els.showPatterns.checked) {
    for (const p of Object.values(state.data.patterns || {})) {
      const patternId = p.pattern_id || p.id || "none";
      const px = xMap(Number(p.x || 0));
      const py = yMap(Number(p.y || 0));
      view.appendChild(
        make("polygon", {
          points: starPoints(px, py),
          fill: colorForPattern(patternId),
          stroke: "#f8fafc",
          "stroke-width": 1.4,
          opacity: 0.92,
        })
      );
      const pLabel = make("text", { x: px + 11, y: py + 4, class: "node-label", opacity: "0.8" });
      pLabel.textContent = short(p.label || patternId, 24);
      view.appendChild(pLabel);
    }
  }

  const groups = new Map();
  const posByCase = new Map();
  for (const c of state.data.cases) {
    const hp = hybridPos(c);
    posByCase.set(c.case_id, hp);
    const k = c.predicted_pattern_id || "other";
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push({ x: xMap(hp.x), y: yMap(hp.y) });
  }
  for (const pts of groups.values()) {
    if (pts.length < 2) continue;
    const cx = pts.reduce((a, p) => a + p.x, 0) / pts.length;
    const cy = pts.reduce((a, p) => a + p.y, 0) / pts.length;
    const r = Math.max(24, Math.sqrt(pts.reduce((a, p) => a + (p.x - cx) ** 2 + (p.y - cy) ** 2, 0) / pts.length) * 1.8);
    view.appendChild(make("circle", { cx, cy, r, fill: "#5aa7ff20", stroke: "#5aa7ff66", "stroke-width": 1.2 }));
  }

  for (const c of state.data.cases) {
    const hp = posByCase.get(c.case_id) || { x: Number(c.x || 0), y: Number(c.y || 0) };
    const cx = xMap(hp.x);
    const cy = yMap(hp.y);
    const sel = state.selected?.case_id === c.case_id;
    const node = make("circle", {
      cx,
      cy,
      r: sel ? 8.8 : 7,
      fill: colorForCase(c),
      stroke: sel ? "#f8fafc" : "#dbeafe",
      "stroke-width": sel ? 2.5 : 1.8,
      class: "node",
    });
    node.addEventListener("click", () => {
      state.selected = c;
      renderDetail(c);
      render();
    });
    view.appendChild(node);

    const label = make("text", { x: cx + 9, y: cy - 8, class: "node-label" });
    label.textContent = short(c.title || c.case_id, 24);
    label.setAttribute("opacity", sel ? "1" : "0.8");
    view.appendChild(label);
  }

  const note = make("text", { x: pad, y: 24, fill: "#9eb5cf", "font-size": 12 });
  note.textContent = "Embedding projection view. Nearby cases are semantically closer; assignment provenance appears in the detail panel.";
  view.appendChild(note);

  wireZoom(view);
}

async function load() {
  const res = await fetch(DATA_PATH, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch ${DATA_PATH}: ${res.status}`);
  state.data = await res.json();
  renderMetrics();
  renderGuide();
  renderDraftCards();
  state.selected = state.data.cases[0] || null;
  if (state.selected) renderDetail(state.selected);
  render();
}

els.colorBy.addEventListener("change", render);
els.showPatterns.addEventListener("change", render);
els.resetZoom.addEventListener("click", () => {
  state.zoom = { scale: 1, tx: 0, ty: 0 };
  render();
});

load().catch((e) => {
  els.detail.innerHTML = `<div class="empty">${e.message}</div>`;
  console.error(e);
});
