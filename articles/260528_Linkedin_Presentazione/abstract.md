# Abstract — Linkedin: Presentazione di SOL

## Tipo
Serie di articoli brevi

## Piattaforma
LinkedIn

## Target
Professionisti tecnici e non tecnici interessati ad automazione, AI agenti, produttività. Non richiede background da sviluppatore.

## Obiettivo
Introdurre SOL, spiegare il problema che risolve, invitare a usarlo e contribuire.

## Messaggi chiave
- Esiste un livello intermedio di automazione non ancora coperto da standard consolidati
- SOL è un formato JSON minimale: l'agente è il runtime, nessun SDK necessario
- Il formato è autoesplicativo: chi esegue non ha bisogno di conoscere la spec
- Chi scrive non ha bisogno di scrivere JSON: una skill in sviluppo permette di descrivere il processo in linguaggio naturale (o YAML/XML) e ottenere un file SOL valido
- Progetto open source MIT, contributi benvenuti

## Articoli previsti

Il primo articolo della serie è già pubblicato in inglese su LinkedIn.
Gli articoli successivi approfondiscono i temi introdotti — non li reintroducono.

| #   | File                          | Italiano                      | Tema                                                                                                                                                                                   | Note                                                                                                                          |
| --- | ----------------------------- | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| 01  | [[01_agent-runtime-sol]].md   | [[01_agent-runtime-sol_IT]]   | Panoramica del landscape e posizionamento di SOL                                                                                                                                       | **Pubblicato** — introduce problema, paradigma, TODO/RUN, tier, multi-agent, traduzione da NL                                 |
| 02  | [[02_example-end-to-end]].md  | [[02_example-end-to-end_IT]]  | Esempio concreto end-to-end: un SOL reale, passo passo                                                                                                                                 | **Pubblicato** — mostra cosa legge l'agente e cosa produce                                                                    |
| 03  | [[03_writing-sol]].md         | [[03_writing-sol_IT]]         | Come si scrive un SOL: dalla descrizione in linguaggio naturale al JSON valido tramite la skill di conversione                                                                         | **Pubblicato** — demo pratica della skill di traduzione                                                                       |
| 04  | [[04_inside-a-routine]].md    | [[04_inside-a-routine_IT]]    | L'anatomia di una routine: TODO/RUN, controllo del flusso (IF, WHEN, REPEAT) e i modi di fermarsi (ONERROR, HALT, RETURN, WAITUSERINPUT)                                               | Articolo lungo e completo che fonde i temi originari 4+5+6: tutto ciò che vive dentro una singola ROUTINE, prima della delega |
| 05  | [[05_delegation-patterns]].md | [[05_delegation-patterns_IT]] | La gerarchia di delega: CALL, SPAWN, DELEGATE — multi-agent reale, non solo tier di modello                                                                                            | I tier sono già citati nel 01; il focus si sposta sui delegation patterns e sui contratti                                     |
| 06  | [[06_json-in-markdown]].md    | [[06_json-in-markdown_IT]]    | SOL come JSON dentro un documento markdown: cosa abilita questo pattern (documentazione e codice insieme, tabelle di config citate dal foreach, diff leggibili, skill autoesplicative) | **Scritto** — nuovo tema, il formato JSON-in-md e le possibilità che apre                                                     |
| 07  | [[07_open-source]].md         | [[07_open-source_IT]]         | Open source, contributi, cosa manca ancora — con riferimento al repo e alle issue aperte                                                                                               | **Scritto** — chiusura della serie                                                                                            |
| 08  | [[08_predictability-strategies]].md | [[08_predictability-strategies_IT]] | I livelli a cui si inietta prevedibilità (L1 linguistico, L2 harness, L3 runtime esterno, L4 orchestratore esterno) più L0 osservabilità — e l'asimmetria isolamento/modello             | **Scritto** — chiude il filo aperto promesso negli articoli 05 e 07                                                           |

## Lingua

Ogni articolo esiste in due versioni: inglese e italiano.  
Convenzione dei file: `02_example-end-to-end.md` (EN) e `02_example-end-to-end_IT.md` (IT).  
L'articolo 01 è pubblicato solo in inglese; la versione italiana è da produrre.

## Post di presentazione e prompt immagine

Per ogni articolo: il testo del post di lancio (EN/IT) e il prompt per l'immagine di copertina. Raccolti qui per riuso e storico — non ancora prodotti per gli articoli 01–07.

### 08 — Predictability strategies

**Post EN**

> Twice in this series I deferred an honest admission: SOL cannot force anything. No parser compels a branch, no scheduler guarantees a `SPAWN` is a real isolated session, no type checker enforces a contract.
>
> That's not a gap — it's what lets a `TODO` say "find the most likely root cause." The price is that nothing in the language can make an agent behave the way you want.
>
> So the real question is never "how do I make SOL prescriptive?" It's: at what layer do I inject predictability, and what does it cost? Four layers, from a free prompt directive to a foreign orchestrator that takes control away from the agent entirely — plus one rule that cuts through all of them: you can pressure context isolation into existence just by enforcing the contract; you can never pressure model choice without something outside the agent's judgment.
>
> Eighth piece of the series on SOL.
>
> Repository: https://github.com/jtplugin/sol

**Post IT**

> Due volte in questa serie ho rinviato un'ammissione onesta: SOL non può forzare nulla. Nessun parser obbliga un ramo, nessuno scheduler garantisce che uno `SPAWN` sia davvero una sessione isolata, nessun type checker impone un contratto.
>
> Non è una lacuna — è ciò che permette a un `TODO` di dire "trova la causa radice più probabile." Il prezzo è che nulla nel linguaggio può obbligare un agente a comportarsi come vuoi tu.
>
> Quindi la domanda vera non è mai "come rendo SOL prescrittivo?". È: a quale livello inietto la prevedibilità, e quanto mi costa? Quattro livelli, da una direttiva gratuita nel prompt a un orchestratore esterno che toglie il controllo all'agente — più una regola che li attraversa tutti: puoi far emergere l'isolamento del contesto semplicemente facendo rispettare il contratto; non puoi mai forzare la scelta del modello senza qualcosa fuori dal giudizio dell'agente.
>
> Ottava puntata della serie su SOL.
>
> Repository: https://github.com/jtplugin/sol

**Prompt immagine**

> A cinematic, premium enterprise AI LinkedIn article cover, 16:9 aspect ratio. An asymmetric composition: at the center, a single luminous vertical column of light rises from darkness, banded into four distinct horizontal strata stacked like sedimentary layers — each stratum subtly different in texture and density, the lowest soft and diffuse, each layer above it progressively sharper, more rigid, more crystalline. At the very top stratum, the light resolves into a single perfectly still, hard-edged point — cold electric white, in total contrast with the soft glow at the base. Thin tendrils of light leak sideways from each stratum into the surrounding darkness, never quite reaching the edges of the frame, as if each layer is exerting a different amount of control over the same rising signal. No wires, no arrows, no machinery — only the gradient of light itself implying the passage from soft suggestion to hard certainty. Palette: deep black background, the base layers in warm amber and soft teal, the upper layers cooling into electric blue, the topmost point in cold electric white. No labels, no text overlays, no readable characters. No flowcharts, no robot faces, no circuit boards. Atmosphere: discipline emerging gradually out of openness, control chosen rather than imposed. Ultra-sharp detail at the topmost point with soft depth-of-field fade toward the base and edges. --ar 16:9 --style raw
