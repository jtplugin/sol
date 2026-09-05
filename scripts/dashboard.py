#!/usr/bin/env python3
"""Generate SOL test dashboard: HTML shell + tests/results/assets/{dashboard.css,dashboard.js}."""

import csv
import hashlib
import json
import re
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT    = Path(__file__).resolve().parent.parent
MAIN_INDEX     = REPO_ROOT / "tests" / "results-main" / "index.jsonl"
PILOT_INDEX    = REPO_ROOT / "tests" / "results" / "index.jsonl"


def _default_index() -> Path:
    """The campaign's index once it exists, the historical one until then.

    campaign.py writes MAIN to a root of its own, so a bare `python
    scripts/dashboard.py` during or after the campaign has to land on the campaign
    -- typing it out of habit and quietly getting the pilot's 576 runs instead
    would be a trap. Whichever it picks is named in the page header and on stdout,
    so the page never misreports what it is showing, and --index overrides.
    """
    return MAIN_INDEX if MAIN_INDEX.exists() else PILOT_INDEX
# Output paths and the two roots below follow --index: main() rebinds them from the
# index's own directory, so a dashboard can be built for any results root.
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
.glossary { background: #1a1d27; border: 1px solid #2d3748; border-radius: 10px; margin-bottom: 2rem; }
.glossary > summary { cursor: pointer; padding: 1rem 1.25rem; font-size: 0.85rem; font-weight: 600; color: #a0aec0; text-transform: uppercase; letter-spacing: 0.05em; list-style: none; }
.glossary > summary::-webkit-details-marker { display: none; }
.glossary > summary::before { content: '\25B8'; display: inline-block; margin-right: 0.6rem; transition: transform 0.15s; }
.glossary[open] > summary::before { transform: rotate(90deg); }
.glossary .gbody { padding: 0 1.25rem 1.5rem; font-size: 0.82rem; line-height: 1.6; color: #cbd5e0; }
.glossary h3 { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #63b3ed; margin: 1.4rem 0 0.6rem; border-top: 1px solid #2d3748; padding-top: 1rem; }
.glossary h3:first-child { border-top: none; margin-top: 0; padding-top: 0; }
.glossary input[type=radio] { position: absolute; opacity: 0; pointer-events: none; }
.glossary .glang-tab { display: inline-block; cursor: pointer; padding: 0.25rem 0.7rem; margin: 0 0.35rem 0.9rem 0; border: 1px solid #2d3748; border-radius: 999px; font-size: 0.72rem; color: #718096; }
.glossary .glang { display: none; }
#glang-en:checked ~ .glang-en, #glang-it:checked ~ .glang-it { display: block; }
#glang-en:checked ~ [for="glang-en"], #glang-it:checked ~ [for="glang-it"] { border-color: #63b3ed; color: #63b3ed; }
.glossary h4 { font-size: 0.82rem; font-weight: 600; color: #e2e8f0; margin: 0.9rem 0 0.2rem; }
.glossary h4 + p { margin-top: 0; }
.glossary p { margin: 0 0 0.5rem; }
.glossary th { text-align: left; padding: 0.3rem 0.6rem 0.3rem 0; color: #a0aec0; font-weight: 600; border-bottom: 1px solid #2d3748; }
.glossary dl { margin: 0; }
.glossary dt { font-weight: 600; color: #e2e8f0; margin-top: 0.9rem; }
.glossary dt:first-child { margin-top: 0; }
.glossary dd { margin: 0.2rem 0 0 0; color: #a0aec0; }
.glossary code { background: #0f1117; padding: 0.1rem 0.35rem; border-radius: 3px; font-size: 0.9em; color: #90cdf4; }
.glossary b { color: #e2e8f0; }
.glossary .warn { border-left: 3px solid #f6ad55; padding-left: 0.9rem; margin: 0.8rem 0; color: #cbd5e0; }
.glossary table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
.glossary table td { padding: 0.3rem 0.6rem 0.3rem 0; vertical-align: top; border-bottom: 1px solid #22262f; }
.glossary table td:first-child { white-space: nowrap; width: 1%; }

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
const fMode      = document.getElementById('fMode');
const fRendering = document.getElementById('fRendering');
const fQuality  = document.getElementById('fQuality');
const fStatus   = document.getElementById('fStatus');
const fEnv      = document.getElementById('fEnv');
const fTraced   = document.getElementById('fTraced');
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

function populateModes() {
  const modes = [...new Set(ROWS.map(r => r.mode))].filter(Boolean).sort();
  populateSelect(fMode, modes, 'All modes');
}

function populateRenderings() {
  const rs = [...new Set(ROWS.map(r => r.rendering))].filter(Boolean).sort();
  populateSelect(fRendering, rs, 'All renderings');
}

// ── get filtered rows ─────────────────────────────────────────────────────────
function getFiltered() {
  const search  = fSearch.value.toLowerCase();
  const wf      = fWorkflow.value;
  const fix     = fFixture.value;
  const inp     = fInput.value;
  const model   = fModel.value;
  const mode      = fMode.value;
  const rendering = fRendering.value;
  const quality = fQuality.value;
  const status  = fStatus.value;
  const env     = fEnv.value;
  // '' = all, 'yes' = emitted a trace, 'no' = emitted none. The third state is
  // the one worth having: a run with no trace is unmeasurable rather than bad,
  // and granite-4.1-8b produced 35 of them out of 36 by answering with a
  // markdown table instead of the EVAL/BRANCH lines the oracle reads.
  const traced  = fTraced.value;
  return ROWS.filter(r =>
    (!wf      || r.workflow === wf) &&
    (!fix     || r.fixture  === fix) &&
    (!inp     || r.input    === inp) &&
    (!model   || r.model    === model) &&
    (!mode      || r.mode      === mode) &&
    (!rendering || r.rendering === rendering) &&
    (!quality || r.quality  === quality) &&
    (!status  || r.status   === status) &&
    (!env     || r.env      === env) &&
    (!traced  || (traced === 'yes' ? r.traced === true : r.traced === false)) &&
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
  // Mean over the runs that were scoreable, with the denominator spelled out in
  // the hint: on MAIN 203 runs of 475 emitted no trace, so a mean that quietly
  // spanned "all filtered runs" would be describing a different set every time
  // the model filter moved.
  const conds = filtered.map(r => r.cond).filter(v => typeof v === 'number');
  document.getElementById('kpi-cond').textContent       = conds.length
    ? (conds.reduce((a, b) => a + b, 0) / conds.length).toFixed(2) : '—';
  document.getElementById('kpi-cond-hint').textContent  = `${conds.length} / ${total} scored`;
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

// Quality and fidelity pass rates grouped by any row key. Used for 'model' and
// for 'rendering' -- the same counting, so it lives once. Rows whose key is empty
// (recorded before the field existed) are dropped rather than bucketed under a
// blank label.
function passRateBy(filtered, key) {
  const s = {};
  filtered.forEach(r => {
    const k = r[key];
    if (!k) return;
    if (!s[k]) s[k] = { total: 0, qPass: 0, fPass: 0, fTotal: 0 };
    s[k].total++;
    if (r.quality  === 'pass') s[k].qPass++;
    if (r.fidelity === 'pass' || r.fidelity === 'fail') {
      s[k].fTotal++;
      if (r.fidelity === 'pass') s[k].fPass++;
    }
  });
  const labels = Object.keys(s).sort();
  return {
    labels,
    qRates: labels.map(k => s[k].total  ? +(s[k].qPass / s[k].total  * 100).toFixed(1) : 0),
    fRates: labels.map(k => s[k].fTotal ? +(s[k].fPass / s[k].fTotal * 100).toFixed(1) : null),
    counts: labels.map(k => s[k].total),
  };
}

// Mean conditional fidelity and comprehension, grouped by any row key -- the
// campaign's actual metrics, where passRateBy above gives its binary ones.
//
// Runs that emitted no trace carry null on both rates and are left OUT of the
// means: counting a missing measurement as zero would blame a model for
// something never observed, and it is precisely the models that emit no trace
// whose scores would be dragged furthest. They are reported instead as their own
// bar, `Traced %`, so a cell that is unmeasurable reads as unmeasurable rather
// than as a small sample.
function meanRatesBy(filtered, key) {
  const s = {};
  filtered.forEach(r => {
    const k = r[key];
    if (!k) return;
    if (!s[k]) s[k] = { n: 0, traced: 0, cond: [], comp: [] };
    s[k].n++;
    if (r.traced) s[k].traced++;
    if (typeof r.cond === 'number') s[k].cond.push(r.cond);
    if (typeof r.comp === 'number') s[k].comp.push(r.comp);
  });
  const mean = a => a.length
    ? +(a.reduce((x, y) => x + y, 0) / a.length * 100).toFixed(1)
    : null;
  const labels = Object.keys(s).sort();
  return {
    labels,
    cond:   labels.map(k => mean(s[k].cond)),
    comp:   labels.map(k => mean(s[k].comp)),
    traced: labels.map(k => s[k].n ? +(s[k].traced / s[k].n * 100).toFixed(1) : null),
    condN:  labels.map(k => s[k].cond.length),
    counts: labels.map(k => s[k].n),
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
let chartFixture, chartModel, chartRendering, chartTimeline, chartDeg, chartEnv;
let chartRateModel, chartRateRendering;

// The 'quality % / fidelity %' pair of bars, twice: by model and by rendering.
function passRateChartConfig() {
  return {
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
  };
}

// The three bars of meanRatesBy, twice: by model and by rendering. Same shape as
// passRateChartConfig, but the tooltip has to say how many runs each mean rests
// on -- a cell where two runs out of thirty produced a scoreable trace can post a
// high mean, and without the count it reads like a result.
function rateChartConfig() {
  return {
    type: 'bar',
    data: { labels: [], datasets: [
      { label: 'Conditional fidelity %', data: [], backgroundColor: '#63b3ed', borderRadius: 4 },
      { label: 'Comprehension %',        data: [], backgroundColor: '#b794f4', borderRadius: 4 },
      { label: 'Traced %',               data: [], backgroundColor: '#4a5568', borderRadius: 4 },
    ]},
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: { callbacks: { label: ctx => {
          const c = ctx.chart._rateMeta || {};
          const i = ctx.dataIndex;
          const n = ctx.datasetIndex === 2 ? (c.counts||[])[i] : (c.condN||[])[i];
          const v = ctx.parsed.y === null ? 'n/a' : ctx.parsed.y + '%';
          return ` ${ctx.dataset.label}: ${v}  (n=${n ?? '?'})`;
        }}},
      },
      scales: { y: { min: 0, max: 100, ticks: { callback: v => v+'%' } }, x: { ticks: { maxRotation: 30 } } }
    }
  };
}

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

  chartModel     = new Chart(document.getElementById('chartModel'),     passRateChartConfig());
  chartRendering = new Chart(document.getElementById('chartRendering'), passRateChartConfig());
  chartRateModel     = new Chart(document.getElementById('chartRateModel'),     rateChartConfig());
  chartRateRendering = new Chart(document.getElementById('chartRateRendering'), rateChartConfig());

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

  const md = passRateBy(filtered, 'model');
  chartModel.data.labels = md.labels;
  chartModel.data.datasets[0].data = md.qRates;
  chartModel.data.datasets[1].data = md.fRates;
  chartModel.update('none');

  const rd = passRateBy(filtered, 'rendering');
  chartRendering.data.labels = rd.labels;
  chartRendering.data.datasets[0].data = rd.qRates;
  chartRendering.data.datasets[1].data = rd.fRates;
  chartRendering.update('none');

  [[chartRateModel, meanRatesBy(filtered, 'model')],
   [chartRateRendering, meanRatesBy(filtered, 'rendering')]].forEach(([ch, d]) => {
    ch._rateMeta = d;
    ch.data.labels = d.labels;
    ch.data.datasets[0].data = d.cond;
    ch.data.datasets[1].data = d.comp;
    ch.data.datasets[2].data = d.traced;
    ch.update('none');
  });

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
// A rate of 0 and a rate that was never measured are different findings, and the
// dash keeps them apart: 0.0 means the model was scored and got everything wrong,
// the dash means there was nothing to score.
function fmtRate(v) {
  return (typeof v === 'number') ? v.toFixed(2) : '—';
}

function renderTable(filtered) {
  rowCount.textContent = filtered.length + ' / ' + ROWS.length + ' rows';
  tbody.innerHTML = filtered.map(r => `
    <tr class="clickable" data-run-id="${r.run_id}">
      <td>${r.ts}</td>
      <td>${r.fixture}</td>
      <td>${r.input}</td>
      <td>${r.model}</td>
      <td>${r.mode || '—'}</td>
      <td>${r.rendering || '—'}</td>
      <td>${r.ctx}</td>
      <td>${r.env}</td>
      <td><span class="chip ${chipClass(r.status)}">${r.status}</span></td>
      <td><span class="chip ${chipClass(r.quality)}">${r.quality}</span></td>
      <td><span class="chip ${chipClass(r.fidelity)}">${r.fidelity}</span></td>
      <td>${fmtRate(r.cond)}</td>
      <td>${fmtRate(r.comp)}</td>
      <td><span class="chip ${chipClass(r.deg)}">${r.deg}</span></td>
      <td>${r.wall}</td>
    </tr>
    <tr class="detail-row" data-for="${r.run_id}">
      <td colspan="15"><div class="detail-panel" id="dp-${r.run_id}"></div></td>
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
  // The prompt, the staged input and the fixture diagram are the same for many
  // runs, so they live once in BLOBS and the row holds a key. Only the output is
  // per-run. See _Blobs in scripts/dashboard.py.
  const reqMsgs     = d.req     ? BLOBS[d.req]     : [];
  const inputData   = d.input   ? BLOBS[d.input]   : null;
  const mermaidText = d.mermaid ? BLOBS[d.mermaid] : '';

  const inputJson  = inputData != null ? JSON.stringify(inputData, null, 2) : '(not available)';
  const reqText    = reqMsgs && reqMsgs.length
    ? reqMsgs.map(m => '[' + m.role + ']\\n' + (typeof m.content === 'string' ? m.content : JSON.stringify(m.content, null, 2))).join('\\n\\n---\\n\\n')
    : '(not recorded)';
  const outputText  = d.output_raw || '(empty)';
  const payloadText = d.output_payload != null ? JSON.stringify(d.output_payload, null, 2) : '';
  const mmdId       = 'mmd-' + runId.replace(/[^a-z0-9]/gi, '_');

  panel.innerHTML = `
    <div class="detail-grid">
      ${mermaidText ? `<div class="detail-section full">
        <div class="detail-label">Fixture diagram</div>
        <div class="mermaid-wrap"><div class="mermaid" id="${mmdId}">${escHtml(mermaidText)}</div></div>
      </div>` : ''}
      <div class="detail-section full">
        <div class="detail-label">Input (${inputData != null ? Object.keys(inputData).join(', ') : '—'})</div>
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

  if (mermaidText) {
    mermaid.render(mmdId + '_svg', mermaidText)
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
  // Every change handler and the reset button route through here, so this is
  // the one place the saved state has to be kept in step. Reset clears every
  // control, which saves an empty state and drops the fragment -- no separate
  // "forget" path to keep correct.
  saveFilters();
}

// ── filter persistence ────────────────────────────────────────────────────────
// campaign.py rewrites this file after every row, so watching a run means
// reloading it constantly -- and a filter that dies on F5 makes the dashboard
// useless at exactly the moment it is worth having. State is written to the URL
// fragment, which survives a reload everywhere and travels if the URL is copied
// or bookmarked, and to localStorage, which survives closing the file and
// opening it again from disk.
//
// Both are best-effort and neither may throw: a file:// page is a hostile
// storage origin -- some browsers refuse localStorage on it outright, and
// history.replaceState can raise SecurityError -- and a dashboard that fails to
// render because it could not remember a dropdown is a worse dashboard than one
// that forgets.
const FILTER_KEY = 'sol-dashboard-filters';
const FILTER_ELS = {
  wf: fWorkflow, fix: fFixture, inp: fInput, model: fModel, mode: fMode,
  rend: fRendering, q: fQuality, st: fStatus, env: fEnv, tr: fTraced, s: fSearch,
};

function saveFilters() {
  const state = {};
  for (const k in FILTER_ELS) { const v = FILTER_ELS[k].value; if (v) state[k] = v; }
  const encoded = new URLSearchParams(state).toString();
  // replaceState, not `location.hash = ...`: the search box saves on every
  // keystroke, and assigning the hash would push a history entry per character.
  try {
    history.replaceState(null, '', encoded ? '#' + encoded : location.href.split('#')[0]);
  } catch (e) { /* file:// may refuse; localStorage still gets it */ }
  try { localStorage.setItem(FILTER_KEY, JSON.stringify(state)); } catch (e) {}
}

function readSavedFilters() {
  // The fragment wins when present: it is what a reload carries, and what the
  // reader chose if they pasted a URL. localStorage is the fallback for a file
  // opened fresh, with no fragment on it.
  const hash = location.hash.replace(/^#/, '');
  if (hash) {
    const out = {};
    new URLSearchParams(hash).forEach((v, k) => { out[k] = v; });
    return out;
  }
  try { return JSON.parse(localStorage.getItem(FILTER_KEY) || '{}') || {}; }
  catch (e) { return {}; }
}

// Cascade order matters: the fixture list depends on the chosen workflow and
// the input list on the chosen fixture, so each list is rebuilt before the next
// value is set. A saved value whose option no longer exists -- a fixture that
// left the index, an input filtered out by a narrower workflow -- is dropped
// rather than forced, which leaves the filter at 'all' instead of at a value
// that would match no row.
function restoreFilters() {
  const s = readSavedFilters();
  const set = (el, v) => {
    if (v && Array.prototype.some.call(el.options, o => o.value === v)) el.value = v;
  };
  set(fWorkflow, s.wf);
  populateFixtures(); set(fFixture, s.fix);
  populateInputs();   set(fInput, s.inp);
  set(fModel, s.model); set(fMode, s.mode); set(fRendering, s.rend);
  set(fQuality, s.q);   set(fStatus, s.st); set(fEnv, s.env); set(fTraced, s.tr);
  if (s.s) fSearch.value = s.s;
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
[fInput, fModel, fMode, fRendering, fQuality, fStatus, fEnv, fTraced].forEach(el => el.addEventListener('change', applyFilters));
fSearch.addEventListener('input', applyFilters);

document.getElementById('btnReset').addEventListener('click', () => {
  fWorkflow.value = ''; populateFixtures(); fFixture.value = '';
  populateInputs();     fInput.value = '';
  fModel.value = ''; fMode.value = ''; fRendering.value = '';
  fQuality.value = ''; fStatus.value = ''; fEnv.value = '';
  fTraced.value = ''; fSearch.value = '';
  applyFilters();
});

// ── boot ──────────────────────────────────────────────────────────────────────
populateWorkflows();
populateFixtures();
populateInputs();
populateModels();
populateModes();
populateRenderings();
populateEnvs();
try { restoreFilters(); } catch (e) { /* never let a saved filter stop the page */ }
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


class _Blobs:
    """Content-addressed store for the parts of a detail panel that repeat.

    The prompt sent to the model is a function of (rendering, queue) and the staged
    input is the queue itself, so MAIN's 1260 runs carry 70 distinct prompts and 10
    distinct input files between them -- measured on the smoke: 16 distinct prompts
    and 10 distinct inputs across 35 runs, 96.6% of the payload duplicated. Inlined
    once per run that projected to a 127 MB page, which a browser has to parse whole
    before painting anything; interned it is 8.7 MB. Only output_raw and the parsed
    payload stay per-run, being genuinely different every time and small (~3.4 KB).
    """

    def __init__(self, existing: dict | None = None):
        self.by_key: dict[str, object] = dict(existing or {})

    def intern(self, value) -> str | None:
        """Return the key for `value`, or None if there is nothing to store.

        The key is the content digest, not a counter. A counter would number blobs
        by the order runs happen to be read, so the same prompt would get a
        different key on the next rebuild -- and the cache below, which carries keys
        from one rebuild to the next, would point at nothing.
        """
        if value is None or value == "" or value == [] or value == {}:
            return None
        serialised = json.dumps(value, sort_keys=True)
        key = hashlib.md5(serialised.encode("utf-8")).hexdigest()[:12]
        self.by_key.setdefault(key, value)
        return key


DETAIL_CACHE_NAME = ".detail-cache.json"


def _read_cache() -> tuple[dict, dict]:
    """Detail entries and blobs kept from the previous rebuild, or empty.

    Any failure -- absent, truncated, written by an older layout -- reads as empty
    and the rebuild simply does the full work. A cache must never be a reason the
    page cannot be built.
    """
    try:
        data = json.loads((RESULTS_DIR / DETAIL_CACHE_NAME).read_text(encoding="utf-8"))
        runs, blobs = data.get("runs"), data.get("blobs")
        if isinstance(runs, dict) and isinstance(blobs, dict):
            return runs, blobs
    except Exception:
        pass
    return {}, {}


def _write_cache(detail: dict, blobs: dict) -> None:
    try:
        (RESULTS_DIR / DETAIL_CACHE_NAME).write_text(
            json.dumps({"runs": detail, "blobs": blobs}), encoding="utf-8")
    except Exception:
        pass


def _load_detail_data(runs: list[dict], use_cache: bool = True) -> tuple[dict, dict]:
    """Detail panels for every run, reading from disk only what is new.

    campaign.py rebuilds after every row. Without a cache each of MAIN's 1260
    rebuilds would reread all ~1836 record files -- 2.3 million file reads over the
    campaign, on the machine that is running the inference. With one, a rebuild
    reads the single record that just appeared.

    Records are immutable once written, so a hit needs no validation. What a hit
    does NOT cover is a fixture edited underneath (its inputs/ or .mmd): that
    material is cached alongside the run that first read it, and `--rebuild`
    discards the cache for exactly that case.
    """
    detail: dict = {}
    cached_runs, cached_blobs = _read_cache() if use_cache else ({}, {})
    blobs = _Blobs(cached_blobs)
    cacheable: dict = {}
    fixture_cache: dict = {}

    for r in runs:
        run_id     = r.get("run_id", "")
        hit = cached_runs.get(run_id)
        if hit is not None:
            detail[run_id] = cacheable[run_id] = hit
            continue
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

        entry = {
            # keys into BLOBS -- the three that repeat across runs
            "req":     blobs.intern(request_messages),
            "input":   blobs.intern(input_data),
            "mermaid": blobs.intern(mermaid_text or ""),
            # per-run, kept inline
            "output_raw":     output_raw,
            "output_payload": output_payload,
        }
        detail[run_id] = entry
        # A run whose record file is not on disk yet is deliberately NOT cached:
        # caching the empty reading would make it permanent, and the record may
        # simply not have been written when this rebuild ran.
        if result_path.exists():
            cacheable[run_id] = entry

    # Blobs no longer referenced by any run -- from an index rebuilt smaller, or a
    # fixture whose material changed -- are dropped rather than accumulated.
    used = {k for e in detail.values()
            for k in (e.get("req"), e.get("input"), e.get("mermaid")) if k}
    kept = {k: v for k, v in blobs.by_key.items() if k in used}

    if use_cache:
        _write_cache(cacheable, kept)
    return detail, kept


def _rel_to_repo(path: Path) -> str:
    """Repo-relative path when it is one, absolute otherwise -- for the header line
    that names which index the page was built from. It used to say
    tests/results/index.jsonl whatever --index was, so a smoke dashboard claimed
    MAIN's data as its source."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _json_for_script(obj) -> str:
    """JSON safe to paste inside an inline <script> block.

    The payload carries whatever the staged inputs and the model produced, and the
    campaign's inputs are real GitHub issues: several contain a literal
    '</script>'. Dropped in raw it closes the block early, the browser reads the
    rest of the data as markup, and the page dies with 'SyntaxError: Invalid or
    unexpected token' -- every chart empty, every filter unpopulated, and no clue
    on the page as to why.

    '<' and '>' become \\u003c / \\u003e, still valid JSON and still the same
    string once parsed; '&' goes with them so no entity can be reconstructed.
    U+2028 and U+2029 are escaped too: legal in JSON, and legal in JS string
    literals only since ES2019.
    """
    return (json.dumps(obj)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


MEASURES_PATH = REPO_ROOT / "doc" / "measures.md"


def _inline_md(s: str) -> str:
    """Bold, italic, inline code and bare links, over already-escaped text."""
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)   # the page is one file: keep the words
    return s


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def split_versions(md: str) -> list[str]:
    """The document's `# ` headings split it into one part per language.

    Two parts, English then Italian, in that order -- stated in the document and
    asserted in tests/toolchain/test_dashboard.py. The heading line itself is
    dropped: the glossary has its own title.
    """
    parts: list[str] = []
    current: list[str] | None = None
    for line in md.splitlines():
        if line.startswith("# "):
            current = []
            parts.append(current)
            continue
        if current is not None:
            current.append(line)
    return ["\n".join(x) for x in parts]


def render_measures(md: str) -> str:
    """One language part of doc/measures.md -> HTML.

    Deliberately small, and covers only what that document uses: `##` sections,
    `###` terms, paragraphs, `>` callouts, and one table. Anything else arrives as
    its own literal text -- visible, which is the failure mode to prefer, and
    caught by tests/toolchain/test_dashboard.py.
    """
    out: list[str] = []
    para: list[str] = []
    quote: list[str] = []
    table: list[str] = []

    def flush_para():
        if para:
            out.append("<p>" + _inline_md(" ".join(para)) + "</p>")
            para.clear()

    def flush_quote():
        if quote:
            out.append('<div class="warn">' + _inline_md(" ".join(quote)) + "</div>")
            quote.clear()

    def flush_table():
        if not table:
            return
        # header, separator, body -- the separator row carries no content
        rows = [[_inline_md(c.strip()) for c in r.strip().strip("|").split("|")]
                for r in table]
        table.clear()
        head, body = rows[0], rows[2:]
        cells = "".join(f"<th>{c}</th>" for c in head)
        out.append("<table><tr>" + cells + "</tr>")
        for r in body:
            out.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
        out.append("</table>")

    def flush_all():
        flush_para(); flush_quote(); flush_table()

    for raw in md.splitlines():
        line = _esc(raw.rstrip())
        stripped = line.strip()

        if stripped.startswith("|"):
            flush_para(); flush_quote()
            table.append(stripped)
            continue
        flush_table()

        if stripped.startswith("&gt; "):
            flush_para()
            quote.append(stripped[5:])
            continue
        flush_quote()

        if not stripped:
            flush_para()
        elif stripped.startswith("### "):
            flush_para()
            out.append("<h4>" + _inline_md(stripped[4:]) + "</h4>")
        elif stripped.startswith("## "):
            flush_para()
            out.append("<h3>" + _inline_md(stripped[3:]) + "</h3>")
        elif stripped.startswith("# "):
            continue                     # the page has its own title for this
        else:
            para.append(stripped)

    flush_all()
    return "\n".join(out)


LANGUAGES = [("en", "English"), ("it", "Italiano")]


def _glossary_html() -> str:
    """The <details> block: both language versions, and a CSS-only switch.

    Radio inputs ahead of the two bodies, shown and hidden by `:checked ~`. No
    script: the block cannot break a page the campaign rebuilds after every row,
    and a browser that dropped the stylesheet would show both versions stacked --
    legible, where a scripted toggle would have left an empty panel.

    If the source document is gone the glossary says so. Dropping it silently
    would leave a page that looks complete and explains nothing.
    """
    try:
        parts = split_versions(MEASURES_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        parts = []
        note = ("<p>doc/measures.md could not be read (" + _esc(str(exc)) +
                "), so this glossary is empty. It is generated from that file.</p>")
    if parts and len(parts) != len(LANGUAGES):
        parts = parts[:1]
    if not parts:
        parts = [None]

    out = ['<details class="glossary">',
           "<summary>Glossary of the measures &middot; Glossario delle misure</summary>",
           '<div class="gbody">']

    if parts[0] is None:
        out.append(note)
    else:
        for i, (code, label) in enumerate(LANGUAGES[:len(parts)]):
            checked = " checked" if i == 0 else ""
            out.append(f'<input type="radio" name="glang" id="glang-{code}"{checked}>'
                       f'<label class="glang-tab" for="glang-{code}">{label}</label>')
        for (code, _label), body in zip(LANGUAGES, parts):
            out.append(f'<div class="glang glang-{code}">{render_measures(body)}</div>')

    out += ["</div>", "</details>"]
    return "\n".join(out)


def build_html(runs: list[dict], index_label: str = "tests/results/index.jsonl",
               use_cache: bool = True) -> str:
    runs = [normalise(r) for r in runs]
    detail_data, blob_data = _load_detail_data(runs, use_cache=use_cache)

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
            # The two dimensions the campaign of doc/experiment-minimum-context.md
            # actually varies. Runs recorded before the fields existed carry "" and
            # render as a dash: absent, not inferred.
            "rendering": r.get("process_rendering", ""),
            "mode":      r.get("mode", ""),
            "status":  r.get("status", ""),
            "quality": r.get("quality", ""),
            "fidelity":r.get("fidelity", ""),
            # The continuous metrics (2026-08-23). quality and fidelity above are
            # binary and saturate at `fail` on a fixture that scores comprehension
            # as well as control flow; these are what tells two failing runs apart.
            # None on runs recorded before the fields existed, and on runs that
            # emitted no trace -- unmeasured, which is not the same as zero.
            "cond":    r.get("conditional_rate"),
            "comp":    r.get("comprehension_rate"),
            "seq":     r.get("sequence_rate"),
            "traced":  r.get("traced"),
            "deg":     r.get("degradation_mode", ""),
            "env":     r.get("env_realization", ""),
            "ctx":     r.get("context", ""),
            "ts":      ts_fmt,
            "wall":    f"{wc/1000:.1f}s" if wc else "—",
            "tokens_in":  r.get("tokens_in", ""),
            "tokens_out": r.get("tokens_out", ""),
        })

    table_rows_json  = _json_for_script(table_rows)
    detail_data_json = _json_for_script(detail_data)
    blob_data_json   = _json_for_script(blob_data)
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
    <div class="sub">Generated {generated_at} &nbsp;·&nbsp; {total} runs &nbsp;·&nbsp; source: {index_label}</div>
  </div>
  <span class="badge">v0.6</span>
</header>

<!-- ── sticky filter bar ── -->
<div class="filter-bar">
  <select id="fWorkflow" title="Workflow"></select>
  <select id="fFixture"  title="Fixture"></select>
  <select id="fInput"    title="Input"></select>
  <div class="sep"></div>
  <select id="fModel"     title="Model"></select>
  <select id="fMode"      title="Mode"></select>
  <select id="fRendering" title="Process rendering"></select>
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
  <select id="fTraced" title="Trace emitted">
    <option value="">All traces</option>
    <option value="yes">traced</option>
    <option value="no">no trace</option>
  </select>
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
    <div class="label">Conditional fidelity</div>
    <div class="value blue" id="kpi-cond">—</div>
    <div class="hint" id="kpi-cond-hint"></div>
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
<div class="charts three">
  <div class="chart-box">
    <h2>Quality pass rate by fixture</h2>
    <div class="chart-wrap"><canvas id="chartFixture"></canvas></div>
  </div>
  <div class="chart-box">
    <h2>Quality &amp; fidelity pass rate by model</h2>
    <div class="chart-wrap"><canvas id="chartModel"></canvas></div>
  </div>
  <div class="chart-box">
    <h2>Quality &amp; fidelity pass rate by rendering</h2>
    <div class="chart-wrap"><canvas id="chartRendering"></canvas></div>
  </div>
</div>

<!-- ── Charts row 2: the continuous metrics ── -->
<div class="charts">
  <div class="chart-box">
    <h2>Conditional fidelity &amp; comprehension by model</h2>
    <div class="chart-wrap"><canvas id="chartRateModel"></canvas></div>
  </div>
  <div class="chart-box">
    <h2>Conditional fidelity &amp; comprehension by rendering</h2>
    <div class="chart-wrap"><canvas id="chartRateRendering"></canvas></div>
  </div>
</div>

<!-- ── Charts row 3 ── -->
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

{_glossary_html()}

<!-- ── Table ── -->
<div class="table-section">
  <h2>All runs</h2>
  <div class="tbl-wrap">
    <table id="mainTable">
      <thead>
        <tr>
          <th>Timestamp</th><th>Fixture</th><th>Input</th><th>Model</th>
          <th>Mode</th><th>Rendering</th>
          <th>Ctx</th><th>Env</th><th>Status</th><th>Quality</th>
          <th>Fidelity</th><th title="Conditional fidelity">Cond</th>
          <th title="Comprehension">Comp</th><th>Degradation</th><th>Wall</th>
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
const BLOBS  = {blob_data_json};
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
    "model_id", "mode", "process_rendering",
    "spec_version", "env_realization", "runner_type",
    "status", "quality", "fidelity", "degradation_mode",
    "conditional_rate", "comprehension_rate", "sequence_rate", "traced",
    "wall_clock_ms", "tokens_in", "tokens_out", "api_base_url", "reasoning_budget",
]


def sync_csv(runs: list[dict], csv_path: Path, results_root: Path) -> int:
    """Append the runs the CSV does not have yet; return how many were added.

    The file is appended to, so its header has to agree with CSV_COLUMNS. When a
    column is added to CSV_COLUMNS the header on disk is one short, and appending
    would write rows whose fields no longer line up with it -- silent corruption of
    every row written from then on. So a header mismatch is migrated instead: the
    existing rows are read back and the file rewritten whole with the new header.
    Nothing is dropped, orphans that reached the CSV without ever being in
    index.jsonl included.

    A migrated row is rebuilt from its index entry where there is one, rather than
    carried over blank in the new columns. The two cases look identical from inside
    the CSV and are not: when conditional_rate was backfilled into index.jsonl from
    the .score.json files, carrying the old rows over verbatim would have written
    475 empty cells next to an index that had every one of them. Orphans keep their
    old values -- for those the CSV is the only copy left.
    """
    existing_ids: set[str] = set()
    existing_rows: list[dict] = []
    write_header = not csv_path.exists()
    header_stale = False

    if not write_header:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            header_stale = list(reader.fieldnames or []) != CSV_COLUMNS
            for row in reader:
                existing_ids.add(row["run_id"])
                if header_stale:
                    existing_rows.append(row)

    index_ids = {r.get("run_id", "") for r in runs}
    if header_stale:
        by_id = {r.get("run_id", ""): r for r in runs}
        existing_rows = [by_id.get(row["run_id"], row) for row in existing_rows]
    new_runs  = [r for r in runs if r.get("run_id", "") not in existing_ids]
    orphans   = collect_orphan_scores(results_root, existing_ids | index_ids)
    all_new   = new_runs + orphans

    if not all_new and not header_stale:
        return 0

    mode = "w" if (write_header or header_stale) else "a"
    with open(csv_path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        if write_header or header_stale:
            writer.writeheader()
        for run in existing_rows + all_new:
            writer.writerow({col: run.get(col, "") for col in CSV_COLUMNS})

    return len(all_new)


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SOL test results dashboard.")
    parser.add_argument("--index",  default=None, metavar="PATH",
                        help="Path to index.jsonl [default: the campaign's, else the pilot's]")
    parser.add_argument("--output", default=None, metavar="PATH",
                        help="Output HTML path [default: dashboard.html beside --index]")
    parser.add_argument("--csv",    default=None, metavar="PATH",
                        help="CSV path [default: index.csv beside --index]")
    parser.add_argument("--rebuild", action="store_true",
                        help="Ignore the detail cache and reread every record")
    args = parser.parse_args()

    index_path = Path(args.index) if args.index else _default_index()

    if not index_path.exists():
        print(f"Error: index file not found: {index_path}", file=sys.stderr)
        sys.exit(1)

    # Everything hangs off the index's own directory. The module-level RESULTS_DIR
    # and ASSETS_DIR are rebound here rather than read as constants: _load_detail_data
    # resolves the per-run record files through RESULTS_DIR, so pointing --index at
    # another results root (tests/results-smoke) while those stayed on tests/results
    # produced a page whose every detail panel was empty and whose assets/ link led
    # nowhere. campaign.py runs on two roots, so this is not hypothetical.
    global RESULTS_DIR, ASSETS_DIR
    results_root = index_path.parent
    RESULTS_DIR  = results_root
    ASSETS_DIR   = results_root / "assets"

    output_path = Path(args.output) if args.output else results_root / "dashboard.html"
    csv_path    = Path(args.csv)    if args.csv    else results_root / "index.csv"

    runs = load_runs(index_path)

    new_rows = sync_csv(runs, csv_path, results_root)
    print(f"CSV synced:           {csv_path}  (+{new_rows} new rows, {len(runs)} total)")

    # write static assets
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    (ASSETS_DIR / "dashboard.css").write_text(DASHBOARD_CSS, encoding="utf-8")
    (ASSETS_DIR / "dashboard.js").write_text(DASHBOARD_JS, encoding="utf-8")
    print(f"Assets written to:    {ASSETS_DIR}/")

    html = build_html(runs, _rel_to_repo(index_path), use_cache=not args.rebuild)
    output_path.write_text(html, encoding="utf-8")
    print(f"Dashboard written to: {output_path}  ({len(runs)} runs)")


if __name__ == "__main__":
    main()
