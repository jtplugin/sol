# SOL Testing — Guida pratica

> Riferimento pratico per eseguire test, aggiungere fixture e leggere i risultati.
> Per il metodo di valutazione, vedi [`testing-sol.md`](testing-sol.md).
> Per l'architettura dei runner, vedi [`testing-runners.md`](testing-runners.md).
> Per la strategia complessiva, vedi [`testing-strategy.md`](testing-strategy.md).

---

## 1. Avvio rapido

**Prerequisiti**

- Python 3.10+
- Per il **session runner** (`executor.py`): CLI `claude` installata e nel PATH (Claude Code).
- Per l'**API runner** (`api_executor.py`): API key Anthropic in `ANTHROPIC_API_KEY`, oppure passata via `--api-key`.

**Comando base: session runner**

```bash
python3 tests/runner/executor.py \
  --fixture w2-branching/release-gate \
  --input i1-blocked \
  --context E1 \
  --model claude-opus-4-8 \
  --dry-run
```

**Comando base: API runner**

```bash
python3 tests/runner/api_executor.py \
  --fixture w2-branching/release-gate \
  --input i1-blocked \
  --context E0 \
  --model claude-opus-4-8 \
  --dry-run
```

I risultati finiscono in `tests/results/` (ignorata da git). Il registro globale è `tests/results/index.jsonl`.

---

## 2. Eseguire test con il session runner (`executor.py`)

Il session runner invoca `claude -p` e raccoglie l'output completo del modello.

**Flag principali**

| Flag | Obbligatorio | Default | Descrizione |
|---|---|---|---|
| `--fixture` | sì | — | ID fixture, es. `w2-branching/release-gate` |
| `--input` | sì* | — | ID input, es. `i1-blocked` |
| `--all-inputs` | sì* | — | Esegue tutti gli input in `fixtures/<id>/inputs/` |
| `--context` | no | `E1` | `E0` (nessun tool) oppure `E1` (Bash limitato a `cat`) |
| `--model` | no | `claude-opus-4-8` | Qualsiasi model ID Claude |
| `--runs` | no | `1` | Numero di esecuzioni per input (test distributivo) |
| `--timeout` | no | `120` | Timeout per singola esecuzione in secondi |
| `--dry-run` | no | off | Esegue e calcola il punteggio senza scrivere file |

\* `--input` e `--all-inputs` si escludono a vicenda; uno dei due è obbligatorio.

**Tutti gli input, 5 esecuzioni ciascuno**

```bash
python3 tests/runner/executor.py \
  --fixture w2-branching/release-gate \
  --all-inputs \
  --context E1 \
  --model claude-opus-4-8 \
  --runs 5
```

**Dry-run (modalità sonda)**

Usa sempre `--dry-run` prima di consolidare i risultati su una nuova fixture o un nuovo caso di expectations. Esegue il flusso completo e stampa il punteggio senza scrivere nulla:

```bash
python3 tests/runner/executor.py \
  --fixture w2-branching/release-gate \
  --input i1-blocked \
  --context E0 \
  --model claude-opus-4-8 \
  --dry-run
```

**Colonne della tabella di output**

```
  #     Input                               Q      F      Degrade
  -----------------------------------------------------------------------
  1     i1-blocked #1                       ✓      ✓      none
```

- `Q` — quality check: `✓` pass, `✗` fail, `–` non verificabile
- `F` — fidelity check (basato sulla trace): stessi simboli
- `Degrade` — degradation mode (vedi §6)

**Scelta del context**

- `E0`: il runner inietta il contenuto del file nel prompt. Il modello non chiama nessun tool. Simula una bare API call senza agent loop.
- `E1`: il file staged viene indicato per percorso; il modello deve leggerlo con `cat` via Bash tool. Simula un ambiente a tool-loop minimale.

---

## 3. Eseguire test con l'API runner (`api_executor.py`)

L'API runner chiama direttamente l'API Anthropic Messages — nessuna CLI `claude`, nessuna sessione Claude Code. È adatto a pipeline CI, endpoint alternativi e benchmark che devono essere indipendenti dall'installazione locale di Claude Code.

**Flag aggiuntivi (rispetto al session runner)**

| Flag | Default | Descrizione |
|---|---|---|
| `--mode` | — | Carica `runner_type`, `url`, `model`, `backend`, `reasoning`, `temperature` da `tests/modes.json` e `key` da `tests/env.json` (es. `claude-api`) |
| `--api-key` | `$ANTHROPIC_API_KEY` | API key Anthropic (sovrascrive `--mode`) |
| `--api-url` | `https://api.anthropic.com` | URL base API (sovrascrive `--mode`) |

Tutti gli altri flag (`--fixture`, `--input`, `--all-inputs`, `--context`, `--model`, `--runs`, `--timeout`, `--dry-run`) funzionano come nel session runner.

**Il context di default è E0** (non E1 come nel session runner), perché le chiamate API single-shot sono la modalità naturale dell'API runner.

**Usare `--mode` (consigliato)**

Il modo più semplice per eseguire l'API runner è con `--mode`, che legge la configurazione della mode da `tests/modes.json` e la credenziale, se la mode ne richiede una, da `tests/env.json`:

```bash
python3 tests/runner/api_executor.py \
  --fixture w2-branching/release-gate \
  --all-inputs \
  --mode claude-api \
  --dry-run
```

**Due file, due mestieri.** `tests/modes.json` è la configurazione delle mode ed è **tracciata in git**: un clone fresco ha tutte le mode pronte. `tests/env.json` contiene solo le chiavi Anthropic ed è **gitignorata**; `tests/env.example.json` ne è il template. Le mode locali (`backend` `openai`/`ollama`) e `claude-code-local` non hanno alcuna entry lì.

Struttura di `tests/modes.json` (`runner_type`, `backend`, `url`, `model`, `reasoning`, più `temperature`/`thinking`/`ctx_size`/`kv_cache_type`/`n_parallel` dove la mode li usa — un campo omesso resta non impostato, `"thinking": false` non equivale ad assente):

```json
{
  "modes": [
    {
      "mode": "claude-api",
      "runner_type": "api",
      "backend": "anthropic",
      "url":  "https://api.anthropic.com",
      "model": "claude-sonnet-4-6",
      "reasoning": 0
    }
  ]
}
```

Struttura di `tests/env.json` — sole credenziali, una entry per ogni mode che richiede una chiave:

```json
{
  "modes": [
    { "mode": "claude-api",          "key": "sk-ant-api03-..." },
    { "mode": "claude-api-thinking", "key": "sk-ant-api03-..." }
  ]
}
```

I singoli flag (`--api-key`, `--api-url`, `--model`) sovrascrivono i valori di `--mode`.

**Sovrascrivere l'endpoint manualmente**

```bash
python3 tests/runner/api_executor.py \
  --fixture w2-branching/release-gate \
  --all-inputs \
  --context E0 \
  --model <provider-model-id> \
  --api-url https://your.provider.endpoint \
  --api-key sk-... \
  --dry-run
```

Qualsiasi endpoint che implementa l'API Anthropic Messages (`POST /v1/messages`) è supportato.

**Utilizzo token e costo**

La risposta API include `input_tokens` e `output_tokens`. Il costo non è disponibile dalla risposta API e viene registrato come `null` nei risultati. Usa i contatori di token e il pricing del provider per calcolare il costo esternamente se necessario.

**Dipendenza SDK**

L'API runner usa l'SDK Python `anthropic` se disponibile (`pip install anthropic`). Se non installato, ricade su un'implementazione pura `urllib` — nessuna dipendenza aggiuntiva richiesta.

**Quando preferire l'API runner**

- Vuoi testare un endpoint o provider non standard.
- Stai girando in CI senza un'installazione di Claude Code.
- Vuoi risultati che portino esplicitamente `runner_type: "api"` e `api_base_url` così sono distinguibili in `index.jsonl`.
- Vuoi una misurazione E0 single-shot senza l'overhead della sessione.

---

## 4. Configurare una nuova fixture

### Layout della directory

```
tests/fixtures/<workload-class>/<fixture-name>/
    <fixture-name>.md        ← documento fixture (frontmatter + corpo prompt con SOL incorporato)
    expectations.json        ← verdetti attesi, un caso per input
    inputs/
        <input-id>.json      ← un file input per caso di test
    README.md                ← intento della fixture, razionale dell'oracolo
```

Scegli la workload class che corrisponde ai costrutti esercitati:

| Classe | Costrutti | Context minimo |
|---|---|---|
| `w0-transform` | solo modello (nessun tool, nessun control flow) | E0 |
| `w1-linear` | `RUN`, `REPEAT` | E1 |
| `w2-branching` | `WHEN`, `UNLESS`, guardia `accepts` | E1 |
| `w3-multi-call` | `CALL`, `SPAWN` | E1+ |
| `error-path` | `ONERROR`, `HALT` | E1 |

### Il documento fixture (`<name>.md`)

Il documento fixture è un file Markdown che è la **fonte unica di verità** per il prompt
che il runner invia al modello. È composto da due parti: un blocco YAML frontmatter e un
corpo Markdown.

**Frontmatter** — metadati machine-readable:

```yaml
---
name: fixture-w2-release-gate
version: "1.0"
schema: "../../../../sol-schema.json"
system_prompt: "Sei un senior release manager che valuta i criteri di rilascio
  e prende decisioni go/no-go."
description: "Fixture W2. ..."
accepts:
  record_path:
    required: true
    desc: "..."
returns:
  verdict:
    anyof: ["BLOCKED", "READY"]
    required: true
    desc: "..."
---
```

Il campo `system_prompt` imposta la persona di dominio del modello. Fornisce competenza
rilevante senza menzionare SOL né spiegare come interpretare lo script — il modello deve
inferire la semantica di esecuzione dallo script SOL da solo. Questa è una scelta
intenzionale: il test misura quanto la notazione SOL sia autoesplicativa.

**Corpo** — il prompt utente, strutturato come sezioni Markdown:

```markdown
# Gate evaluation task

Evaluate the release record by executing strictly the SOL script below.

## File content

\`\`\`json
{{file_content}}
\`\`\`

## SOL script

\`\`\`json
{ ...JSON ROUTINE SOL qui... }
\`\`\`
```

Il runner sostituisce `{{file_content}}` con il contenuto JSON serializzato dell'input
staged prima di inviare il prompt. L'ultimo blocco ` ```json ` nel corpo viene analizzato
come script SOL per uso interno (validazione schema, prompt E1 con staged-path).

**Suggerimento per la frase TODO:** Fai riferimento esplicito al contenuto del file
perché il modello sappia dove leggere in contesto E0 (no-tools):

```json
{"TODO": "Read the 'line' field from the file content above. ..."}
```

### `expectations.json`

Struttura:

```json
{
  "cases": [
    {
      "input": "inputs/i1-blocked.json",
      "expected_verdict": "BLOCKED",
      "expected_branch": "branch-0"
    },
    {
      "input": "inputs/i2-approved.json",
      "expected_verdict": "APPROVED",
      "expected_branch": "branch-1"
    }
  ]
}
```

- `expected_verdict`: il valore che il modello deve restituire nel payload JSON.
- `expected_branch`: l'etichetta `BRANCH` nella trace che il modello deve emettere. Ometti se la fixture non emette una riga `BRANCH`.

**Aggiungi il caso di expectations PRIMA di eseguire.** Senza un caso corrispondente, il checker segna sempre quality come `fail` (wrong-value) indipendentemente da cosa restituisce il modello, perché confronta il verdetto con `null`.

### Flusso di sonda (probe workflow)

1. Scrivi il documento SOL e fallo passare il lint.
2. Scrivi un file input e il suo caso di expectations.
3. `--dry-run` su quell'input per verificare che il punteggio sia affidabile.
4. Solo allora esegui con `--runs N`.

### Formato del file input

Un input è un oggetto JSON semplice. Lo schema è quello specificato dal contratto `accepts`. Esempio:

```json
{
  "pr_id": "PR-42",
  "title": "Add dark mode",
  "checks": ["ci", "review"],
  "all_checks_passed": false
}
```

---

## 5. Leggere i risultati

### Layout dei file

```
tests/results/
  <fixture-id>/<context>/<model>/<spec-version>/
    <run-id>.json            ← RunRecord
    <run-id>.score.json      ← ScoreRecord
  index.jsonl                ← registro append-only, una riga per esecuzione
```

Esempio di percorso:
```
tests/results/w2-branching/release-gate/E1/claude-opus-4-8/0.6/
  w2-branching-release-gate-i1-blocked-20260604T125406-r01.json
```

### Campi del RunRecord (`.json`)

| Campo | Contenuto |
|---|---|
| `run_id` | Identificatore univoco dell'esecuzione |
| `timestamp` | Timestamp UTC ISO-8601 |
| `config.fixture_id` | Fixture eseguita |
| `config.context` | E0 \| E1 |
| `config.model_id` | Modello usato |
| `config.runner_type` | `"claude-code"` (session runner) oppure `"api"` (API runner) |
| `config.api_base_url` | Endpoint API se `runner_type="api"`, altrimenti `null` |
| `config.env_realization` | `"native"` (session runner) oppure `"emulated"` (API runner) |
| `execution.status` | `done` \| `error` \| `na` |
| `execution.wall_clock_ms` | Durata totale dell'esecuzione |
| `trace.steps` | Righe di trace strutturate emesse dal modello |
| `output.raw` | Output grezzo completo del modello |
| `output.returned_payload` | Payload JSON parsato dal RETURN |
| `usage.tokens_in` | Token in input (API runner: dalla risposta; session runner: aggregato) |
| `usage.tokens_out` | Token in output |
| `usage.cost` | Costo in USD (solo session runner; `null` per API runner) |

### Campi dello ScoreRecord (`.score.json`)

| Campo | Significato |
|---|---|
| `fidelity.result` | `pass` \| `fail` \| `not_checkable` |
| `fidelity.expected_branch` | Etichetta branch da expectations |
| `fidelity.observed_branch` | Etichetta branch dalla trace |
| `quality.result` | `pass` \| `fail` \| `not_checkable` |
| `quality.expected` | Verdetto atteso |
| `quality.got` | Verdetto restituito |
| `efficiency.wall_clock_ms` | Wall clock (copiato dal RunRecord) |
| `efficiency.tokens_in/out` | Utilizzo token |
| `degradation_mode` | Come il modello ha fallito (oppure `none`) |

### `index.jsonl`

Ogni riga è una riga JSON — un sommario appiattito di un'esecuzione. Usalo per filtrare e aggregare senza caricare i singoli file.

**Filtrare per runner type:**

```python
import json
rows = [json.loads(l) for l in open("tests/results/index.jsonl")]
api_rows     = [r for r in rows if r.get("runner_type") == "api"]
session_rows = [r for r in rows if r.get("runner_type") == "claude-code"]
```

**Confrontare session vs API sulla stessa fixture:**

```python
fixture = "w2-branching/release-gate"
for rt in ("claude-code", "api"):
    subset = [r for r in rows
              if r["fixture_id"] == fixture and r.get("runner_type") == rt]
    passed = sum(1 for r in subset if r["quality"] == "pass")
    print(f"{rt}: {passed}/{len(subset)} quality pass")
```

---

## 6. Degradation mode

Il campo `degradation_mode` descrive come si è comportato il modello quando non ha prodotto il risultato atteso:

| Mode              | Significato                                       |
| ----------------- | ------------------------------------------------- |
| `none`            | Risultato corretto, nessuna degradazione          |
| `wrong-value`    | Ha eseguito il branch `WHEN`/`UNLESS` sbagliato   |
| `no-output`       | Nessun payload JSON restituito                    |
| `refused`         | Il modello si è rifiutato di eseguire il processo |
| `garbled-output`  | L'output non è JSON parsabile                     |
| `execution-error` | Errore del runner (timeout, crash, ecc.)          |
| `na`              | Non applicabile (es. fixture `not_checkable`)     |

`not_checkable` in `quality.result` o `fidelity.result` non è un fallimento — significa che la fixture non ha un oracolo deterministico per quella dimensione. Conta solo le righe `pass` e `fail` nel calcolo dei pass rate.

---

## 7. Workflow comuni

### "Voglio verificare come un modello gestisce un nuovo caso limite"

1. Crea un nuovo file input in `tests/fixtures/<class>/<name>/inputs/`.
2. Aggiungi il caso corrispondente in `expectations.json`.
3. Esegui prima con `--dry-run` per confermare che il punteggio sia corretto.
4. Esegui con `--runs 5` per ottenere un campione distributivo.

### "Voglio confrontare session runner vs API runner sulla stessa fixture"

```bash
# Session runner
python3 tests/runner/executor.py \
  --fixture w2-branching/release-gate --all-inputs \
  --context E1 --model claude-opus-4-8 --runs 5

# API runner (stessa fixture, stesso modello, E0 — context più comparabile)
python3 tests/runner/api_executor.py \
  --fixture w2-branching/release-gate --all-inputs \
  --context E0 --model claude-opus-4-8 --runs 5
```

Poi filtra `index.jsonl` per `runner_type` per confrontare i risultati fianco a fianco.

### "Voglio aggiungere un nuovo modello alla matrice"

Cambia solo `--model`. Nessuna modifica alle fixture. I risultati sono memorizzati in una directory `<model>` separata, quindi non collidono con le esecuzioni esistenti.

### "Voglio eseguire il prodotto cartesiano completo per una fixture"

```bash
for context in E0 E1; do
  python3 tests/runner/executor.py \
    --fixture w2-branching/release-gate \
    --all-inputs --context $context \
    --model claude-opus-4-8 --runs 3
done
```

### "Un'esecuzione mostra wrong-value al 100% — il modello è rotto?"

Verifica prima: ogni input ha un caso corrispondente in `expectations.json`? Se un input non ha un caso, il checker lo segna sempre come `fail` indipendentemente dall'output del modello. Esegui `--dry-run` su un input e ispeziona l'output grezzo prima di concludere che il modello è in errore.

### "Voglio eseguire i test R1 del toolchain"

```bash
python3 -m pytest tests/toolchain -q
```

Sono unit test deterministici per `sol-lint.py` e `checker.py`. Non invocano nessun modello e devono passare su ogni commit.

### "Devo aggiungere runner_type ai risultati esistenti"

Se hai run record prodotti prima che `runner_type` venisse aggiunto allo schema:

```bash
# Anteprima modifiche
python3 tests/runner/migrate_runner_type.py --dry-run

# Applica
python3 tests/runner/migrate_runner_type.py
```

Lo script è idempotente.
