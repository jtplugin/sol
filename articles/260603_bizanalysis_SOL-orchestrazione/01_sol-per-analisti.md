# L'agente è il runtime: SOL e l'orchestrazione AI dal punto di vista dell'analista di business

C'è un divario che ogni analista conosce bene. Da una parte c'è il *descrivere* un processo: una procedura scritta, una slide, un diagramma BPMN, una user story. Dall'altra c'è il *farlo eseguire*: a quel punto serve qualcuno che traduca la descrizione in codice, in un workflow, in un'integrazione. Tra l'intento e l'esecuzione si apre un fossato, e su quel fossato l'analista di solito costruisce un ponte fatto di specifiche, hand-off verso l'IT e cicli di validazione.

Gli agenti AI promettono di colmare quel fossato. La promessa è seducente: descrivi il compito in linguaggio naturale e un modello lo esegue. Ma chi ci ha provato sa dove si rompe. Un prompt lungo regge finché il processo è lineare; appena compaiono diramazioni ("se il progetto è in ritardo, allora…"), cicli ("per ogni cliente…") o gestione delle eccezioni, la prosa diventa ambigua e l'agente comincia a improvvisare. Il punto debole non è la capacità del modello: è la *forma* con cui gli diamo le istruzioni.

Anche per questo nel tempo si è passati dal _prompt_ al _context_ ed ora al _harness engineering_. Livelli sempre più profondi di costruzione dell'interazione con il modello AI (fondamentalmente non deterministico, almeno al livello dell'analista) per ottenere quella ripetibilità e fedeltà alle richieste che i modelli algoritmici soddisfano senza problemi.

**SOL** (*Simple Orchestration Language*) nasce esattamente in uno spazio intermedio. Prende atto che i modelli AI gestiscono meglio alcune istruzioni, alcuni formati rispetto agli altri e che gli attuali strumenti con cui concretamente si interagisce con il modello offrono livelli di controllo che permettono a specifiche chiare di dare risultati prevedibili.

## Che cos'è SOL, in una frase

SOL è un **formato per definire processi**, non un linguaggio di programmazione. Si scrive un processo come un documento strutturato secondo degli standard su cui l'AI è di suo meglio attrezzata; un agente AI lo legge, ne comprende l'intento e lo esegue.

Il principio cardine si riassume così: **l'agente è il runtime**. Negli approcci tradizionali serve un interprete, un SDK o un motore di orchestrazione che esegue il flusso. In SOL non c'è nulla da installare: il documento *è* la specifica, e l'intelligenza che lo esegue è lo stesso agente che lo legge. Niente oggetti da disegnare su piattaforme dedicate, nessuna dipendenza tecnica nascosta dietro le quinte. Solo approfittare della potenza degli strumenti che abbiamo a disposizione.

Per un analista questo ha una conseguenza diretta: la distanza tra "la specifica di processo che scrivo" e "ciò che viene eseguito" si accorcia drasticamente. Il documento che descrive il processo è il documento che lo esegue.

## Due ipotesi tecniche alla base di SOL
SOl si basa su due ipotesi da verificare e un beneficio certo.
Le ipotesi sono due:
1. Istruzioni strutturate con un JSON siano interpretate meglio di semplici istruzioni discorsive (in "prosa")
2. Alcune parole chiave sono sufficientemente chiare e universali che l'AI sa come interpretarle senza ulteriori spiegazioni
Sto conducendo dei test in vari scenari per verificare queste ipotesi, ma i primi risultati sembrano darmi ragione.

Il beneficio sicuro è:
- Posso generare il mio processo in SOL partendo da un flowchart o, tramite AI, da una sua descrizione in linguaggio naturale e posso trasformare e rendere immediatamente e deterministicamente intelligibile in un flowchart o in una descrizione di un processo SOL.

A questo proposito abbiamo già una serie di strumenti, anche questi rilasciati come open source, per trasformare un processo in prosa in uno script SOL e per convertire SOL in mermaid o Draw.io. Non devo dire io l'efficacia di rappresentazioni in questa forma, specialmente per individuare carenze di processo o casi non gestiti...

## Il cambio di paradigma: un'inversione di controllo

Qui conviene fermarsi, perché è facile fraintendere la novità di SOL riducendola a "istruzioni in pseudocodice". Non è quello il punto.

Pensiamo a come funziona l'automazione classica, anche quella che integra l'AI. Al comando c'è un'orchestrazione **deterministica** — un motore a regole, un workflow, uno script — che guida il flusso passo dopo passo e, *nei punti in cui serve giudizio*, chiama un modello AI per svolgere un compito specifico (classificare un testo, riassumere, estrarre un'informazione). L'intelligenza è un componente accessorio: un plugin invocato da una pipeline meccanica che resta saldamente al comando.

SOL ribalta la direzione della chiamata. Al comando c'è **l'agente**, che orchestra il processo nel suo insieme; e *scende* nel deterministico — comandi esatti, script, operazioni algoritmiche — quando e dove l'esattezza conta. Il deterministico non è più il motore che chiama l'AI: è ciò che l'AI chiama.

Per questo abbiamo due istruzioni differenti in SOL:

- un'istruzione **interpretativa** (TODO) dichiara un esito desiderato e lascia all'agente decidere il *come* (quali file leggere, quali strumenti usare, come recuperare da un imprevisto). È dove vive il giudizio. Gli agenti conoscoo la parola TODO, tutti i loro plan sono delle todo-list.
- un **comando letterale** (RUN) è eseguito esattamente come scritto: nessuna reinterpretazione. È l'operazione algoritmica precisa che l'agente invoca quando il risultato deve essere riproducibile — chiamare proprio quello script, eseguire proprio quel calcolo.

Ora questo è l'esempio chiave per capire il concetto di gestione della prevedibilità a cui mi riferivo. Se dico

**TODO: crea la versione inglese del del file pippo.txt**
**RUN: python send_to_server.py {{versione inglese di pippo.txt}}**

l'agente riesce ad interpretare il diverso significato delle due istruzioni grazie anche al resto del contenuto e così saprà che *^TODO** significa *fai questa cosa con la tua intelligenza* mentre **RUN** significa *esegui proprio questo comando*

La coerenza delle convenzioni, la loro somiglianza con gli esempi di addestramento, da all'agente la possibilità concreta di interpretare in modo corretto il comportamento, anche di capire a cosa si riferisce il testo tra doppie parentesi graffe.

## SOL come "BPMN che si esegue"

Gli analisti vivono nei diagrammi. La buona notizia è che ogni costrutto di SOL corrisponde a una primitiva di flowchart che conosciamo già: passi sequenziali, decisioni (rombi), cicli, gestione delle eccezioni, fine del processo. Questo non è un caso: SOL è stato pensato perché un processo possa essere letto sia da un agente sia da una persona, e tradotto automaticamente in un diagramma (come ho detto, ho realizzato dei semplici convertitori verso mermaid e draw.io).

Vediamo un processo reale — la **chiusura settimanale dei progetti**: ogni venerdì leggere lo stato di tutti i progetti, calcolare la *velocity*, scrivere un report per progetto, aggiornare la to-do list e inviare il riepilogo via email al team.

```mermaid
flowchart TD
    START(["▶ Chiusura settimanale"]):::terminal
    A["Leggi tutti gli status.md dei progetti · fast"]:::todo
    B["Calcola la velocity<br/>(script: compute_velocity.py)"]:::run
    ERR1["⚠ Errore → segnala e arresta"]:::onerror
    B -. errore .-> ERR1
    C["Leggi reports/velocity.json · fast"]:::todo
    LOOP{"per ogni progetto"}:::ctrl
    D["Scrivi la sezione del progetto:<br/>stato verde/giallo/rosso,<br/>3 punti chiave, priorità · smart"]:::todo
    COND{"velocity &lt; 0.3 oppure task critici<br/>bloccati da oltre 5 giorni?"}:::ctrl
    E["Aggiungi una nota di alert<br/>alla sezione del progetto"]:::todo
    M1(" "):::join
    F["Aggiorna todo.md:<br/>chiusi → Completati,<br/>priorità → Questa settimana · fast"]:::todo
    G["Prepara il corpo dell'email<br/>dal report · fast"]:::todo
    COND2{"almeno un progetto<br/>in stato rosso?"}:::ctrl
    H["Anteponi una riga di alert<br/>in grassetto coi progetti rossi"]:::todo
    M2(" "):::join
    I["Invia l'email al team"]:::todo
    ERR2["⚠ Errore → salva la bozza<br/>e segnala"]:::onerror
    I -. errore .-> ERR2
    END(["⏹ fine"]):::terminal

    START --> A --> B --> C --> LOOP
    LOOP -->|per ogni progetto| D --> COND
    COND -->|sì| E --> M1
    COND -->|no| M1
    M1 --> LOOP
    LOOP -->|fine ciclo| F --> G --> COND2
    COND2 -->|sì| H --> M2
    COND2 -->|no| M2
    M2 --> I --> END

    classDef todo fill:#dbeafe,stroke:#3b82f6,color:#1e3a8a
    classDef run fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef ctrl fill:#fef9c3,stroke:#ca8a04,color:#713f12
    classDef onerror fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    classDef terminal fill:#1e293b,stroke:#475569,color:#f8fafc
    classDef join fill:#e2e8f0,stroke:#64748b,color:#1e293b
```

> **Legenda** — Blu: passi *interpretativi* (l'agente decide il come). Verde: comando *letterale* (lo script di calcolo della velocity, eseguito esattamente). Giallo: decisioni e cicli (la logica di processo). Rosso: gestione delle eccezioni.

Si legge come un qualsiasi diagramma di processo, e qui sta il valore per chi fa analisi. Notiamo tre cose:

- **Le condizioni sono regole di business in linguaggio naturale.** "Almeno un progetto in stato rosso", "velocity sotto 0,3 o task critici bloccati da oltre 5 giorni": sono giudizi che un motore tradizionale non saprebbe valutare senza una definizione formale e calcolabile. L'agente le risolve rispetto al contenuto reale dei file. La regola resta scritta come l'analista la scriverebbe, non tradotta in un predicato.
- **C'è un solo punto deterministico, ed è esplicito.** Il calcolo della velocity è un comando letterale (verde): un numero non si "interpreta". Tutto il resto è giudizio. La separazione è visibile a colpo d'occhio.
- **La gestione delle eccezioni è parte del processo, non un dettaglio implementativo.** Se il calcolo fallisce, il processo si ferma e lo segnala; se l'email non parte, salva la bozza. Sono esattamente i percorsi alternativi che un analista mappa in un BPMN.

Il punto strategico: **una sola fonte di verità**. Lo stesso documento è il diagramma che mostri allo stakeholder e la specifica che l'IT (o l'agente) esegue. Niente più diagramma che diverge dal codice perché qualcuno ha aggiornato l'uno e dimenticato l'altro.

## Dove si colloca SOL nel panorama dell'orchestrazione

SOL non vive nel vuoto. Il panorama dell'orchestrazione AI oggi ha tre famiglie principali:

- **Framework code-first** (LangGraph, CrewAI, AutoGen): modellano l'interazione tra agenti scrivendo codice. Massima flessibilità e controllo, ma richiedono sviluppo e infrastruttura DevOps significativi.
- **Piattaforme dati integrate** (Snowflake, Databricks): l'orchestrazione avviene dove risiedono i dati, con forte governance. Il rovescio è il rischio di lock-in.
- **Architetture ibride enterprise** (il pattern "backbone deterministica + nodi agentici"): un motore a regole garantisce auditabilità e ripetibilità dei passaggi critici, mentre l'AI interviene solo dove serve capacità interpretativa.

Rispetto a questi, SOL si posiziona come **livello intermedio di automazione**. Non compete con un motore enterprise quando l'esigenza è riproducibilità e audit rigorosi; non richiede il costo di sviluppo di un framework code-first quando l'esigenza è descrivere un processo e farlo eseguire da un agente capace.

| | Framework code-first | **SOL** |
|---|---|---|
| Chi guida l'esecuzione | un motore deterministico | l'agente |
| Forma della definizione | codice (Python) | documento leggibile, convertibile in diagramma |
| Chi può scriverlo | sviluppatori | chi sa descrivere un processo |
| Costo di adozione | alto (SDK, infrastruttura) | minimo (nessun runtime) |
| Riproducibilità | alta | dove serve, via comandi letterali |
| Punto di forza | controllo fine, scala | dall'intento all'esecuzione senza traduzione |

In sintesi: **si usa SOL** quando il processo è abbastanza complesso da beneficiare del giudizio di un agente, ma abbastanza strutturato da richiedere indicazioni chiare su *cosa* fare e *quando*. **Si usa un framework** quando servono riproducibilità byte-per-byte, latenza garantita o un'orchestrazione di cui rispondere in sede di audit.

## Casi d'uso e applicabilità

Gli scenari più naturali per un analista sono i processi ricorrenti, basati su conoscenza, dove ogni esecuzione richiede un po' di giudizio ma la struttura è stabile:

- **Reportistica e briefing ricorrenti.** Un briefing quotidiano che legge lo stato dei progetti, fa emergere ritardi e scadenze imminenti e produce un riassunto. La struttura (cosa leggere, quali condizioni evidenziare) è fissa; il contenuto cambia ogni giorno.
- **Cicli di chiusura periodica.** La chiusura settimanale vista sopra: aggregazione di stato, calcolo di metriche, redazione di un report per entità, aggiornamento di una lista di attività, comunicazione al team. Mescola passi interpretativi e un passo deterministico (il calcolo).
- **Processi di revisione e controllo.** Un "runner" che, dato un insieme di modifiche, applica una checklist di revisione, delega l'analisi a un agente specializzato e raccoglie i risultati con severità e suggerimenti. È il pattern in cui l'orchestrazione coordina più ruoli.

Lo schema ricorrente è sempre lo stesso: **intento di business → struttura del flusso → l'agente esegue**. L'analista lavora al primo e al secondo livello — il terzo è demandato all'agente.

## Inserirsi in altri contesti di orchestrazione — e i limiti onesti

SOL non pretende di sostituire gli altri strumenti: è pensato per *innestarsi*. Può essere usato per definire le *skill* di un agente dentro un ambiente come Claude Code o Cursor; può convivere con framework esterni, che possiedono il controllo di flusso mentre SOL descrive *cosa fa ciascun nodo*; e si presta a scenari di interoperabilità tra agenti.

Ma qui serve onestà intellettuale — il tipo di onestà che un analista pretende prima di portare una tecnologia agli stakeholder. **SOL esprime un *intento*; il linguaggio da solo non può garantirne la realizzazione.** Alcune cose dipendono dal contesto d'esecuzione, e vanno presidiate lì, non promesse dal documento:

- **L'isolamento tra agenti e la scelta del modello.** SOL può dichiarare che un sotto-compito giri in un contesto separato o su un modello più "smart", ma è l'ambiente di esecuzione (l'harness, o un runtime esterno) a doverlo rendere reale. Il documento lo *chiede*; non lo *impone*.
- **La pausa per l'intervento umano.** SOL ha un'istruzione per marcare un punto di controllo dove serve una decisione umana. È utile per esprimere l'intento, ma è una scorciatoia dipendente dal contesto: funziona solo se l'esecuzione è garantita interattiva; altrimenti degrada a un arresto pulito. Per un gate umano che regga in *ogni* contesto — il caso tipico della governance — il pattern robusto è la **decomposizione del processo**: due processi distinti, con la decisione umana in mezzo. È una distinzione che conta quando il checkpoint è un controllo formale e non un semplice "chiedi conferma".

Riconoscere questi limiti non indebolisce SOL: lo colloca correttamente. Il linguaggio è il livello dell'*intento*; la predicibilità è una decisione di deployment che si prende *attorno* ad esso, scegliendo il livello più leggero che dà la garanzia di cui si ha davvero bisogno.

## Cosa SOL deliberatamente non fa

Per chiudere il cerchio, vale la pena dire cosa SOL evita di proposito. Non prescrive la strategia di esecuzione (cosa parallelizzare, in che ordine): lo deduce l'agente. E non garantisce determinismo: due esecuzioni dello stesso processo possono differire, perché l'agente esercita giudizio. Dove serve riproducibilità esatta, la risposta è un comando letterale verso uno script — non un'istruzione interpretativa.

Sono scelte, non lacune. SOL copre uno *sweet spot* preciso: processi abbastanza complessi da beneficiare della comprensione di un agente, abbastanza strutturati da richiedere una guida su cosa fare e quando.

## In conclusione

Per l'analista di business, SOL propone un cambio di prospettiva concreto: l'intento di processo, espresso in forma strutturata-ma-leggibile, diventa direttamente eseguibile, senza il passaggio obbligato dalla traduzione in codice. Il diagramma che mostri allo stakeholder e la specifica che viene eseguita sono lo stesso artefatto. E il paradigma sottostante — un'AI che orchestra e scende nel deterministico quando serve, anziché una pipeline deterministica che ogni tanto invoca l'AI — riallinea l'automazione al modo in cui un professionista competente lavora davvero.

SOL è un progetto open source (licenza MIT). Per chi volesse provarlo senza scrivere JSON a mano, esiste anche una *skill* che traduce una descrizione in linguaggio naturale (o YAML/XML) in un processo SOL valido. Il punto di partenza è il repository:

Repository: https://github.com/jtplugin/sol

---
*Autore: Gianni Tommasi*
