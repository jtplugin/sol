#!/usr/bin/env python3
"""
build_verification_html.py — self-contained, offline HTML review tool for
the manual verification of the sampled pool.

Reviews only the items actually consumed by the checker: those a model
classifies before its queue halts, in at least one of the K=10 queues
(see processed_item_ids()) -- not the full 300-item pool. REPLICATION is
sealed/unused by this campaign and the remaining MAIN draws that get
pulled into a queue but sit past its halt point are never seen by a model,
so neither needs verified ground truth yet.

Reads pool-manifest.json (id/repo/nlbse_label, committed) + pool-main.json +
pool-replication.json (full title/body, local/gitignored) + queues-manifest.json
(committed) and, if present, a blind AI classification pass
(tests/data-local/ai-blind-labels.json, {id -> {ai_label, rationale}}) --
and emits ONE self-contained HTML file with the needed items' text embedded
inline. No network calls, no external assets, opens straight from disk.
This file carries third-party (NLBSE) text and must never be committed or
published.

Three judgments are kept permanently distinct and all shown at once, never
merged into a single field:
  - NLBSE   -- the original maintainer-assigned label (never overwritten)
  - AI (blind) -- an independent classification pass that never saw the
    NLBSE label, used only to flag disagreement for human attention, never
    as ground truth by itself
  - Your judgment -- the human reviewer's final call, defaults to NLBSE as
    a starting point but is stored as its own field

Usage:
    python3 tests/scripts/build_verification_html.py

Output: tests/data-local/verification-sheet.html (gitignored)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "support-intake"
DATA_LOCAL = REPO_ROOT / "tests" / "data-local"
AI_LABELS_PATH = DATA_LOCAL / "ai-blind-labels.json"
IT_TRANSLATIONS_PATH = DATA_LOCAL / "it-translations.json"


def processed_item_ids() -> set[str]:
    """Item ids that are actually classified by a model in at least one of
    the K=10 queues before that queue halts -- items drawn into a queue but
    positioned after its halted_at never reach the model, and REPLICATION is
    sealed and unused by this campaign, so neither needs verified ground
    truth right now. Restricting manual review to this set (not the full
    300-item pool) is what the checker's comprehension oracle actually
    consumes."""
    qm = json.loads((FIXTURE_DIR / "queues-manifest.json").read_text(encoding="utf-8"))
    ids: set[str] = set()
    for q in qm["queues"]:
        ids.update(q["item_ids"][: q["n_processed"]])
    return ids


def main() -> None:
    manifest = json.loads((FIXTURE_DIR / "pool-manifest.json").read_text(encoding="utf-8"))
    main_pool = json.loads((DATA_LOCAL / "pool-main.json").read_text(encoding="utf-8"))
    repl_pool = json.loads((DATA_LOCAL / "pool-replication.json").read_text(encoding="utf-8"))
    text_by_id = {r["id"]: r for r in main_pool + repl_pool}

    ai_by_id: dict[str, dict] = {}
    if AI_LABELS_PATH.exists():
        ai_raw = json.loads(AI_LABELS_PATH.read_text(encoding="utf-8"))
        ai_by_id = {r["id"]: r for r in ai_raw}
        print(f"Blind AI labels found: {len(ai_by_id)} items")
    else:
        print("No blind AI labels found (tests/data-local/ai-blind-labels.json) -- column left empty")

    it_by_id: dict[str, dict] = {}
    if IT_TRANSLATIONS_PATH.exists():
        it_raw = json.loads(IT_TRANSLATIONS_PATH.read_text(encoding="utf-8"))
        it_by_id = {r["id"]: r for r in it_raw}
        print(f"Italian translations found: {len(it_by_id)} items")
    else:
        print("No Italian translations found (tests/data-local/it-translations.json) -- IT column left empty")

    show_all = "--all" in sys.argv

    needed_ids = processed_item_ids()
    print(f"Items actually processed by a model in >=1 queue: {len(needed_ids)}/{len(manifest['items'])} "
          f"-- restricting review to these (REPLICATION stays sealed, unused MAIN draws stay unverified)")

    items = []
    n_skipped = 0
    n_already_verified = 0
    for entry in manifest["items"]:
        if entry["id"] not in needed_ids:
            n_skipped += 1
            continue
        if entry.get("verified") and not show_all:
            n_already_verified += 1
            continue
        row = text_by_id.get(entry["id"])
        if row is None:
            sys.exit(f"{entry['id']} missing from pool-main/replication.json -- run hydrate.py --mode pool first")
        ai = ai_by_id.get(entry["id"])
        it = it_by_id.get(entry["id"])
        items.append({
            "id": entry["id"],
            "repo": entry["repo"],
            "split": entry["split"],
            "nlbse_label": entry["nlbse_label"].upper(),
            "ai_label": (ai or {}).get("ai_label"),
            "ai_rationale": (ai or {}).get("rationale"),
            "title": row["title"],
            "body": row["body"],
            "title_it": (it or {}).get("title_it"),
            "body_it": (it or {}).get("body_it"),
        })

    data_json = json.dumps(items, ensure_ascii=False)
    # Defend against issue bodies that literally contain "</script" -- the
    # HTML tokenizer would close our <script> block right there, regardless
    # of it being inside a JS string. "<\/script" is valid JS (no-op escape)
    # and the HTML parser no longer sees a matching close tag.
    data_json = re.sub(r"</(script)", r"<\\/\1", data_json, flags=re.IGNORECASE)
    html = HTML_TEMPLATE.replace("__ITEMS_JSON__", data_json).replace("__N_ITEMS__", str(len(items)))

    out_path = DATA_LOCAL / "verification-sheet.html"
    out_path.write_text(html, encoding="utf-8")
    n_disagree = sum(1 for it in items if it["ai_label"] and it["ai_label"] != it["nlbse_label"])
    print(f"Wrote {out_path} ({len(items)} items, {n_skipped} not needed for this campaign, "
          f"{n_already_verified} already verified and skipped [use --all to include], "
          f"{out_path.stat().st_size / 1024:.0f} KB)")
    if ai_by_id:
        print(f"NLBSE/AI disagreement: {n_disagree}/{len(items)} items")


HTML_TEMPLATE = r"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Verifica manuale pool NLBSE</title>
<style>
:root {
  --bg: #f7f7f5; --panel: #ffffff; --text: #1c1c1c; --muted: #6b6b6b;
  --border: #e2e2df; --accent: #b25a2e; --accent-soft: #f2e2d8;
  --ok: #3f7d4a; --warn: #b5892a; --bad: #b23e3e;
  --mono: "SF Mono", Consolas, "Liberation Mono", Menlo, monospace;
  --sans: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root { --bg:#16161a; --panel:#1e1e23; --text:#eaeaea; --muted:#9a9a9a; --border:#33333a; --accent:#e0895a; --accent-soft:#3a2a20; --ok:#7fbf8c; --warn:#e0b45a; --bad:#e07f7f; }
}
* { box-sizing: border-box; }
body { margin:0; font-family:var(--sans); background:var(--bg); color:var(--text); }
header {
  position: sticky; top:0; z-index:10; background:var(--panel); border-bottom:1px solid var(--border);
  padding: 12px 20px; display:flex; flex-wrap:wrap; gap:12px; align-items:center;
}
header h1 { font-size:15px; margin:0; font-weight:600; white-space:nowrap; }
header .sub { color:var(--muted); font-size:11.5px; }
.controls { display:flex; gap:8px; flex-wrap:wrap; margin-left:auto; align-items:center; }
.controls label { font-size:11px; color:var(--muted); display:flex; flex-direction:column; gap:2px; }
input[type="search"], select {
  font: inherit; padding:6px 10px; border-radius:6px; border:1px solid var(--border);
  background:var(--bg); color:var(--text);
}
button {
  font: inherit; padding:6px 12px; border-radius:6px; border:1px solid var(--accent);
  background:var(--accent); color:white; cursor:pointer;
}
button.secondary { background:transparent; color:var(--accent); }
button:hover { filter:brightness(1.08); }
.progress-wrap { display:flex; align-items:center; gap:8px; font-size:12px; color:var(--muted); }
.progress-bar { width:110px; height:6px; border-radius:4px; background:var(--border); overflow:hidden; }
.progress-fill { height:100%; background:var(--ok); width:0%; transition:width .2s; }
main { max-width:none; margin:0; padding:16px 24px 90px; }
.count-line { color:var(--muted); font-size:12px; margin:0 0 10px 2px; }
.card {
  background:var(--panel); border:1px solid var(--border); border-radius:10px;
  padding:16px 18px; margin-bottom:14px;
}
.card.reviewed { border-left:3px solid var(--ok); }
.card.tolerant { border-left:3px solid var(--warn); }
.card.disagree { box-shadow: 0 0 0 1px var(--bad) inset; }
.card-head { display:flex; flex-wrap:wrap; gap:8px; align-items:baseline; margin-bottom:6px; }
.card-id { font-family:var(--mono); font-size:12px; color:var(--muted); }
.card-repo { font-size:12px; color:var(--muted); background:var(--bg); border:1px solid var(--border); border-radius:4px; padding:1px 6px; }
.card-split { font-size:11px; color:var(--muted); }
.disagree-flag { font-size:11px; color:var(--bad); font-weight:600; margin-left:auto; }
.text-cols { display:flex; gap:16px; align-items:stretch; }
.text-col { flex:1 1 0; min-width:0; }
.text-col .col-label { font-size:10px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; margin-bottom:3px; }
.card-title { font-size:15px; font-weight:600; margin:4px 0 8px; }
.card-body {
  font-family:var(--mono); font-size:12.5px; line-height:1.5; white-space:pre-wrap; word-break:break-word;
  background:var(--bg); border:1px solid var(--border); border-radius:6px; padding:10px 12px;
  color:var(--text); height:100%;
}
@media (max-width: 900px) {
  .text-cols { flex-direction:column; }
}
.opinions-row {
  display:flex; flex-wrap:wrap; gap:18px; margin-top:12px; padding-top:10px; border-top:1px dashed var(--border);
  font-size:12.5px; align-items:center;
}
.opinion { display:flex; gap:6px; align-items:baseline; }
.opinion .who { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.02em; }
.opinion .val { font-weight:600; }
.opinion .rationale { color:var(--muted); font-size:11px; font-style:italic; }
.yours-group { display:flex; gap:6px; align-items:center; }
.radio-opt { display:flex; align-items:center; gap:3px; font-size:12.5px; padding:3px 8px; border-radius:5px; border:1px solid var(--border); cursor:pointer; }
.radio-opt.checked { background:var(--accent-soft); border-color:var(--accent); }
.radio-opt input { accent-color:var(--accent); }
.tolerant-row { display:flex; gap:8px; align-items:center; font-size:12.5px; margin-left:auto; }
.tolerant-row select { font-size:12px; padding:3px 6px; }
footer.bar {
  position:sticky; bottom:0; background:var(--panel); border-top:1px solid var(--border);
  padding:10px 20px; display:flex; gap:10px; justify-content:flex-end; align-items:center;
}
.hint { color:var(--muted); font-size:11px; }
</style>
</head>
<body>

<header>
  <div>
    <h1>Verifica manuale pool NLBSE — __N_ITEMS__ item</h1>
    <div class="sub">solo gli item realmente valutati da almeno una coda (REPLICATION resta sigillata) · autosalva nel browser · niente rete, niente server</div>
  </div>
  <div class="controls">
    <label>cerca
      <input type="search" id="search" placeholder="id / repo / titolo / corpo…" size="24">
    </label>
    <label>stato
      <select id="filter-status">
        <option value="">tutti</option>
        <option value="disagree">⚠ disaccordo NLBSE/IA</option>
        <option value="unreviewed">da rivedere</option>
        <option value="reviewed">rivisti (confermati)</option>
        <option value="changed">label cambiata da te</option>
        <option value="tolerant">tolleranti</option>
      </select>
    </label>
    <label>tipo (NLBSE)
      <select id="filter-type">
        <option value="">tutti</option>
        <option value="BUG">bug</option>
        <option value="FEATURE">feature</option>
        <option value="QUESTION">question</option>
      </select>
    </label>
    <label>prodotto
      <select id="filter-repo"><option value="">tutti</option></select>
    </label>
  </div>
</header>

<main>
  <div class="count-line" id="count-line"></div>
  <div id="list"></div>
</main>

<footer class="bar">
  <span class="hint">Le risposte si salvano da sole mentre lavori.</span>
  <div class="progress-wrap">
    <div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>
    <span id="progress-text">0 / 0</span>
  </div>
  <button class="secondary" id="reset-btn">Azzera tutto</button>
  <button id="export-btn">Esporta correzioni (JSON)</button>
</footer>

<script>
const ITEMS = __ITEMS_JSON__;
const STORAGE_KEY = "sol2-verification-v2";
const LABELS = ["BUG", "FEATURE", "QUESTION"];
const LABEL_LC = { BUG: "bug", FEATURE: "feature", QUESTION: "question" };

let state = {};
try { state = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"); } catch (e) { state = {}; }

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  updateProgress();
}

function getEntry(id) {
  if (!state[id]) state[id] = { corrected_label: null, tolerant: false, tolerant_alt_label: null };
  return state[id];
}

function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
}

function isDisagree(item) {
  return item.ai_label && item.ai_label !== item.nlbse_label;
}

function updateProgress() {
  const total = ITEMS.length;
  const reviewed = ITEMS.filter(it => state[it.id] && state[it.id].corrected_label).length;
  document.getElementById("progress-text").textContent = reviewed + " / " + total;
  document.getElementById("progress-fill").style.width = (100 * reviewed / total) + "%";
}

function cardStatus(item) {
  const e = state[item.id];
  if (!e || !e.corrected_label) return "unreviewed";
  if (e.tolerant) return "tolerant";
  if (e.corrected_label !== item.nlbse_label) return "changed";
  return "reviewed";
}

function renderCard(item) {
  const e = getEntry(item.id);
  const current = e.corrected_label || item.nlbse_label;
  const status = cardStatus(item);
  const statusClass = status === "unreviewed" ? "" : (e.tolerant ? "tolerant" : "reviewed");
  const disagreeClass = isDisagree(item) ? "disagree" : "";

  const labelOpts = LABELS.map(l => `
    <label class="radio-opt ${current === l ? 'checked' : ''}" data-label="${l}">
      <input type="radio" name="label-${item.id}" value="${l}" ${current === l ? "checked" : ""}>
      ${LABEL_LC[l]}
    </label>`).join("");

  const altOpts = LABELS.filter(l => l !== current).map(l =>
    `<option value="${l}" ${e.tolerant_alt_label === l ? "selected" : ""}>${LABEL_LC[l]}</option>`
  ).join("");

  const aiOpinion = item.ai_label
    ? `<div class="opinion"><span class="who">IA (cieca)</span> <span class="val">${LABEL_LC[item.ai_label]}</span>
       ${item.ai_rationale ? `<span class="rationale">— ${escapeHtml(item.ai_rationale)}</span>` : ""}</div>`
    : `<div class="opinion"><span class="who">IA (cieca)</span> <span class="val" style="color:var(--muted)">— non ancora disponibile</span></div>`;

  return `
  <div class="card ${statusClass} ${disagreeClass}" data-id="${item.id}" data-repo="${item.repo}" data-type="${item.nlbse_label}"
       data-search="${escapeHtml((item.id + ' ' + item.repo + ' ' + item.title + ' ' + item.body + ' ' + (item.title_it||'') + ' ' + (item.body_it||'')).toLowerCase())}">
    <div class="card-head">
      <span class="card-id">${item.id}</span>
      <span class="card-repo">${item.repo}</span>
      <span class="card-split">${item.split}</span>
      ${isDisagree(item) ? '<span class="disagree-flag">⚠ NLBSE ≠ IA</span>' : ''}
    </div>
    <div class="text-cols">
      <div class="text-col">
        <div class="col-label">originale (en)</div>
        <div class="card-title">${escapeHtml(item.title)}</div>
        <div class="card-body">${escapeHtml(item.body)}</div>
      </div>
      <div class="text-col">
        <div class="col-label">traduzione (it)</div>
        <div class="card-title">${item.title_it ? escapeHtml(item.title_it) : '<span style="color:var(--muted);font-weight:400">— non disponibile —</span>'}</div>
        <div class="card-body">${item.body_it ? escapeHtml(item.body_it) : '— traduzione non disponibile —'}</div>
      </div>
    </div>
    <div class="opinions-row">
      <div class="opinion"><span class="who">NLBSE</span> <span class="val">${LABEL_LC[item.nlbse_label]}</span></div>
      ${aiOpinion}
      <div class="yours-group">
        <span class="who" style="align-self:center">Tu</span>
        ${labelOpts}
      </div>
      <label class="tolerant-row">
        <input type="checkbox" class="tolerant-cb" ${e.tolerant ? "checked" : ""}>
        ambiguo
        <select class="alt-select" ${e.tolerant ? "" : "disabled"}>
          <option value="">— alternativa —</option>
          ${altOpts}
        </select>
      </label>
    </div>
  </div>`;
}

function renderList() {
  const container = document.getElementById("list");
  container.innerHTML = ITEMS.map(renderCard).join("");

  container.querySelectorAll(".card").forEach(card => {
    const id = card.dataset.id;
    const item = ITEMS.find(it => it.id === id);

    card.querySelectorAll('input[type="radio"]').forEach(radio => {
      // "click" not "change": change never fires when the radio was already
      // checked (e.g. the default matches NLBSE and you click it to confirm
      // agreement) -- click fires on every click regardless of prior state.
      radio.addEventListener("click", () => {
        const e = getEntry(id);
        e.corrected_label = radio.value;
        saveState();
        card.querySelectorAll(".radio-opt").forEach(o => o.classList.toggle("checked", o.dataset.label === radio.value));
        card.className = "card " + (cardStatus(item) === "unreviewed" ? "" : (e.tolerant ? "tolerant" : "reviewed")) + (isDisagree(item) ? " disagree" : "");
        refreshAltOptions(card, id);
      });
    });

    const tolCb = card.querySelector(".tolerant-cb");
    const altSelect = card.querySelector(".alt-select");
    tolCb.addEventListener("change", () => {
      const e = getEntry(id);
      e.tolerant = tolCb.checked;
      altSelect.disabled = !tolCb.checked;
      if (!tolCb.checked) { e.tolerant_alt_label = null; altSelect.value = ""; }
      saveState();
      card.className = "card " + (cardStatus(item) === "unreviewed" ? "" : (e.tolerant ? "tolerant" : "reviewed")) + (isDisagree(item) ? " disagree" : "");
    });
    altSelect.addEventListener("change", () => {
      const e = getEntry(id);
      e.tolerant_alt_label = altSelect.value || null;
      saveState();
    });
  });

  updateProgress();
  applyFilters();
}

function refreshAltOptions(card, id) {
  const item = ITEMS.find(it => it.id === id);
  const e = getEntry(id);
  const current = e.corrected_label || item.nlbse_label;
  const altSelect = card.querySelector(".alt-select");
  const prev = altSelect.value;
  altSelect.innerHTML = '<option value="">— alternativa —</option>' +
    LABELS.filter(l => l !== current).map(l => `<option value="${l}">${LABEL_LC[l]}</option>`).join("");
  if (LABELS.includes(prev) && prev !== current) altSelect.value = prev;
}

function populateRepoFilter() {
  const repos = [...new Set(ITEMS.map(it => it.repo))].sort();
  const sel = document.getElementById("filter-repo");
  repos.forEach(r => {
    const opt = document.createElement("option");
    opt.value = r; opt.textContent = r;
    sel.appendChild(opt);
  });
}

function applyFilters() {
  const q = document.getElementById("search").value.trim().toLowerCase();
  const repo = document.getElementById("filter-repo").value;
  const status = document.getElementById("filter-status").value;
  const type = document.getElementById("filter-type").value;
  let shown = 0;
  document.querySelectorAll(".card").forEach(card => {
    const id = card.dataset.id;
    const item = ITEMS.find(it => it.id === id);
    let visible = true;
    if (q && !card.dataset.search.includes(q)) visible = false;
    if (repo && card.dataset.repo !== repo) visible = false;
    if (type && card.dataset.type !== type) visible = false;
    if (status === "disagree" && !isDisagree(item)) visible = false;
    else if (status && status !== "disagree" && cardStatus(item) !== status) visible = false;
    card.style.display = visible ? "" : "none";
    if (visible) shown++;
  });
  document.getElementById("count-line").textContent = shown + " / " + ITEMS.length + " item mostrati";
}

document.getElementById("search").addEventListener("input", applyFilters);
document.getElementById("filter-repo").addEventListener("change", applyFilters);
document.getElementById("filter-status").addEventListener("change", applyFilters);
document.getElementById("filter-type").addEventListener("change", applyFilters);

document.getElementById("export-btn").addEventListener("click", () => {
  const out = ITEMS.map(it => {
    const e = state[it.id] || {};
    return {
      id: it.id,
      verified: !!e.corrected_label,
      verified_label: e.corrected_label ? e.corrected_label.toLowerCase() : null,
      tolerant: !!e.tolerant,
      tolerant_alt_label: e.tolerant_alt_label ? e.tolerant_alt_label.toLowerCase() : null,
    };
  });
  const blob = new Blob([JSON.stringify(out, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "pool-corrections.json";
  a.click();
});

document.getElementById("reset-btn").addEventListener("click", () => {
  if (confirm("Azzerare tutte le risposte salvate in questo browser?")) {
    localStorage.removeItem(STORAGE_KEY);
    state = {};
    renderList();
  }
});

populateRepoFilter();
renderList();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
