(() => {
  "use strict";
  const expanded = window.pipelineCollection === "expanded";
  const dataURL = expanded ? "./data/pipeline_demo_data_v2.json" : "./data/pipeline_demo_data.json";
  const mapURL = expanded ? "./viz-v2.html" : "./viz.html";
  const select = document.getElementById("sampleSelect");
  const stages = document.getElementById("walkthrough");
  let data;
  let graph = { cases: [] };
  let otherGraph = { cases: [] };
  let display = { cases: {}, patterns: {} };
  const pretty = value => typeof value === "string" ? value : JSON.stringify(value, null, 2);
  const human = value => String(value || "").replaceAll("_", " ");
  function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text != null) element.textContent = String(text);
    if (className) element.className = className;
    return element;
  }
  function safeURL(value) {
    try {
      const url = new URL(value);
      return ["http:", "https:"].includes(url.protocol) ? url.href : null;
    } catch { return null; }
  }
  function raw(parent, label, value) {
    if (value == null || value === "") return;
    const details = node("details", null, "raw-block");
    details.append(node("summary", label), node("pre", pretty(value), "code-box"));
    parent.append(details);
  }
  function section(title) {
    const element = node("section", null, "panel walkthrough-stage");
    element.append(node("h2", title));
    stages.append(element);
    return element;
  }
  function paragraph(parent, text, label) {
    if (!text) return;
    if (label) parent.append(node("h3", label));
    parent.append(node("p", Array.isArray(text) ? text.join(" ") : text));
  }
  const caseCopy = id => display.cases?.[id] || {};
  const patternCopy = id => display.patterns?.[id] || {};
  const caseTitle = sample => caseCopy(sample.case_id).title || sample.title || sample.case_id;
  const patternTitle = pattern => patternCopy(pattern?.pattern_id).title || human(pattern?.label || pattern?.pattern_id);
  function patternById(id) { return (data.patterns || []).find(pattern => pattern.pattern_id === id); }
  function render(sample, updateURL = true) {
    const card = sample.case_card || {};
    const copy = caseCopy(sample.case_id);
    const decision = sample.novelty_decision || {};
    const prompts = data.prompts || {};
    stages.replaceChildren();
    select.value = sample.case_id;
    document.getElementById("selectedTitle").textContent = caseTitle(sample);
    const source = document.getElementById("openSampleSource");
    const sourceURL = safeURL(sample.source_url || card.source_url);
    source.hidden = !sourceURL;
    if (sourceURL) source.href = sourceURL;
    else source.removeAttribute("href");
    const mapLink = document.getElementById("viewMap");
    const mapContainsCase = graph.cases?.some(c=>c.case_id===sample.case_id);
    const alternateContainsCase = otherGraph.cases?.some(c=>c.case_id===sample.case_id);
    mapLink.hidden = !mapContainsCase && !alternateContainsCase;
    if (!mapLink.hidden) mapLink.href = `${mapContainsCase ? mapURL : (expanded ? "./viz.html" : "./viz-v2.html")}?case=${encodeURIComponent(sample.case_id)}`;
    else mapLink.removeAttribute("href");
    if (updateURL) {
      const url = new URL(location.href);
      url.searchParams.set("case", sample.case_id);
      history.replaceState(null, "", url);
    }

    const sourceSection = section("1. Source");
    paragraph(sourceSection, copy.source_type || human(sample.curator?.source_kind) || (sourceURL ? new URL(sourceURL).hostname : "Source unavailable"));
    paragraph(sourceSection, copy.notes);
    const excerptQuote = card.evidence_spans?.find(span => span.quote)?.quote;
    if (excerptQuote) sourceSection.append(node("blockquote", excerptQuote));
    raw(sourceSection, "Full source excerpt", sample.input_post_excerpt || sample.thread_json?.body);
    raw(sourceSection, "Source JSON", sample.thread_json);
    raw(sourceSection, "Recorded source assessments", sample.risk_gate || sample.curator ? { risk_gate: sample.risk_gate, curator: sample.curator } : null);
    const batch = node("details", null, "raw-block");
    batch.append(node("summary", "Recorded batch context"));
    raw(batch, "Exa criteria", data.exa?.criteria_template || prompts.exa_search_families || prompts.exa_criteria);
    const results = data.run?.results || data.exa?.results || [];
    const resultDetails = node("details", null, "raw-block");
    resultDetails.append(node("summary", "Exa results"));
    const resultList = node("ul", null, "recorded-list");
    results.forEach(result => {
      const li = node("li");
      const resultCaseId = result.case_id || (result.thread_id ? `case-${result.thread_id}` : "");
      const title = caseCopy(resultCaseId).title || result.title || resultCaseId || "Source";
      const url = safeURL(result.url);
      const item = node(url ? "a" : "span", title);
      if (url) { item.href = url; item.target = "_blank"; item.rel = "noopener noreferrer"; }
      li.append(item);
      resultList.append(li);
    });
    resultDetails.append(resultList);
    raw(resultDetails, "Results JSON", results);
    batch.append(resultDetails);
    raw(batch, "Source report", data.run?.source_report);
    raw(batch, "Gate prompt", prompts.risk_gate);
    raw(batch, "Gate report", data.run?.gate_report);
    raw(batch, "Curator prompt", prompts.case_worthiness_curator);
    raw(batch, "Curator report", data.run?.curator_report);
    sourceSection.append(batch);

    const caseSection = section("2. Case card");
    paragraph(caseSection, copy.summary || card.summary);
    paragraph(caseSection, copy.mechanism, "Mechanism");
    paragraph(caseSection, copy.outcome, "Outcome");
    const evidence = node("details", null, "raw-block");
    evidence.append(node("summary", "Evidence"));
    (card.evidence_spans || []).forEach(span => {
      evidence.append(node("blockquote", span.quote));
      paragraph(evidence, span.why_it_matters);
    });
    caseSection.append(evidence);
    raw(caseSection, "Case-card prompt", prompts.case_card_extractor);
    raw(caseSection, "Case card JSON", card);

    const similarSection = section("3. Similar cases");
    const retrieval = sample.novelty_input_bundle?.retrieval || {};
    const caseHits = retrieval.case_hits || [];
    const ids = [...new Set([...caseHits.map(hit => hit.id || hit.case_id), ...(decision.supporting_case_ids || [])])].filter(id => id && id !== sample.case_id);
    const availableIds = ids.filter(id => graph.cases?.some(c=>c.case_id===id) || otherGraph.cases?.some(c=>c.case_id===id));
    if (availableIds.length) {
      const list = node("ul", null, "recorded-list");
      availableIds.forEach(id => {
        const related = data.samples.find(item => item.case_id === id) || graph.cases?.find(item => item.case_id === id) || otherGraph.cases?.find(item => item.case_id === id);
        const li = node("li");
        const link = node("a", caseCopy(id).title || (related ? caseTitle(related) : id));
        const destination = graph.cases?.some(c=>c.case_id===id) ? mapURL : (expanded ? "./viz.html" : "./viz-v2.html");
        link.href = `${destination}?case=${encodeURIComponent(id)}`;
        li.append(link);
        list.append(li);
      });
      similarSection.append(list);
    } else paragraph(similarSection, ids.length ? "Related cases are available in the recorded analysis below." : "No similar cases recorded.");
    const patternHits = retrieval.pattern_hits || sample.retrieval_pattern_hits || [];
    if (patternHits.length) {
      similarSection.append(node("h3", "Retrieved patterns"));
      const list = node("ul", null, "recorded-list");
      patternHits.slice(0, 3).forEach(hit => {
        const id = hit.id || hit.pattern_id;
        const pattern = patternById(id) || { pattern_id: id, label: hit.label };
        const li = node("li");
        li.append(node("strong", patternTitle(pattern)));
        paragraph(li, patternCopy(id).summary || pattern.summary);
        list.append(li);
      });
      similarSection.append(list);
    }
    raw(similarSection, "Embedding input", sample.canonical_text || card.canonical_text);
    raw(similarSection, "Embedding specification", prompts.canonicalization_spec);
    raw(similarSection, "Retrieval JSON", { case_hits: caseHits, pattern_hits: patternHits, supporting_case_ids: decision.supporting_case_ids });

    const decisionSection = section("4. Pattern decision");
    paragraph(decisionSection, human(decision.verdict || "No decision recorded"), "Recorded decision");
    const chosenId = decision.closest_pattern || decision.suspected_pattern;
    const pattern = patternById(chosenId) || (sample.pattern_card?.pattern_id === chosenId ? sample.pattern_card : null);
    paragraph(decisionSection, chosenId ? patternTitle(pattern || { pattern_id: chosenId }) : "None recorded", decision.closest_pattern ? "Recorded closest pattern" : "Recorded suspected pattern");
    if (pattern) {
      const pcopy = patternCopy(pattern.pattern_id);
      paragraph(decisionSection, pcopy.summary || pattern.summary);
      paragraph(decisionSection, pcopy.qualifies, "Qualifies when");
      paragraph(decisionSection, pcopy.boundary, "Boundary");
    }
    paragraph(decisionSection, decision.why_counterargument_fails || decision.counterargument);
    const mapPatternId = graph.cases?.find(item => item.case_id === sample.case_id)?.predicted_pattern_id;
    if (mapPatternId && mapPatternId !== chosenId) {
      paragraph(decisionSection, patternTitle(patternById(mapPatternId) || { pattern_id: mapPatternId }), "Map pattern");
    }
    raw(decisionSection, "Decision reasoning", { shared_features: decision.shared_features, differentiators: decision.differentiators, counterargument: decision.counterargument, why_counterargument_fails: decision.why_counterargument_fails });
    raw(decisionSection, "Router prompt", prompts.novelty_router);
    raw(decisionSection, "Judge prompt", prompts.novelty_judge || prompts.novelty_and_pattern_fit);
    raw(decisionSection, "Recorded model inputs", sample.novelty_input_bundle);
    raw(decisionSection, "Pattern card JSON", pattern);
    raw(decisionSection, "Novelty decision JSON", decision);
    raw(decisionSection, "Additional analysis", sample.ai_written_judge_bonus || sample.origin_gate_pre);
  }
  async function load() {
    const [response, overrides, mapData, alternateData] = await Promise.all([
      fetch(dataURL),
      fetch("./data/display_content.json").then(res => res.ok ? res.json() : {}).catch(() => ({})),
      fetch(expanded ? "./data/case_graph_data_v2.json" : "./data/case_graph_data.json").then(res => res.ok ? res.json() : {}).catch(() => ({})),
      fetch(expanded ? "./data/case_graph_data.json" : "./data/case_graph_data_v2.json").then(res => res.ok ? res.json() : {}).catch(() => ({})),
    ]);
    if (!response.ok) throw new Error("Saved walkthrough unavailable.");
    data = await response.json();
    display = overrides || display;
    graph = mapData || graph;
    otherGraph = alternateData || otherGraph;
    if (!data.samples?.length) throw new Error("No recorded samples available.");
    select.replaceChildren();
    data.samples.forEach(sample => {
      const option = node("option", caseTitle(sample));
      option.value = sample.case_id;
      select.append(option);
    });
    select.disabled = false;
    const requested = new URLSearchParams(location.search).get("case");
    render(data.samples.find(sample => sample.case_id === requested) || data.samples[0]);
    select.addEventListener("change", () => render(data.samples.find(sample => sample.case_id === select.value) || data.samples[0]));
    window.addEventListener("popstate", () => {
      const id = new URLSearchParams(location.search).get("case");
      render(data.samples.find(sample => sample.case_id === id) || data.samples[0], false);
    });
  }
  load().catch(error => {
    document.getElementById("selectedTitle").textContent = error.message;
    select.disabled = true;
  });
})();
