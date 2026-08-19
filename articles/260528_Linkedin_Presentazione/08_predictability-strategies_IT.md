# La prevedibilità non è una funzionalità del linguaggio — è un livello che scegli

Due volte in questa serie, un'ammissione onesta è stata rinviata: SOL non può forzare nulla. Nessun parser obbliga a prendere un ramo, nessuno scheduler garantisce che uno `SPAWN` diventi davvero una sessione isolata, nessun type checker impone un contratto. La specifica lo dice chiaramente — i contratti sono *"onorati dalla comprensione dell'agente, non da un type checker a runtime"*, e `model` è *"un suggerimento, non un imperativo."*

Non è una lacuna di cui scusarsi. È ciò che permette a un `TODO` di dire *"identifica la causa radice più probabile"* — qualcosa che nessun motore deterministico potrebbe valutare in partenza. Il prezzo, però, è reale: nulla nel linguaggio può obbligare un agente a comportarsi come vuoi tu. Quindi la domanda giusta non è mai stata *"come rendo SOL prescrittivo?"*. È: *se ho bisogno che un certo comportamento sia prevedibile, a quale livello inietto quella prevedibilità, e quanto mi costa?*

---

## Cosa significa davvero "prevedibile" qui

Non output identici byte per byte — le foglie in linguaggio naturale lo rendono impossibile per progetto. Quello che vogliamo è che **la struttura dichiarata sia davvero realizzata**: uno `SPAWN` che gira in un contesto davvero isolato e non in un role-play in-context; un confine `model: "smart"` che finisce davvero su un modello più forte; un contratto davvero verificato al confine; un ramo o un `ONERROR` che scattano davvero come scritto. Sono proprietà di *fedeltà di esecuzione*. SOL le esprime; qualcosa fuori da SOL deve renderle affidabili.

---

## L'asimmetria che forma ogni scelta

Non tutti gli intenti sono ugualmente forzabili, e il motivo conta più di qualsiasi tecnica singola elencata sotto.

**L'isolamento del contesto è implicato dal contratto stesso.** SOL dice che un `AGENT` *"riceve solo ciò che `SPAWN` passa via `with`, e restituisce solo ciò che descrive `returns`."* È un'affermazione sul flusso di informazione. Qualunque livello faccia rispettare fedelmente "il chiamato vede solo `with`" è *costretto* a creare un contesto pulito — non c'è altro modo di soddisfare quel vincolo. L'isolamento, in altre parole, può essere fatto emergere semplicemente prendendo sul serio il contratto.

**La scelta del modello non è implicata da nulla.** Nessuna proprietà di flusso d'informazione richiede un modello specifico — è esattamente per questo che `model` è *solo* un suggerimento. Forzare un modello particolare richiede sempre un livello esterno al giudizio dell'agente.

Conseguenza pratica: puoi far pressione sull'isolamento dall'interno della disciplina stessa di SOL; non puoi far pressione sulla scelta del modello senza un risolutore esterno. Questa singola asimmetria decide la maggior parte di ciò che segue.

---

## Quattro livelli, un solo principio

Ogni strategia inietta prevedibilità in un punto diverso. Più si va in profondità, più l'autorità si sposta fuori dall'agente e dentro un esecutore deterministico — comprando determinismo al prezzo di portabilità e lavoro di ingegneria.

| Livello | Dove | Forza | Portabilità | Sforzo |
|---|---|---|---|---|
| **L1 — Linguistico** | Dentro il prompt | Bassa | Qualunque modello | Banale |
| **L2 — Harness** | Funzionalità della piattaforma | Media–Alta | Specifica dell'harness | Bassa–Media |
| **L3 — Runtime esterno** | Un helper deterministico affianco a SOL | Alta | Tra modelli diversi | Media–Alta |
| **L4 — Orchestratore esterno** | SOL diventa solo specifica del nodo | Massima | Specifica dello strumento | Alta |
| **L0 — Osservabilità** | *(ortogonale)* misura, non forzare | — | Alta | Bassa–Media |

La regola che attraversa tutto: **scegli il livello più superficiale che ti dà il determinismo di cui hai davvero bisogno.** Sovra-ingegnerizzare la prevedibilità spreca esattamente quanto ignorarla.

**L1, la leva più economica**, è una direttiva posta sopra il blocco SOL — *"tratta ogni `SPAWN` come un confine reale; avvia un sub-agente pulito; rispetta `accepts` alla lettera."* Non costa nulla e funziona su qualunque modello, ma resta una richiesta a un lettore non deterministico.

**L2 si appoggia all'harness su cui già stai girando.** La leva singola più forte qui è registrare ogni `AGENT` SOL come sub-agente nativo — in Claude Code, un file sotto `.claude/agents/` con un frontmatter `model:`. Quando la sessione raggiunge lo `SPAWN` corrispondente, il meccanismo nativo dell'harness lo apre sul modello dichiarato, con un isolamento genuino come effetto collaterale. Hooks e spawning come tool MCP stanno nelle vicinanze, ciascuno scambiando un po' di discrezione dell'agente per un po' più di determinismo.

**L3 è dove la prevedibilità smette di dipendere dalla buona volontà.** Un piccolo helper esterno risolve un tier in un modello concreto, lancia una sessione isolata, verifica il ritorno contro il contratto — e il passo SOL che dispaccia diventa un semplice `RUN` di quell'helper invece di uno `SPAWN` in-context. È l'unica famiglia di strategie che può forzare la scelta del modello, proprio perché la scelta del modello non è implicata dal contratto. È anche un parziale allontanamento da "l'agente è il runtime": il confine ora viene eseguito, non interpretato.

**L4 va più lontano:** incorporare SOL dentro un orchestratore esterno (LangGraph e simili), dove il framework possiede il controllo del flusso in modo deterministico e SOL si riduce a descrivere cosa fa ogni nodo. Massimo determinismo, ma inverte la premessa stessa di SOL — il controllo torna a un motore esterno.

**L0 è ortogonale a tutti gli altri.** Non forzare, misura: cattura la traccia di esecuzione, verifica a posteriori se uno `SPAWN` è stato davvero isolato, sul tier previsto, con il contratto rispettato. È l'unico approccio che ti dice se uno qualunque di L1–L4 sta davvero funzionando — la prevedibilità che non puoi osservare è prevedibilità di cui non puoi fidarti.

---

## Un percorso decisionale di massima

Parti sempre da L1 — le direttive di esecuzione sono gratuite e alzano il pavimento. Se ti serve isolamento ma non un modello specifico, appoggiati a contratti forti più i sub-agenti nativi di L2; l'isolamento è implicato dal contratto, quindi spesso basta questo. Se ti serve un modello *specifico* a un confine, nessuna quantità di prompting L1 te lo garantisce — vai al sub-agente nativo di L2 oppure a L3. Se ti serve un'orchestrazione riproducibile e verificabile, considera la compilazione di L3 oppure L4, accettando che il controllo del flusso guidato dall'agente di SOL faccia un passo indietro. E qualunque cosa scegli, aggiungi L0 — strumentalo perché le regressioni siano visibili invece che silenziose.

---

## Il centro onesto della serie

Questo chiude un filo che la serie aveva aperto nell'articolo sulla delega: SOL resta deliberatamente non-prescrittivo, perché è ciò che gli permette di parlare in termini di intento piuttosto che di transizioni fisse. La prevedibilità non si ottiene snaturando questo — si ottiene iniettandola, deliberatamente, a un livello che hai scelto e che sai nominare. Il linguaggio non smette mai di essere il livello del *cosa* significa un processo; tutto quello che c'è in questo articolo vive *attorno* ad esso, non al suo interno.

Repository: https://github.com/jtplugin/sol

---
*Autore: Gianni Tommasi*
