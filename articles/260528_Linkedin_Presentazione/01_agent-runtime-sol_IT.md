# Agent Runtime: SOL — Una Nuova Frontiera nell'Orchestrazione AI

L'orchestrazione degli agenti AI sta vivendo una transizione fondamentale: dall'impiego di modelli isolati alla creazione di ecosistemi complessi in cui molteplici entità specializzate collaborano per risolvere compiti articolati. Di seguito, una panoramica dei principali approcci all'orchestrazione oggi presenti nel panorama, e del ruolo distintivo di **SOL** (*Simple Orchestration Language*) al suo interno.

## Gli approcci attuali all'orchestrazione

Oggi il mercato e la ricerca offrono tre categorie principali di soluzioni.

### Framework open-source code-first (LangGraph, CrewAI, AutoGen)

Questi strumenti modellano le interazioni tra agenti direttamente attraverso il codice.

- **LangGraph** utilizza grafi a stati finiti e checkpointing per garantire persistenza e controllo granulare dell'esecuzione.
- **CrewAI** si concentra sulla delega basata sui ruoli (backstory, obiettivi, responsabilità), offrendo una curva di apprendimento più bassa.
- **AutoGen** (ora AG2) punta sulla conversazione tra agenti come meccanismo di coordinamento peer-to-peer.

Questi framework offrono massima flessibilità, ma richiedono infrastrutture DevOps significative e competenze avanzate di ingegneria AI.

### Piattaforme dati verticalmente integrate (Snowflake, Databricks)

In questo modello, l'orchestrazione avviene dove risiedono già i dati.

L'approccio privilegia la governance uniforme e la sicurezza, permettendo agli agenti di interrogare dataset governati senza spostamenti massivi di dati. Il limite principale è il rischio di vendor lock-in e la difficoltà di orchestrare workflow distribuiti su ambienti multi-cloud.

### Architetture ibride enterprise (il pattern "Trident")

Molte aziende adottano approcci ibridi che combinano una backbone deterministica (motori a regole, sistemi di workflow) con nodi agentici delimitati.

Questo garantisce che i passaggi critici rimangano verificabili e ripetibili, mentre l'AI viene introdotta solo dove è necessaria capacità interpretativa o adattiva.

## SOL: l'agente come runtime

SOL (*Simple Orchestration Language*) si inserisce in questo scenario con un paradigma diverso: **l'agente stesso diventa il runtime**.

Mentre gli altri approcci richiedono interpreti dedicati, SDK o motori di orchestrazione per eseguire i workflow, SOL è un formato JSON minimale che l'agente può leggere, comprendere ed eseguire autonomamente.

## Cosa rende SOL diverso

### Nessuna dipendenza

SOL non richiede SDK o ambienti di esecuzione complessi.

Qualsiasi LLM sufficientemente capace può interpretare la specifica ed eseguirla, eliminando di fatto il gap tra "descrivere cosa fare" (linguaggio naturale) e "programmare come farlo" (Python o codice di workflow).

### TODO e RUN: un'inversione di controllo

A differenza dei sistemi di workflow tradizionali, SOL distingue tra:

- istruzioni **TODO**, espresse in linguaggio naturale, in cui l'agente decide quali passi e strumenti utilizzare
- comandi **RUN**, eseguiti letteralmente per preservare il controllo preciso sulle operazioni critiche

Il cambiamento profondo non è la distinzione linguaggio naturale/letterale, ma il *verso* del controllo. Nell'automazione classica un motore deterministico guida il flusso e chiama un passo AI dove serve giudizio; l'intelligenza è un plugin dentro una pipeline meccanica. SOL ribalta la direzione: è l'agente a orchestrare, e RUN è l'operazione deterministica a cui ricorre quando conta l'esattezza. Il deterministico non è più il motore che chiama l'AI — è ciò che l'AI chiama.

### Tier semantici del modello

Invece di vincolare i workflow a specifici ID di modello (es. gpt-4o), SOL utilizza livelli di esecuzione semantici come:

- fast
- balanced
- smart

È l'agente esecutore a decidere quale modello sottostante si adatta meglio alla complessità del compito a runtime.

### Modulare e multi-agent per design

Un'altra caratteristica distintiva di SOL è la sua apertura alla composizione modulare e alla progettazione esplicita di comportamenti multi-agent.

I workflow SOL possono essere strutturati come blocchi riutilizzabili, permettendo ai pattern di orchestrazione di evolvere in modo incrementale invece di essere strettamente accoppiati a un singolo grafo di esecuzione monolitico.

Questa modularità rende possibile:

- comporre skill di agente riutilizzabili
- delegare responsabilità ad agenti specializzati
- definire pattern di esecuzione gerarchici o collaborativi
- separare le fasi di pianificazione, esecuzione, validazione e revisione tra ruoli agentici diversi

Invece di trattare il comportamento multi-agent come un dettaglio implementativo nascosto nel codice del framework, SOL permette che questi pattern di interazione diventino parte della specifica di orchestrazione stessa.

Questo rende i workflow più portabili, ispezionabili e adattabili attraverso diversi runtime ed ecosistemi di agenti.

### Compilazione da linguaggio naturale a SOL

Per ridurre la barriera all'adozione, SOL supporta anche uno strato di traduzione che converte descrizioni in linguaggio naturale, YAML o XML in specifiche SOL eseguibili.

Una skill dedicata può trasformare descrizioni di workflow leggibili da un umano in documenti SOL strutturati, permettendo agli utenti di definire orchestrazioni senza modificare manualmente il JSON.

Questo approccio offre diversi vantaggi:

- gli utenti non tecnici possono descrivere i workflow in modo conversazionale
- le definizioni di processo esistenti in YAML o XML possono essere adattate con frizione minima
- la logica di orchestrazione rimane ispezionabile e strutturata dopo la conversione
- i team possono raffinare progressivamente i workflow da descrizioni informali a pattern di esecuzione deterministici

In pratica, questo significa che SOL può funzionare sia come:

- formato di orchestrazione di basso livello
- sia come destinazione di compilazione per descrizioni di alto livello orientate all'utente

Questo rafforza ulteriormente la filosofia di SOL: l'agente deve interpretare ed eseguire l'intento direttamente, invece di costringere gli sviluppatori a codificare completamente la logica di orchestrazione in astrazioni di programmazione tradizionali.

## Posizionamento strategico

Rispetto a framework di orchestrazione complessi come LangGraph, SOL si posiziona come un livello intermedio di automazione.

È particolarmente adatto per descrivere *skill* di agente riutilizzabili in ambienti come Claude Code o Cursor, dove le istruzioni in prosa pura diventano ambigue non appena si introducono cicli (REPEAT) o rami condizionali complessi (IF, WHEN).

Mentre l'orchestrazione classica si concentra sulla costruzione di macchine deterministiche guidate dall'AI, SOL sfrutta invece la capacità di ragionamento dell'agente per trasformare un documento strutturato in azione coerente.

Il risultato è una riduzione della complessità di sviluppo mantenendo il più possibile il controllo del flusso.

Repository: https://github.com/jtplugin/sol

---
*Autore: Gianni Tommasi — [Versione originale in inglese su LinkedIn](https://www.linkedin.com/pulse/agent-runtime-sol-new-frontier-ai-orchestration-gianni-tommasi-zut6f)*
