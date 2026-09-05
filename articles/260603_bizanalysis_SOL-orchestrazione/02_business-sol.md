# A che condizioni un processo scritto viene davvero eseguito

*Secondo di tre articoli. Il primo presenta SOL, un formato per scrivere processi che un'AI esegue
direttamente, e si chiude con tre domande. Questo risponde. v5, 2026-09-02.*

> **Una nota sul testo, e chi ha deciso cosa.**
>
> Il testo l'ha steso un'AI. Lo dichiaro perché in un articolo di numeri la domanda giusta non è chi
> ha scritto le frasi: è chi ha deciso cosa i dati potevano dire.
>
> Le ipotesi le ho depositate io prima di lanciare, in modo da potermi smentire. Esecuzione, conti e
> analisi sono lavoro della macchina, diversi rilievi contro quello che avevo già
> scritto sono emersi dalla riflessione sui dati fatta a quattro mani: alcune conclusioni non hanno 
> retto ai conti rifatti e sono uscite dall'articolo. Resta comunque
> mia, oltre alla revisione a mano dei casi di test, la scelta di cosa qui si possa affermare.
>
> Questa è la sintesi. Metodo per esteso, dati grezzi e notebook stanno nel repository: ogni numero
> citato si ricalcola da lì.
>
> — Gianni Tommasi

---

## Il perimetro

- Otto gigabyte di VRAM. Ha determinato quali modelli, quantizzazioni e finestre di contesto fossero
  provabili. Con sedici sarebbe un altro studio.
- Un dominio: segnalazioni su software. Processi di taglia media.
- Sei configurazioni locali e tre modelli commerciali. 5.421 esecuzioni concluse: 4.581 in casa,
  840 sui commerciali.
- Tre studi in sequenza, ciascuno nato da cosa ha mostrato il precedente. Nessuna media li attraversa.
- Ci sono casi di test che nessuno — nemmeno i commerciali — ha risolto. Abbassano all'85% il massimo
  successo conseguito.

**Non è una classifica di modelli né una misura assoluta di SOL**. La domanda era: *esistono condizioni
in cui un processo scritto una volta viene eseguito davvero? Quali, quanto rendono, come si rompe
quando non ci sono.*

---

## Le domande

1. Un modello piccolo, di quelli che girano su una macchina normale, capisce il processo così com'è,
   senza aiuti?
2. Se dello stesso processo preparo una versione in prosa, ottengo un risultato migliore?
3. Se gli passo anche le spiegazioni su come interpretare il formato, miglioro o peggioro?

Scritte prima di lanciare.

---

## Il banco

Triage di richieste di supporto: classificare, stimare le ore da una tabella, verificare un budget,
instradare su tre squadre con regole di precedenza e stati di carico.

I casi vengono da NLBSE'24 Issue Report Classification[^1]: segnalazioni reali da React, TensorFlow,
VS Code, Bitcoin e OpenCV, etichettate come *bug*, *richiesta di funzionalità* o *domanda*.
Estrazione casuale con seme fisso, stratificata. Il progetto di provenienza è nascosto al modello.

Ho ricontrollato le etichette a mano su 91 dei 150 casi usati. **Ne ho cambiate 23**, quasi tutte
nella stessa direzione: marcate *domanda*, erano *bug*. Un quarto delle etichette di riferimento
andava corretto.

Una risposta passa solo se **tutti** i campi coincidono con l'atteso. Un campo sbagliato su otto
affonda il caso.

**I tre studi.**

| | unità | cosa chiede |
|---|---|---|
| 1 | una coda di 6–11 richieste per invocazione | esegui portandoti dietro lo stato: ogni richiesta presa scala il budget |
| 2 | una richiesta per invocazione | stesse regole, stato nei dati d'ingresso, più l'instradamento su tre squadre |
| 3 | come 2 | identico, tolto l'obbligo di mostrare il lavoro |

Gli studi 2 e 3 girano su venti richieste fisse, le stesse in ogni condizione.

**Le sette forme.** Lo stesso algoritmo consegnato in sette modi: il documento nudo (`L0`); lo stesso
con quattro livelli crescenti di spiegazione (`L1`–`L4`), fino alla specifica completa del formato;
e due versioni in prosa. La **prosa algoritmica** esce da un convertitore deterministico in Python
che converte le convenzioni JSON in testo struttrato tradizionale, copiando alla lettera il testo delle istruzioni. La **prosa generata** la
scrive un modello, da un prompt fissato in anticipo. Entrambi i convertitori fanno parte della skill
che accompagna SOL.

**I modelli.** Qwen3.5 9B, Ministral 3 8B, Granite 4.1 8B, Gemma 4 12B, Phi-4 mini, quantizzati per
stare su una GPU da 8 GB. Qwen provato in due modalità che si comportano come due modelli diversi:
sei configurazioni locali. Accanto, tre modelli commerciali sul solo studio 3, 280 esecuzioni
ciascuno: **Haiku 4.5**, **Sonnet 5** e **Opus 5** — dal più piccolo al più capace della famiglia
Claude, stessi casi, stesse forme, stesse repliche.

La prima versione di questo articolo ne aveva uno solo, e diceva a chiare lettere che *«se i modelli
più capaci stiano dalla parte di Haiku»* era un'attesa e non un risultato. Gli altri due sono stati
lanciati per chiuderla, con l'ipotesi depositata prima. Risposta: **da Haiku in su non cambia nulla
di quello che conta qui**, e per questo nel resto dell'articolo i tre stanno in una riga sola.

---

## Le risposte

### 0. Un modello commerciale capisce SOL senza aiuti?

**Sì, la risposta è incontrovertibile: Haiku, Sonnet e Opus non distinguono tra una forma e l'altra**.
Se sbagliano, sbagliano sempre sugli stessi item: interpretano male quella richiesta, non le istruzioni 
per indirizzarla.

94,1% Haiku, 100% Sonnet e Opus. Zero esecuzioni senza risposta su 840. Ogni fallimento è **"risposta ben formata, valore
sbagliato"**: zero errori di lettura, di formato o di consegna, su tutti e tre. Nessuno di loro ha
mai fallito la lettura del processo — hanno sbagliato il giudizio sul caso.

Sull'intero banco i tre commerciali fanno 78,9%, 84,6% e 83,6%: il
gradino sta fra i locali e il primo di loro, non fra il primo e gli altri due. Salire di modello
dopo Haiku non compra niente su questo compito — la differenza fra il secondo e il terzo vale tre
esecuzioni su 280 — e la ragione si legge in un fatto solo: **le tre richieste che nessuno risolve
sono le stesse per tutti e tre**, sbagliate quattordici volte su quattordici da modelli che distano
un fattore trenta di taglia. Non è capacità che manca: è disaccordo su che cosa sia la richiesta.


### 1. Un modello piccolo lo capisce senza aiuti?

La risposta è molto più variegata.

**Modelli locali, documento nudo: da 0,000 a 0,760.** Phi-4 mini non ne risolve nemmeno una.

Non c'è un gradiente. I sei modelli locali non formano una scala che porta verso i commerciali: il
locale più forte non è il più insensibile alla forma. C'è una discontinuità, e sta lì.

Da qui in poi, quindi, «i commerciali» al plurale: una riga sola per tutti e tre.

### 2. La prosa fa meglio?

**Su quattro modelli locali su sei, sì.** Su Gemma la differenza vale 43 punti.

**Su due — Granite e Ministral — no**: il formato migliore è un livello SOL, in entrambi gli studi
indipendenti.

**Sui commerciali la differenza non c'è**: +0,005 su Haiku e −0,010 su Sonnet, dentro un margine di
incertezza di quattro punti e mezzo. SOL o prosa, per quei modelli, è la stessa cosa.

Anzi, dovendo proprio dire, su Opus il segno gira — +0,059 a favore di SOL — e vale la pena dire da dove viene, perché non è una
differenza di comprensione. Il processo, al primo passo, dice di leggere il *file* della richiesta; il
banco non passa davvero un file: ne incolla il contenuto dentro il prompt. In quattro esecuzioni della sola prosa
algoritmica Opus si è fermato lì, ha risposto *input non valido* ed è uscito allo step iniziale
invece di proseguire. È l'unico modello dei nove che l'ha fatto, ed è l'esecuzione più letterale della
procedura scritta in tutta la campagna: il disaccordo è con una convenzione del banco, non con il
documento.

### 3. Spiegare il formato aiuta?

**Mai.** Diciotto confronti diretti fra il documento nudo e i livelli con spiegazione, su tutti e
nove i modelli: zero miglioramenti.

Sui due livelli più ricchi il conto è di costo. `L4` non è mai il migliore in ventuno combinazioni
di studio e modello, ed è il peggiore in cinque. Per arrivarci il prompt passa da 3.122 token a
11.758: **quasi quattro volte tanto**, per un beneficio mai osservato.

Il confine sta fra il secondo e il terzo livello.

---

## Quello che non cercavo

### Il formato migliore è una proprietà della coppia modello + compito

Due compiti diversi, stessi sei modelli, stesse sette forme.

```
stesso compito, misurato due volte  :  5 modelli su 6 concordano    p = 0,0003
compito diverso                     :  1 modello su 6              p = 0,60
                       (il puro caso ne darebbe 0,86 su 6)
```

Dentro lo stesso compito la preferenza si ripete. **Cambiando compito solo in un caso su sei la preferenza 
viene mantenuta:.** Ministral e Phi-4 mini si scambiano di posto — il primo passa dalla
prosa a un livello SOL, il secondo fa il percorso inverso.

Non esiste una tabella di raccomandazioni. Non *«Gemma vuole la prosa»*, non *«usa la prosa sui
modelli piccoli»*: la risposta vale per la coppia che avete davanti e decade appena ne cambiate uno
dei due elementi.

### Nei modelli locali, non è la struttura a costare, è il JSON

La prosa algoritmica ha la **stessa struttura** dello script SOL — stessi passi, stesse condizioni,
stesso ordine — scritta in linguaggio naturale invece che in JSON. Il percorso è quindi una
scomposizione:

| passaggio | guadagno |
|---|---:|
| notazione: da JSON a prosa strutturata | **+0,093** |
| riscrittura: da prosa strutturata a prosa generata | +0,081 |
| totale | +0,174 |

**Il 53% del guadagno viene dal solo cambio di notazione**, a struttura e contenuto identici.

Phi-4 mini con `L0` fa **0,000**; con la stessa identica procedura in prosa strutturata fa **0,156**.
Non è che non sappia fare il compito: non sa leggere quella notazione.

Una delle ipotesi con cui SOL è nato è che l'AI legga JSON quasi nativamente. Per una parte dei
modelli non è vero.

### Non consegnare e consegnare sbagliato sono due guasti diversi

Esecuzioni che non hanno prodotto niente — nessuna risposta, rifiuto, tempo scaduto:

| modello | studio 1 | studio 2 | studio 3 |
|---|---:|---:|---:|
| `qwen3.5-9b-think` | 40% | 28% | 19% |
| `phi4-mini` | 37% | 9% | 9% |
| `qwen3.5-9b-nothink` | 4% | 28% | 0% |
| `granite-4.1-8b` | 1% | 0% | 0% |
| `gemma-4-12b` | 0% | 1% | 0% |
| `ministral-8b` | 0% | 0% | 0% |
| i tre commerciali | — | — | **0%** |

Separando *risponde male* da *non risponde*, due modelli che sembrano pari non lo sono:

| | resa grezza | resa quando risponde | quota muta |
|---|---:|---:|---:|
| `qwen3.5-9b-think` | 0,595 | **0,777** | 23,4% |
| `ministral-8b` | 0,584 | 0,584 | 0,0% |

Il primo è il migliore dei locali quando parla e tace un quarto delle volte; il secondo è più debole
e non manca mai. Rimedi opposti: al primo serve finestra e meno cerimonia, al secondo un formato
migliore. Un tasso aggregato li rende indistinguibili.

### Lo stato che attraversa i passi è il punto di rottura

Nel banco a coda ogni richiesta presa scala il budget: la stessa richiesta, in una posizione diversa,
prende un ramo diverso. Un bug che non ci sta nel budget **ferma tutto**.

**L'arresto è il modo di fallimento più frequente: 540 esecuzioni su 1.236, il 44%.** È l'unico
costrutto che dipende da quel che è successo prima. Vale su tre modelli su sei; sugli altri tre il
guasto è altrove — sbagliano il valore, o non consegnano.

Come si rompe: **il modello individua il punto di arresto, lo scrive nella risposta, e poi consegna
comunque l'intera coda.** In 82 esecuzioni, 46 delle quali su una sola configurazione. Legge
"fermati qui" come un fatto da riportare, non come un'uscita da prendere.

**Il processo tenga le regole, il sistema tenga lo stato.** Consegnate un caso per invocazione, con
lo stato nei dati d'ingresso, e il costrutto che si rompe non c'è più.

### Chiedere di mostrare il lavoro si paga in risposte mancate

I primi due banchi chiedevano una riga di protocollo per ogni valutazione e ogni ramo preso. Il
terzo è il clone senza quell'obbligo.

Le due configurazioni che il protocollo strozzava consegnavano **solo nel 72%** dei casi; tolto
l'obbligo salgono al **100%** e all'**81%**. Il protocollo non fa sbagliare le risposte: fa sì che
non arrivino.

Definite il risultato atteso e verificate quello. Se vi serve l'audit, fatelo fare al sistema attorno
al modello.

### Quello che il modello sa gestire è congelato

Su Gemma, guardando una cosa sola — se imbocchi il ramo giusto — su venti richieste sempre le stesse:

```
L0, L1, L2, L3, L4, prosa algoritmica  →  8 richieste
prosa generata                         →  10 richieste
```

Non otto di numero: **gli stessi identici otto**, caso per caso, in tutte e sei le versioni.
Allegare la specifica non ne aggiunge uno né ne toglie uno. Solo la prosa generata rompe il
congelamento, e recupera esattamente due dei casi mancanti.

Sono i casi in cui la risposta è "assegna alla squadra che possiede il prodotto". Ogni caso che
richiede di instradare altrove o di rimandare, Gemma lo sbaglia, in tutte e sei le versioni.

Nel banco c'è un caso costruito apposta perché fosse insidioso: la squadra competente è satura e la
risposta corretta è comunque non deviare. Gemma lo supera tre volte su tre — **perché non devia
mai**. Dei nove casi che richiedono di spostare o rimandare non ne risolve nemmeno uno.

Conta quali casi passano, non quanti.

---

## Cosa possiamo dire su SOL

**Nei modelli commerciali SOL è autoesplicativo, e il crudo è il massimo.** Tutti e tre leggono il
documento nudo senza un solo errore di lettura in 840 esecuzioni, risolvono fra il 94% e il 100% del
risolvibile, e non distinguono fra SOL e prosa. *Crudo* non è un compromesso: è il risultato
migliore, al costo minimo — e vale su tre modelli su tre, non su uno.

**Sotto la frontiera la domanda cambia.** Non *qual è il linguaggio giusto*, ma *quale
trasformazione, per questo modello, per questo compito, su questa macchina*. E quella domanda non ha una risposta
pubblicabile: ha una procedura.

**Quindi non c'è una tabella, c'è un processo di test.** Ed è qui che sta il valore di SOL.

Non serve perché sia il formato che il modello legge meglio — su quattro locali su sei non lo è.
Serve perché è **l'unico punto da cui si generano tutte le forme dello stesso algoritmo**. Scritta
la procedura una volta, i convertitori producono le varianti da confrontare, e quello che confrontate
sono notazioni della stessa regola. Scritta direttamente in prosa, per confrontarla dovreste
riscriverla, e da lì confrontereste documenti diversi.

La portabilità delle regole dai requisiti al prompt non è un contorno di SOL: è quello che rende
eseguibile la scelta.

**In termini di rischio.** Il minimo risultato che potete ottenere è quello fornito dal formato peggiore; se 
non fate il test e vi affidate alla sorte, senza misurare:

| | migliore | minimo |
|---|---:|---:|
| `sonnet-5` | 1,000 | **0,971** |
| `opus-5` | 1,000 | 0,882 |
| `haiku-4.5` | 0,971 | 0,882 |
| `qwen3.5-9b-think` | 0,882 | 0,647 |
| `ministral-8b` | 0,765 | 0,529 |
| `gemma-4-12b` | 0,882 | 0,353 |
| `granite-4.1-8b` | 0,588 | 0,250 |
| `qwen3.5-9b-nothink` | 0,382 | 0,235 |
| `phi4-mini` | 0,265 | **0,000** |

La scelta del formato è un'assicurazione, e serve dove il minimo è basso. Con un commerciale
sbagliare formato vi lascia comunque sopra il migliore dei locali. Con Phi-4 mini finite a zero.

Il rovescio: **Qwen con ragionamento, col formato giusto, arriva a 0,882** — esattamente il livello
che due dei tre commerciali toccano nel loro caso peggiore. E Gemma ci arriva con tempi di
elaborazione inferiori e meno token. Un modello che gira in casa ci arriva: dovete solo azzeccare il
formato giusto. I commerciali non ne hanno bisogno.

---

## La ricetta

Per un processo decisionale di complessità simile e su hardware da 8 GB:

1. verificate che il modello **consegni**, prima di misurare quanto è bravo; avere un modello tarato nel vostro ambiente 
concreto di esecuzione è la premessa indispensabile che viene prima della scrittura del prompt;
2. scrivete il processo in una forma governabile e fatelo confermare dall'utente sull'algoritmo, 
in qualunque modo rappresentato, non sul prompt;
3. trattate un item alla volta, eventualmente passando dati sullo stato nei dati d'ingresso (nel nostro caso: richiesta 
dell'utente + WIP per ciascun team);
4. niente documentazione del formato allegata, niente protocollo di esecuzione richiesto; a meno di non aver 
sperimentato che nel vostro caso migliora i risultati;
5. verificate il risultato campo per campo contro le attese: è un test da rendere automatico, ma è importante;
6. misurate il formato di somministrazione dell'algoritmo (SOL, prosa) sul vostro processo e sul vostro modello, 
e rimisurate quando ne cambiate uno; questo implica che ogni applicazione che intende usare documenti locali dovrebbe
avere sempre in piedi il suo meccanismo di testing ripetibile e rilanciabile in qualunque momento.

Un banco interno di cento casi etichettati vale più di qualunque classifica pubblica, e più di questo
articolo.

---

## Limiti

Un dominio, una scheda video, sei configurazioni locali, tre modelli commerciali **della stessa
famiglia**. Un tasso del 55–75% non è un impiegato infallibile: è un primo passaggio economico e
instancabile, da mettere davanti a una coda con una soglia di confidenza e una corsia di revisione
umana.

Altre domande restano aperte, senza dubbio, per esempio quanto pesi l'accumulo di stato di per sé
o come si comportino i modelli di altri fornitori, o se i risultati reggano, nella sostanza, con un 
diverso campione di item (quest'ultimo lo sto preparando).

---

*Il terzo articolo raccoglie i modi in cui una campagna come questa inganna chi la conduce.*

Il testo delle segnalazioni non è ridistribuibile: il repository ne contiene riferimenti, etichette,
impronte e uno script che lo ricostruisce dalla fonte.

Repository: https://github.com/jtplugin/sol

---

[^1]: Gli autori del dataset chiedono che chi lo usa citi quattro lavori.
R. Kallis, G. Colavito, A. Al-Kaswan, L. Pascarella, O. Chaparro, P. Rani, *The NLBSE'24 Tool
Competition*, NLBSE'24, 2024.
R. Kallis, A. Di Sorbo, G. Canfora, S. Panichella, *Predicting issue types on GitHub*, Science of
Computer Programming, 205, 102598, 2021 — doi:10.1016/j.scico.2020.102598.
R. Kallis, A. Di Sorbo, G. Canfora, S. Panichella, *Ticket Tagger: Machine Learning Driven Issue
Classification*, ICSME 2019, pp. 406–409 — doi:10.1109/ICSME.2019.00070.
G. Colavito, F. Lanubile, N. Novielli, *Few-Shot Learning for Issue Report Classification*, NLBSE
2023, pp. 16–19 — doi:10.1109/NLBSE59153.2023.00011.

---
*Gianni Tommasi*
