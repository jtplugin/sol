# The measures

> **The English text is the official one.** The Italian half that follows it is a working
> translation, kept here rather than anywhere else so that changing one and not the other is a
> thing you have to decide to do rather than a thing that happens. These definitions do not move
> often; when they move, both halves move together, in the same edit.
>
> `scripts/dashboard.py` renders both and puts a language switch on the glossary. The `###` term
> headings are identical in the two versions on purpose — they are the dashboard's own column
> names, and a test compares the two lists, so the halves cannot fall out of step structurally.

What each number the campaign records means, and how it is computed. The authority is
`tests/runner/checker.py`; this restates it in prose, and is the single place that does.
`scripts/dashboard.py` renders this file into the glossary on the dashboard, so the page and this
document cannot drift apart.

Where a value is absent the dashboard shows a dash. **Absent is not zero.** Zero is the score of a
model that was measured and got everything wrong; the dash says there was nothing to measure.

## Binary verdicts

### Status

The outcome of the **execution**, not of the answer. `done`: the model replied. `error`: the call
failed. `timeout`: it expired. `skipped-window`: the prompt does not fit the model's context
window, so the row was never attempted.

### Quality

The returned object compared against `expected_output`: `pass` when every expected key carries
exactly the expected value. `not_checkable` when there is no payload, or no expectation to compare
it against. Computed in `check()`.

> **On `support-intake` it cannot pass, and its red is not a result.** The fixture asks for fifteen
> semantic classifications on top of the control flow, and end-to-end equality is not a bar an 8B
> model clears. This is deliberate (§6.2 of the protocol): the campaign's metric is conditional
> fidelity, not this.

### Fidelity

The binary verdict of the sequence oracle: `pass` **only** when `sequence_rate` is exactly 1.0. A
run at 95% reads `fail` exactly as one at 0% does — the continuous rates below are what tell them
apart. Computed in `_check_sequence_fidelity()`, or `_check_fidelity()` on fixtures that carry a
single branch label rather than a sequence.

## Continuous rates (0–1)

### Quality rate — field-level agreement

The graded reading of the quality comparison: the fraction of `expected_output`'s **leaf fields**
the payload reproduces exactly. Dicts recurse by key, lists by position, every scalar (null
included) is one leaf; equality is strict, the same standard as the binary verdict — `"17"`
against `17` is a miss here exactly as `wrong-format` is a fail there. A payload wrong in one
field of eight scores 0.875 where the binary verdict says only `fail`; that difference is the
power the binary oracle gives up (`experiment-kv-quantization.md` §5), and the reason the measure
exists (§10 of the protocol, prerequisite of the tracking A/B). `None` — absence of a measurement,
not a zero — when the run returned no payload or the case has no expectation. Computed in
`_field_rate()`, stored as `quality.rate`, indexed as `quality_rate`. Added §12 2026-08-25,
re-derived for every record on disk at zero GPU.

### Sequence rate

Right actions in the right places against the ground-truth sequence, compared position by
position. The denominator is `max(len(expected), len(observed))`, not `len(expected)`: a run that
never halts keeps emitting actions past the expected end, and capping the comparison window at the
expected length rewarded it for degenerating. Computed in `_check_sequence_fidelity()`.

### Redundancy ratio

`len(observed) / len(expected)`. Read next to the rate above: rate low and ratio ≈1 → wrong actions
at the right cadence; rate low and ratio high → a loop that never halts; rate low and ratio <1 →
stopped early.

### Cond — conditional fidelity

**The campaign's primary metric.** The oracle re-runs the process using the model's **own**
classifications (its `EVAL:` trace lines) instead of the true ones, and compares the result against
what the model actually did (its `BRANCH:` lines).

This isolates control flow from comprehension: a model that gets the product wrong but then
executes the process coherently *for that wrong product* scores high Cond and low Comp. The
denominator is the length of the sequence the oracle produces from the model's own
classifications. Computed in `_check_conditional_fidelity()`.

### Comp — comprehension

`(product, intent)` pairs read from the `EVAL:` lines and compared against the verified ground
truth, one per item. The rate is over the ground-truth items, not over the ones the model happened
to name: items it never spoke about count as missed.

`not_checkable` when there is **no** `EVAL` line at all. A partial trace is still scored over every
item — five lines out of fifteen is an observation; silence is not. Computed in
`_check_comprehension()`.

### Traced

Whether the run emitted any trace line at all. It has its own filter in the dashboard's toolbar. An
untraced run is not a bad run, it is an **unmeasurable** one: Cond and Comp are both absent for it.

## Degradation mode — the diagnosis

One label per run. The first group comes from comparing the payload; the sequence oracle's own
labels, where there is one, take precedence over them.

| Mode | Meaning |
|---|---|
| `none` | the payload matches what was expected |
| `extra-fields` | it matches, but carries keys beyond the expected ones |
| `wrong-format` | values agree once case is folded or a number written as a string is coerced |
| `wrong-structure` | the expected values are present, nested differently |
| `wrong-value` | payload present, values wrong |
| `garbled-output` | what came back is not an object |
| `no-output` | no payload could be extracted from the answer |
| `refused` | no payload, and the text reads as a refusal |
| `halt-not-taken` | the payload names the *right* stopping point in `halted_at` and returns the whole queue anyway: the model located the exit, reported it, and did not take it. Read off the payload, not the trace, so it is visible on models that skip the scaffolding entirely. A strictly more informative sub-case of `no-halt`, checked first |
| `no-halt` | the expected sequence ended in an `ESCALATE` and the model ran past it, or did something else at that position |
| `partial-sequence` | it executed, but drifted partway through (`0 < sequence_rate < 1`) |
| `budget-drift` | every action right, but the accumulator in the final payload does not agree: right decisions, wrong bookkeeping |
| `execution-error`, `connection-error`, `timeout`, `na` | failures of the apparatus, not of the model |

## Coordinates

### Rendering

How the process was written into the prompt. `L0`–`L4`: the SOL document with increasing
collateral, each level a strict prefix of the next. `prose-mechanical`: rendered from the SOL
document by the skill's deterministic renderer, no model in the loop. `prose-generated`: rendered
from the same document by a model in one pass, from a frozen prompt.

> **The seven do not sit on one axis.** Five of them form a curve; two are comparison points
> against that curve. A figure that plots all seven in sequence, or an average taken across them,
> reads a change of language as a change of quantity, and is wrong by construction (§5.4).

### Mode

The `tests/modes.json` entry that produced the run. It is not the model: `qwen3.5-9b` think and
nothink are the same gguf and differ only in their reasoning budget.

### Ctx / Env

`E0`: all the material is in the prompt and the model has no tools. `E1`: the model has tools.
`emulated` / `native` says whether the environment was simulated by the runner or real.

### Wall, tokens in/out

Wall-clock time of the single call and the tokens it consumed, as the provider reports them.
Neither enters any score.

## Reading the charts

### The pass-rate rows

Percentage of runs whose `quality` or `fidelity` reads `pass`. Binary: on a fixture where passing
is unreachable they sit at zero even when the runs beneath them differ enormously.

### Conditional fidelity & comprehension

Means of Cond and Comp, plus the percentage of runs that emitted a trace. **Runs with no trace are
left out of the means** rather than counted as zero: it is precisely the cells that emit no trace
whose scores a null-as-zero rule would flatten, and they would then read as models that executed
the process and got it wrong. The tooltip says how many runs each bar rests on — a high mean over
two traced runs out of thirty is not a result.

# Le misure

Cosa significa ogni numero che la campagna registra, e come è calcolato. L'autorità è
`tests/runner/checker.py`; questo lo riespone in prosa, ed è l'unico posto che lo fa.
`scripts/dashboard.py` rende questo file nel glossario della dashboard, così la pagina e questo
documento non possono divergere.

Dove un valore manca, la dashboard mostra un trattino. **Assente non è zero.** Zero è il voto di un
modello che è stato misurato e ha sbagliato tutto; il trattino dice che non c'era niente da misurare.

## Esiti binari

### Status

Esito dell'**esecuzione**, non della risposta. `done`: il modello ha risposto. `error`: la chiamata
è fallita. `timeout`: è scaduta. `skipped-window`: il prompt non entra nella finestra di contesto
del modello, quindi la riga non è mai stata tentata.

### Quality

L'oggetto restituito confrontato con `expected_output`: `pass` se ogni chiave attesa ha esattamente
il valore atteso. `not_checkable` quando non c'è payload, o non c'è un atteso con cui confrontarlo.
Calcolato in `check()`.

> **Su `support-intake` non può passare, e il suo rosso non è un risultato.** Il fixture chiede
> quindici classificazioni semantiche oltre al control-flow, e l'uguaglianza end-to-end non è
> un'asticella che un modello da 8B supera. È voluto (§6.2 del protocollo): la metrica della
> campagna è la conditional fidelity, non questa.

### Fidelity

Verdetto binario dell'oracolo di sequenza: `pass` **solo** se `sequence_rate` vale esattamente 1.0.
Un run al 95% legge `fail` esattamente come uno allo 0% — per distinguerli servono i tassi continui
qui sotto. Calcolato in `_check_sequence_fidelity()`, oppure in `_check_fidelity()` sui fixture che
portano una singola etichetta di ramo invece di una sequenza.

## Tassi continui (0–1)

### Quality rate — field-level agreement

La lettura graduata del confronto di quality: la frazione dei **campi foglia** di
`expected_output` che il payload riproduce esattamente. I dict ricorrono per chiave, le liste per
posizione, ogni scalare (null compreso) è una foglia; l'uguaglianza è stretta, lo stesso metro del
verdetto binario — `"17"` contro `17` è un errore qui esattamente come `wrong-format` è un fail
là. Un payload sbagliato in un campo su otto vale 0.875 dove il verdetto binario dice solo `fail`;
quella differenza è la potenza statistica a cui l'oracolo binario rinuncia
(`experiment-kv-quantization.md` §5), ed è la ragione per cui la misura esiste (§10 del
protocollo, prerequisito dell'A/B sul tracking). `None` — assenza di misura, non uno zero — quando
il run non ha restituito payload o il caso non ha expectation. Calcolata in `_field_rate()`,
salvata come `quality.rate`, indicizzata come `quality_rate`. Aggiunta §12 2026-08-25, ri-derivata
per ogni record su disco a GPU spenta.

### Sequence rate

Azioni giuste al posto giusto rispetto alla sequenza di riferimento, confrontate posizione per
posizione. Il denominatore è `max(len(attese), len(osservate))`, non `len(attese)`: un run che non
si ferma continua a emettere azioni oltre la fine attesa, e tagliare la finestra di confronto alla
lunghezza attesa lo premiava proprio per il fatto di degenerare. Calcolato in
`_check_sequence_fidelity()`.

### Redundancy ratio

`len(osservate) / len(attese)`. Si legge accanto al tasso qui sopra: rate basso e ratio ≈1 → azioni
sbagliate alla cadenza giusta; rate basso e ratio alto → un ciclo che non si ferma; rate basso e
ratio <1 → fermato troppo presto.

### Cond — conditional fidelity

**La metrica primaria della campagna.** L'oracolo riesegue il processo usando le classificazioni
**del modello stesso** (le sue righe `EVAL:`) invece di quelle vere, e confronta il risultato con
quello che il modello ha davvero fatto (le sue righe `BRANCH:`).

Isola il control-flow dalla comprensione: un modello che sbaglia il prodotto ma poi esegue il
processo in modo coerente *con quel prodotto sbagliato* prende Cond alto e Comp basso. Il
denominatore è la lunghezza della sequenza che l'oracolo produce dalle classificazioni del modello.
Calcolato in `_check_conditional_fidelity()`.

### Comp — comprehension

Coppie `(product, intent)` lette dalle righe `EVAL:` e confrontate con la verità di riferimento
verificata, una per item. Il tasso è sugli item della verità di riferimento, non su quelli che il
modello ha nominato: gli item di cui non ha parlato contano come mancati.

`not_checkable` quando non c'è **nessuna** riga `EVAL`. Una traccia parziale resta valutata su tutti
gli item — cinque righe su quindici sono un'osservazione, il silenzio no. Calcolato in
`_check_comprehension()`.

### Traced

Se il run ha emesso almeno una riga di traccia. Ha un filtro suo nella barra della dashboard. Un run
non tracciato non è un run cattivo, è un run **non misurabile**: Cond e Comp sono entrambe assenti.

## Degradation mode — la diagnosi

Una sola etichetta per run. Il primo gruppo nasce dal confronto del payload; le etichette
dell'oracolo di sequenza, quando ce n'è una, prevalgono su quelle.

| Modo | Significato |
|---|---|
| `none` | il payload corrisponde all'atteso |
| `extra-fields` | corrisponde, ma porta chiavi oltre quelle attese |
| `wrong-format` | i valori coincidono a meno di maiuscole, o di un numero scritto come stringa |
| `wrong-structure` | i valori attesi ci sono, annidati diversamente |
| `wrong-value` | payload presente, valori sbagliati |
| `garbled-output` | quello che è tornato non è un oggetto |
| `no-output` | nessun payload estraibile dalla risposta |
| `refused` | nessun payload, e il testo si legge come un rifiuto |
| `halt-not-taken` | il payload nomina il punto d'uscita *giusto* in `halted_at` e restituisce comunque tutta la coda: il modello ha trovato l'uscita, l'ha dichiarata, e non l'ha presa. Si legge dal payload, non dal trace, quindi è visibile anche sui modelli che saltano l'impalcatura. Sottocaso di `no-halt` strettamente più informativo, controllato per primo |
| `no-halt` | la sequenza attesa finiva con un `ESCALATE` e il modello è andato oltre, o ha fatto altro in quel punto |
| `partial-sequence` | ha eseguito, ma ha deviato per strada (`0 < sequence_rate < 1`) |
| `budget-drift` | tutte le azioni giuste, ma l'accumulatore nel payload finale non torna: decisioni giuste, contabilità sbagliata |
| `execution-error`, `connection-error`, `timeout`, `na` | guasti dell'apparato, non del modello |

## Coordinate

### Rendering

Come il processo è stato scritto nel prompt. `L0`–`L4`: il documento SOL con collaterale crescente,
ogni livello prefisso stretto del successivo. `prose-mechanical`: reso dal documento SOL dal
renderer deterministico della skill, senza modello nel giro. `prose-generated`: reso dallo stesso
documento da un modello in un passo, da un prompt congelato.

> **I sette non stanno su un asse solo.** Cinque formano una curva; due sono punti di confronto
> contro quella curva. Un grafico che li mette tutti in fila, o una media presa fra di loro, legge
> un cambio di linguaggio come un cambio di quantità, ed è sbagliato per costruzione (§5.4).

### Mode

La voce di `tests/modes.json` che ha prodotto il run. Non è il modello: `qwen3.5-9b` think e nothink
sono lo stesso gguf e si distinguono solo per il budget di ragionamento.

### Ctx / Env

`E0`: tutto il materiale è nel prompt e il modello non ha strumenti. `E1`: il modello ha strumenti.
`emulated` / `native` dice se l'ambiente era simulato dal runner o reale.

### Wall, tokens in/out

Tempo di parete della singola chiamata e i token che ha consumato, come li riporta il provider. Non
entrano in nessun punteggio.

## Come leggere i grafici

### The pass-rate rows

Percentuale di run il cui `quality` o `fidelity` legge `pass`. Binarie: su un fixture dove il pass è
irraggiungibile restano a zero anche quando i run sotto sono enormemente diversi fra loro.

### Conditional fidelity & comprehension

Medie di Cond e Comp, più la percentuale di run che hanno emesso una traccia. **I run senza traccia
sono esclusi dalle medie** invece di essere contati zero: sono proprio le celle che non emettono
traccia quelle che una regola zero-al-posto-di-assente appiattirebbe, e leggerebbero come modelli
che hanno eseguito il processo sbagliando. Il tooltip dice su quanti run poggia ogni barra — una
media alta su due run tracciati su trenta non è un risultato.
