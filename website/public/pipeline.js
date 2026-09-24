const DATA_URL = "./data/pipeline_demo_data.json";

const els = {
  metrics: document.getElementById("metrics"),
  sampleSelect: document.getElementById("sampleSelect"),
  useSampleEverywhereBtn: document.getElementById("useSampleEverywhereBtn"),
  openSampleSourceBtn: document.getElementById("openSampleSourceBtn"),
  exaSummary: document.getElementById("exaSummary"),
  exaModelInfo: document.getElementById("exaModelInfo"),
  exaInput: document.getElementById("exaInput"),
  exaResultsBody: document.getElementById("exaResultsBody"),
  caseModelInfo: document.getElementById("caseModelInfo"),
  caseQuality: document.getElementById("caseQuality"),
  sampleTextInput: document.getElementById("sampleTextInput"),
  casePromptInput: document.getElementById("casePromptInput"),
  inputPost: document.getElementById("inputPost"),
  caseCardOut: document.getElementById("caseCardOut"),
  canonicalModelInfo: document.getElementById("canonicalModelInfo"),
  canonicalInput: document.getElementById("canonicalInput"),
  canonicalOut: document.getElementById("canonicalOut"),
  noveltyModelInfo: document.getElementById("noveltyModelInfo"),
  originModelInfo: document.getElementById("originModelInfo"),
  noveltyInput: document.getElementById("noveltyInput"),
  originBonusInput: document.getElementById("originBonusInput"),
  assignedPattern: document.getElementById("assignedPattern"),
  patternCardOut: document.getElementById("patternCardOut"),
  noveltyOut: document.getElementById("noveltyOut"),
  originBonusOut: document.getElementById("originBonusOut"),
  runExaBtn: document.getElementById("runExaBtn"),
  useExaInputBtn: document.getElementById("useExaInputBtn"),
  runCaseBtn: document.getElementById("runCaseBtn"),
  useSampleInputBtn: document.getElementById("useSampleInputBtn"),
  runCanonicalBtn: document.getElementById("runCanonicalBtn"),
  useCanonicalInputBtn: document.getElementById("useCanonicalInputBtn"),
  runNoveltyBtn: document.getElementById("runNoveltyBtn"),
  useNoveltyInputBtn: document.getElementById("useNoveltyInputBtn"),
  runOriginBonusBtn: document.getElementById("runOriginBonusBtn"),
  useOriginBonusInputBtn: document.getElementById("useOriginBonusInputBtn"),
  promptModal: document.getElementById("promptModal"),
  promptTitle: document.getElementById("promptTitle"),
  promptBody: document.getElementById("promptBody"),
  closeModalBtn: document.getElementById("closeModalBtn"),
};

const state = {
  data: null,
  selectedCaseId: null,
};

function pretty(v) {
  return JSON.stringify(v, null, 2);
}

function stageReset() {
  els.exaResultsBody.innerHTML = "";
  els.exaInput.value = "";
  els.inputPost.textContent = "";
  els.sampleTextInput.value = "";
  els.casePromptInput.textContent = "";
  els.caseCardOut.textContent = "";
  els.canonicalInput.value = "";
  els.canonicalOut.textContent = "";
  els.noveltyInput.value = "";
  els.originBonusInput.value = "";
  els.assignedPattern.innerHTML = "";
  els.patternCardOut.textContent = "";
  els.noveltyOut.textContent = "";
  els.originBonusOut.textContent = "";
}

function getSample() {
  return state.data.samples.find((s) => s.case_id === state.selectedCaseId) || state.data.samples[0];
}

function openSampleSource() {
  const s = getSample();
  const url = s?.source_url;
  if (url) window.open(url, "_blank", "noopener,noreferrer");
}

function renderMetrics() {
  const meta = state.data.meta;
  const cards = [
    ["Forum Cases", meta.forum_case_count],
    ["Pattern Cards", meta.pattern_count],
  ];
  els.metrics.innerHTML = cards
    .map(([k, v]) => `<article class="metric"><div class="k">${k}</div><div class="v">${v}</div></article>`)
    .join("");
}

function renderStageModelInfo() {
  const q = state.data.case_card_quality || {};
  const embeddingModel = state.data.meta?.embedding_model || "embedding-model";
  const routerModel = state.data.meta?.router_model || "small-model";
  const judgeModel = state.data.meta?.judge_model || "language-model";
  const originModel = state.data.meta?.origin_bonus_model || q.origin_model || q.gate_model || "small-model";

  els.exaModelInfo.textContent = "Model: Exa search monitor API (no LLM used in this step).";
  els.caseModelInfo.textContent = `Models: gate=${q.gate_model || "small-model"}, case-card extractor=${q.casecard_model || "extraction-model"}.`;
  els.canonicalModelInfo.textContent = `Model: ${embeddingModel} (used for embedding canonical text).`;
  els.noveltyModelInfo.textContent = `Models: router=${routerModel}, novelty judge=${judgeModel}.`;
  els.originModelInfo.textContent = `Model: ${originModel} (AI-written extent judge: full|partial|none|unknown).`;
}

function renderSampleSelect() {
  els.sampleSelect.innerHTML = state.data.samples
    .map((s) => `<option value="${s.case_id}">${s.title || s.case_id}</option>`)
    .join("");
  if (!state.selectedCaseId && state.data.samples.length) state.selectedCaseId = state.data.samples[0].case_id;
  els.sampleSelect.value = state.selectedCaseId;
}

function showPrompt(key) {
  const prompts = state.data.prompts || {};
  const titleMap = {
    exa_criteria: "Exa Monitor Criteria (Template)",
    case_card_extractor: "Case Card Extractor Prompt",
    canonicalization_spec: "Canonicalization Transform Spec",
    novelty_router: "Novelty Router Prompt",
    novelty_judge: "Novelty Judge Prompt",
  };
  els.promptTitle.textContent = titleMap[key] || "Prompt";
  els.promptBody.textContent = prompts[key] || "Not found.";
  els.promptModal.classList.remove("hidden");
}

function hidePrompt() {
  els.promptModal.classList.add("hidden");
}

function runExaStage() {
  let criteria = state.data.exa.criteria_template;
  try {
    criteria = JSON.parse(els.exaInput.value);
  } catch (_e) {}
  const monitors = criteria.monitors || [];
  els.exaSummary.innerHTML = `
    <strong>Global domain exclusions:</strong> ${(criteria.global_exclude_domains || []).join(", ")}<br>
    <strong>Monitor lanes:</strong> ${monitors.map((m) => m.name).join(", ")}
  `;

  const rows = state.data.exa.results || [];
  els.exaResultsBody.innerHTML = rows
    .map(
      (r) => `<tr>
      <td>${r.title || r.case_id}</td>
      <td><a class="source-link" href="${r.url}" target="_blank" rel="noopener noreferrer">${r.url}</a></td>
    </tr>`
    )
    .join("");
}

function runCaseStage() {
  const s = getSample();
  const q = state.data.case_card_quality || {};
  els.caseQuality.textContent = `Prompt method: ${q.method || "liability_heavy_v1"}.`;
  const excerpt = s.input_post_excerpt || "(No excerpt)";
  if (!els.sampleTextInput.value.trim()) {
    els.sampleTextInput.value = pretty(s.thread_json || {});
  }
  els.inputPost.textContent = excerpt;
  let threadJson = s.thread_json || {};
  try {
    threadJson = JSON.parse(els.sampleTextInput.value);
  } catch (_e) {}
  const promptReady = {
    task: "case_card_extraction",
    thread_json: threadJson,
  };
  els.casePromptInput.textContent = pretty(promptReady);
  els.caseCardOut.textContent = pretty(s.case_card);
}

function canonicalizeCaseCardLikePipeline(card) {
  const cd = (card && card.core_dimensions) || {};
  const n = (card && card.novelty) || {};
  const lines = [];
  const j = (k, v) => `${k}: ${v == null ? "unknown" : v}`;
  lines.push(j("case_id", card?.case_id));
  lines.push(j("source_thread_id", card?.source_thread_id));
  lines.push(j("summary", (card?.summary || "").trim()));
  lines.push("-- core_dimensions --");
  [
    "organizing_principle",
    "mechanism_of_effect",
    "interaction_mode",
    "target_of_effect",
    "agency_attribution",
    "relationship_framing",
    "stance",
    "ritualization_level",
    "identity_co_construction",
    "coordination_level",
    "real_world_consequence",
    "diffusion_stage",
  ].forEach((k) => lines.push(j(k, cd[k])));
  lines.push("-- novelty --");
  lines.push(j("verdict", n.verdict));
  lines.push(j("candidate_new_family", n.candidate_new_family || ""));
  lines.push(j("candidate_new_axes", (n.candidate_new_axes || []).join(", ")));
  lines.push(j("surface_vs_structural", n.surface_vs_structural));
  lines.push(j("counterargument_to_novelty", n.counterargument_to_novelty));
  lines.push(j("why_counterargument_fails", n.why_counterargument_fails));
  lines.push("-- evidence --");
  (card?.evidence_spans || []).forEach((e) =>
    lines.push(j("evidence", `${e.dimension}: ${e.quote} | ${e.why_it_matters}`))
  );
  lines.push("-- comparison --");
  (card?.comparison?.nearest_known_patterns || []).forEach((f) =>
    lines.push(j("pattern_fit", `${f.label} fit=${f.fit} overlap=${f.overlap} difference=${f.difference}`))
  );
  lines.push(j("why_existing_labels_fail", card?.comparison?.why_existing_labels_fail));
  return lines.join("\n");
}

function runCanonicalStage() {
  const s = getSample();
  if (!els.canonicalInput.value.trim()) {
    els.canonicalInput.value = pretty(s.case_card || {});
  }
  let card = s.case_card || {};
  try {
    card = JSON.parse(els.canonicalInput.value);
  } catch (_e) {}
  els.canonicalOut.textContent = canonicalizeCaseCardLikePipeline(card) || "(No canonical text)";
}

function runNoveltyStage() {
  const s = getSample();
  if (!els.noveltyInput.value.trim()) {
    els.noveltyInput.value = pretty(s.novelty_input_bundle || {});
  }
  let bundle = s.novelty_input_bundle || {};
  try {
    bundle = JSON.parse(els.noveltyInput.value);
  } catch (_e) {}
  const d = s.novelty_decision || {};
  const top = ((bundle.retrieval || {}).pattern_hits || s.retrieval_pattern_hits || []).slice(0, 3);
  const closest = d.closest_pattern || d.suspected_pattern || "(none)";
  const patternCard = (state.data.patterns || []).find((p) => p.pattern_id === closest) || null;
  els.assignedPattern.innerHTML = `
    <strong>Closest/Suspected Pattern:</strong> ${closest}<br>
    <strong>Verdict:</strong> ${d.verdict || "unknown"}<br>
    <strong>Top retrieval hits:</strong> ${top.map((x) => `${x.id} (${Number(x.score || 0).toFixed(3)})`).join(", ") || "none"}
  `;
  els.patternCardOut.textContent = patternCard ? pretty(patternCard) : "Pattern card not found for this case.";
  els.noveltyOut.textContent = pretty(d);
}

function runOriginBonusStage() {
  const s = getSample();
  if (!els.originBonusInput.value.trim()) {
    els.originBonusInput.value = pretty(s.thread_json || {});
  }
  const out = s.ai_written_judge_bonus || s.origin_gate_pre || {
    verdict: "unknown",
    llm_written_extent: "unknown",
    confidence: 0,
    rationale: "No AI-written assessment found in this sample.",
  };
  els.originBonusOut.textContent = pretty(out);
}

async function load() {
  const res = await fetch(DATA_URL, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load ${DATA_URL}: ${res.status}`);
  state.data = await res.json();
  renderMetrics();
  renderStageModelInfo();
  renderSampleSelect();
  stageReset();
  els.exaInput.value = pretty(state.data.exa.criteria_template || {});
  runExaStage();
}

els.sampleSelect.addEventListener("change", () => {
  state.selectedCaseId = els.sampleSelect.value;
});

els.useSampleEverywhereBtn.addEventListener("click", () => {
  const s = getSample();
  els.sampleTextInput.value = pretty(s.thread_json || {});
  els.canonicalInput.value = pretty(s.case_card || {});
  els.noveltyInput.value = pretty(s.novelty_input_bundle || {});
  els.originBonusInput.value = pretty(s.thread_json || {});
  runCaseStage();
  runCanonicalStage();
  runNoveltyStage();
  runOriginBonusStage();
});
els.openSampleSourceBtn.addEventListener("click", openSampleSource);

els.runExaBtn.addEventListener("click", runExaStage);
els.useExaInputBtn.addEventListener("click", () => {
  els.exaInput.value = pretty(state.data.exa.criteria_template || {});
  runExaStage();
});
els.runCaseBtn.addEventListener("click", runCaseStage);
els.useSampleInputBtn.addEventListener("click", () => {
  const s = getSample();
  els.sampleTextInput.value = pretty(s.thread_json || {});
  runCaseStage();
});
els.runCanonicalBtn.addEventListener("click", runCanonicalStage);
els.useCanonicalInputBtn.addEventListener("click", () => {
  const s = getSample();
  els.canonicalInput.value = pretty(s.case_card || {});
  runCanonicalStage();
});
els.runNoveltyBtn.addEventListener("click", runNoveltyStage);
els.useNoveltyInputBtn.addEventListener("click", () => {
  const s = getSample();
  els.noveltyInput.value = pretty(s.novelty_input_bundle || {});
  runNoveltyStage();
});
els.runOriginBonusBtn.addEventListener("click", runOriginBonusStage);
els.useOriginBonusInputBtn.addEventListener("click", () => {
  const s = getSample();
  els.originBonusInput.value = pretty(s.thread_json || {});
  runOriginBonusStage();
});
document.querySelectorAll("[data-prompt]").forEach((btn) => {
  btn.addEventListener("click", () => showPrompt(btn.getAttribute("data-prompt")));
});
els.closeModalBtn.addEventListener("click", hidePrompt);
els.promptModal.addEventListener("click", (e) => {
  if (e.target === els.promptModal) hidePrompt();
});

load().catch((e) => {
  stageReset();
  els.exaSummary.textContent = e.message;
});
