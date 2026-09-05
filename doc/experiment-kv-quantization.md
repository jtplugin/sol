# KV cache quantizzata: cambia i risultati con SOL?

**Tipo:** spike, eseguito in sessione interattiva il 2026-08-20.
**Dati grezzi e strumenti:** script e risultati di lavoro, tenuti fuori dal repository; elencati
per nome al §10.
**Dipende da:** la revisione del 2026-08-19 che ha portato nel runner il fattore thinking, nel
record la configurazione di cella, e nell'oracolo le due metriche continue.

---

## 1. La domanda, e perché conta

Ogni cella della campagna va configurata al meglio per il suo modello — decisione di Gianni del
2026-08-19. La configurazione non è un dettaglio di tuning: è parte di cosa significa «quel modello
su questo hardware». Ma alcune scelte di configurazione potrebbero **degradare i risultati**, e
allora vanno dichiarate.

La KV cache quantizzata a `q8_0` è il primo caso concreto, e non è opzionale. Su questa scheda
(8151 MiB) le misure del pilota tecnico dicono che a `f16`, ai contesti richiesti da L4, tre celle su cinque
non stanno in memoria:

| cella | VRAM libera a f16 | VRAM libera a q8_0 | soglia |
|---|---|---|---|
| ministral-3-8b | 43 MiB | 561 MiB | 150 MiB |
| granite-4.1-8b | 43 MiB | 219 MiB | 150 MiB |
| gemma-4-12b | 125 MiB | 579 MiB | 150 MiB |
| qwen3.5-9b | 1641 MiB | 2025 MiB | 150 MiB |
| phi4-mini | 1097 MiB | 2913 MiB | 150 MiB |

*(fonti: le misure di VRAM del pilota tecnico, `celle_results.json` per f16 e `kvq_results.json`
per q8_0)*

Tre celle su cinque **esistono solo grazie a quella cache**. Se degrada, i loro 450 run di MAIN si
leggono con un'avvertenza, e la cosa va saputa prima di spendere le notti, non dopo.

Ne discende anche un vincolo di metodo che ha condizionato tutto il resto: **l'A/B è eseguibile
soltanto sui due modelli che reggono entrambe le cache**, Qwen e Phi. Su Ministral, Granite e gemma
il braccio `f16` non è misurabile — non è «stretto», è assente.

---

## 2. Primo tentativo, fallito per disegno

Fatto durante il pilota tecnico con `abkv.py`. Soggetto: Phi-4-mini, l'unico non-thinking che regge entrambe
le cache. n=10 per braccio, fixture `w2-branching/support-intake`, coda `queue-01`, `--dry-run`.

| | f16 | q8_0 |
|---|---|---|
| quality pass | 0/10 | 0/10 |
| fidelity pass | 0/10 | 0/10 |
| tempo medio | 27,8 s | 28,9 s |
| modi di guasto | 10 wrong-value | 7 wrong-value, 2 no-output, 1 refused |

**Phi-4-mini è al pavimento**: fallisce sempre, con entrambe le cache, e sotto di lui non c'è spazio
in cui una degradazione possa mostrarsi. La distribuzione dei modi di guasto cambia (3/10 anomalie
con q8_0 contro 0/10) ma a n=10 vale p≈0,21: suggestivo, non dimostrato.

L'errore non fu nell'esecuzione, fu nella **scelta del soggetto**. Da qui la prescrizione scritta
nella card: rifarlo con un modello che *a volte passa*, verificando **prima** che non sia al
pavimento.

---

## 3. Un difetto dello strumento, trovato preparando il pre-check

`tests/runner/run.py` — l'entrypoint interattivo — **non inoltra** `thinking`, `ctx_size`,
`kv_cache_type` e `n_parallel` a `run_headless_api`. Usa il proprio `_load_env_entry` (riga 47)
invece di `_load_mode`, e la chiamata a riga 150 si ferma a `level=`. I quattro parametri esistono
nella firma (`api_executor.py:554`) e restano a `None`.

Conseguenza: **via `run.py` le mode `-think` e `-nothink` sono indistinguibili**,
`chat_template_kwargs` non entra mai nel payload. Un A/B condotto così avrebbe confrontato due
bracci identici e concluso «nessuna differenza» — una risposta pulita e falsa.

`campaign.py` è invece corretto: usa `_load_mode` (riga 138) e passa `thinking` (righe 318, 342).
**MAIN non è toccata.** Il buco è solo sull'entrypoint manuale.

Aggirato chiamando `api_executor.py` direttamente, la cui `main()` carica i quattro campi
(riga 994). Nessuna modifica a codice di produzione. Il difetto di `run.py` **resta aperto** e
merita una card sua: non è un fix di passaggio.

---

## 4. Pre-check: tre livelli, sei bracci, diciotto run

Soggetto Qwen3.5-9B a `f16`, `w2-branching/support-intake` / `queue-01` / E0 / `--dry-run`.
Strumento: `proto/precheck9.py`.

| liv | braccio | Q | F | tempi | token | degradazione |
|---|---|---|---|---|---|---|
| L0 | think | 0/3 | 0/3 | 39s · 265s · 81s | 14.885–26.228 | no-output ×3 |
| L0 | nothink | 0/3 | 0/3 | 28s · 33s · 29s | ~14.700 | **refused ×3** |
| L1 | think | **1/3** | 0/3 | 49s · 268s · 267s | 16.997–27.955 | none, no-output ×2 |
| L1 | nothink | 0/3 | 0/3 | 33s · 267s · 33s | 16.577–27.957 | no-halt ×3 |
| L2 | think | **1/3** | 0/3 | 277s · 67s · 267s | 18.644–28.357 | no-output ×2, none |
| L2 | nothink | 0/3 | 0/3 | 32s · 27s · 28s | 16.690–16.954 | no-halt ×3 |

**Quality 2/18 · Fidelity 0/18.**

Due cose imparate qui, entrambe correzioni a ipotesi sbagliate.

**La scala L non è una scala di difficoltà decrescente.** La scala (`api_executor.py`,
`_build_prompt_e0`) è cumulativa: `L0` è il prompt spoglio, `L4` ha tutto il collaterale. L più
alto significa **più impalcatura**, quindi compito più facile. Il primo giro a L0 fu fatto
credendo il contrario, e infatti a L0 il modello *si rifiuta* — tre run su tre, veloci e con token
quasi identici: non rumore, una risposta netta.

> **Rilettura, 2026-08-22.** Quel rifiuto a L0 non misurava la scala: all'epoca `L0`
> consegnava al modello la sola coda di segnalazioni, senza script SOL e senza catalogo prodotti.
> Il modello non si rifiutava di eseguire SOL — non aveva ricevuto nessun processo da eseguire, né
> i dati per classificare. Dopo il riallineamento `L0` è dati + SOL senza prosa esplicativa: i
> numeri a L0 riportati qui non sono confrontabili con quelli prodotti dopo questa data. Le altre
> conclusioni di questo documento, che poggiano su L1 e L2, restano valide nel merito ma sono a
> loro volta a prompt pre-riallineamento.

**Nessun soggetto ha margine su questa fixture.** Salendo la scaletta `think` è piatto a 1/3 da L1 a
L2, con due fallimenti sempre uguali: fughe a ~28.000 token e ~270 secondi. `nothink` non si sveglia
mai. E dei cinque modelli, solo Qwen e Phi possono fare l'A/B; Phi è al pavimento. Con un oracolo
binario, la card 9 era senza soggetti.

---

## 5. La scoperta: l'oracolo binario buttava via il segnale

`checker.py::_check_sequence_fidelity`:

```python
rate = (matches / n) if n else None
result = "not_checkable" if rate is None else ("pass" if rate == 1.0 else "fail")
```

**La soglia è `rate == 1.0`.** Esatta, nessun credito parziale: un passo in più o in meno e il run
vale zero. E dopo la revisione del 2026-08-19 il denominatore è `max(len(expected), len(observed))`, quindi un run che
non si arresta si schiaccia il tasso da solo.

Quindi `Fidelity 0/18` non significava «il modello era lontanissimo». Significava «nessuno dei 18 ha
centrato la sequenza esatta», e con un oracolo binario non si distingue chi manca un passo da chi
delira.

Ma `sequence_rate` e `redundancy_ratio` — introdotti proprio da quella revisione — sono **continui ed
esistono su ogni run**, anche fallito. `redundancy_ratio` classifica pure il modo di guasto: ~1 →
azioni sbagliate alla cadenza giusta; alto → loop; <1 → arresto precoce.

I run del pre-check giravano in `--dry-run`, che non scrive record: quei due valori venivano
calcolati e scartati. Il primo run catturandoli (`proto/kvab.py`) ha dato subito
`rate=0.4, redundancy=2.14` su un run che nella tabella binaria era un `XX` indistinguibile dagli
altri.

**Conseguenza di metodo:** l'A/B non ha bisogno di un modello che «a volte passa». Quel requisito
era un'imposizione dell'oracolo, non della domanda. Si confrontano le due distribuzioni di
`sequence_rate`.

`proto/kvab.py` percorre la stessa pipeline invoke → score di `campaign.py::_execute_row` ma si
ferma prima dei tre salvataggi: nessun record, nessun `index.jsonl`. Il dataset della campagna resta
intatto (verificato: 576 righe prima e dopo, `git status` pulito su `tests/results/`).

---

## 6. A/B su metrica continua

Qwen3.5-9B `-nothink`, L2, `queue-01`, `temperature: 0.2`, n=10 per braccio.

| | f16 | q8_0 |
|---|---|---|
| VRAM libera | 1641 MiB | **2025 MiB** |
| `sequence_rate` ordinati | 0.011 0.011 0.011 0.167 0.167 0.312 0.333 0.333 0.333 0.400 | 0.009 0.011 0.011 0.011 0.167 0.267 0.333 0.333 0.333 0.400 |
| media su tutti | 0,208 | 0,188 |
| fughe (`redundancy > 10`) | 3/10 | 4/10 |
| media sui soli run sani | 0,292 (n=7) | **0,306** (n=6) |
| tempo medio | 105 s | 131 s |
| quality pass | 0/10 | 0/10 |
| fidelity pass | 0/10 | 0/10 |

La distribuzione è **bimodale**, con due mode molto distanti: run sani intorno a 0,17–0,40 con
ridondanza ~2,1 e ~30 s; fughe a ~0,011 con ridondanza ~65 e ~273 s.

### Test

```
tutti i run     diff = 0.0204   p = 0.782   permutazione esatta (184.756)
solo run sani   diff = 0.0133   p = 0.858   permutazione esatta (1.716)
fughe 3 vs 4                    p = 1.000   Fisher esatto
```

**Nessuna degradazione rilevabile.** E le due misure puntano in **direzioni opposte**: sulla media
totale `q8_0` è peggio di 0,02, sui run sani è meglio di 0,013. Quando il segno del presunto effetto
si inverte a seconda del sottoinsieme, il presunto effetto è rumore.

Prova qualitativa, più forte del test: **i due bracci contengono gli stessi identici valori**.
`0.333` con ridondanza `2.142857` compare tre volte per braccio; `0.400`, `0.167` e la fuga a
~`0.011` con ridondanza ~65 compaiono in entrambi. La cache a 8 bit non produce **un solo modo di
guasto** che `f16` non produca già.

I 26 secondi in più di `q8_0` sono aritmetica delle fughe, non della cache: una fuga costa ~273 s,
ce n'è una in più, 273/10 ≈ 27.

### Cosa questo test può e non può escludere

Sensibilità calcolata sui dati raccolti:

```
tutti i run    sd=0.159  media=0.198  effetto minimo rilevabile (n=10) = 0.199  → 101% della media
solo run sani  sd=0.085  media=0.299  effetto minimo rilevabile (n=6)  = 0.138 →  46% della media
```

Con n=10 e questa dispersione, l'unico effetto visibile sarebbe **un dimezzamento del tasso o
peggio**. Una degradazione del 20% avrebbe prodotto esattamente il risultato ottenuto. Quindi *«non
ho trovato nulla»* significa *«non c'è un effetto grosso»*, **non** *«non c'è effetto»*.

Costo per stringere:

| degradazione da rilevare | n per braccio | tempo stimato |
|---|---|---|
| 50% | 41 | ~2,4 h |
| 25% | 163 | ~9,5 h |
| 10% | 1.016 | ~59 h |

Il rumore però non è nella misura: è nel modello — la lotteria delle fughe più il campionamento a
`temperature: 0.2`. Una metrica più fine misurerebbe con più precisione un fenomeno che di suo varia
così. La leva giusta è togliere il rumore, non comprare precisione.

---

## 7. Test meccanicistico a temperatura 0

Idea: a greedy, se il backend è riproducibile, **ogni differenza fra i due bracci è causata solo
dalla numerica della cache**. La domanda passa da statistica a diretta. Strumento: `proto/kv0.py`,
n=3 per braccio, stesso prompt, `temperature: 0.0`.

### Blocco A — determinismo

```
f16    3/3 run → hash unico  387001247b1a
q8_0   3/3 run → hash unico  1c80bae5b4bf
```

A greedy **llama.cpp è riproducibile**. Dato nuovo: il probe di determinismo del pilota aveva
misurato solo a `temperature: 0.2`, dove trovava 4 output distinti su 5. Il confronto appaiato ha
fondamento.

### Blocco B — confronto appaiato

I due bracci **divergono**. Hash diversi, lunghezze 39.589 contro 38.710 caratteri, entrambi a
13.024 token, cioè entrambi al tetto del contesto.

Primo carattere diverso: **indice 2082**, cioè il **5,3% dell'output** — circa 24 righe `BRANCH:`,
~685 token generati. I due calcoli sono identici fino a lì, poi:

```
comune  …BRANCH: item=item-181 action=ASSIGN remaining=-
f16     3\n…BRANCH: item=item-213 action=ASSIGN remaining=-3
q8_0    8\n…BRANCH: item=item-213 action=ASSIGN remaining=-13
```

La divergenza è **su un numero**: il contatore `remaining` dello stato accumulato. Stesso item,
stessa azione, valore diverso. È esattamente il punto in cui una cache quantizzata dovrebbe fare
danno — l'aritmetica di stato, dopo che abbastanza contesto si è depositato nella KV.

Output grezzi conservati in `proto/kv0_raw_f16.txt` e `proto/kv0_raw_q8_0.txt`.

### Il limite di questo blocco

Al momento della divergenza **entrambi i bracci stanno già fallendo**: `remaining=-3` prima della
separazione è già un valore senza senso, ed entrambi finiscono al tetto del contesto in fuga. La
cache cambia la traiettoria di un run **già degenere**, non la causa.

---

## 8. Conclusione

I due risultati non si contraddicono, si compongono:

- la cache **cambia** il percorso dei token — dimostrato, non stimato: due flussi deterministici che
  si separano dopo ~685 token su un valore numerico
- il cambiamento **non sposta** né il tasso di fedeltà né la frequenza delle fughe in modo
  rilevabile, e non introduce modi di guasto nuovi
- cioè: **perturba, ma la perturbazione non ha un segno sistematico sulla qualità.** Rimescola la
  lotteria, non la trucca

### Frase per il writeup

> A temperatura 0 il backend llama.cpp è riproducibile, e `q8_0` contro `f16` produce percorsi di
> token diversi: l'accordo si rompe dopo ~685 token generati, su un valore numerico dello stato
> accumulato. L'effetto è quindi reale e misurabile a livello di calcolo. Non è però rilevabile
> sugli esiti: n=10 per braccio a `temperature: 0.2` non mostra differenze né sul tasso di fedeltà
> di sequenza (p=0,78) né sulla frequenza dei run in fuga (p=1,00), e i modi di guasto sono gli
> stessi in entrambi i bracci. `q8_0` libera 384 MiB, che è ciò che mette Ministral, Granite e
> gemma sulla scheda.

**Non c'è asterisco da mettere su MAIN.**

### Limiti, dichiarati

1. **Un modello, un livello, una coda.** Qwen3.5-9B `-nothink` a L2 su `queue-01`. Non si estende
   per costruzione a Ministral, Granite e gemma, che il braccio `f16` non possono eseguire.
2. **n=10 esclude effetti grandi, non piccoli.** Sotto ~0,1 di `sequence_rate` la differenza resta
   invisibile con questa dispersione.
3. **Nessun run ha superato quality o fidelity**, in nessun braccio. Il confronto è fra due
   distribuzioni di *fallimento*, non fra due tassi di successo. È ciò che la metrica continua
   permette e il pass/fail no.
4. **Il test a temperatura 0 non è la configurazione di campagna** (0,2). Risponde a «la cache
   perturba il calcolo?», non a «degrada i risultati come configurati?».
5. **La divergenza avviene su una traiettoria già degenere**, quindi non dice nulla sul segno
   dell'effetto quando il modello lavora bene — condizione che su questa fixture non si è mai
   verificata.

---

## 9. Trovato strada facendo

Difetti reali emersi preparando gli esperimenti, non parte della domanda della card. Tutti corretti
e committati; i messaggi di commit portano il dettaglio.

| difetto | dove | esito |
|---|---|---|
| `campaign-cells.json` nominava un gguf inesistente per gemma-4-12b | avrebbe marcato 150 righe di MAIN `skipped-acceptance`, stato indistinguibile da un verdetto hardware e non ritentabile | corretto, più tre test di invariante cella/mode/disco |
| configurazione di cella non versionata | `tests/env.json` è gitignorato per le chiavi: la config dell'esperimento non era ricostruibile | aggiunto `tests/campaign-modes.json` |
| `task-router.md` con JSON invalido dal 2026-06-17 | fixture non caricabile nemmeno dal runner, `JSONDecodeError` non catturata | riparata |
| il test di lint parsava le fixture diversamente dal runner | rosso su `cart-total`, che il runner carica benissimo | helper delegato a `runner.runner._load_fixture` |
| `sales-summary` nascondeva due guardie in prosa | il diagramma mostrava cinque scatole dove il processo si biforca due volte | guardie alzate a `IF`, fixture spostata in `w2-branching` |
| `run.py` non inoltra la configurazione di cella | vedi §3 | **aperto**, merita una card |

---

## 10. Fonti verificabili

Gli script e gli output di questo spike sono artefatti di lavoro e **non fanno parte del
repository**. Si elencano qui perché ogni numero riportato sopra viene da uno di essi:

| file | contenuto |
|---|---|
| `precheck9.py` | pre-check parametrico per livello, due bracci |
| `precheck9_L0_results.json` · `_L1_` · `_L2_` | i 18 run del §4, con tabelle e code di stdout |
| `kvab.py` | A/B su metrica continua, invoke → score senza salvataggi |
| `kvab_llama-qwen3.5-9b-nothink_L2.json` | i 20 run del §6, con `sequence_rate` e `redundancy_ratio` per run |
| `kv0.py` | determinismo + confronto appaiato a temperatura 0 |
| `kv0_llama-qwen3.5-9b-nothink_L2.json` | hash per braccio, indice di divergenza, contesto |
| `kv0_raw_f16.txt` · `kv0_raw_q8_0.txt` | i due output grezzi, 39.589 e 38.710 caratteri |

Il primo tentativo su Phi-4-mini appartiene agli artefatti del pilota tecnico (`abkv.py`,
`abkv_results.json`), insieme alle misure di VRAM (`celle_results.json`, `kvq_results.json`) e al
probe di determinismo a temperatura 0,2 (`determinismo_results.json`).
