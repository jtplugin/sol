#!/usr/bin/env python3
"""Generate SOL test dashboard: HTML shell + tests/results/assets/{dashboard.css,dashboard.js}."""

import csv
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT    = Path(__file__).resolve().parent.parent
DEFAULT_INDEX  = REPO_ROOT / "tests" / "results" / "index.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "tests" / "results" / "dashboard.html"
DEFAULT_CSV    = REPO_ROOT / "tests" / "results" / "index.csv"
ASSETS_DIR     = REPO_ROOT / "tests" / "results" / "assets"

# ── CSS ──────────────────────────────────────────────────────────────────────

DASHBOARD_CSS = """\
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; background: #0f1117; color: #e2e8f0; min-height: 100vh; }
header { background: #1a1d27; border-bottom: 1px solid #2d3748; padding: 1.25rem 2rem; display: flex; align-items: center; gap: 1rem; }
header h1 { font-size: 1.35rem; font-weight: 700; color: #fff; letter-spacing: -0.02em; }
header .sub { font-size: 0.78rem; color: #718096; margin-top: 0.15rem; }
.badge { background: #2d3748; color: #90cdf4; font-size: 0.7rem; font-weight: 600; padding: 0.2rem 0.55rem; border-radius: 999px; }

/* sticky filter bar */
.filter-bar {
  position: sticky; top: 0; z-index: 100;
  background: #1a1d27; border-bottom: 1px solid #2d3748;
  padding: 0.6rem 2rem; display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center;
}
.filter-bar select, .filter-bar input[type=text] {
  background: #0f1117; border: 1px solid #2d3748; color: #e2e8f0;
  border-radius: 6px; padding: 0.3rem 0.6rem; font-size: 0.78rem; outline: none;
}
.filter-bar select:focus, .filter-bar input[type=text]:focus { border-color: #63b3ed; }
.filter-bar input[type=text] { width: 200px; }
.filter-bar .sep { width: 1px; height: 1.2rem; background: #2d3748; margin: 0 0.25rem; }
#row-count { font-size: 0.72rem; color: #4a5568; margin-left: auto; white-space: nowrap; }
.btn-reset {
  background: none; border: 1px solid #2d3748; color: #718096; border-radius: 6px;
  padding: 0.3rem 0.65rem; font-size: 0.75rem; cursor: pointer;
}
.btn-reset:hover { border-color: #63b3ed; color: #63b3ed; }

main { padding: 1.5rem 2rem; max-width: 1400px; margin: 0 auto; }

/* KPI cards */
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
.card { background: #1a1d27; border: 1px solid #2d3748; border-radius: 10px; padding: 1.1rem 1.25rem; }
.card .label { font-size: 0.72rem; color: #718096; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.4rem; }
.card .value { font-size: 2rem; font-weight: 700; line-height: 1; }
.card .value.green  { color: #68d391; }
.card .value.blue   { color: #63b3ed; }
.card .value.yellow { color: #f6e05e; }
.card .value.white  { color: #fff; }
.card .hint { font-size: 0.7rem; color: #4a5568; margin-top: 0.3rem; min-height: 1rem; }

/* charts */
.charts { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; margin-bottom: 2rem; }
.charts.three { grid-template-columns: 1fr 1fr 1fr; }
@media (max-width: 900px) { .charts, .charts.three { grid-template-columns: 1fr; } }
.chart-box { background: #1a1d27; border: 1px solid #2d3748; border-radius: 10px; padding: 1.25rem; }
.chart-box h2 { font-size: 0.85rem; font-weight: 600; color: #a0aec0; margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 0.05em; }
.chart-wrap { position: relative; height: 220px; }

/* table */
.table-section { background: #1a1d27; border: 1px solid #2d3748; border-radius: 10px; padding: 1.25rem; }
.table-section h2 { font-size: 0.85rem; font-weight: 600; color: #a0aec0; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1rem; }
.tbl-wrap { overflow-x: auto; max-height: 480px; overflow-y: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
thead th {
  background: #0f1117; color: #718096; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.05em; padding: 0.55rem 0.75rem; text-align: left;
  position: sticky; top: 0; z-index: 1; border-bottom: 1px solid #2d3748; white-space: nowrap;
}
tbody tr { border-bottom: 1px solid #1e2535; transition: background 0.1s; }
tbody tr:hover { background: #202535; }
tbody td { padding: 0.5rem 0.75rem; white-space: nowrap; }
.chip { display: inline-block; font-size: 0.68rem; font-weight: 600; padding: 0.15rem 0.5rem; border-radius: 999px; }
.chip.pass  { background: #1c3a27; color: #68d391; }
.chip.fail  { background: #3b1c1c; color: #fc8181; }
.chip.error { background: #3b2c1c; color: #fbd38d; }
.chip.done  { background: #1a2840; color: #63b3ed; }
.chip.nc    { background: #2a2a3a; color: #718096; }
.chip.none  { background: #1a2535; color: #4a5568; }
footer { text-align: center; padding: 1.5rem; font-size: 0.72rem; color: #2d3748; }

/* detail panel */
.detail-row td { padding: 0 !important; }
.detail-panel {
  background: #12151f; border-top: 1px solid #2d3748; border-bottom: 2px solid #3d4f6e;
  padding: 1rem 1.25rem; display: none;
}
.detail-panel.open { display: block; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
@media (max-width: 900px) { .detail-grid { grid-template-columns: 1fr; } }
.detail-section { background: #1a1d27; border: 1px solid #2d3748; border-radius: 8px; padding: 0.9rem 1rem; }
.detail-section.full { grid-column: 1 / -1; }
.detail-label { font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: #63b3ed; margin-bottom: 0.5rem; }
.detail-pre { font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 0.72rem; color: #cbd5e0; white-space: pre-wrap; word-break: break-word; max-height: 260px; overflow-y: auto; }
.mermaid-wrap { overflow-x: auto; }
.mermaid { min-height: 60px; }
tbody tr.clickable { cursor: pointer; }
tbody tr.active-row { background: #1a2840 !important; }
"""

# ── JS ────────────────────────────────────────────────────────────────────────

DASHBOARD_JS = """\
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
    ? d.request_messages.map(m => '[' + m.role + ']\\n' + (typeof m.content === 'string' ? m.content : JSON.stringify(m.content, null, 2))).join('\\n\\n---\\n\\n')
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
"""

# ── HTML shell ────────────────────────────────────────────────────────────────

def load_runs(index_path: Path) -> list[dict]:
    runs = []
    with open(index_path) as f:
        for line in f:
            line = line.strip()
            if line:
                runs.append(json.loads(line))
    return runs


def load_score_file(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    run_id = data.get("run_id", "")
    if not run_id:
        return None
    q   = data.get("quality")
    f   = data.get("fidelity")
    eff = data.get("efficiency", {})
    return {
        "run_id": run_id, "timestamp": "",
        "fixture_id": data.get("fixture_id", ""),
        "staged_input_id": data.get("staged_input_id", ""),
        "context": data.get("context", ""),
        "model_id": data.get("model_id", ""),
        "spec_version": "", "env_realization": "", "runner_type": "", "status": "",
        "quality":  q.get("result", "") if isinstance(q, dict) else (q or ""),
        "fidelity": f.get("result", "") if isinstance(f, dict) else (f or ""),
        "degradation_mode": data.get("degradation_mode", ""),
        "wall_clock_ms": eff.get("wall_clock_ms", "") if isinstance(eff, dict) else "",
        "tokens_in":  eff.get("tokens_in",  "") if isinstance(eff, dict) else "",
        "tokens_out": eff.get("tokens_out", "") if isinstance(eff, dict) else "",
        "api_base_url": "",
    }


def collect_orphan_scores(results_root: Path, known_ids: set[str]) -> list[dict]:
    orphans = []
    for score_file in results_root.rglob("*.score.json"):
        row = load_score_file(score_file)
        if row and row["run_id"] not in known_ids:
            orphans.append(row)
    return orphans


def normalise(run: dict) -> dict:
    q = run.get("quality")
    if isinstance(q, dict):
        run["quality"] = q.get("result", "unknown")
    f = run.get("fidelity")
    if isinstance(f, dict):
        run["fidelity"] = f.get("result", "unknown")
    return run


FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
RESULTS_DIR  = REPO_ROOT / "tests" / "results"


def _load_detail_data(runs: list[dict]) -> dict:
    detail: dict = {}
    fixture_cache: dict = {}

    for r in runs:
        run_id     = r.get("run_id", "")
        fixture_id = r.get("fixture_id", "")
        input_id   = r.get("staged_input_id", "")
        context    = r.get("context", "E0")
        model_id   = r.get("model_id", "").replace("/", "_").replace(":", "_")
        spec_ver   = r.get("spec_version", "0.6") or "0.6"
        safe_ctx   = context.replace("+", "plus")

        result_path = (RESULTS_DIR / fixture_id / safe_ctx / model_id / spec_ver / f"{run_id}.json")
        request_messages: list = []
        output_raw: str = ""
        output_payload = None

        if result_path.exists():
            try:
                data = json.loads(result_path.read_text(encoding="utf-8"))
                request_messages = data.get("trace", {}).get("request_messages", [])
                output_raw       = data.get("output", {}).get("raw", "")
                output_payload   = data.get("output", {}).get("returned_payload")
            except Exception:
                pass

        input_data = None
        if fixture_id and input_id:
            input_path = FIXTURES_DIR / fixture_id / "inputs" / f"{input_id}.json"
            if input_path.exists():
                try:
                    input_data = json.loads(input_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

        mermaid_text = fixture_cache.get(fixture_id, {}).get("mmd")
        if mermaid_text is None and fixture_id:
            fix_dir = FIXTURES_DIR / fixture_id
            mmd_files = list(fix_dir.glob("*.mmd"))
            if mmd_files:
                try:
                    mermaid_text = mmd_files[0].read_text(encoding="utf-8")
                except Exception:
                    mermaid_text = ""
            else:
                mermaid_text = ""
            fixture_cache.setdefault(fixture_id, {})["mmd"] = mermaid_text

        detail[run_id] = {
            "request_messages": request_messages,
            "output_raw":       output_raw,
            "output_payload":   output_payload,
            "input_data":       input_data,
            "mermaid":          mermaid_text or "",
        }

    return detail


def build_html(runs: list[dict]) -> str:
    runs = [normalise(r) for r in runs]
    detail_data = _load_detail_data(runs)

    table_rows = []
    for r in runs:
        ts = r.get("timestamp", "")
        try:
            ts_fmt = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            ts_fmt = ts
        wc = r.get("wall_clock_ms")
        table_rows.append({
            "run_id":  r.get("run_id", ""),
            "fixture": r.get("fixture_id", ""),
            "input":   r.get("staged_input_id", ""),
            "model":   r.get("model_id", ""),
            "status":  r.get("status", ""),
            "quality": r.get("quality", ""),
            "fidelity":r.get("fidelity", ""),
            "deg":     r.get("degradation_mode", ""),
            "env":     r.get("env_realization", ""),
            "ctx":     r.get("context", ""),
            "ts":      ts_fmt,
            "wall":    f"{wc/1000:.1f}s" if wc else "—",
            "tokens_in":  r.get("tokens_in", ""),
            "tokens_out": r.get("tokens_out", ""),
        })

    table_rows_json  = json.dumps(table_rows)
    detail_data_json = json.dumps(detail_data)
    generated_at     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total            = len(runs)

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SOL Test Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<link rel="stylesheet" href="assets/dashboard.css">
</head>
<body>

<header>
  <div>
    <h1>SOL Test Dashboard</h1>
    <div class="sub">Generated {generated_at} &nbsp;·&nbsp; {total} runs &nbsp;·&nbsp; source: tests/results/index.jsonl</div>
  </div>
  <span class="badge">v0.6</span>
</header>

<!-- ── sticky filter bar ── -->
<div class="filter-bar">
  <select id="fWorkflow" title="Workflow"></select>
  <select id="fFixture"  title="Fixture"></select>
  <select id="fInput"    title="Input"></select>
  <div class="sep"></div>
  <select id="fModel"   title="Model"></select>
  <select id="fQuality" title="Quality">
    <option value="">All quality</option>
    <option value="pass">pass</option>
    <option value="fail">fail</option>
  </select>
  <select id="fStatus" title="Status">
    <option value="">All status</option>
    <option value="done">done</option>
    <option value="error">error</option>
  </select>
  <select id="fEnv" title="Env"></select>
  <div class="sep"></div>
  <input id="fSearch" type="text" placeholder="Search run id / fixture / input…">
  <button id="btnReset" class="btn-reset">Reset</button>
  <span id="row-count"></span>
</div>

<main>

<!-- ── KPI cards ── -->
<div class="cards">
  <div class="card">
    <div class="label">Total runs</div>
    <div class="value white" id="kpi-total">—</div>
  </div>
  <div class="card">
    <div class="label">Quality pass</div>
    <div class="value green" id="kpi-qpct">—</div>
    <div class="hint" id="kpi-qhint"></div>
  </div>
  <div class="card">
    <div class="label">Fidelity pass</div>
    <div class="value blue" id="kpi-fpct">—</div>
    <div class="hint" id="kpi-fhint"></div>
  </div>
  <div class="card">
    <div class="label">Models tested</div>
    <div class="value yellow" id="kpi-models">—</div>
    <div class="hint" id="kpi-model-hint"></div>
  </div>
  <div class="card">
    <div class="label">Fixtures</div>
    <div class="value white" id="kpi-fixtures">—</div>
  </div>
</div>

<!-- ── Charts row 1 ── -->
<div class="charts">
  <div class="chart-box">
    <h2>Quality pass rate by fixture</h2>
    <div class="chart-wrap"><canvas id="chartFixture"></canvas></div>
  </div>
  <div class="chart-box">
    <h2>Quality &amp; fidelity pass rate by model</h2>
    <div class="chart-wrap"><canvas id="chartModel"></canvas></div>
  </div>
</div>

<!-- ── Charts row 2 ── -->
<div class="charts three">
  <div class="chart-box">
    <h2>Runs per day</h2>
    <div class="chart-wrap"><canvas id="chartTimeline"></canvas></div>
  </div>
  <div class="chart-box">
    <h2>Degradation modes</h2>
    <div class="chart-wrap"><canvas id="chartDeg"></canvas></div>
  </div>
  <div class="chart-box">
    <h2>Environment realization</h2>
    <div class="chart-wrap"><canvas id="chartEnv"></canvas></div>
  </div>
</div>

<!-- ── Table ── -->
<div class="table-section">
  <h2>All runs</h2>
  <div class="tbl-wrap">
    <table id="mainTable">
      <thead>
        <tr>
          <th>Timestamp</th><th>Fixture</th><th>Input</th><th>Model</th>
          <th>Ctx</th><th>Env</th><th>Status</th><th>Quality</th>
          <th>Fidelity</th><th>Degradation</th><th>Wall</th>
        </tr>
      </thead>
      <tbody id="tableBody"></tbody>
    </table>
  </div>
</div>

</main>
<footer>SOL Test Dashboard &nbsp;·&nbsp; generated by scripts/dashboard.py</footer>

<script>
const ROWS   = {table_rows_json};
const DETAIL = {detail_data_json};
</script>
<script src="assets/dashboard.js"></script>
</body>
</html>
"""
    return html


# ── CSV sync ──────────────────────────────────────────────────────────────────

CSV_COLUMNS = [
    "run_id", "timestamp", "fixture_id", "staged_input_id", "context",
    "model_id", "spec_version", "env_realization", "runner_type",
    "status", "quality", "fidelity", "degradation_mode",
    "wall_clock_ms", "tokens_in", "tokens_out", "api_base_url", "reasoning_budget",
]


def sync_csv(runs: list[dict], csv_path: Path, results_root: Path) -> int:
    existing_ids: set[str] = set()
    write_header = not csv_path.exists()

    if not write_header:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_ids.add(row["run_id"])

    index_ids = {r.get("run_id", "") for r in runs}
    new_runs  = [r for r in runs if r.get("run_id", "") not in existing_ids]
    orphans   = collect_orphan_scores(results_root, existing_ids | index_ids)
    all_new   = new_runs + orphans

    if not all_new:
        return 0

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for run in all_new:
            writer.writerow({col: run.get(col, "") for col in CSV_COLUMNS})

    return len(all_new)


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SOL test results dashboard.")
    parser.add_argument("--index",  default=str(DEFAULT_INDEX),  help="Path to index.jsonl")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output HTML path")
    parser.add_argument("--csv",    default=str(DEFAULT_CSV),    metavar="PATH")
    args = parser.parse_args()

    index_path  = Path(args.index)
    output_path = Path(args.output)
    csv_path    = Path(args.csv)

    if not index_path.exists():
        print(f"Error: index file not found: {index_path}", file=sys.stderr)
        sys.exit(1)

    runs = load_runs(index_path)

    results_root = index_path.parent
    new_rows = sync_csv(runs, csv_path, results_root)
    print(f"CSV synced:           {csv_path}  (+{new_rows} new rows, {len(runs)} total)")

    # write static assets
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    (ASSETS_DIR / "dashboard.css").write_text(DASHBOARD_CSS, encoding="utf-8")
    (ASSETS_DIR / "dashboard.js").write_text(DASHBOARD_JS, encoding="utf-8")
    print(f"Assets written to:    {ASSETS_DIR}/")

    html = build_html(runs)
    output_path.write_text(html, encoding="utf-8")
    print(f"Dashboard written to: {output_path}  ({len(runs)} runs)")


if __name__ == "__main__":
    main()
