# Chiudere la serie: SOL è open source, ed ecco cosa significa esattamente

Sei articoli dopo, il quadro è completo: un problema (un livello intermedio di automazione senza uno standard), un formato (JSON, l'agente come runtime), un vocabolario (`TODO`/`RUN`, controllo del flusso, delega) e una forma di file (JSON dentro Markdown). Quello che resta da dire non riguarda il linguaggio — riguarda il progetto che lo circonda.

SOL è open source, licenza MIT, ospitato su [github.com/jtplugin/sol](https://github.com/jtplugin/sol). Dirlo e fermarsi lì sarebbe il modo facile, un po' vuoto, di chiudere una serie. Ecco invece la versione onesta: cosa c'è davvero nel repository, cosa è deliberatamente incompiuto, e a cosa assomiglia un contributo.

---

## Cosa c'è oggi

- **La specifica stessa** — attualmente alla linea `0.6`, l'unica fonte di verità. Tutto il resto nel repository deriva da essa, non il contrario.
- **La motivazione di design** — `DESIGN.md` e `why-sol-works.md` giustificano ogni scelta, incluse quelle che sembrano omissioni (niente variabili, niente strategia di esecuzione, nessuna garanzia di determinismo). Se ti stai chiedendo "perché non X", c'è una buona probabilità che la risposta sia già lì.
- **Una mappa comparativa** — rispetto a LangGraph, CrewAI, AutoGen e altri, che posiziona SOL come livello intermedio piuttosto che come concorrente dei framework di orchestrazione completi.
- **Strumenti per la scrittura** — una skill di Claude Code (`sol-translate`) che trasforma prosa, pseudocodice, YAML o XML in SOL valido, e strumenti che vanno nella direzione opposta: `sol2mermaid.py` e `sol2drawio.py` proiettano un processo SOL su un diagramma leggibile anche da chi non legge JSON.
- **Esempi concreti** — processi SOL reali in `examples/`, non solo frammenti da specifica.

---

## Cosa è deliberatamente incompiuto

Questa parte conta più della lista qui sopra. Un progetto che si dichiara finito di solito si sta sopravvalutando.

**Il testing è un metodo, non ancora una suite.** `doc/testing-sol.md` descrive *come* valutare SOL con fedeltà — separando la fedeltà di esecuzione dalla qualità del risultato, su una matrice linguaggio × harness × modello — ma i runner e la pipeline dei risultati sono ancora in costruzione. L'uso concreto in Claude Code è, da quanto risulta finora, più che soddisfacente; ma è un'affermazione diversa da "misurato rigorosamente ovunque."

**Le strategie di prevedibilità sono mappate, non ancora scritte.** L'articolo precedente di questa serie si è chiuso su un filo aperto: SOL può far pressione sull'isolamento del contesto dall'interno del linguaggio, ma nulla forza una scelta di modello senza un livello esterno. I compromessi di ciascun livello — direttiva in prompt, funzionalità dell'harness, piccolo runtime deterministico, orchestratore esterno — sono mappati ma non sono ancora il tema dell'articolo dedicato che meriterebbero.

**Il tracker delle issue è corto, di proposito.** Al momento della scrittura c'è esattamente una richiesta di enhancement aperta, che chiede strumenti per convertire tra SOL e diagrammi draw.io in entrambe le direzioni. Un tracker corto non è segno di un progetto finito — è segno di un progetto giovane, la cui superficie non è ancora stata messa sotto stress da un uso esterno. È un invito, non un difetto da nascondere.

---

## A cosa assomiglia davvero un contributo

`CONTRIBUTING.md` è corto per un motivo — il progetto preferisce che tu lo legga piuttosto che lo scorra distrattamente. La forma è questa:

- **La specifica è la fonte di verità.** Se un cambiamento non è nella specifica, non è SOL. Schema, README, esempi — derivano tutti da essa, mai il contrario.
- **Apri un'issue prima di una PR che cambia la specifica.** Le proposte per nuove istruzioni richiedono motivazione, un esempio e un'analisi dei casi limite — lo stesso livello che questa serie ha cercato di mantenere.
- **Gli articoli non richiedono nessuna issue.** La cartella `articles/` accetta PR direttamente: nuovi pezzi, traduzioni, casi di studio. Questa stessa serie vive sotto quella regola.
- **Il versioning è semantico ed esplicito** — patch per le chiarificazioni, minor per le aggiunte compatibili all'indietro, major per i cambiamenti che rompono la semantica esistente.

---

## Perché finire qui

Una specifica che sta in un solo documento, un runtime che è semplicemente "l'agente", e un progetto che dice chiaramente dove smette di essere finito — questa combinazione è il vero argomento di vendita, più di qualsiasi singola funzionalità trattata negli ultimi sei articoli. Se a un livello intermedio di automazione manca davvero uno standard, il modo per scoprire se SOL riempie quel vuoto non è fidarsi della parola di questa serie. È scrivere un processo, consegnarlo a un agente, e vedere cosa succede.

Repository: https://github.com/jtplugin/sol — issue e PR benvenute.

---
*Autore: Gianni Tommasi*
