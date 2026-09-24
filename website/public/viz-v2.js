const DATA_PATH = "./data/case_graph_data_v2.json";

const els = {
  metrics: document.getElementById("metrics"),
  svg: document.getElementById("caseSvg"),
  detail: document.getElementById("detailPanel"),
  mapGuide: document.getElementById("mapGuide"),
  colorBy: document.getElementById("colorBy"),
  showPatterns: document.getElementById("showPatterns"),
  resetZoom: document.getElementById("resetZoomBtn"),
};

const state = { data: null, selected: null, zoom: { scale: 1, tx: 0, ty: 0 } };
const LIABILITY_COLORS = {
  product_safety: "#ef4444",
  privacy: "#14b8a6",
  fraud_enablement: "#fb7185",
  brand_trust: "#38bdf8",
  duty_of_care: "#f59e0b",
  regulatory: "#8b5cf6",
  ip: "#a78bfa",
  default: "#94a3b8",
};

function humanize(v) {
  return String(v || "").replaceAll("_", " ").replace(/\s+/g, " ").trim();
}

function short(v, n = 26) {
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
  return colorForPatternId(c.predicted_pattern_id || "none");
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

function renderMetrics() {
  const d = state.data.meta;
  els.metrics.innerHTML = [
    ["Case Cards", d.case_count],
    ["Pattern Cards", d.pattern_count],
    ["Embedding Model", d.embedding_model],
    ["Projection", humanize(d.projection)],
    ["Assignment", d.assignment],
  ].map(([k, v]) => `<article class="metric"><div class="k">${k}</div><div class="v">${v}</div></article>`).join("");
}

function renderGuide() {
  els.mapGuide.innerHTML = `
    <h2>How to Read This Map</h2>
    <div class="guide-grid">
      <div class="guide-item">
        <div class="guide-visual"><span class="dot dot-case"></span></div>
        <div>
          <div class="legend-title">Case node</div>
          <p class="small">Each circle is a curated case card embedded from its summary, evidence, and retrieval text.</p>
        </div>
      </div>
      <div class="guide-item">
        <div class="guide-visual"><span class="star-chip">★</span></div>
        <div>
          <div class="legend-title">Pattern node</div>
          <p class="small">Each star sits at the centroid of the case cards currently assigned to that pattern.</p>
        </div>
      </div>
      <div class="guide-item">
        <div class="guide-visual"><span class="swatch-line"></span></div>
        <div>
          <div class="legend-title">Cluster halo</div>
          <p class="small">The halo shows the rough footprint of a current pattern cluster.</p>
        </div>
      </div>
      <div class="guide-item">
        <div class="guide-visual"><span class="color-chip liability-chip">Mode</span></div>
        <div>
          <div class="legend-title">Coloring</div>
          <p class="small">Color by assigned pattern or by the leading liability pathway attached to the case card.</p>
        </div>
      </div>
    </div>
    <div class="guide-block">
      <ul class="list compact-list">
        <li>Nearby points are semantically closer in embedding space.</li>
        <li>The axes are projection coordinates, not named risk dimensions.</li>
        <li>The pattern stars are centroid markers, not a separate pattern-only embedding projection.</li>
      </ul>
    </div>
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
    const factor = evt.deltaY < 0 ? 1.1 : 0.9;
    const nextScale = Math.max(0.6, Math.min(8, state.zoom.scale * factor));
    const ratio = nextScale / state.zoom.scale;
    state.zoom.tx = a.x - (a.x - state.zoom.tx) * ratio;
    state.zoom.ty = a.y - (a.y - state.zoom.ty) * ratio;
    state.zoom.scale = nextScale;
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
  const pattern = state.data.patterns[c.predicted_pattern_id];
  const evidence = (c.evidence_spans || []).slice(0, 5)
    .map((span) => `<li><strong>${humanize(span.dimension || "evidence")}</strong>: ${span.quote || ""}</li>`)
    .join("");
  const top = (c.top_patterns || [])
    .map((hit) => `<li>${humanize(hit.label || hit.pattern_id)} <span class="sub">${Number(hit.score || 0).toFixed(3)}</span></li>`)
    .join("");
  const impacts = (c.impact_pathways || []).map((item) => `<li>${humanize(item)}</li>`).join("");
  const liabilities = (c.provider_liability_assessment || [])
    .map((item) => `<li><strong>${humanize(item.liability_type)}</strong> (${humanize(item.risk_level)})</li>`)
    .join("");

  els.detail.innerHTML = `
    <h3>${humanize(c.title)}</h3>
    <p class="sub">${c.summary || ""}</p>
    ${c.source_url ? `<a class="source-link" href="${c.source_url}" target="_blank" rel="noopener noreferrer">Open source post</a>` : ""}
    <dl class="kv">
      <dt>Assigned Pattern</dt><dd>${humanize(c.predicted_pattern_label || c.predicted_pattern_id)}</dd>
      <dt>Pattern Score</dt><dd>${Number(c.predicted_pattern_score || 0).toFixed(3)}</dd>
      <dt>Major Liability</dt><dd>${humanize(c.major_liability || "unknown")}</dd>
      <dt>Source</dt><dd>${humanize(c.source_id || "unknown")}</dd>
    </dl>

    <div class="pattern-focus">
      <h3>Observed Mechanism</h3>
      <p class="small">${humanize(c.core_dimensions?.mechanism_of_effect || c.core_dimensions?.organizing_principle || "unknown")}</p>
      <p class="small"><strong>Interaction:</strong> ${humanize(c.core_dimensions?.interaction_mode || "unknown")}</p>
      <p class="small"><strong>Consequence:</strong> ${humanize(c.core_dimensions?.real_world_consequence || "unknown")}</p>
    </div>

    <h3>Evidence Highlights</h3>
    <ul class="list">${evidence || "<li>No extracted evidence spans.</li>"}</ul>

    <h3>Impact Pathways</h3>
    <ul class="list">${impacts || "<li>No impact pathways listed.</li>"}</ul>

    <h3>Top Pattern Matches</h3>
    <ul class="list">${top || "<li>No pattern hits available.</li>"}</ul>

    <div class="pattern-focus">
      <h3>Linked Pattern Card</h3>
      ${pattern ? `
        <p class="small"><strong>${humanize(pattern.label || pattern.pattern_id)}</strong><br>${pattern.summary || ""}</p>
        <p class="small"><strong>Required:</strong> ${(pattern.required_signals || []).map(humanize).join("; ") || "None"}</p>
        <p class="small"><strong>Insufficient:</strong> ${(pattern.insufficient_signals || []).map(humanize).join("; ") || "None"}</p>
        <p class="small"><strong>Boundary:</strong> ${(pattern.boundary_notes || []).map(humanize).join("; ") || "None"}</p>
      ` : `<p class="small">Pattern card unavailable.</p>`}
    </div>

    <h3>Model Provider Liability</h3>
    <ul class="list">${liabilities || "<li>No structured liability assessment listed.</li>"}</ul>
  `;
}

function render() {
  const svg = els.svg;
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  const width = 980;
  const height = 560;
  const pad = 48;
  const view = make("g");
  svg.appendChild(view);

  const grid = make("g", { opacity: 0.45 });
  for (let i = 0; i <= 8; i++) {
    const x = pad + ((width - pad * 2) * i) / 8;
    const y = pad + ((height - pad * 2) * i) / 8;
    grid.appendChild(make("line", { x1: x, y1: pad, x2: x, y2: height - pad, stroke: "#2a3a50" }));
    grid.appendChild(make("line", { x1: pad, y1: y, x2: width - pad, y2: y, stroke: "#2a3a50" }));
  }
  view.appendChild(grid);

  const xMap = (v) => pad + ((Number(v) + 1) / 2) * (width - pad * 2);
  const yMap = (v) => height - pad - ((Number(v) + 1) / 2) * (height - pad * 2);

  const groups = new Map();
  for (const c of state.data.cases) {
    const key = c.predicted_pattern_id || "other";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push({ x: xMap(c.x), y: yMap(c.y) });
  }

  for (const points of groups.values()) {
    if (points.length < 2) continue;
    const cx = points.reduce((sum, p) => sum + p.x, 0) / points.length;
    const cy = points.reduce((sum, p) => sum + p.y, 0) / points.length;
    const r = Math.max(24, Math.sqrt(points.reduce((sum, p) => sum + (p.x - cx) ** 2 + (p.y - cy) ** 2, 0) / points.length) * 1.8);
    view.appendChild(make("circle", { cx, cy, r, fill: "#5aa7ff20", stroke: "#5aa7ff66", "stroke-width": 1.2 }));
  }

  if (els.showPatterns.checked) {
    for (const pattern of Object.values(state.data.patterns || {})) {
      const px = xMap(pattern.x || 0);
      const py = yMap(pattern.y || 0);
      const node = make("polygon", {
        points: starPoints(px, py),
        fill: colorForPattern(pattern.pattern_id),
        stroke: "#f8fafc",
        "stroke-width": 1.4,
        opacity: 0.92,
      });
      view.appendChild(node);
      const label = make("text", { x: px + 11, y: py + 4, class: "node-label", opacity: "0.82" });
      label.textContent = short(pattern.label || pattern.pattern_id, 24);
      view.appendChild(label);
    }
  }

  for (const c of state.data.cases) {
    const cx = xMap(c.x);
    const cy = yMap(c.y);
    const selected = state.selected?.case_id === c.case_id;
    const node = make("circle", {
      cx,
      cy,
      r: selected ? 8.8 : 6.8,
      fill: colorForCase(c),
      stroke: selected ? "#f8fafc" : "#dbeafe",
      "stroke-width": selected ? 2.5 : 1.6,
      class: "node",
    });
    node.addEventListener("click", () => {
      state.selected = c;
      renderDetail(c);
      render();
    });
    view.appendChild(node);

    const label = make("text", { x: cx + 8, y: cy - 7, class: "node-label", opacity: selected ? "1" : "0.78" });
    label.textContent = short(c.title || c.case_id, 24);
    view.appendChild(label);
  }

  const note = make("text", { x: pad, y: 24, fill: "#9eb5cf", "font-size": 12 });
  note.textContent = "Embedding projection view. Nearby cases are semantically closer; stars mark current pattern centroids.";
  view.appendChild(note);

  wireZoom(view);
}

async function load() {
  const res = await fetch(DATA_PATH, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch ${DATA_PATH}: ${res.status}`);
  state.data = await res.json();
  renderMetrics();
  renderGuide();
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

load().catch((err) => {
  els.detail.innerHTML = `<div class="empty">${err.message}</div>`;
  console.error(err);
});
