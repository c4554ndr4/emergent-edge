'use strict';
const $ = (selector) => document.querySelector(selector);
let data, activeTopic = 'all', returnFocus;
const make = (tag, className, text) => { const el = document.createElement(tag); if (className) el.className = className; if (text !== undefined) el.textContent = text; return el; };
const topicLabel = (id) => data.topics.find(topic => topic.id === id)?.label || id;
function renderTopics() {
  const topics = [{id:'all',label:'All cases'}, ...data.topics];
  $('#topics').replaceChildren(...topics.map(topic => {
    const button = make('button','topic');
    button.setAttribute('aria-pressed', String(activeTopic === topic.id));
    button.append(make('span','',topic.label), make('span','',topic.id === 'all' ? data.cases.length : data.cases.filter(c => c.topic === topic.id).length));
    button.addEventListener('click', () => { activeTopic = topic.id; renderTopics(); renderCases(); $('#topics').querySelectorAll('button')[topics.indexOf(topic)].focus(); });
    return button;
  }));
}
function renderCases() {
  const query = $('#search').value.trim().toLocaleLowerCase();
  const cases = data.cases.filter(c => (activeTopic === 'all' || c.topic === activeTopic) && [c.id,c.title,c.summary,c.mechanism,c.context,c.sourceKind,topicLabel(c.topic),...c.tags].join(' ').toLocaleLowerCase().includes(query));
  $('#cards').replaceChildren(...cases.map(c => {
    const button = make('button','card');
    button.setAttribute('aria-label', `Open case ${c.id}: ${c.title}`);
    const meta = make('div','card-meta eyebrow'); meta.append(make('span','',topicLabel(c.topic)), make('span','',c.id));
    const bottom = make('div','card-bottom'); const arrow = make('span','arrow','↗'); arrow.setAttribute('aria-hidden','true'); bottom.append(make('span','',c.sourceKind),arrow);
    button.append(meta,make('h2','',c.title),make('p','',c.mechanism),bottom);
    button.addEventListener('click', () => openCase(c.id,button));
    return button;
  }));
  $('#empty').hidden = cases.length !== 0;
  $('#status').textContent = `${cases.length} cases`;
}
function openCase(id, opener) {
  const c = data.cases.find(item => item.id === id); if (!c) return;
  if (!$('#detail').open) returnFocus = opener || document.activeElement;
  $('#detail-meta').textContent = `${topicLabel(c.topic)} · ${c.id}`;
  const title = make('h2','',c.title); title.id = 'detail-title';
  const tags = make('div','tags'); tags.append(...c.tags.map(tag => make('span','tag',tag)));
  const content = [title,make('p','',c.summary),make('h3','','Mechanism'),make('p','',c.mechanism),make('h3','','Evidence & context'),make('p','',c.context),make('p','source-kind',c.sourceKind),tags];
  const related = data.cases.filter(item => item.topic === c.topic && item.id !== c.id).slice(0,3);
  if (related.length) {
    const links = make('div','related');
    related.forEach(item => { const button = make('button','',item.title); button.addEventListener('click', () => openCase(item.id)); links.append(button); });
    content.push(make('h3','','Related cases'),links);
  }
  $('#detail-content').replaceChildren(...content);
  if (!$('#detail').open) $('#detail').showModal();
  $('#detail').scrollTop = 0; $('#detail .close').focus();
  history.replaceState(null,'',`#${id}`);
}
for (const dialog of document.querySelectorAll('dialog')) {
  dialog.querySelector('.close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target !== dialog) return; const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close(); });
}
$('#detail').addEventListener('close', () => { history.replaceState(null,'',location.pathname + location.search); if (returnFocus?.isConnected) returnFocus.focus(); });
$('#about-open').addEventListener('click', () => $('#about').showModal());
$('#search').addEventListener('input', () => { if(data) renderCases(); });
$('#clear').addEventListener('click', () => { activeTopic = 'all'; $('#search').value = ''; renderTopics(); renderCases(); $('#search').focus(); });
window.addEventListener('hashchange', () => { if (data && /^#EE-\d+$/.test(location.hash)) openCase(location.hash.slice(1)); });
fetch('/data/cases.json').then(response => { if (!response.ok) throw new Error('Failed to load'); return response.json(); }).then(result => {
  if (!Array.isArray(result.cases) || !Array.isArray(result.topics)) throw new Error('Invalid cases');
  data = result; $('#total').textContent = data.cases.length; renderTopics(); renderCases();
  if (/^#EE-\d+$/.test(location.hash)) openCase(location.hash.slice(1));
}).catch(() => { $('#error').hidden = false; $('.collection').hidden = true; $('#search').disabled = true; });
