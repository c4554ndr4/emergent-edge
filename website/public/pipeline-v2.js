const DATA_URL = "./data/pipeline_demo_data_v2.json";

const els = {
  metrics: document.getElementById("metrics"),
  sampleSelect: document.getElementById("sampleSelect"),
  openSampleSourceBtn: document.getElementById("openSampleSourceBtn"),
  selectedTitle: document.getElementById("selectedTitle"),
  selectedSummary: document.getElementById("selectedSummary"),
  selectedTags: document.getElementById("selectedTags"),
  heroNotes: document.getElementById("heroNotes"),
  exaSelectedSummary: document.getElementById("exaSelectedSummary"),
  exaBatchStats: document.getElementById("exaBatchStats"),
  exaResultsBody: document.getElementById("exaResultsBody"),
  exaInput: document.getElementById("exaInput"),
  gateVerdict: document.getElementById("gateVerdict"),
  gateWhy: document.getElementById("gateWhy"),
  gateCategories: document.getElementById("gateCategories"),
  gatePrompt: document.getElementById("gatePrompt"),
  gateOut: document.getElementById("gateOut"),
  curatorVerdict: document.getElementById("curatorVerdict"),
  curatorWhy: document.getElementById("curatorWhy"),
  curatorCategories: document.getElementById("curatorCategories"),
  curatorPrompt: document.getElementById("curatorPrompt"),
  curatorOut: document.getElementById("curatorOut"),
  caseCardTitle: document.getElementById("caseCardTitle"),
  caseCardSummary: document.getElementById("caseCardSummary"),
  caseCardMeta: document.getElementById("caseCardMeta"),
  caseEvidenceList: document.getElementById("caseEvidenceList"),
  caseMechanism: document.getElementById("caseMechanism"),
  caseConsequence: document.getElementById("caseConsequence"),
  casePrompt: document.getElementById("casePrompt"),
  caseCardOut: document.getElementById("caseCardOut"),
  canonicalOut: document.getElementById("canonicalOut"),
  noveltyVerdict: document.getElementById("noveltyVerdict"),
  noveltyReason: document.getElementById("noveltyReason"),
  noveltyMeta: document.getElementById("noveltyMeta"),
  patternTitle: document.getElementById("patternTitle"),
  patternSummary: document.getElementById("patternSummary"),
  sharedFeatures: document.getElementById("sharedFeatures"),
  differentiators: document.getElementById("differentiators"),
  noveltyPrompt: document.getElementById("noveltyPrompt"),
  patternCardOut: document.getElementById("patternCardOut"),
  noveltyOut: document.getElementById("noveltyOut"),
};

const state = { data: null, selectedCaseId: null };

function pretty(v) {
  return JSON.stringify(v, null, 2);
}

function humanize(v) {
  return String(v || "").replaceAll("_", " ").replace(/\s+/g, " ").trim();
}

function metricCard(label, value) {
  return `<article class="metric"><div class="k">${label}</div><div class="v">${value}</div></article>`;
}

function listMarkup(items, fallback = "None") {
  if (!items || !items.length) return `<li>${fallback}</li>`;
  return items.map((item) => `<li>${item}</li>`).join("");
}

function getSample() {
  return state.data.samples.find((s) => s.case_id === state.selectedCaseId) || state.data.samples[0];
}

function getPattern(patternId) {
  return (state.data.patterns || []).find((p) => p.pattern_id === patternId) || null;
}

function renderMetrics() {
  const meta = state.data.meta;
  els.metrics.innerHTML = [
    metricCard("Fresh Candidates", meta.fresh_candidate_count),
    metricCard("Risk Gate Kept", meta.risk_gate_kept),
    metricCard("Curated", meta.curator_kept),
    metricCard("Case Corpus", meta.corpus_case_count),
    metricCard("Pattern Cards", meta.pattern_count),
  ].join("");
}

function renderSampleSelect() {
  els.sampleSelect.innerHTML = state.data.samples
    .map((s) => `<option value="${s.case_id}">${s.title || s.case_id}</option>`)
    .join("");
  if (!state.selectedCaseId && state.data.samples.length) state.selectedCaseId = state.data.samples[0].case_id;
  els.sampleSelect.value = state.selectedCaseId;
}

function renderHero(sample) {
  const decision = sample.novelty_decision || {};
  const verdict = decision.verdict ? humanize(decision.verdict) : "unknown";
  const closest = decision.closest_pattern ? humanize(decision.closest_pattern) : null;
  els.selectedTitle.textContent = sample.title || sample.case_id;
  els.selectedSummary.textContent = sample.case_card?.summary || "";
  els.selectedTags.innerHTML = [
    sample.lane ? `<span class="tag case">${humanize(sample.lane)}</span>` : "",
    `<span class="tag pattern">${verdict}</span>`,
    closest ? `<span class="tag ref">${closest}</span>` : "",
  ].join("");
  els.heroNotes.innerHTML = listMarkup([
    `Exa runs multiple search families per day and deduplicates reviewed URLs before model calls.`,
    `A small-model liability gate removes obvious non-cases before expensive processing.`,
    `A stronger curator keeps only posts that look worth preserving as case cards.`,
    `Case cards are generated with ${state.data.meta.casecard_model} and then compared against a deliberate generic pattern library.`,
    `Only cases that fail a clean existing-pattern fit need strong novelty adjudication.`,
  ]);
}

function renderExaStage(sample) {
  const lanes = state.data.run.source_report?.lanes || [];
  const totalAnalyzed = lanes.reduce((sum, lane) => sum + Number(lane.items_from_search || 0), 0);
  const totalKept = lanes.reduce((sum, lane) => sum + Number(lane.threads_added || 0), 0);
  const totalOld = lanes.reduce((sum, lane) => sum + Number(lane.dropped_old_year || 0), 0);
  const totalHarm = lanes.reduce((sum, lane) => sum + Number(lane.dropped_low_harm || 0), 0);
  const totalNews = lanes.reduce((sum, lane) => sum + Number(lane.dropped_news_style || 0), 0);
  els.exaBatchStats.innerHTML = [
    `<div><strong>Analyzed</strong><span>${totalAnalyzed}</span></div>`,
    `<div><strong>Kept</strong><span>${totalKept}</span></div>`,
    `<div><strong>Dropped old</strong><span>${totalOld}</span></div>`,
    `<div><strong>Dropped low harm</strong><span>${totalHarm}</span></div>`,
    `<div><strong>Dropped news-style</strong><span>${totalNews}</span></div>`,
  ].join("");
  els.exaSelectedSummary.innerHTML = listMarkup([
    `The selected case came from ${humanize(sample.lane || "a daily search family")}.`,
    `Search families are intentionally different: bug reports, security failures, community incidents, and companion/memory failures.`,
    `This stage only decides whether a source is interesting enough to inspect further. It does not create a case card yet.`,
    `Reviewed URLs and duplicate material are filtered out before the run continues.`,
  ]);
  els.exaResultsBody.innerHTML = (state.data.run.results || [])
    .map((r) => `
      <tr>
        <td>${humanize(r.lane)}</td>
        <td>${r.url ? `<a class="source-link" href="${r.url}" target="_blank" rel="noopener noreferrer">${r.title || r.thread_id}</a>` : (r.title || r.thread_id)}</td>
        <td>${humanize(r.status)}</td>
      </tr>`)
    .join("");
  els.exaInput.textContent = state.data.prompts.exa_search_families || "";
}

function renderGateStage() {
  const report = state.data.run.gate_report || {};
  els.gateVerdict.textContent = `${report.threads_kept || 0} kept / ${report.threads_total || 0} reviewed`;
  els.gateWhy.textContent = `This stage exists to cheaply remove obvious non-liability material before case-card generation.`;
  els.gateCategories.innerHTML = listMarkup([
    `Drops generic commentary, broad discourse, gratitude posts, and weak non-incident material.`,
    `Keeps concrete harm reports, operational failures, exploit writeups, and genuinely weird edge cases.`,
    `Uses ${state.data.meta.gate_model} so the high-cost models only see stronger candidates.`,
  ]);
  els.gatePrompt.textContent = state.data.prompts.risk_gate || "";
  els.gateOut.textContent = pretty(report);
}

function renderCuratorStage() {
  const report = state.data.run.curator_report || {};
  els.curatorVerdict.textContent = `${report.threads_kept || 0} kept / ${report.threads_total || 0} reviewed`;
  els.curatorWhy.textContent = `This is the quality-control step that turns a broad daily search into a readable standing corpus.`;
  els.curatorCategories.innerHTML = listMarkup([
    `Keeps first-person testimony, personal essays with concrete stakes, and procedural writeups with tested details.`,
    `Drops raw news, generic policy debate, SEO pages, and weak complaints that do not support a durable case card.`,
    `Uses ${state.data.meta.curator_model} because this is where judgment quality matters more than speed.`,
  ]);
  els.curatorPrompt.textContent = state.data.prompts.case_worthiness_curator || "";
  els.curatorOut.textContent = pretty(report);
}

function renderCaseStage(sample) {
  const card = sample.case_card || {};
  const dimensions = card.core_dimensions || {};
  els.caseCardTitle.textContent = sample.title || sample.case_id;
  els.caseCardSummary.textContent = card.summary || "";
  els.caseCardMeta.innerHTML = [
    `<div><strong>Confidence</strong><span>${Number(card.confidence || 0).toFixed(2)}</span></div>`,
    `<div><strong>Interaction Mode</strong><span>${humanize(dimensions.interaction_mode || "unknown")}</span></div>`,
    `<div><strong>Diffusion</strong><span>${humanize(dimensions.diffusion_stage || "unknown")}</span></div>`,
  ].join("");
  els.caseEvidenceList.innerHTML = listMarkup((card.evidence_spans || []).slice(0, 5).map((span) => {
    const quote = span.quote || "";
    const why = span.why_it_matters || "";
    return `<strong>${humanize(span.dimension || "evidence")}</strong>: ${quote}${why ? ` <span class="small">${why}</span>` : ""}`;
  }));
  els.caseMechanism.textContent = humanize(dimensions.mechanism_of_effect || dimensions.organizing_principle || "unknown");
  els.caseConsequence.textContent = humanize(dimensions.real_world_consequence || "unknown");
  els.casePrompt.textContent = state.data.prompts.case_card_extractor || "";
  els.caseCardOut.textContent = pretty(card);
  els.canonicalOut.textContent = sample.canonical_text || card.canonical_text || "";
}

function renderNoveltyStage(sample) {
  const decision = sample.novelty_decision || {};
  const pattern = sample.pattern_card || getPattern(decision.closest_pattern || decision.suspected_pattern);
  els.patternTitle.textContent = pattern ? humanize(pattern.label || pattern.pattern_id) : "No matched pattern card";
  els.patternSummary.textContent = pattern?.summary || "This case is currently sitting outside the nearest existing pattern boundary.";
  els.noveltyVerdict.textContent = humanize(decision.verdict || "unknown");
  els.noveltyReason.textContent = decision.why_counterargument_fails || decision.counterargument || decision.new_axis || "";
  els.noveltyMeta.innerHTML = [
    `<div><strong>Closest Pattern</strong><span>${humanize(decision.closest_pattern || "none")}</span></div>`,
    `<div><strong>Confidence</strong><span>${Number(decision.confidence || 0).toFixed(2)}</span></div>`,
    `<div><strong>New Axis</strong><span>${humanize(decision.new_axis || "none")}</span></div>`,
  ].join("");
  els.sharedFeatures.innerHTML = listMarkup((decision.shared_features || []).map(humanize));
  els.differentiators.innerHTML = listMarkup((decision.differentiators || []).map(humanize));
  els.noveltyPrompt.textContent = state.data.prompts.novelty_and_pattern_fit || "";
  els.patternCardOut.textContent = pattern ? pretty(pattern) : "Pattern card not found.";
  els.noveltyOut.textContent = pretty(decision);
}

function openSampleSource() {
  const sample = getSample();
  if (sample?.source_url) {
    window.open(sample.source_url, "_blank", "noopener,noreferrer");
  }
}

function renderAll() {
  const sample = getSample();
  renderHero(sample);
  renderExaStage(sample);
  renderGateStage();
  renderCuratorStage();
  renderCaseStage(sample);
  renderNoveltyStage(sample);
}

async function load() {
  const res = await fetch(DATA_URL, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load ${DATA_URL}: ${res.status}`);
  state.data = await res.json();
  renderMetrics();
  renderSampleSelect();
  renderAll();
}

els.sampleSelect.addEventListener("change", () => {
  state.selectedCaseId = els.sampleSelect.value;
  renderAll();
});
els.openSampleSourceBtn.addEventListener("click", openSampleSource);

load().catch((err) => {
  els.selectedTitle.textContent = "Failed to load pipeline demo";
  els.selectedSummary.textContent = err.message;
  console.error(err);
});
