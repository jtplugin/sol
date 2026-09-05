# SOL — Fact Sheet della campagna principale

Generato da `report/analysis/01_fatti.ipynb` il 2026-09-05.
Sorgente: `report/analysis/tidy.csv`, costruita da `load_raw.py` sugli artefatti grezzi
`tests/results-main/**/*.score.json`.
**Non modificare a mano: rigenerare eseguendo il notebook.**

> Fatti descrittivi con la loro N e il loro intervallo (capitoli 1-7 del notebook),
> e i test appaiati sull'item (capitolo 8). Ogni affermazione di significativita' e'
> accompagnata dal test che la regge e dall'ampiezza dell'effetto.

## Il disegno

Tre studi in sequenza, non un fattoriale. **Nessuna media attraversa gli studi.**

| studio | fixture | unita' | misura | run |
|---|---|---|---|---:|
| 1 | `support-intake` | la coda (6-11 item) | quota di item corretti sulla coda | 1236 |
| 2 | `support-routing` | l'item (1 per run) | 8 campi per item, `pass` = tutti e 8 | 1676 |
| 3 | `support-routing-notrace` | l'item (1 per run) | come 2, senza misure di traccia | 2519 |

Lo studio 3 nasce da un ritrovamento dello studio 2: il tracing nei comandi aveva un effetto suo. Toglierlo costa `comprehension_rate` e `conditional_rate` (assenti al 100% nello studio 3) e in cambio da' un dato di successo pulito. Su quella configurazione, e solo su quella, sono stati somministrati anche i tre bracci **hosted** — `claude-code-haiku` (2026-08-31), `claude-code-sonnet` e `claude-code-opus` (2026-09-02), 280 run ciascuno: stessi item, stessi rendering, stesse repliche, stesso oracolo, e come unica coordinata mobile l'id del modello.

## Qualita' del dato

- **`tests/results-main/index.csv` diverge dai punteggi grezzi su 17 run** (0.3%): e' un derivato rigenerato in un momento diverso dalla valutazione. Non usarlo come sorgente — questo foglio legge i `.score.json`.
- **`expected_branch` / `observed_branch` sono vuoti su tutte le righe**: il controllo di ramo non ha mai prodotto valori, e il verdetto `fidelity` poggia solo su `sequence_rate`.
- **Disegno sbilanciato fra studi**: le celle modello x rendering vanno da 40 a 112 run. Dentro gli studi 2-3 invece il disegno e' pieno e appaiato (20 item per condizione).
- **12 run hanno (cella, replica) duplicato** (0.2%): ri-esecuzioni aggiunte in coda, non sostituzioni. Restano nel dataset.
- **`degradation_mode` non e' una misura indipendente**: e' l'etichetta della causa del fallimento e coincide con `quality` (`none` <-> `pass`). Citarli come due risultati distinti dice due volte la stessa cosa.

### Dove taglia l'etichetta `quality`

- `quality = pass` significa **`quality_rate == 1.0` esatto**: perfetto, non buono.
- I run etichettati `fail` hanno quality_rate medio **0.639** (mediana 0.625): il fallimento medio ha circa due terzi del lavoro corretto.
- Su `fidelity` il quadro e' opposto: i `fail` hanno sequence_rate medio **0.049**, quasi zero. Le due etichette `fail` non significano la stessa cosa e non vanno sommate.

## Studio 1 — intake

1236 run su 10 code, 6 modelli, 7 rendering.

- Quota media di item corretti per coda: **0.732** (mediana 0.792).
- Code risolte **alla perfezione**: **1.5%**.

Le due letture distano ~50 punti sulla stessa campagna: la prima dice quanto lavoro il modello fa bene, la seconda quante volte lo fa *tutto* bene. Vanno riportate insieme.

| modello | quota media di item corretti | n run |
|---|---:|---:|
| `qwen3.5-9b-think` | 0.842 | 210 |
| `qwen3.5-9b-nothink` | 0.820 | 213 |
| `gemma-4-12b` | 0.803 | 207 |
| `granite-4.1-8b` | 0.774 | 189 |
| `ministral-8b` | 0.710 | 207 |
| `phi4-mini` | 0.372 | 210 |

## Studi 2-3 — routing, un item per volta

4195 run su **20 item** (`r01`..`r20`), esito binario per item. Disegno **appaiato**: ogni condizione (studio x modello x rendering) vede tutti e 20 gli item.

### Item a pavimento — 3 su 20

Item che nessun modello, in nessun rendering, risolve piu' del 5% delle volte:

| item | successi | run | tasso | IC95 |
|---|---:|---:|---:|---|
| `r02` | 0 | 210 | 0.000 | [0.000, 0.018] |
| `r19` | 0 | 210 | 0.000 | [0.000, 0.018] |
| `r10` | 1 | 211 | 0.005 | [0.001, 0.026] |

Sono il 15% del denominatore e tolgono la stessa quota a tutte le condizioni: non misurano il trattamento, misurano l'item. Vanno riportati a parte.

Escursione fra item: dal 0.0% (`r02`) al 81.0% (`r06`).

### Quota di item risolti, per modello

| modello | studio 2 | studio 3 | scarto |
|---|---:|---:|---:|
| `qwen3.5-9b-nothink` | 0.143 | 0.264 | +0.121 |
| `gemma-4-12b` | 0.343 | 0.446 | +0.103 |
| `qwen3.5-9b-think` | 0.557 | 0.633 | +0.076 |
| `granite-4.1-8b` | 0.395 | 0.380 | -0.015 |
| `phi4-mini` | 0.089 | 0.064 | -0.025 |
| `ministral-8b` | 0.611 | 0.557 | -0.054 |

Complessivo sui soli modelli locali: studio 2 = **0.356** (IC95 [0.334, 0.379], n=1676), studio 3 = **0.391** (IC95 [0.368, 0.415], n=1679).

**3 modelli salgono, 3 scendono.** Il complessivo e' la somma di due gruppi che vanno in direzioni opposte, non un effetto condiviso da tutti.

Tolti i 3 item a pavimento (denominatore 17 invece di 20), studio 3:

| modello | su 20 item | su 17 item |
|---|---:|---:|
| `claude-code-sonnet` | 0.846 | 0.996 |
| `claude-code-opus` | 0.836 | 0.983 |
| `claude-code-haiku` | 0.789 | 0.929 |
| `qwen3.5-9b-think` | 0.633 | 0.746 |
| `ministral-8b` | 0.557 | 0.655 |
| `gemma-4-12b` | 0.446 | 0.525 |
| `granite-4.1-8b` | 0.380 | 0.449 |
| `qwen3.5-9b-nothink` | 0.264 | 0.307 |
| `phi4-mini` | 0.064 | 0.076 |

## Studio 3 — la scala hosted

Tre bracci sulla stessa fixture, stessi venti item, stessi sette rendering, stesse due repliche. Fra loro si muove solo l'id del modello.

| braccio | item risolti | run | tasso | IC95 | `quality_rate` medio |
|---|---:|---:|---:|---|---:|
| `claude-code-haiku` | 221 | 280 | **0.789** | [0.738, 0.833] | 0.908 |
| `claude-code-sonnet` | 237 | 280 | **0.846** | [0.800, 0.884] | 0.942 |
| `claude-code-opus` | 234 | 280 | **0.836** | [0.788, 0.875] | 0.931 |
| sei celle locali, pooled | 657 | 1679 | 0.391 | — | 0.757 |

**Da haiku a sonnet +0.057; da sonnet a opus -0.011**, cioe' 3 run su 280. Il salto sta fra le celle locali e il primo braccio hosted; lungo la scala hosted il terzo piolo non aggiunge niente al secondo. **Il tetto di questo compito e' misurato, e non e' 1.0.**

### Profilo sui sette rendering, braccio per braccio

| rendering | `claude-code-haiku` | `claude-code-sonnet` | `claude-code-opus` |
|---|---:|---:|---:|
| `L0` | 0.800 | 0.850 | 0.850 |
| `L1` | 0.775 | 0.825 | 0.850 |
| `L2` | 0.800 | 0.850 | 0.850 |
| `L3` | 0.775 | 0.850 | 0.850 |
| `L4` | 0.800 | 0.850 | 0.850 |
| `prose-generated` | 0.825 | 0.850 | 0.850 |
| `prose-mechanical` | 0.750 | 0.850 | 0.750 |
| **escursione** | **0.075** | **0.025** | **0.100** |
| ampiezza IC 95% media | 0.246 | 0.222 | 0.226 |

Su tutti e tre l'escursione fra formati e' **piu' stretta dell'incertezza sulla singola condizione** e gli intervalli si sovrappongono: coerente con l'ipotesi che sopra la frontiera i formati non facciano differenza. Con un braccio solo era una proprieta' di quel modello; con tre e' una proprieta' del compito a quel livello di resa.

### Dove stanno i fallimenti

| item | `claude-code-haiku` | `claude-code-sonnet` | `claude-code-opus` |
|---|---:|---:|---:|
| `r02` | 14/14 | 14/14 | 14/14 |
| `r10` | 14/14 | 14/14 | 14/14 |
| `r19` | 14/14 | 14/14 | 14/14 |
| `r15` | 9/14 | 1/14 | 1/14 |
| `r11` | 5/14 | 0/14 | 1/14 |
| `r09` | 1/14 | 0/14 | 0/14 |
| `r14` | 1/14 | 0/14 | 0/14 |
| `r16` | 1/14 | 0/14 | 0/14 |
| `r05` | 0/14 | 0/14 | 1/14 |
| `r07` | 0/14 | 0/14 | 1/14 |

**`r02`, `r10`, `r19` sbagliano 14 volte su 14 su tutti e tre i bracci**, e da soli spiegano il 71% dei fallimenti di `claude-code-haiku`, il 98% dei fallimenti di `claude-code-sonnet`, il 91% dei fallimenti di `claude-code-opus`.

Non e' rumore stocastico e non lo muove nessun contesto collaterale: e' lo stesso disaccordo sul *che cosa sia* la richiesta, ripetuto identico da modelli che distano un fattore trenta di taglia. Cio' che la scala compra e' la coda — gli item che un braccio sbaglia qualche volta — non quei tre.

Escursione fra rendering, modello per modello (studio 3):

| modello | min | max | escursione | media | sd attesa |
|---|---:|---:|---:|---:|---:|
| `claude-code-sonnet` | 0.825 | 0.850 | 0.025 | 0.846 | 0.057 |
| `claude-code-opus` | 0.750 | 0.850 | 0.100 | 0.836 | 0.059 |
| `claude-code-haiku` | 0.750 | 0.825 | 0.075 | 0.789 | 0.064 |
| `qwen3.5-9b-think` | 0.550 | 0.750 | 0.200 | 0.633 | 0.076 |
| `ministral-8b` | 0.450 | 0.650 | 0.200 | 0.557 | 0.079 |
| `gemma-4-12b` | 0.300 | 0.750 | 0.450 | 0.446 | 0.079 |
| `granite-4.1-8b` | 0.211 | 0.500 | 0.289 | 0.378 | 0.077 |
| `qwen3.5-9b-nothink` | 0.200 | 0.325 | 0.125 | 0.264 | 0.070 |
| `phi4-mini` | 0.000 | 0.225 | 0.225 | 0.064 | 0.039 |

**Le escursioni non sono confrontabili fra modelli a livelli diversi.** Con un esito binario la variabilita' e' massima intorno a 0.5 e si schiaccia ai bordi (colonna `sd attesa`). Haiku e `phi4-mini` stanno entrambi vicino a un bordo: parte della loro escursione stretta e' il soffitto o il pavimento, non l'indifferenza al formato.

## Costo

| misura | media | mediana | p95 | max |
|---|---:|---:|---:|---:|
| wall_clock_ms | 34467 | 14940 | 144737 | 295421 |
| tokens_in | 8667 | 4898 | 22703 | 50208 |
| tokens_out | 1672 | 744 | 7110 | 13024 |

Distribuzioni fortemente asimmetriche: citare la mediana, non la media.

## Differenze verificate

Tutti i test sono **appaiati sull'item**: la difficolta' dell'item esce dal confronto invece di gonfiarlo. alpha = 0.05. Soglia di equivalenza fissata **a priori** a **0.1** (dieci punti percentuali), su criterio pratico: sotto quella soglia la scelta del formato non cambierebbe una decisione in un caso d'uso reale.

### Togliere il tracing (studio 2 -> studio 3)

Wilcoxon dei ranghi con segno, appaiato su `rendering x item`, soli modelli locali.

| modello | studio 2 | studio 3 | differenza | IC95 | p | esito |
|---|---:|---:|---:|---|---:|---|
| `qwen3.5-9b-nothink` | 0.143 | 0.264 | +0.121 | [+0.070, +0.173] | 3.71e-05 | sale |
| `gemma-4-12b` | 0.343 | 0.446 | +0.104 | [+0.046, +0.161] | 0.000368 | sale |
| `qwen3.5-9b-think` | 0.557 | 0.635 | +0.077 | [+0.016, +0.139] | 0.0134 | sale |
| `granite-4.1-8b` | 0.395 | 0.380 | -0.014 | [-0.069, +0.040] | 0.56 | non concluso |
| `phi4-mini` | 0.089 | 0.064 | -0.025 | [-0.057, +0.007] | 0.127 | non concluso |
| `ministral-8b` | 0.611 | 0.557 | -0.054 | [-0.117, +0.010] | 0.132 | non concluso |

**3 modelli salgono in modo significativo, 0 scendono, 3 restano senza conclusione** (3 dei quali descrittivamente in calo, ma il test non lo conferma).

Da leggere con precisione: i test **non** dimostrano un effetto in due direzioni opposte. Dimostrano un effetto positivo su una parte dei modelli e nessun effetto dimostrato sugli altri — un calo descrittivo che il test non conferma non e' un calo. Resta vero che l'effetto **non e' uniforme**: il complessivo che media tutti i modelli descrive un modello medio che non esiste.

### Il rendering conta, a modello fissato? (studio 3)

Friedman sui 20 item x 7 rendering. Kendall's W e' l'ampiezza: 0 = gli item non concordano su quale rendering sia migliore, 1 = lo ordinano tutti allo stesso modo.

| modello | chi2 | p | Kendall W | migliore | peggiore | escursione | esito |
|---|---:|---:|---:|---|---|---:|---|
| `gemma-4-12b` | 42.2 | 1.71e-07 | 0.351 | `prose-generated` | `L2` | 0.450 | il rendering conta |
| `claude-code-opus` | 24.0 | 0.000522 | 0.200 | `L0` | `prose-mechanical` | 0.100 | il rendering conta |
| `phi4-mini` | 20.2 | 0.0026 | 0.168 | `prose-generated` | `L0` | 0.225 | il rendering conta |
| `granite-4.1-8b` | 18.3 | 0.00549 | 0.161 | `L1` | `L4` | 0.289 | il rendering conta |
| `ministral-8b` | 11.6 | 0.0724 | 0.096 | `L2` | `prose-mechanical` | 0.200 | non concluso |
| `qwen3.5-9b-think` | 8.1 | 0.228 | 0.068 | `prose-generated` | `L1` | 0.200 | non concluso |
| `qwen3.5-9b-nothink` | 6.6 | 0.359 | 0.055 | `prose-generated` | `L0` | 0.125 | non concluso |
| `claude-code-sonnet` | 6.0 | 0.423 | 0.050 | `L0` | `L1` | 0.025 | non concluso |
| `claude-code-haiku` | 4.8 | 0.563 | 0.040 | `prose-generated` | `prose-mechanical` | 0.075 | non concluso |

Il rendering risulta significativo su **4 modelli su 9**.

### I bracci hosted sono indifferenti ai formati? — test di equivalenza

TOST appaiato su tutte le 21 coppie di rendering, margine ±0.1, sui 17 item non a pavimento. Equivalenza dichiarata solo se **ogni** coppia rientra nella soglia (test a intersezione-unione: conservativo, nessuna correzione per confronti multipli necessaria).

- Coppie equivalenti entro ±0.1: **9 su 21**.
- Coppia piu' lontana dall'equivalenza: `prose-generated vs prose-mechanical` (differenza +0.088, p TOST = 0.4041).
- **Verdetto: NON CONCLUSO — almeno una coppia fuori soglia.**

Lo stesso test sugli altri due bracci, che l'ipotesi la mettono alla prova invece di averla generata:

| braccio | coppie equivalenti | diff max | verdetto |
|---|---:|---:|---|
| `claude-code-haiku` | 9/21 | 0.088 | NON CONCLUSO — almeno una coppia fuori soglia |
| `claude-code-sonnet` | 21/21 | 0.029 | EQUIVALENZA DICHIARATA |
| `claude-code-opus` | 15/21 | 0.118 | NON CONCLUSO — almeno una coppia fuori soglia |

Il test gira anche sui 20 item completi: i 3 item a pavimento danno differenza zero in ogni coppia e quindi restringono la varianza, rendendo l'equivalenza *piu' facile* da dichiarare. Vale la lettura sui 17 item, riportata qui.

Lo stesso test su tutti i modelli:

| modello | quota media | coppie equivalenti | diff max | p Friedman | verdetto |
|---|---:|---:|---:|---:|---|
| `claude-code-sonnet` | 0.846 | 21/21 | 0.029 | 0.423 | indifferente al formato |
| `claude-code-opus` | 0.836 | 15/21 | 0.118 | 0.000522 | non concluso |
| `claude-code-haiku` | 0.789 | 9/21 | 0.088 | 0.563 | non concluso |
| `qwen3.5-9b-think` | 0.633 | 0/21 | 0.235 | 0.228 | non concluso |
| `ministral-8b` | 0.557 | 0/21 | 0.235 | 0.0724 | non concluso |
| `gemma-4-12b` | 0.446 | 3/21 | 0.529 | 1.71e-07 | non concluso |
| `granite-4.1-8b` | 0.380 | 0/21 | 0.344 | 0.00549 | non concluso |
| `qwen3.5-9b-nothink` | 0.264 | 1/21 | 0.147 | 0.359 | non concluso |
| `phi4-mini` | 0.064 | 3/21 | 0.265 | 0.0026 | non concluso |

Friedman e TOST rispondono a due domande diverse — *c'e' una differenza?* e *la differenza e' abbastanza piccola da non contare?* — e possono dire **entrambi no**: significa che i dati non bastano a decidere in nessuna direzione, non che l'effetto sia nullo.

### Quanti item servirebbero per decidere

Sulla coppia piu' lontana dall'equivalenza di ciascun modello, potenza 0.80, margine ±0.1:

| modello | item ora | coppia peggiore | differenza | item necessari |
|---|---:|---|---:|---|
| `claude-code-sonnet` | 17 | `L0 vs L1` | +0.029 | ~20 |
| `claude-code-opus` | 17 | `L0 vs prose-mechanical` | +0.118 | — *differenza >= margine 0.1: nessun campione la rende equivalente* |
| `claude-code-haiku` | 17 | `prose-generated vs prose-mechanical` | +0.088 | ~1726 |
| `qwen3.5-9b-think` | 17 | `L1 vs prose-generated` | -0.235 | — *differenza >= margine 0.1: nessun campione la rende equivalente* |
| `ministral-8b` | 17 | `L2 vs prose-mechanical` | +0.235 | — *differenza >= margine 0.1: nessun campione la rende equivalente* |
| `gemma-4-12b` | 17 | `L2 vs prose-generated` | -0.529 | — *differenza >= margine 0.1: nessun campione la rende equivalente* |
| `granite-4.1-8b` | 16 | `L1 vs L4` | +0.344 | — *differenza >= margine 0.1: nessun campione la rende equivalente* |
| `qwen3.5-9b-nothink` | 17 | `L0 vs prose-generated` | -0.147 | — *differenza >= margine 0.1: nessun campione la rende equivalente* |
| `phi4-mini` | 17 | `L0 vs prose-generated` | -0.265 | — *differenza >= margine 0.1: nessun campione la rende equivalente* |

Dove la differenza osservata supera gia' il margine, nessun campione la rende equivalente: li' la risposta non e' *servono piu' dati*, e' **il formato conta**.

### C'e' un formato migliore e uno peggiore, in generale?

Blocco = **(modello, item)**: ogni blocco vede tutti e sette i rendering sullo stesso item con lo stesso modello. Friedman per la domanda d'insieme, confronti appaiati con correzione di Holm per il dettaglio. La verifica gira sui **tre studi**.

| studio | blocchi | migliore | peggiore | Friedman p | Kendall W |
|---|---:|---|---|---:|---:|
| 1 — intake | 40 | `prose-generated` (0.779) | `L4` (0.701) | 0.258 | 0.032 |
| 2 — routing | 119 | `prose-generated` (0.424) | `L4` (0.294) | 0.00402 | 0.027 |
| 3 — notrace | 179 | `prose-generated` (0.626) | `L4` (0.494) | 4.06e-06 | 0.033 |

Media per formato, studio per studio (dal peggiore al migliore):

| formato | studio 1 | studio 2 | studio 3 |
|---|---:|---:|---:|
| `L4` | 0.701 | 0.294 | 0.494 |
| `L3` | 0.722 | 0.315 | 0.511 |
| `L0` | 0.742 | 0.361 | 0.515 |
| `L2` | 0.748 | 0.366 | 0.526 |
| `L1` | 0.724 | 0.391 | 0.528 |
| `prose-mechanical` | 0.761 | 0.349 | 0.559 |
| `prose-generated` | 0.779 | 0.424 | 0.626 |

Lo studio 1 **non e' significativo** (Friedman p = 0.258 su 40 blocchi, che vengono da sole 10 code): li' l'ordinamento e' solo descrittivo, e vale come conferma di direzione, non come prova. Le due affermazioni sotto sono **verificate sugli studi 2 e 3**, e lo studio 1 le accompagna senza contraddirle.

**Due affermazioni reggono:**

- **`prose-generated` e' il migliore.** Nello studio 3 batte **tutti e sei** gli altri formati con correzione di Holm (6/6), con differenze da +0.067 a +0.131. E' il risultato piu' solido della campagna. Media piu' alta anche negli studi 1 e 2.
- **`L4` e' il peggiore.** Media piu' bassa in tutti e tre gli studi; significativamente peggio di 1 formati su 6 nello studio 3 e di 2 nello studio 2. Affermazione piu' debole della precedente: in entrambi gli studi il formato che lo batte in modo significativo e' soprattutto `prose-generated`, mentre lo scarto dagli altri `Ln` non supera la soglia.

**Una affermazione NON regge: che `prose-mechanical` sia il formato peggiore.** E' 2° su 7 nello studio 1, 5° nello studio 2, 2° nello studio 3. Nello studio 3 e' significativamente **migliore** di `L4` (+0.064, Holm p = 0.101) e non e' peggiore di nessun altro formato. Sui 9 modelli dello studio 3 risulta il peggiore in 3 — fra cui `claude-code-haiku`, dove pero' lo scarto sta dentro l'intervallo della singola condizione, e `claude-code-opus`, dove quella cella e' fatta delle quattro run che hanno risposto `INVALID_INPUT` invece di eseguire.

**Cautela sull'ordinamento completo.** Kendall's W sta fra 0.027 e 0.033: la concordanza fra blocchi e' bassissima. La direzione agli estremi regge — ed e' rafforzata dal ripetersi nei tre studi — ma blocco per blocco l'ordinamento e' quasi rumore. *`L4` e' il peggiore* si puo' scrivere; *`L3` e' peggio di `L2`* no.

### Il contrasto che conta: SOL contro prosa

L'ipotesi originaria della campagna non e' sui singoli livelli, e' se faccia differenza dare al modello **l'algoritmo in SOL** oppure **lo stesso processo in prosa**. Contrasto a due gruppi: `SOL` = media di `L0`..`L4` sull'item, `PROSA` = media dei due formati in prosa. Studio 3, 17 item non a pavimento, appaiato, margine ±0.1.

| modello | SOL | PROSA | differenza | IC95 | p | esito |
|---|---:|---:|---:|---|---:|---|
| `gemma-4-12b` | 0.400 | 0.838 | -0.438 | [-0.650, -0.227] | 0.00742 | PROSA meglio |
| `phi4-mini` | 0.024 | 0.206 | -0.182 | [-0.322, -0.043] | 0.0274 | PROSA meglio |
| `qwen3.5-9b-think` | 0.716 | 0.824 | -0.108 | [-0.202, -0.014] | 0.04 | PROSA meglio |
| `qwen3.5-9b-nothink` | 0.276 | 0.382 | -0.106 | [-0.226, +0.014] | 0.128 | non concluso |
| `granite-4.1-8b` | 0.431 | 0.531 | -0.100 | [-0.238, +0.038] | 0.22 | non concluso |
| `claude-code-sonnet` | 0.994 | 1.000 | -0.006 | [-0.017, +0.006] | 0.317 | equivalenti |
| `claude-code-haiku` | 0.929 | 0.926 | +0.003 | [-0.039, +0.045] | 0.785 | equivalenti |
| `ministral-8b` | 0.671 | 0.618 | +0.053 | [-0.036, +0.142] | 0.324 | non concluso |
| `claude-code-opus` | 1.000 | 0.941 | +0.059 | [+0.007, +0.111] | 0.0455 | SOL meglio |

**La prosa batte SOL su 3 modelli locali su 6**, fino a 0.438 su `gemma-4-12b`. **Nessun modello locale mostra il contrario in modo significativo** (`ministral-8b` ha il segno invertito ma non regge il test).

| braccio hosted | SOL | PROSA | differenza | IC95 | TOST | esito |
|---|---:|---:|---:|---|---:|---|
| `claude-code-haiku` | 0.929 | 0.926 | +0.003 | [-0.039, +0.045] | 0.0002 | equivalenti |
| `claude-code-sonnet` | 0.994 | 1.000 | -0.006 | [-0.017, +0.006] | 0.0000 | equivalenti |
| `claude-code-opus` | 1.000 | 0.941 | +0.059 | [+0.007, +0.111] | 0.0700 | SOL meglio |

Su `claude-code-haiku` e `claude-code-sonnet` le due strade sono **equivalenti**: differenza +0.003 (IC95 [-0.039, +0.045], TOST p = 0.0002) e -0.006 (TOST p = 0.0000), entrambe dentro il margine di ±0.1. Dove il TOST sulle 21 coppie non concludeva, questo contrasto conclude: aggregare cinque livelli contro due formati toglie molto rumore rispetto al confronto di una condizione contro un'altra.

**Un modello rompe il quadro, ed e' `claude-code-opus`: SOL batte la prosa** (+0.059, p = 0.0455). E' l'unico *SOL meglio* significativo di tutta la campagna, e prima di citarlo va detto da dove viene: le quattro run `prose-mechanical` in cui quel modello ha risposto `INVALID_INPUT` invece di eseguire — cioe' un rifiuto motivato, non una comprensione peggiore della prosa. Su quel braccio la prosa non e' *peggio capita*: e' l'unico formato in cui il modello ha applicato la clausola di guardia del processo. Contarlo come un punto a favore di SOL sarebbe leggere il banco al posto del modello.

Anche contro `prose-generated` — il formato migliore d'insieme — Haiku non mostra differenza:

| confronto | differenza | TOST |
|---|---:|---|
| `prose-generated vs L0` | +0.029 | equivalente |
| `prose-generated vs L1` | +0.059 | non concluso |
| `prose-generated vs L2` | +0.029 | equivalente |
| `prose-generated vs L3` | +0.059 | non concluso |
| `prose-generated vs L4` | +0.029 | equivalente |
| `prose-generated vs prose-mechanical` | +0.088 | non concluso |

**Cautela sul soffitto.** Su quei 17 item Haiku sta fra 0.882 e 0.971 in ogni condizione: c'e' pochissimo spazio per differire. L'equivalenza vale **a quel livello di prestazione** — non dimostra che i formati siano equivalenti in assoluto, dimostra che per un modello che risolve quasi tutto non fanno differenza.

**Trasparenza sull'ordine dei test.** Questo contrasto e' stato specificato *dopo* aver visto i risultati coppia-a-coppia. Corrisponde all'ipotesi originaria della campagna e il margine di equivalenza non e' stato adattato all'esito, ma non e' una pre-registrazione: chi lo cita lo dica.

### Quali bracci vale la pena riproporre

Domanda operativa, non di pubblicazione: la soglia qui non e' `p < 0.05`, e' **"quel braccio ha mai portato un beneficio?"**

Rango di ciascun formato dentro ogni cella studio x modello (21 celle, 1 = migliore dei sette):

| formato | rango medio | migliore su 7 | peggiore su 7 | quinto o peggio |
|---|---:|---:|---:|---:|
| `prose-generated` | 2.45 | 9 | 1 | 2 |
| `L2` | 3.88 | 3 | 1 | 9 |
| `prose-mechanical` | 3.98 | 1 | 4 | 7 |
| `L1` | 4.02 | 3 | 4 | 8 |
| `L0` | 4.14 | 1 | 1 | 8 |
| `L3` | 4.40 | 1 | 0 | 11 |
| `L4` | 5.12 | 0 | 5 | 13 |

**`L4` non e' mai il migliore, in nessuna delle 21 celle**, ed e' il peggiore in 5. `L3` ha lo stesso profilo attenuato (migliore 1 volte, peggiore 0).

Nella matrice completa dei 21 confronti per studio, con Holm, **nessun livello SOL batte mai niente** in nessuno dei tre studi — unica eccezione `L1` che batte `L4` nello studio 2. Tutto cio' che vince, lo vince `prose-generated`:

| formato | batte | battuto da | saldo |
|---|---:|---:|---:|
| `prose-generated` | 6 | 0 | +6 |
| `prose-mechanical` | 0 | 0 | +0 |
| `L1` | 1 | 1 | +0 |
| `L2` | 0 | 1 | -1 |
| `L0` | 0 | 1 | -1 |
| `L3` | 0 | 1 | -1 |
| `L4` | 0 | 3 | -3 |

**Onesta' sulla molteplicita'**: sui sette test dei segni con correzione di Holm solo `prose-generated` sopravvive (p = 0.010); `L4` sale a 1.00. Come **prova statistica** l'evidenza contro `L4` e' direzionale, non conclusiva. Come **criterio di selezione dei bracci** e' sufficiente: non ha mai portato un beneficio in tre studi.

#### Il meccanismo: il contesto collaterale costa la finestra

| formato | token prompt (mediana) | token output | tasso |
|---|---:|---:|---:|
| `L0` | 2710 | 590 | 0.353 |
| `L1` | 2720 | 652 | 0.383 |
| `L2` | 3122 | 648 | 0.372 |
| `L3` | 9782 | 672 | 0.353 |
| `L4` | 11758 | 580 | 0.324 |
| `prose-generated` | 2379 | 360 | 0.512 |
| `prose-mechanical` | 2437 | 515 | 0.442 |

Spearman fra token del prompt e tasso di successo: **rho = -0.400, p = 0.5046**. Piu' contesto collaterale, meno resa, in modo monotono.

Il salto di costo non e' graduale: da `L2` a `L3` il prompt cresce di **3.1 volte** (3122 -> 9782 token) e non compra nulla. `L4` costa 4.9 volte `prose-generated` per il risultato peggiore.

Era previsto: `doc/experiment-minimum-context.md:575` — *«the L scale competes with reasoning for the window ... A model that closes well at L1 may have no room left at L4. The curve can be a bell rather than a step.»* La campagna lo conferma, e `tokens_out` a `L4` scende a 580 contro i 652 di `L1`.

#### Raccomandazione

**Non riproporre `L3` e `L4`.** Sono la stessa scommessa — pagare tre-quattro volte il prompt per dare al modello la specifica e gli esempi — e nei dati non paga mai. Il confine di costo sta fra `L2` e `L3` ed e' netto.

Bracci da tenere: **`L0`, `L1`, `L2`** (tutti sotto i 3122 token) e i **due formati in prosa**. Cinque bracci invece di sette, e ci sta dentro tutto cio' che ha mostrato di avere un effetto.

#### Il contrasto ristretto ai bracci consigliati

Tolti `L3` e `L4`, il confronto giusto e' **il meglio di SOL** (`L0`, `L1`, `L2`) contro la prosa — ed e' anche il piu' onesto verso SOL, perche' toglie i due livelli che lo zavorravano.

| modello | SOL (L0,L1,L2) | prosa | differenza | IC95 | esito |
|---|---:|---:|---:|---|---|
| `gemma-4-12b` | 0.431 | 0.838 | -0.407 | [-0.611, -0.203] | PROSA meglio |
| `phi4-mini` | 0.020 | 0.206 | -0.186 | [-0.334, -0.038] | PROSA meglio |
| `qwen3.5-9b-think` | 0.703 | 0.824 | -0.121 | [-0.222, -0.020] | PROSA meglio |
| `qwen3.5-9b-nothink` | 0.284 | 0.382 | -0.098 | [-0.196, +0.000] | PROSA meglio |
| `claude-code-sonnet` | 0.990 | 1.000 | -0.010 | [-0.029, +0.009] | equivalenti |
| `claude-code-haiku` | 0.931 | 0.926 | +0.005 | [-0.038, +0.048] | equivalenti |
| `granite-4.1-8b` | 0.542 | 0.531 | +0.010 | [-0.132, +0.153] | non concluso |
| `ministral-8b` | 0.637 | 0.618 | +0.020 | [-0.068, +0.108] | equivalenti |
| `claude-code-opus` | 1.000 | 0.941 | +0.059 | [+0.007, +0.111] | SOL meglio |

**Con i soli bracci consigliati la prosa batte SOL su 4 modelli locali** (erano 3 confrontando tutti e cinque i livelli). Togliere `L3` e `L4` rende il confronto piu' **preciso**, non piu' favorevole a SOL.

**`claude-code-haiku` resta equivalente su entrambe le letture**: contro `prose-generated` differenza -0.039 (IC95 [-0.099, +0.020], TOST p = 0.0315); contro entrambi i formati in prosa differenza **+0.005** esatto (IC95 [-0.038, +0.048], TOST p = 0.0003).

Gli altri due bracci, sul contrasto ristretto contro entrambi i formati in prosa:

| braccio | SOL (L0,L1,L2) | prosa | differenza | TOST | esito |
|---|---:|---:|---:|---:|---|
| `claude-code-sonnet` | 0.990 | 1.000 | -0.010 | 0.0000 | equivalenti |
| `claude-code-opus` | 1.000 | 0.941 | +0.059 | 0.0700 | SOL meglio |


**Cautela sul soffitto, qui piu' stringente che altrove**: su quei 17 item `prose-generated` con Haiku risolve una quota di 0.971. L'affermazione che regge e' *su un compito che Haiku risolve quasi interamente, dare l'algoritmo in SOL o in prosa non cambia nulla*; non dimostra che non cambierebbe su un compito piu' difficile.

**Nota di metodo.** L'equivalenza di Haiku e' emersa da tre contrasti successivi — 21 coppie, SOL vs prosa, SOL ristretto vs prosa — tutti specificati dopo aver visto i risultati precedenti. Sono raffinamenti della **stessa** ipotesi, non tre conferme indipendenti: uscire tre volte non moltiplica l'evidenza.

**Cosa e' cambiato il 2026-09-02.** I bracci `claude-code-sonnet` e `claude-code-opus` sono dati nuovi, raccolti dopo che questi contrasti erano stati specificati, quindi il contrasto gira su di loro **fuori campione**. Va detto con precisione cosa questo e' e cosa non e': la pre-registrazione di quei bracci riguardava la scala di qualita' e la posizione dei fallimenti (`doc/experiment-minimum-context.md` §12), **non** il contrasto SOL/prosa. Quindi e' una replica su dati nuovi, non una conferma pre-registrata di questa ipotesi. Su `claude-code-sonnet` regge; su `claude-code-opus` il segno si inverte per via delle quattro run `INVALID_INPUT`.

## Il formato migliore e' una proprieta' della coppia (modello, compito)

La campagna contiene due compiti diversi — `support-intake` (una coda di 6-11 item per run) e `support-routing` (un item per run) — girati sugli stessi sei modelli locali con gli stessi sette rendering. Permette quindi un controllo: la preferenza di formato e' del **modello** o della **coppia**?

| modello | compito A — intake | compito B — routing | B senza tracing |
|---|---|---|---|
| `gemma-4-12b` | `prose-generated` | `prose-generated` | `prose-generated` |
| `granite-4.1-8b` | `L0` | `L1` | `L1` |
| `ministral-8b` | `prose-generated` | `L2` | `L2` |
| `phi4-mini` | `L2` | `prose-generated` | `prose-generated` |
| `qwen3.5-9b-nothink` | `prose-mechanical` | `prose-generated` | `prose-generated` |
| `qwen3.5-9b-think` | `L1` | `L3` | `prose-generated` |

| confronto | concordano | p contro il caso |
|---|---:|---:|
| **stesso compito**, due studi separati | **5/6** | 0.00031 |
| **compito diverso** | **1/6** | 0.603 |

Il caso puro darebbe 0.86 concordanze su 6. Dentro lo stesso compito ce ne sono 5: la preferenza e' reale e ripetibile. Cambiando compito ne resta 1, **esattamente quanto ricominciando da zero**.

`ministral-8b` e `phi4-mini` si scambiano di posto — il primo da `prose-generated` a `L2`, il secondo da `L2` a `prose-generated`. Non e' che uno preferisca la prosa e l'altro SOL: la preferenza **si inverte col compito**.

**Conseguenza operativa: non esiste una tabella di raccomandazioni da consultare.** Non *gemma vuole la prosa*, non *usa la prosa sui modelli piccoli*. La risposta vale per la coppia che si ha davanti e decade appena se ne cambia uno dei due elementi: va misurata sul posto.

Il che rende SOL utile per una ragione diversa dall'essere il formato migliore: e' **l'unico punto da cui si generano tutte le forme dello stesso algoritmo**. Una procedura scritta direttamente in prosa, per essere confrontata con le alternative, andrebbe riscritta — e a quel punto non si confrontano piu' notazioni ma documenti diversi, che e' l'errore che `build_prose_mechanical.py` evita sostituendo la sola sezione di processo.

## Due formalismi, non prosa contro struttura

`prose-mechanical` non e' "la prosa": il generatore sostituisce **solo la sezione di processo** e copia il resto byte per byte, con il renderer deterministico dello skill. Il risultato ha la **stessa struttura** dello script SOL — stessi passi, stesse condizioni, stesso ordine — scritta in linguaggio naturale invece che in JSON.

| braccio | struttura | notazione |
|---|---|---|
| `L0` | quella di SOL | **JSON** |
| `prose-mechanical` | quella di SOL | **linguaggio naturale**, resa deterministica |
| `prose-generated` | riscritta da un modello, non garantita | linguaggio naturale |

Il percorso `L0 -> prose-mechanical -> prose-generated` e' quindi una scomposizione. Aggregato su 152 blocchi (modello x item), appaiato:

| passaggio | guadagno | IC95 | p Holm |
|---|---:|---|---:|
| notazione: JSON -> prosa strutturata | **+0.052** | [-0.001, +0.104] | 0.0576 |
| riscrittura: prosa strutturata -> prosa generata | **+0.079** | [+0.026, +0.132] | 0.0193 |
| totale: JSON -> prosa generata | **+0.130** | [+0.074, +0.187] | 0.0001 |

**Il 39% del guadagno viene dal solo cambio di notazione**, il 61% dalla riscrittura. Entrambi i passaggi reggono da soli, ma il secondo e' al limite (p Holm 0.019) e dipende dall'ampiezza della famiglia di test — con la famiglia piu' larga usata sopra non passava. Il primo e' piu' saldo.

**Non e' la struttura a costare, e' la sintassi JSON.** `prose-mechanical` ha la stessa struttura di SOL e cambia solo come e' scritta; quel cambio da solo vale meta' del beneficio della conversione completa. Il formalismo di SOL non e' il problema: lo e' la sua rappresentazione in JSON, per i modelli che faticano a leggerla.

L'effetto della sola notazione, modello per modello:

| modello | `L0` (JSON) | `prose-mechanical` | guadagno |
|---|---:|---:|---:|
| `gemma-4-12b` | 0.441 | 0.794 | +0.353 |
| `qwen3.5-9b-nothink` | 0.235 | 0.382 | +0.147 |
| `phi4-mini` | 0.000 | 0.147 | +0.147 |
| `qwen3.5-9b-think` | 0.716 | 0.765 | +0.049 |
| `claude-code-sonnet` | 1.000 | 1.000 | +0.000 |
| `granite-4.1-8b` | 0.531 | 0.531 | +0.000 |
| `claude-code-haiku` | 0.941 | 0.882 | -0.059 |
| `ministral-8b` | 0.588 | 0.529 | -0.059 |
| `claude-code-opus` | 1.000 | 0.882 | -0.118 |

Positivo su 4 modelli su 9, nessuno regge la correzione da solo: e' un fenomeno **aggregato**, e il segnale sta quasi tutto in `gemma-4-12b` (+0.353 da un cambio di notazione a contenuto identico). Su `claude-code-haiku` l'effetto e' nullo o leggermente negativo, coerente con tutto il resto.

La riga di `phi4-mini` vale da sola: con `L0` fa **0.000**, con la stessa identica procedura in prosa strutturata **0.147**. Non e' che non sappia fare il compito: non sa leggere quella notazione.

### L'ipotesi di progetto: «il JSON e' quasi nativo per l'AI»

SOL usa JSON perche' si e' assunto che i modelli lo riconoscano e lo maneggino quasi nativamente, piu' di YAML o XML. La scomposizione sopra la mette alla prova, perche' isola il costo della notazione a struttura e contenuto identici.

**Non vale per tutti.** Passare dal JSON alla resa in linguaggio naturale guadagna +0.052 nell'aggregato e +0.353 su `gemma-4-12b`: se il JSON fosse letto nativamente da ogni modello, quel guadagno non esisterebbe. La scelta della sintassi ha un costo, e non e' distribuito uniformemente.

#### Una regola diagnostica che sembra perfetta e non lo e'

Verrebbe naturale dedurne un test rapido: *misura la penalita' JSON di un modello e saprai se somministrargli SOL o la prosa*. Nello studio 3 la regola azzecca **8/9** — tutti.

**Fuori campione azzecca 4/6**, e la quantita' su cui poggia non e' stabile:

| modello | penalita' studio 2 | penalita' studio 3 | stesso segno |
|---|---:|---:|---|
| `gemma-4-12b` | -0.088 | +0.353 | NO |
| `granite-4.1-8b` | +0.000 | +0.000 | si |
| `ministral-8b` | -0.059 | -0.059 | si |
| `phi4-mini` | +0.206 | +0.147 | si |
| `qwen3.5-9b-nothink` | -0.118 | +0.147 | NO |
| `qwen3.5-9b-think` | -0.029 | +0.049 | NO |

Spearman fra le due misure: **rho = -0.143, p = 0.787** — nessuna relazione. Il segno si inverte su 3 modelli su 6.

Il 8/9 e' **circolare**: la penalita' (`L0` contro `prose-mechanical`) e la famiglia vincente (massimo fra i sette) sono calcolate sugli **stessi 16 item**. Se per un modello `prose-mechanical` batte `L0`, e' gia' piu' probabile che il massimo cada fra i formati in prosa: la corrispondenza e' quasi aritmetica, non predittiva. **E' riportata qui con la sua smentita perche' chi la ricalcolera' la ritrovera'.**

Spiegazione alternativa, da tenere: studio 2 e studio 3 non differiscono solo per campionamento — il secondo ha il tracing tolto dai comandi. L'instabilita' potrebbe essere un'**interazione** fra notazione e tracing, non rumore. La conclusione pratica non cambia: la penalita' JSON non e' una proprieta' del modello indipendente dal contesto, e non si puo' usare come diagnostico.

Quello che invece e' stabile e' il risultato diretto — il formato migliore per modello, che coincide fra i due studi su 5 modelli su 6. La conclusione *come somministrarla dipende dal modello* regge; la strada per deciderlo e' misurare il formato migliore, non stimare l'affinita' al JSON.

## Le conclusioni operative, messe alla prova

### 1. Un po' di contesto in piu' per capire SOL aiuta? Quanto ne serve?

`L1` e `L2` contro `L0` crudo, tutti e 9 i modelli, appaiato, Holm sui 18 confronti: **0 casi su 18** in cui il contesto aggiuntivo migliora in modo significativo.

**Non serve nessun contesto aggiuntivo**, a nessun livello. E' il risultato piu' solido della campagna sul piano operativo — non dipende dal soffitto di Haiku ne' da contrasti specificati a posteriori: e' un confronto diretto su tutti i modelli.

Che `L3`/`L4` **peggiorino** e' un'affermazione diversa, verificata a parte qui sotto: non regge. L'argomento contro quei due livelli e' il **costo**, non un danno dimostrato.

### 2. Sui modelli commerciali: usatelo crudo?

**Sostenuta su tre bracci su tre.** `L0` crudo risolve: `claude-code-haiku` **94.1%** (equivalente a 5/6 altri formati), `claude-code-sonnet` **100.0%** (equivalente a 6/6 altri formati), `claude-code-opus` **100.0%** (equivalente a 5/6 altri formati), sui 17 item risolvibili, margine TOST ±0.1. 'Crudo' non e' un compromesso: e' il massimo, al costo minimo.

Due limiti da dichiarare insieme all'affermazione:

- **sono tre modelli della stessa famiglia, su UNA fixture, al soffitto.** Il plurale ora e' nei dati per tre modelli hosted su tre, ma la fixture resta una e la famiglia una; nessun modello non-Anthropic e' stato testato;
- **il "minimo di contesto" non serve**: non c'e' un solo modello su cui aggiungerlo abbia aiutato. La forma difendibile e' *usatelo crudo*; l'alternativa con contesto va presentata come innocua, non come migliore.

### 3. Sui modelli locali: convertitelo in prosa?

**Sostenuta nella direzione, non nel metodo, e non su tutti.** La prosa batte SOL su 4 modelli locali su sei (bracci ristretti); su `granite-4.1-8b` e `ministral-8b` non c'e' differenza, e vanno anzi entrambi leggermente a favore di SOL.

Sul *come* convertire, `prose-generated` (resa da un modello con prompt congelato) contro `prose-mechanical` (renderer deterministico `sol2prose.py`):

| modello | generated | mechanical | differenza | esito |
|---|---:|---:|---:|---|
| `ministral-8b` | 0.706 | 0.529 | +0.176 | non concluso |
| `phi4-mini` | 0.265 | 0.147 | +0.118 | non concluso |
| `claude-code-opus` | 1.000 | 0.882 | +0.118 | non concluso |
| `qwen3.5-9b-think` | 0.882 | 0.765 | +0.118 | non concluso |
| `claude-code-haiku` | 0.971 | 0.882 | +0.088 | non concluso |
| `gemma-4-12b` | 0.882 | 0.794 | +0.088 | non concluso |
| `claude-code-sonnet` | 1.000 | 1.000 | +0.000 | non concluso |
| `granite-4.1-8b` | 0.531 | 0.531 | +0.000 | non concluso |
| `qwen3.5-9b-nothink` | 0.382 | 0.382 | +0.000 | non concluso |

Nessuna differenza significativa su nessun modello. La direzione favorisce la resa generata in 6 casi su 9, ma non e' dimostrata. **"Convertitelo in prosa" regge; "usando il prompt" e' una preferenza pratica, non un risultato.**

### 4. Il ramo `prose-mechanical` e' un fallimento del convertitore?

**Non sostenuta — i dati dicono il contrario.**

Aggregato su 152 blocchi (modello x item), studio 3, item non a pavimento:

| confronto | differenza | p | dopo Holm |
|---|---:|---:|---|
| `prose-mechanical vs prose-generated` | -0.079 | 0.0097 | peggio |
| `prose-mechanical vs L4` | +0.076 | 0.0202 | non concluso |
| `prose-mechanical vs L0` | +0.052 | 0.0576 | non concluso |
| `prose-mechanical vs L1` | +0.036 | 0.1437 | non concluso |
| `prose-mechanical vs L2` | +0.038 | 0.1929 | non concluso |

Il convertitore deterministico produce output che fa risolvere **piu' item di SOL crudo**, in modo significativo, e **non e' distinguibile da `prose-generated`**. Rango medio 3.98 su sette — secondo, davanti a tutti e cinque i livelli SOL. Bilancio nei tre studi: 0 vinte, 0 perse.

**Nota epistemologica, valida e da tenere.** Questi numeri sono una proprieta' di `sol2prose.py`, non della conversione meccanica come classe: da qui non si conclude nulla su cosa farebbe un convertitore migliore. Ma lo stesso argomento impedisce la conclusione opposta — non si puo' dichiarare immaturo cio' che non ha sottoperformato. Una valutazione qualitativa della prosa prodotta (leggibilita', fedelta', casi che sbaglia) sarebbe una base legittima, ma e' un'altra evidenza: non e' questa campagna.

### 5. "Piu' contesto spesso peggiora" — regge?

**No.** `L3` e `L4` testa a testa contro `L0`/`L1`/`L2`: su 54 confronti per modello con Holm, **0 peggioramenti significativi** e 0 miglioramenti. Sull'aggregato per blocchi:

| confronto | differenza | p | dopo Holm |
|---|---:|---:|---:|
| `L3 − L0` | -0.008 | 0.7413 | 0.9145 |
| `L3 − L1` | -0.023 | 0.3302 | 0.9145 |
| `L3 − L2` | -0.021 | 0.2286 | 0.9145 |
| `L4 − L0` | -0.024 | 0.2819 | 0.9145 |
| `L4 − L1` | -0.039 | 0.1553 | 0.7764 |
| `L4 − L2` | -0.037 | 0.0296 | 0.1776 |

La formulazione esatta e': **dare altro contesto non aiuta mai, e costa tre volte tanto.** Il livello piu' caro e' anche il piu' debole per ogni misura descrittiva — mai il migliore in 21 celle, il peggiore in 5, battuto da `prose-generated` in due studi — ma il peggioramento rispetto ai livelli economici **non e' dimostrato**. La raccomandazione di lasciar perdere `L3`/`L4` resta, e l'argomento decisivo e' il costo: si paga il triplo per un beneficio mai osservato.

### 6. "Sui locali il formato migliore va trovato con i test" — i test sono stabili?

**Si', e questo la rafforza.** Il formato migliore per modello coincide fra studio 2 e studio 3 — due studi indipendenti — su **5 modelli locali su 6**:

| modello | migliore studio 2 | migliore studio 3 | concorda |
|---|---|---|---|
| `gemma-4-12b` | `prose-generated` | `prose-generated` | si |
| `granite-4.1-8b` | `L1` | `L1` | si |
| `ministral-8b` | `L2` | `L2` | si |
| `phi4-mini` | `prose-generated` | `prose-generated` | si |
| `qwen3.5-9b-nothink` | `prose-generated` | `prose-generated` | si |
| `qwen3.5-9b-think` | `L3` | `prose-generated` | no |

Da notare `granite-4.1-8b` e `ministral-8b`: il loro formato migliore e' un **livello SOL**, in entrambi gli studi. Non e' rumore, e' ripetuto. *Testalo* non e' una formula di prudenza: i test danno risposte stabili, e la risposta non e' la stessa per tutti.

### 7. "I modelli di frontiera si comporteranno come Haiku" — e' nei dati?

**Adesso si', ed e' stato misurato invece che estrapolato.** Fino al 2026-09-01 questa riga diceva *ipotesi di lavoro, non conseguenza dei dati*, e quantificava il costo della verifica in ~280 run per modello. La verifica e' stata fatta il 2026-09-02: `claude-code-sonnet` e `claude-code-opus`, 280 run ciascuno, stessa fixture e stesse coordinate (protocollo e predizione registrati **prima** della corsa in `doc/experiment-minimum-context.md` §12).

| braccio | tasso | `quality_rate` | escursione fra formati | attesa dal caso |
|---|---:|---:|---:|---:|
| `claude-code-haiku` | 0.789 | 0.908 | 0.0882 | 0.0882 |
| `claude-code-sonnet` | 0.846 | 0.942 | 0.0294 | 0.0294 |
| `claude-code-opus` | 0.836 | 0.931 | 0.1176 | 0.0588 |

**Cosa e' confermato**: la consegna e il tipo di guasto. Tutti e tre restituiscono un oggetto leggibile in tutte le run e falliscono solo per valore sbagliato, mai per lettura del formato.

**Cosa e' confermato a meta'**: la piattezza sui formati. Su `claude-code-sonnet` e' ora **dimostrata** — 21/21 coppie entro ±0.1, l'unico modello della campagna con equivalenza dichiarata su tutte le coppie. Su `claude-code-haiku` resta *non conclusa* come prima. Su `claude-code-opus` **no**: la sua escursione e' il doppio dell'attesa dal caso, e sta tutta in una cella — `prose-mechanical`, dove quattro run hanno risposto `INVALID_INPUT` invece di eseguire. Tolte quelle quattro, la sua riga e' piatta come le altre; contate, non lo e'. La riga onesta e' questa, non la media.

**Cosa e' smentito**: che la scala continuasse a salire. Da sonnet a opus il tasso fa -0.011 — 3 run su 280 — e i tre item che nessuno dei tre risolve sono gli stessi. Il tetto di questo compito si tocca al secondo piolo, e non e' 1.0.

**I modelli non stanno comunque su una scala di potenza.** Sono qualitativamente diversi, e ordinarli per resa media su questa fixture chiamandola capacita' e' lo stesso errore che il documento di disegno vieta per i sette rendering. Lo scarto su cui contare e' **i tre bracci hosted contro i sei locali**; fra i tre hosted non c'e' scala.

L'escursione fra formati si comprime da sola vicino al soffitto, quindi confrontare le escursioni grezze non dice nulla. Correzione: per ogni modello si simula il mondo in cui il formato **non ha alcun effetto** — tenendo la difficolta' di ogni item come e' — e si guarda quanta escursione il caso produrrebbe comunque a quel livello (5000 simulazioni, seed fisso).

| modello | resa | escursione osservata | attesa dal caso | p |
|---|---:|---:|---:|---:|
| `claude-code-haiku` | 0.929 | 0.0882 | 0.0882 | 0.706 |
| `qwen3.5-9b-nothink` | 0.307 | 0.1471 | 0.1176 | 0.737 |
| `qwen3.5-9b-think` | 0.746 | 0.2353 | 0.1765 | 0.933 |
| `claude-code-sonnet` | 0.996 | 0.0294 | 0.0294 | 0.961 |
| `ministral-8b` | 0.655 | 0.2353 | 0.1471 | 0.978 |
| `granite-4.1-8b` | 0.460 | 0.3438 | 0.1875 | 0.989 |
| `claude-code-opus` | 0.983 | 0.1176 | 0.0588 | 0.999 |
| `gemma-4-12b` | 0.525 | 0.5294 | 0.1471 | 1.000 |
| `phi4-mini` | 0.076 | 0.2647 | 0.1176 | 1.000 |

`claude-code-haiku` ha escursione **0.0882** contro un'attesa dal caso di **0.0882** (p = 0.706): esattamente quella che il caso prevede al suo livello. **La sua piattezza non e' un artefatto del soffitto** — la simulazione il livello lo tiene in conto. Tutti e 6 i modelli locali stanno invece sopra l'attesa.


**Un ordinamento a tre livelli darebbe un punto in piu'?** `Haiku > qwen3.5-9b-think > altri` regge **sulla resa**: nello studio 3 `qwen-think` batte tutti e cinque gli altri locali (appaiato, Holm) e Haiku batte `qwen-think` di 0.165; nello studio 2 ne batte quattro su cinque.

Ma **non si trasferisce alla sensibilita' al formato**. Rapporto fra escursione osservata e attesa dal caso:

| modello | rapporto | p |
|---|---:|---:|
| `claude-code-haiku` | 1.00 | 0.706 |
| `claude-code-sonnet` | 1.00 | 0.961 |
| `qwen3.5-9b-nothink` | 1.25 | 0.737 |
| `qwen3.5-9b-think` | 1.33 | 0.933 |
| `ministral-8b` | 1.60 | 0.978 |
| `granite-4.1-8b` | 1.83 | 0.989 |
| `claude-code-opus` | 2.00 | 0.999 |
| `phi4-mini` | 2.25 | 1.000 |
| `gemma-4-12b` | 3.60 | 1.000 |

`qwen3.5-9b-think` e' **4o su 9** per piattezza, non secondo: sopra di lui c'e' `qwen3.5-9b-nothink`, che sulla resa e' quasi il peggiore. Il modello locale piu' forte non e' il piu' piatto.

**Non c'e' un gradiente da estrapolare: c'e' un salto, e sta fra i bracci hosted e tutto il resto.** E' anche la forma piu' difendibile — una discontinuita' non obbliga a ordinare modelli che qualitativamente non sono ordinabili, mentre una tendenza si'. E il salto ora ha tre punti dalla sua parte invece di uno.

**E la piattezza da sola non e' una virtu': lo e' solo in alto.** `qwen3.5-9b-nothink` ha rapporto 1.25, piatto quasi quanto Haiku, ma a un livello che rende la piattezza irrilevante. La misura operativa e' il **pavimento garantito** — la resa del formato peggiore, cioe' quel che si ottiene non testando:

| modello | formato migliore | migliore | formato peggiore | pavimento | costo di sbagliare |
|---|---|---:|---|---:|---:|
| `claude-code-sonnet` | `L0` | 1.000 | `L1` | **0.971** | 0.029 |
| `claude-code-haiku` | `prose-generated` | 0.971 | `prose-mechanical` | **0.882** | 0.088 |
| `claude-code-opus` | `L0` | 1.000 | `prose-mechanical` | **0.882** | 0.118 |
| `qwen3.5-9b-think` | `prose-generated` | 0.882 | `L1` | **0.647** | 0.235 |
| `ministral-8b` | `L2` | 0.765 | `prose-mechanical` | **0.529** | 0.235 |
| `gemma-4-12b` | `prose-generated` | 0.882 | `L2` | **0.353** | 0.529 |
| `granite-4.1-8b` | `L1` | 0.588 | `L4` | **0.250** | 0.338 |
| `qwen3.5-9b-nothink` | `prose-generated` | 0.382 | `L0` | **0.235** | 0.147 |
| `phi4-mini` | `prose-generated` | 0.265 | `L0` | **0.000** | 0.265 |

Con Haiku il pavimento e' 88.2%: sbagliare formato lascia comunque sopra il migliore dei locali. Con i locali il pavimento va da 0.0% a 64.7% — con `phi4-mini` e `L0` crudo si finisce a zero. **La scelta del formato e' un'assicurazione, e serve solo dove il pavimento e' basso.**

Rovescio incoraggiante: `qwen3.5-9b-think` con `prose-generated` arriva a 0.882, il livello che i bracci hosted toccano nel loro caso peggiore. Un modello locale ci arriva — deve solo azzeccare il formato.

Restano **tre modelli della stessa famiglia, su una fixture**. Sonnet e Opus non sono piu' un'attesa; Fable e ogni modello non-Anthropic lo sono ancora, e un braccio costa **280 run** — lo studio 3 cosi' com'e'.

## Lo strato operativo

Misure che vengono **prima** della resa: non quanto bene il modello esegue, ma se arriva a eseguire. E' la parte determinata dal contesto di esecuzione — 8 GB di VRAM, quantizzazioni e finestre scelte per rendere i modelli operativi — e non compare in nessuna percentuale di resa.

### La frontiera: le run che non consegnano

`no-output` + `refused` + `timeout` — il modello non ha prodotto niente di utilizzabile. E' un guasto diverso da *risponde sbagliato*, e chiede un rimedio opposto: finestra e meno cerimonia invece di un formato migliore.

| modello | 1 — intake | 2 — routing | 3 — notrace |
|---|---:|---:|---:|
| `claude-code-haiku` | — | — | 0/280 (0%) |
| `claude-code-opus` | — | — | 0/280 (0%) |
| `claude-code-sonnet` | — | — | 0/280 (0%) |
| `gemma-4-12b` | 0/207 (0%) | 4/280 (1%) | 0/280 (0%) |
| `granite-4.1-8b` | 2/189 (1%) | 1/276 (0%) | 0/276 (0%) |
| `ministral-8b` | 1/207 (0%) | 0/280 (0%) | 0/280 (0%) |
| `phi4-mini` | 77/210 (37%) | 25/280 (9%) | 24/280 (9%) |
| `qwen3.5-9b-nothink` | 9/213 (4%) | 78/280 (28%) | 0/280 (0%) |
| `qwen3.5-9b-think` | 83/210 (40%) | 79/280 (28%) | 53/283 (19%) |

Due configurazioni su sei perdono fra un terzo e i due quinti delle esecuzioni sul banco a coda **senza mai arrivare a una risposta**. I tre bracci hosted: **0 su 840 run** in tutti e tre gli indicatori. Sopra la frontiera lo strato operativo sparisce, e non su un modello solo.

### La resa condizionata alla consegna

| modello | resa grezza | resa se risponde | quota muta |
|---|---:|---:|---:|
| `qwen3.5-9b-think` | 0.595 | **0.777** | 23.4% |
| `ministral-8b` | 0.584 | **0.584** | 0.0% |
| `gemma-4-12b` | 0.395 | **0.397** | 0.7% |
| `granite-4.1-8b` | 0.388 | **0.388** | 0.2% |
| `qwen3.5-9b-nothink` | 0.204 | **0.237** | 13.9% |
| `phi4-mini` | 0.077 | **0.084** | 8.8% |

`qwen3.5-9b-think` e `ministral-8b` hanno resa grezza quasi identica (0.595 contro 0.584) e **non sono intercambiabili**: il primo e' il migliore dei locali quando parla, e tace il 23% delle volte; il secondo e' piu' debole e non tace mai. Per chi mette in produzione e' la distinzione piu' utile della campagna.

### La finestra di contesto

`stop_reason = 'length'` su **294 run su 4591** locali = **6.4%**. E' l'unico punto in cui il vincolo hardware si vede direttamente nel dato. Distribuzione fortemente concentrata:

```
qwen3.5 210   phi4 45   qwen3.5 28   ministral 7   granite 4   gemma 0
```

| rendering | quota `length` | token prompt (mediana) |
|---|---:|---:|
| `L0` | 0.090 | 3161 |
| `L1` | 0.099 | 3169 |
| `L2` | 0.073 | 3578 |
| `L3` | 0.051 | 10296 |
| `L4` | 0.040 | 12257 |
| `prose-generated` | 0.038 | 3111 |
| `prose-mechanical` | 0.058 | 2954 |

**I livelli che costano tre-quattro volte il prompt troncano *meno*, non di piu'.** Qualunque cosa faccia perdere `L3` e `L4`, non e' restare senza spazio per rispondere: un'ipotesi in meno da difendere, e l'argomento economico contro quei bracci ne esce rafforzato.

### Il divario 1,5% contro 35,6% non e' un effetto: e' un esponente

Le code dello studio 1 hanno da **6 a 11** item (media semplice 8.70, su 10 code). La quota di code risolte alla perfezione e la quota di item risolti a caso singolo **non hanno la stessa unita'**.

```
quota media di item corretti per coda      p = 0.7324
lunghezza media della coda (pesata sulle run)  k = 8.72
se gli errori fossero indipendenti, p^k      = 0.0662
code perfette osservate                      = 0.0154
item risolti nello studio 2 (locali)         = 0.3562
```

La catena e' 0.732 -> 0.066 -> 0.015: **quasi tutta la distanza e' il denominatore**, cioe' chiedere ~9 decisioni tutte giuste invece di una. Il residuo e' cio' che resterebbe da attribuire, e fra i due banchi sono cambiate tre cose insieme (consegna, accumulo di stato, un asse di decisione in piu' a caso singolo): non e' attribuibile a nessuna delle tre.

Sull'unita' piu' vicina a un confronto alla pari, il banco a coda fa **0.732** contro **0.356** del banco a caso singolo: **il verso si rovescia.** Con la cautela che *item corretto* nella coda e *tutti e 8 i campi* a caso singolo non sono il medesimo criterio.

### Dove si rompe la coda, modello per modello

| modello | arresto (somma) | `no-halt` | `halt-not-taken` | `wrong-value` | `no-output` |
|---|---:|---:|---:|---:|---:|
| `qwen3.5-9b-nothink` | **0.958** | 0.742 | 0.216 | 0.000 | 0.028 |
| `ministral-8b` | **0.768** | 0.729 | 0.039 | 0.159 | 0.005 |
| `gemma-4-12b` | **0.643** | 0.594 | 0.048 | 0.014 | 0.000 |
| `qwen3.5-9b-think` | **0.110** | 0.090 | 0.019 | 0.357 | 0.376 |
| `granite-4.1-8b` | **0.101** | 0.026 | 0.074 | 0.878 | 0.005 |
| `phi4-mini` | **0.010** | 0.010 | 0.000 | 0.619 | 0.290 |

Sull'aggregato l'arresto e' **540 run su 1236** (44%): il modo di fallimento piu' frequente in assoluto, e riguarda l'unico costrutto che dipende da quel che e' successo prima.

**Ma vale su 3 modelli su 6.** `granite-4.1-8b` e `phi4-mini` sbagliano il *valore*, `qwen3.5-9b-think` *non consegna*. *Il fallimento e' l'arresto* e' un'affermazione sull'aggregato, non sul modello medio — che non esiste.

Il modo piu' istruttivo e' `halt-not-taken` — **82 run su 1236**, di cui **46 su `qwen3.5-9b-nothink`**: il modello individua il punto di arresto, lo scrive nella risposta, e poi consegna comunque l'intera coda. Legge *fermati qui* come un fatto da riportare, non come un'uscita da prendere.

### Studio 2, `gemma-4-12b`: l'insieme dei rami e' congelato

Domanda diversa da *quanti item risolve*: su quali item imbocca il **ramo** giusto. Su 20 item, l'insieme e' **identico** in 6 rendering su 7 — non solo lo stesso conteggio, gli stessi item:

```
L0, L1, L2, L3, L4, prose-mechanical
  -> n=8: ['r01', 'r02', 'r03', 'r06', 'r07', 'r08', 'r15', 'r20']
prose-generated
  -> n=10: aggiunge ['r11', 'r18']
```

Cinque livelli crescenti di documentazione e il renderer deterministico lasciano l'insieme **invariato**: allegare la specifica non ne aggiunge uno ne' ne toglie uno. Solo la prosa generata lo rompe. Nota: due degli item a ramo corretto sono item a pavimento, che `gemma` sbaglia comunque — ramo giusto e risposta giusta sono misure diverse.

### Come falliscono i bracci hosted, e la colonna da non usare

| braccio | run | fallimenti | `degradation_mode` |
|---|---:|---:|---|
| `claude-code-haiku` | 280 | 59 | {'none': 221, 'wrong-value': 59} |
| `claude-code-sonnet` | 280 | 43 | {'none': 237, 'wrong-value': 43} |
| `claude-code-opus` | 280 | 46 | {'none': 234, 'wrong-value': 46} |

**Tutti dello stesso tipo: risposta ben formata, valore sbagliato**, su 840 run complessive. Zero `no-output`, zero `refused`, zero `partial-sequence`. Nessuno dei tre ha mai fallito la *lettura* del formato: hanno sbagliato il *giudizio sul caso*. E' l'evidenza piu' diretta che SOL sia autoesplicativo sopra la frontiera — misurata su tre modelli, non inferita da una differenza di tassi.

**Una riga a parte, 4 run su 840.** `claude-code-opus` su `prose-mechanical`: lo `status` restituito non e' `OK` ma INVALID_INPUT. Non e' una risposta sbagliata, e' un rifiuto motivato di eseguire — il primo passo del processo dice di leggere un file, il banco a E0 l'input lo pre-inietta nel prompt, e quel modello ha applicato la clausola di guardia invece di usare l'input che aveva sotto gli occhi. L'oracolo le conta come fallite, e per il suo metro lo sono; il disaccordo pero' e' sulla convenzione del banco, non sulla comprensione del processo.

**Attenzione a `fidelity`**: nello studio 3 vale `fail` su tutte le 2519 run, Haiku compreso, e `sequence_rate` e' costante a 0. Lo studio 3 e' quello *senza tracing*: il controllo di sequenza non ha nulla da controllare. In quello studio `fidelity` non e' una misura di fedelta' e non va citata.

### Le misure abbandonate

Colonne vuote o costanti. Non sono guasti: sono strade di misura immaginate all'inizio e non perseguite. Vanno dichiarate, perche' chi apre i dati grezzi le trova comunque.

| colonna | valorizzata su | valori distinti |
|---|---:|---:|
| `comprehension_rate` | 1479/5431 | 30 |
| `conditional_rate` | 1479/5431 | 46 |
| `sequence_rate` | 5421/5431 | 85 |
| `redundancy_ratio` | 5421/5431 | 95 |

`expected_branch` / `observed_branch` non sono **mai** state valorizzate, in nessuno dei tre studi. `comprehension_rate` / `conditional_rate` esistono solo dove il tracing esiste. `sequence_rate` e' costante a zero nello studio 3.

### `L4` contro `L0`, cella per cella

Su **12 celle** (6 configurazioni locali x 2 banchi a caso singolo): **7 peggiora, 3 migliora, 2 pari**. Guadagno massimo **+0.125**, perdita massima **-0.267**.

L'asimmetria sta nell'**ampiezza**, non nella frequenza — e nessuno di questi scarti regge il test testa a testa con Holm. L'argomento contro `L3`/`L4` resta il **costo**.

### Classificare e' molto piu' facile che eseguire

Nello studio 1 il tracing espone il passo di classificazione separatamente dall'esito complessivo. Sul sottoinsieme dove e' leggibile (n=643 su 1236): etichetta **tutte** le richieste correttamente nel 10.1% dei casi, contro 1.4% di code interamente risolte — **7.22x**. Su tutto il banco: 5.3% contro 1.5% — 3.42x.

La selezione ha un verso: quelle righe le emette chi il protocollo non ha strozzato, quindi il sottoinsieme e' fatto dei modelli che se la cavavano meglio. **Vanno riportati entrambi i denominatori.**

## Cosa resta aperto

- Lo studio 1 non e' stato testato: unita' diversa (la coda, non l'item) e solo 10 code, contro 20 item appaiati degli studi 2-3.
- L'ordinamento fra modelli non e' stato testato: gli item sono appaiati fra condizioni, ma il confronto fra modelli su un solo compito (`support-routing-notrace`) resta un campione di **tre compiti** in tutto. Il numero di run non allarga quel perimetro.
- I 3 item a pavimento non sono stati diagnosticati: nessuna configurazione li risolve, il che e' un fatto sulla fixture, non sui modelli. Dal 2026-09-02 il punto e' piu' stretto: `r02`, `r10`, `r19` resistono anche a tre modelli hosted, quindi sono un disaccordo sulla verita' di riferimento, non una difficolta' di resa.
- La scala hosted e' una sola famiglia (Anthropic) su una sola fixture: nessun modello di altro fornitore e' stato misurato, e il compito e' uno.

---

# Conclusione

SOL descrive un processo. Per usarlo con un modello come **istruzioni da eseguire** ci sono piu' strade, tutte gia' dentro la skill: darglielo **crudo**, oppure renderlo in linguaggio naturale — con il renderer deterministico o facendolo rendere all'AI.

**Quale sia la strada giusta non si puo' sapere in anticipo, e non e' una proprieta' del modello.** E' una proprieta' della coppia *modello + compito*: sui due compiti della campagna il formato migliore per lo stesso modello coincide su **1 modello su 6**, quanto il puro caso, mentre sullo stesso compito misurato due volte coincide su **5 modelli su 6**. `ministral-8b` e `phi4-mini` si scambiano proprio di posto cambiando compito.

Quindi non c'e' una tabella da consultare: c'e' un test da fare, sul proprio modello e sul proprio compito. **Ed e' qui che SOL serve** — non perche' sia il formato migliore, ma perche' e' l'unico punto da cui si generano tutte le forme dello stesso algoritmo. Scritta la procedura una volta, i renderer producono le varianti da confrontare; scritta direttamente in prosa, per confrontarla bisognerebbe riscriverla, e non si confronterebbero piu' notazioni ma documenti diversi.

Il resto sono i fatti che quel test, sui casi misurati qui, ha prodotto.

Nessuna di queste strade e' un ripiego, e non sono la stessa cosa. Il renderer deterministico **non produce "prosa"**: produce la stessa struttura di SOL — stessi passi, stesse condizioni, stesso ordine — scritta in linguaggio naturale invece che in JSON. Sono due formalismi, non struttura contro discorsivita'.

E quel solo cambio di notazione vale il **39% del guadagno** della conversione completa (+0.052 su +0.130): non e' la struttura di SOL a costare, e' la sua rappresentazione in JSON. La riscrittura da parte di un modello aggiunge il resto (+0.079), ma con un margine piu' fragile.

Sui modelli hosted — tre, testati: `haiku`, `sonnet`, `opus` — le due strade sono **equivalenti**: SOL crudo risolve il 94.1% dei 17 item risolvibili su haiku, il miglior formato in prosa il 97.1%, e i due non sono distinguibili; sugli altri due bracci il quadro e' lo stesso. Chi lavora li' puo' usarlo nativo, e risparmiare il passaggio di conversione.

Su **modelli locali** la strada migliore va individuata con dei test — e i test danno risposte stabili: su **5 modelli su 6** il formato migliore coincide in due studi indipendenti. Per 4 modelli su sei quella risposta e' la prosa; per 2 — `granite-4.1-8b`, `ministral-8b` — e' un livello SOL, ripetutamente.

**Dare al modello piu' contesto per capire SOL non aiuta.** Su 18 confronti fra il livello minimo e i livelli intermedi: 0 miglioramenti. E i due livelli piu' ricchi — specifica ed esempi del repository — costano **3.1 volte** il prompt senza mai ripagarlo.

Detto in termini di rischio invece che di resa: **la scelta del formato e' un'assicurazione, e serve solo dove il pavimento e' basso.** Il pavimento e' cio' che si ottiene col formato peggiore, cioe' non testando e pescando a caso. Con `claude-code-haiku` vale **88.2%**: sbagliare formato costa 0.088 e lascia comunque sopra il migliore dei locali. Con i modelli locali il pavimento va da **0.0%** a **64.7%**.

Vale anche il rovescio, ed e' la parte incoraggiante: `qwen3.5-9b-think` col formato giusto (`prose-generated`) arriva a **0.882** — il livello che i bracci hosted toccano nel loro caso peggiore. Un modello locale ci arriva; deve solo azzeccare il formato, e loro no.

Quello che separa i bracci hosted dai locali non e' un gradiente ma **un salto**: la loro escursione fra i sette formati coincide con quella che il caso produrrebbe comunque al loro livello (haiku 0.0882 osservata contro 0.0882 attesa), mentre tutti e 4591 i locali stanno sopra la loro. E il locale piu' capace non e' il piu' insensibile al formato: non c'e' una scala da prolungare.

Che i modelli piu' capaci di Haiku stessero dalla sua parte del salto era un'attesa dichiarata non verificata. **Ora e' verificata**: Sonnet e Opus stanno dalla stessa parte — e la scala si ferma li', perche' da Sonnet a Opus il tasso fa -0.011 e i tre item che nessuno risolve sono gli stessi per tutti e tre.

---

# Commento — da dove viene ogni affermazione

Il testo sopra e' la sintesi da cui si e' partiti, riscritta dove i dati non la reggevano. Qui si dice, frase per frase, cosa la sostiene e cosa e' stato tolto.

### "Nessuna delle due e' un ripiego"

Era l'affermazione piu' a rischio, perche' la lettura iniziale era l'opposta: che il ramo `prose-mechanical` fosse un fallimento del convertitore. I dati dicono il contrario. Sui 152 blocchi non a pavimento il renderer deterministico batte `L0` crudo (+0.052) e `L4` (+0.076), entrambi con Holm, e non e' distinguibile da `prose-generated`. Rango medio 3.98 su sette: secondo, davanti a tutti e cinque i livelli SOL.

Resta vero — ed e' un'obiezione corretta — che quei numeri parlano di `sol2prose.py`, non della conversione meccanica come classe. Ma vale in entrambe le direzioni: impedisce di generalizzare a un convertitore migliore, e impedisce di dichiarare immaturo cio' che non ha sottoperformato.

### "Su Haiku le due strade sono equivalenti"

Sostenuta: contrasto SOL contro prosa, differenza +0.005 esatta, IC95 [-0.038, +0.048], TOST p = 0.0003 entro il margine di ±0.1 fissato a priori.

Fino al 2026-09-01 era l'**unico** caso di equivalenza dimostrata della campagna. Non lo e' piu': `claude-code-sonnet`, dato nuovo e quindi fuori campione rispetto a questo contrasto, e' l'unico modello con equivalenza dichiarata su **tutte e 21** le coppie di rendering, oltre che sul contrasto aggregato. L'affermazione esce rafforzata da un braccio che non e' servito a costruirla.

Due cose sono state tolte dalla formulazione iniziale.

La prima: *"o con un minimo di contesto"*. Il minimo di contesto **non serve** — non c'e' un solo modello su cui aggiungerlo abbia aiutato — quindi presentarlo come alternativa equivalente e' corretto, come alternativa migliore no.

La seconda: il plurale. *"I modelli commerciali"* era un modello solo; dal 2026-09-02 sono tre, della stessa famiglia, sulla stessa fixture, e tutti e tre **al soffitto**: `prose-generated` risolve il 97% dei 17 item risolvibili su haiku, non c'e' spazio sopra, e Opus non ne trova. L'affermazione che regge e' *su un compito che i modelli hosted risolvono quasi interamente, SOL o prosa non cambia nulla*; non dimostra che non cambierebbe su un compito piu' difficile — e il fatto che Opus non superi Sonnet dice che quel compito non si ottiene salendo di modello.

C'e' anche un problema di percorso, dichiarato in 8.8: l'equivalenza e' emersa da tre contrasti successivi, ciascuno specificato dopo aver visto il precedente. Sono raffinamenti della stessa ipotesi, non tre conferme indipendenti.

### "Su modelli locali va individuata con dei test"

Sostenuta, e rafforzata da una verifica che non era nella sintesi di partenza: **i test danno risposte stabili**. Il formato migliore per modello coincide fra studio 2 e studio 3 — due studi indipendenti, separati dalla rimozione del tracing — su 5 modelli su 6.

Il dettaglio che rende la frase una raccomandazione vera e non una scappatoia: per `granite-4.1-8b`, `ministral-8b` il formato migliore e' un **livello SOL**, in entrambi gli studi. Se la risposta fosse sempre *converti*, dire *testalo* sarebbe una perdita di tempo; siccome per due modelli su sei la risposta e' *no*, non lo e'.

Tolto dalla formulazione iniziale: *"convertitelo usando il prompt"*. Il **come** convertire non e' deciso dai dati — `prose-generated` contro `prose-mechanical` non e' significativo su nessuno dei 9 modelli, pur andando nella stessa direzione in 6 casi. *Convertitelo in prosa* regge; *usando il prompt* e' una preferenza pratica.

### "Dare piu' contesto non aiuta"

E' il risultato piu' solido della campagna sul piano operativo: 0 miglioramenti su 18 confronti appaiati, con Holm. Non dipende dal soffitto di Haiku, non dipende da contrasti scelti a posteriori, non dipende dalla scelta del margine: e' un confronto diretto, su tutti e 9 i modelli.

Qui e' stato tolto un pezzo della formulazione iniziale — *"e spesso peggiora"* — e vale la pena dire perche', perche' l'errore era anche di chi ha scritto la prima versione di questo foglio. `L3` e `L4` testa a testa contro `L0`/`L1`/`L2`: su 54 confronti per modello, **0 peggioramenti significativi**. Sull'aggregato per blocchi nessuna differenza sopravvive alla correzione.

Il livello piu' caro **e'** il piu' debole per ogni misura descrittiva — mai il migliore in 21 celle, il peggiore in 5, battuto da `prose-generated` in due studi — ma *essere il peggiore* e *peggiorare le cose* sono affermazioni diverse, e solo la prima e' dimostrata. La raccomandazione non cambia; cambia l'argomento, che diventa **economico**: si paga il triplo del prompt (3122 -> 9782 token) per un beneficio mai osservato. Ed e' un argomento piu' difficile da attaccare.

### "Ci aspettiamo che i modelli piu' capaci si comportino come Haiku"

Fino al 2026-09-01 questa era rimasta nel testo marcata come **attesa non verificata**, e la marcatura era la correzione. Il 2026-09-02 e' stata **verificata**: due bracci in piu', 280 run ciascuno, protocollo e predizione registrati prima della corsa. Quel che segue e' perche' la marcatura era giusta, e cosa la verifica ha cambiato.

Il ragionamento — *gia' Haiku non fa differenze, quindi Sonnet, Opus e Fable nemmeno* — sembra un'estrapolazione lungo una scala di capacita'. **Quella scala non esiste**: i modelli sono qualitativamente diversi, e ordinarli per resa su questa fixture chiamandola potenza e' un errore di categoria. Una versione precedente di questo foglio lo commetteva, correlando resa e sensibilita' al formato sui sette punti che allora c'erano; l'analisi e' stata rifatta.

Il contrasto che regge e' **Haiku contro i sei locali**, corretto per il livello: escursione osservata 0.0882 contro 0.0882 attesa dal caso (p = 0.706), mentre tutti i locali stanno sopra la loro attesa. E' un risultato solido, e toglie di mezzo l'obiezione del soffitto che pesava su tutte le altre affermazioni su Haiku.

Da **un punto solo** non si estrapolava, ed era giusto non farlo: i sei locali non formano una scala che porta verso Haiku, quindi non c'era nessuna tendenza da prolungare fino a Sonnet o Opus. La verifica ha dato ragione all'ipotesi sul comportamento — piattezza sui formati, consegna sempre, fallimenti solo di valore — e torto a chi l'avrebbe letta come una scala: da sonnet a opus il tasso fa -0.011, e i tre item che nessuno risolve sono gli stessi.

La lezione di metodo e' quella: l'estrapolazione sarebbe stata *quasi* giusta, e la parte sbagliata — la direzione della scala — e' proprio quella che nessuno avrebbe controllato. **La marcatura come attesa e' costata due bracci; leggerla come conseguenza dei dati sarebbe costata una conclusione falsa.**
