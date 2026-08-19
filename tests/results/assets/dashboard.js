/* SOL Test Dashboard — reactive filter engine */

// derive workflow from fixture id (first hyphen-segment: w1, w2, w3…)
ROWS.forEach(r => { r.workflow = r.fixture ? r.fixture.split('-')[0] : ''; });

mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose' });

// ── colour helpers ────────────────────────────────────────────────────────────
const CHART_COLORS = ['#63b3ed','#68d391','#f6ad55','#fc8181','#b794f4','#76e4f7','#fbd38d','#9ae6b4'];
function chipClass(val) {
  if (val === 'pass')          return 'pass';
  if (val === 'fail')          return 'fail';
  if (val === 'error')         return 'error';
  if (val === 'done')          return 'done';
  if (val === 'not_checkable') return 'nc';
  if (val === 'none')          return 'none';
  return '';
}

Chart.defaults.color = '#718096';
Chart.defaults.borderColor = '#2d3748';
Chart.defaults.font.family = 'system-ui, -apple-system, sans-serif';

// ── filter elements ───────────────────────────────────────────────────────────
const fWorkflow = document.getElementById('fWorkflow');
const fFixture  = document.getElementById('fFixture');
const fInput    = document.getElementById('fInput');
const fModel    = document.getElementById('fModel');
const fQuality  = document.getElementById('fQuality');
const fStatus   = document.getElementById('fStatus');
const fEnv      = document.getElementById('fEnv');
const fSearch   = document.getElementById('fSearch');
const rowCount  = document.getElementById('row-count');
const tbody     = document.getElementById('tableBody');

function populateSelect(sel, values, allLabel) {
  const cur = sel.value;
  sel.innerHTML = `<option value="">${allLabel}</option>`;
  values.forEach(v => {
    const o = document.createElement('option');
    o.value = o.textContent = v;
    if (v === cur) o.selected = true;
    sel.appendChild(o);
  });
}

function populateWorkflows() {
  const wfs = [...new Set(ROWS.map(r => r.workflow))].filter(Boolean).sort();
  populateSelect(fWorkflow, wfs, 'All W');
}

function populateFixtures() {
  const wf = fWorkflow.value;
  const fixtures = [...new Set(
    ROWS.filter(r => !wf || r.workflow === wf).map(r => r.fixture)
  )].filter(Boolean).sort();
  populateSelect(fFixture, fixtures, 'All fixtures');
}

function populateInputs() {
  const wf  = fWorkflow.value;
  const fix = fFixture.value;
  const inputs = [...new Set(
    ROWS.filter(r => (!wf || r.workflow === wf) && (!fix || r.fixture === fix))
        .map(r => r.input)
  )].filter(Boolean).sort();
  populateSelect(fInput, inputs, 'All inputs');
}

function populateModels() {
  const models = [...new Set(ROWS.map(r => r.model))].filter(Boolean).sort();
  populateSelect(fModel, models, 'All models');
}

function populateEnvs() {
  const envs = [...new Set(ROWS.map(r => r.env))].filter(Boolean).sort();
  populateSelect(fEnv, envs, 'All envs');
}

// ── get filtered rows ─────────────────────────────────────────────────────────
function getFiltered() {
  const search  = fSearch.value.toLowerCase();
  const wf      = fWorkflow.value;
  const fix     = fFixture.value;
  const inp     = fInput.value;
  const model   = fModel.value;
  const quality = fQuality.value;
  const status  = fStatus.value;
  const env     = fEnv.value;
  return ROWS.filter(r =>
    (!wf      || r.workflow === wf) &&
    (!fix     || r.fixture  === fix) &&
    (!inp     || r.input    === inp) &&
    (!model   || r.model    === model) &&
    (!quality || r.quality  === quality) &&
    (!status  || r.status   === status) &&
    (!env     || r.env      === env) &&
    (!search  || r.run_id.toLowerCase().includes(search)
              || r.fixture.toLowerCase().includes(search)
              || r.input.toLowerCase().includes(search))
  );
}

// ── KPI update ────────────────────────────────────────────────────────────────
function updateKPIs(filtered) {
  const total  = filtered.length;
  const qPass  = filtered.filter(r => r.quality  === 'pass').length;
  const fPass  = filtered.filter(r => r.fidelity === 'pass').length;
  const fCheck = filtered.filter(r => r.fidelity === 'pass' || r.fidelity === 'fail').length;
  const models   = [...new Set(filtered.map(r => r.model))].filter(Boolean);
  const fixtures = [...new Set(filtered.map(r => r.fixture))].filter(Boolean);

  document.getElementById('kpi-total').textContent      = total;
  document.getElementById('kpi-qpct').textContent       = total  ? (qPass/total*100).toFixed(1)+'%' : '—';
  document.getElementById('kpi-qhint').textContent      = `${qPass} / ${total}`;
  document.getElementById('kpi-fpct').textContent       = fCheck ? (fPass/fCheck*100).toFixed(1)+'%' : '—';
  document.getElementById('kpi-fhint').textContent      = `${fPass} / ${fCheck} checkable`;
  document.getElementById('kpi-models').textContent     = models.length;
  document.getElementById('kpi-model-hint').textContent = models.map(m => m.split('/').pop().split('-').pop()).join(', ');
  document.getElementById('kpi-fixtures').textContent   = fixtures.length;
}

// ── chart data helpers ────────────────────────────────────────────────────────
function fixtureData(filtered) {
  const s = {};
  filtered.forEach(r => {
    if (!s[r.fixture]) s[r.fixture] = { total: 0, pass: 0 };
    s[r.fixture].total++;
    if (r.quality === 'pass') s[r.fixture].pass++;
  });
  const labels = Object.keys(s).sort();
  return {
    labels,
    rates:  labels.map(k => s[k].total ? +( s[k].pass / s[k].total * 100).toFixed(1) : 0),
    counts: labels.map(k => s[k].total),
  };
}

function modelData(filtered) {
  const s = {};
  filtered.forEach(r => {
    if (!s[r.model]) s[r.model] = { total: 0, qPass: 0, fPass: 0, fTotal: 0 };
    s[r.model].total++;
    if (r.quality  === 'pass') s[r.model].qPass++;
    if (r.fidelity === 'pass' || r.fidelity === 'fail') {
      s[r.model].fTotal++;
      if (r.fidelity === 'pass') s[r.model].fPass++;
    }
  });
  const labels = Object.keys(s).sort();
  return {
    labels,
    qRates: labels.map(k => s[k].total  ? +(s[k].qPass / s[k].total  * 100).toFixed(1) : 0),
    fRates: labels.map(k => s[k].fTotal ? +(s[k].fPass / s[k].fTotal * 100).toFixed(1) : null),
  };
}

function dayData(filtered) {
  const s = {};
  filtered.forEach(r => {
    let day = 'unknown';
    try { day = r.ts.slice(0, 10); } catch(e) {}
    if (!s[day]) s[day] = { total: 0, pass: 0 };
    s[day].total++;
    if (r.quality === 'pass') s[day].pass++;
  });
  const labels = Object.keys(s).filter(d => d !== 'unknown').sort();
  return {
    labels,
    totals: labels.map(d => s[d].total),
    passes: labels.map(d => s[d].pass),
    fails:  labels.map(d => s[d].total - s[d].pass),
  };
}

function degData(filtered) {
  const s = {};
  filtered.forEach(r => { const k = r.deg || 'unknown'; s[k] = (s[k]||0) + 1; });
  const labels = Object.keys(s).sort();
  return { labels, values: labels.map(k => s[k]) };
}

function envData(filtered) {
  const s = {};
  filtered.forEach(r => { const k = r.env || 'unknown'; s[k] = (s[k]||0) + 1; });
  const labels = Object.keys(s).sort();
  return { labels, values: labels.map(k => s[k]) };
}

// ── chart instances ───────────────────────────────────────────────────────────
let chartFixture, chartModel, chartTimeline, chartDeg, chartEnv;

function initCharts() {
  chartFixture = new Chart(document.getElementById('chartFixture'), {
    type: 'bar',
    data: { labels: [], datasets: [{ label: 'Quality pass %', data: [], backgroundColor: '#63b3ed', borderRadius: 4 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: {
        callbacks: { label: ctx => ` ${ctx.parsed.y}%  (${(chartFixture._counts||[])[ctx.dataIndex] ?? '?'} runs)` }
      }},
      scales: { y: { min: 0, max: 100, ticks: { callback: v => v+'%' } }, x: { ticks: { maxRotation: 30 } } }
    }
  });

  chartModel = new Chart(document.getElementById('chartModel'), {
    type: 'bar',
    data: { labels: [], datasets: [
      { label: 'Quality %',  data: [], backgroundColor: '#68d391', borderRadius: 4 },
      { label: 'Fidelity %', data: [], backgroundColor: '#63b3ed', borderRadius: 4 },
    ]},
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { boxWidth: 12, font: { size: 11 } } } },
      scales: { y: { min: 0, max: 100, ticks: { callback: v => v+'%' } }, x: { ticks: { maxRotation: 30 } } }
    }
  });

  chartTimeline = new Chart(document.getElementById('chartTimeline'), {
    type: 'bar',
    data: { labels: [], datasets: [
      { label: 'Pass',  data: [], backgroundColor: '#68d391', stack: 's', borderRadius: 2 },
      { label: 'Other', data: [], backgroundColor: '#fc8181', stack: 's', borderRadius: 2 },
    ]},
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { boxWidth: 12, font: { size: 11 } } } },
      scales: { x: { stacked: true, ticks: { maxRotation: 40, font: { size: 10 } } }, y: { stacked: true } }
    }
  });

  chartDeg = new Chart(document.getElementById('chartDeg'), {
    type: 'doughnut',
    data: { labels: [], datasets: [{ data: [], backgroundColor: CHART_COLORS, borderWidth: 0 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 11 } } } }
    }
  });

  chartEnv = new Chart(document.getElementById('chartEnv'), {
    type: 'doughnut',
    data: { labels: [], datasets: [{ data: [], backgroundColor: ['#b794f4','#f6ad55','#76e4f7','#68d391','#fc8181'], borderWidth: 0 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 11 } } } }
    }
  });
}

function updateCharts(filtered) {
  const fd = fixtureData(filtered);
  chartFixture._counts = fd.counts;
  chartFixture.data.labels = fd.labels;
  chartFixture.data.datasets[0].data = fd.rates;
  chartFixture.update('none');

  const md = modelData(filtered);
  chartModel.data.labels = md.labels;
  chartModel.data.datasets[0].data = md.qRates;
  chartModel.data.datasets[1].data = md.fRates;
  chartModel.update('none');

  const dd = dayData(filtered);
  chartTimeline.data.labels = dd.labels;
  chartTimeline.data.datasets[0].data = dd.passes;
  chartTimeline.data.datasets[1].data = dd.fails;
  chartTimeline.update('none');

  const dg = degData(filtered);
  chartDeg.data.labels = dg.labels;
  chartDeg.data.datasets[0].data = dg.values;
  chartDeg.update('none');

  const ed = envData(filtered);
  chartEnv.data.labels = ed.labels;
  chartEnv.data.datasets[0].data = ed.values;
  chartEnv.update('none');
}

// ── table ─────────────────────────────────────────────────────────────────────
function renderTable(filtered) {
  rowCount.textContent = filtered.length + ' / ' + ROWS.length + ' rows';
  tbody.innerHTML = filtered.map(r => `
    <tr class="clickable" data-run-id="${r.run_id}">
      <td>${r.ts}</td>
      <td>${r.fixture}</td>
      <td>${r.input}</td>
      <td>${r.model}</td>
      <td>${r.ctx}</td>
      <td>${r.env}</td>
      <td><span class="chip ${chipClass(r.status)}">${r.status}</span></td>
      <td><span class="chip ${chipClass(r.quality)}">${r.quality}</span></td>
      <td><span class="chip ${chipClass(r.fidelity)}">${r.fidelity}</span></td>
      <td><span class="chip ${chipClass(r.deg)}">${r.deg}</span></td>
      <td>${r.wall}</td>
    </tr>
    <tr class="detail-row" data-for="${r.run_id}">
      <td colspan="11"><div class="detail-panel" id="dp-${r.run_id}"></div></td>
    </tr>`).join('');
  attachRowClicks();
}

// ── detail panel ──────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function attachRowClicks() {
  document.querySelectorAll('tr.clickable').forEach(tr => {
    tr.addEventListener('click', () => toggleDetail(tr));
  });
}

function toggleDetail(tr) {
  const runId = tr.dataset.runId;
  const panel = document.getElementById('dp-' + runId);
  if (!panel) return;
  const isOpen = panel.classList.contains('open');
  document.querySelectorAll('.detail-panel.open').forEach(p => p.classList.remove('open'));
  document.querySelectorAll('tr.active-row').forEach(r => r.classList.remove('active-row'));
  if (isOpen) return;
  tr.classList.add('active-row');
  panel.classList.add('open');
  if (panel.dataset.rendered) return;
  panel.dataset.rendered = '1';

  const d = DETAIL[runId] || {};
  const inputJson  = d.input_data != null ? JSON.stringify(d.input_data, null, 2) : '(not available)';
  const reqText    = d.request_messages && d.request_messages.length
    ? d.request_messages.map(m => '[' + m.role + ']\n' + (typeof m.content === 'string' ? m.content : JSON.stringify(m.content, null, 2))).join('\n\n---\n\n')
    : '(not recorded)';
  const outputText  = d.output_raw || '(empty)';
  const payloadText = d.output_payload != null ? JSON.stringify(d.output_payload, null, 2) : '';
  const mmdId       = 'mmd-' + runId.replace(/[^a-z0-9]/gi, '_');

  panel.innerHTML = `
    <div class="detail-grid">
      ${d.mermaid ? `<div class="detail-section full">
        <div class="detail-label">Fixture diagram</div>
        <div class="mermaid-wrap"><div class="mermaid" id="${mmdId}">${escHtml(d.mermaid)}</div></div>
      </div>` : ''}
      <div class="detail-section full">
        <div class="detail-label">Input (${d.input_data != null ? Object.keys(d.input_data).join(', ') : '—'})</div>
        <pre class="detail-pre">${escHtml(inputJson)}</pre>
      </div>
      <div class="detail-section full">
        <div class="detail-label">Request sent</div>
        <pre class="detail-pre">${escHtml(reqText)}</pre>
      </div>
      <div class="detail-section${payloadText ? '' : ' full'}">
        <div class="detail-label">Raw output</div>
        <pre class="detail-pre">${escHtml(outputText)}</pre>
      </div>
      ${payloadText ? `<div class="detail-section">
        <div class="detail-label">Parsed payload</div>
        <pre class="detail-pre">${escHtml(payloadText)}</pre>
      </div>` : ''}
    </div>`;

  if (d.mermaid) {
    mermaid.render(mmdId + '_svg', d.mermaid)
      .then(result => { const el = document.getElementById(mmdId); if (el) el.innerHTML = result.svg; })
      .catch(() => {});
  }
}

// ── apply all filters ─────────────────────────────────────────────────────────
function applyFilters() {
  const filtered = getFiltered();
  updateKPIs(filtered);
  updateCharts(filtered);
  renderTable(filtered);
}

// ── cascade handlers ──────────────────────────────────────────────────────────
fWorkflow.addEventListener('change', () => {
  populateFixtures(); fFixture.value = '';
  populateInputs();   fInput.value = '';
  applyFilters();
});
fFixture.addEventListener('change', () => {
  populateInputs(); fInput.value = '';
  applyFilters();
});
[fInput, fModel, fQuality, fStatus, fEnv].forEach(el => el.addEventListener('change', applyFilters));
fSearch.addEventListener('input', applyFilters);

document.getElementById('btnReset').addEventListener('click', () => {
  fWorkflow.value = ''; populateFixtures(); fFixture.value = '';
  populateInputs();     fInput.value = '';
  fModel.value = ''; fQuality.value = ''; fStatus.value = ''; fEnv.value = ''; fSearch.value = '';
  applyFilters();
});

// ── boot ──────────────────────────────────────────────────────────────────────
populateWorkflows();
populateFixtures();
populateInputs();
populateModels();
populateEnvs();
initCharts();
applyFilters();
