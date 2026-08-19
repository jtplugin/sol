# Dentro una routine SOL: passi, diramazioni, cicli e sapere quando fermarsi

I primi tre articoli della serie hanno introdotto SOL, percorso un processo reale riga per riga e mostrato come generarne uno a partire da una descrizione in linguaggio naturale. Lungo la strada due parole hanno continuato a comparire — `TODO` e `RUN` — e altre sono apparse di sfuggita negli esempi: `WHEN`, `IF`, `REPEAT`, `ONERROR`, `HALT`.

Questo articolo mette insieme l'intero vocabolario di una singola routine. Tutto ciò di cui parliamo vive *dentro una sola `ROUTINE`* e gira in *un solo contesto*: le foglie che fanno il lavoro, il controllo del flusso che le organizza e i costrutti che fanno terminare le cose in modo deliberato. Cosa succede quando serve più di un agente è il tema del prossimo articolo. Questo riguarda tutto ciò che puoi esprimere prima di arrivarci.

È più lungo degli altri di proposito: alla fine avrai letto ogni costrutto necessario per scrivere a mano un processo completo e non banale.

---

## Parte 1 — Le due foglie: TODO e RUN

Ogni routine si riduce a foglie: singole unità di lavoro. Ne esistono esattamente due tipi, e la scelta tra loro dipende da una sola domanda.

**Il metodo è specificato, oppure lo è solo il risultato?**

Se puoi scrivere il comando esatto — un'invocazione shell, una chiamata a uno script, un endpoint API con i suoi parametri — e deve essere eseguito alla lettera, quello è un `RUN`. L'agente non lo interpreta; lo passa direttamente.

```json
{ "RUN": "python3 scripts/compute_velocity.py projects/" }
```

Se sai cosa vuoi ma il metodo è meglio lasciarlo al giudizio dell'agente, quello è un `TODO`. L'agente legge il risultato atteso e decide come arrivarci.

```json
{
  "TODO": "Write the section for {{project}} in reports/weekly-summary.md: overall status (green / yellow / red), the three most relevant points of the week, and priorities for next week",
  "model": "smart"
}
```

Il primo è un `RUN` non perché sia *semplice* ma perché il comando è *dato* — non c'è nulla da decidere sul come. Il secondo è un `TODO` non perché sia *complesso* ma perché è specificato solo il risultato; il metodo (quali file leggere, cosa conta come "rilevante", come formulare le priorità) spetta all'agente.

Nota che il `TODO` è preciso. Non è la precisione a rendere qualcosa un `RUN` — lo è un *metodo* completamente specificato. Il test pratico: se il testo si potesse incollare in un terminale ed eseguire, appartiene a un `RUN`; se lo si potesse solo consegnare a un collega come brief, è un `TODO`.

Due errori derivano direttamente dall'invertire questa logica:

- **Descrivere un comando come TODO** — `{ "TODO": "Esegui scripts/compute_velocity.py su projects/" }` nomina un comando verbatim ma delega una scelta che non esiste. L'agente potrebbe parafrasare la chiamata o passare argomenti diversi. Perdi il determinismo per niente.
- **Forzare un risultato in un RUN** — `{ "RUN": "riassumi i progetti e segnala quelli red" }` non è un comando; nessun binario accetta quell'invocazione. Metterlo nel campo `RUN` non lo rende deterministico, lo rende ineseguibile.

`TODO` non significa "vago" e `RUN` non significa "importante". Il passo di sintesi più difficile e delicato di un processo è spesso un `TODO` — preciso sul *cosa*, deliberatamente aperto sul *come*.

---

## Parte 2 — Organizzare le foglie: il controllo del flusso

Una lista di foglie viene eseguita dall'alto verso il basso. I processi reali si diramano e si ripetono — e la tentazione è scrivere quella logica *dentro* un `TODO`: "per ogni progetto, se è red aggiungi un alert, altrimenti…".

È l'unica cosa che SOL ti chiede di non fare. Decisioni e cicli sono fatti strutturali, e ciascuno ha un costrutto. Quando sono sepolti nella prosa, l'agente deve ri-derivare la struttura a ogni esecuzione — esattamente l'ambiguità che SOL esiste per rimuovere. Tirali fuori.

### IF — una decisione binaria

```json
{
  "IF": {
    "when": "every evaluated entry passes",
    "then": [{ "TODO": "Set the review status to pass" }],
    "else": [{ "TODO": "Set the review status to fail and list the failing entries with their rationale" }]
  }
}
```

Una condizione, un `then`, un `else` opzionale. Nota cosa contiene `when`: *"every evaluated entry passes"* — non un predicato computabile ma un giudizio, scritto in linguaggio naturale perché è lì che appartiene l'interpretazione. Tirarlo fuori in un `IF` non lo trasforma in codice; rende il punto di diramazione **esplicito e ispezionabile** invece di nasconderlo in una frase.

### WHEN — casi mutuamente esclusivi

```json
{
  "WHEN": [
    {
      "when": "any project has overdue tasks",
      "then": [{ "TODO": "List overdue items at the top with owner and original due date" }]
    },
    {
      "when": "any project has a deadline within 3 days",
      "then": [{ "TODO": "Add an upcoming deadlines section" }]
    },
    { "else": [{ "TODO": "Note that nothing is overdue or imminent" }] }
  ]
}
```

`WHEN` serve per una lista di casi. La regola pratica: **usa `WHEN` quando le diramazioni sono mutuamente esclusive**, come uno switch. Quando le condizioni possono sovrapporsi e vuoi valutarle indipendentemente, usa invece una sequenza di blocchi `IF` separati — ognuno sta in piedi da solo e non c'è ambiguità su quale "vinca".

### REPEAT — iterazione

`REPEAT` ha quattro forme, una chiave ciascuna:

| Chiave | Semantica |
|---|---|
| `foreach` | una volta per elemento di una collezione |
| `while` | finché una condizione è vera |
| `until` | finché una condizione diventa vera |
| `for` | un numero fisso di volte |

```json
{
  "REPEAT": {
    "foreach": "project in the projects/ directory",
    "ROUTINE": [
      {
        "TODO": "Write the section for {{project}} in reports/weekly-summary.md",
        "model": "smart"
      },
      {
        "IF": {
          "when": "{{project}} has velocity below 0.3 or critical tasks blocked over 5 days",
          "then": [{ "TODO": "Append an explicit alert note to {{project}}'s section" }]
        }
      }
    ]
  }
}
```

Questo frammento mostra perché i costrutti espliciti contano. L'`IF` qui vive *dentro* il `REPEAT`, quindi scatta una volta per progetto. Lo stesso processo ha una seconda condizione quasi identica — "se **almeno un** progetto è red, anteponi un alert all'email" — che vive *fuori* dal ciclo, valutata una sola volta su tutti i progetti. Stesse parole, "se red", ma scope diverso e significato diverso. La struttura rende visibile questa distinzione; la prosa la seppellisce.

> **Perché non basta un prompt con un loop?** Perché "per ogni progetto, decidi se è red, e separatamente decidi se un qualsiasi progetto è red" è esattamente il tipo di istruzione che un LLM legge in modo incoerente da un'esecuzione all'altra. La struttura `REPEAT`/`IF` fissa *dove* avviene ciascun giudizio. Mantieni il giudizio in linguaggio naturale dentro `when` — è tutto il punto di SOL — ma smetti di lasciare al caso il *controllo del flusso*.

---

## Parte 3 — Sapere quando fermarsi

La maggior parte dei passi semplicemente finisce e parte il successivo. Ma un processo ha anche bisogno di modi deliberati per *terminare* — e SOL li distingue nettamente, perché fermarsi per un errore, fermarsi perché si è finito e fermare l'intero mondo sono tre intenzioni diverse.

### RETURN — "qui ho finito"

`RETURN` termina il processo corrente e restituisce il controllo verso l'alto — al processo padre, al punto di chiamata o all'umano al livello più alto. L'agente prosegue; solo *questa* routine è finita. È l'uscita di completamento ordinaria, ed è il modo in cui un processo soddisfa un contratto `returns` (di più nel prossimo articolo).

```json
{ "RETURN": "Draft approved — handing the result back to the caller." }
```

> **Un caveat prima dei prossimi due costrutti.** Ricorda che SOL è *non prescrittivo*: l'agente interpreta il documento invece di eseguire una tabella di transizioni fissa. Esistono strategie per rendere l'esecuzione più prevedibile — saranno il tema di un prossimo articolo. Due costrutti sono particolarmente esposti all'interpretazione: `HALT` (qui sotto) e `WAITUSERINPUT` (più avanti). Il modo in cui un dato runtime onora un "ferma tutto" o un "pausa e attendi un umano" può variare, quindi testa entrambi nel tuo specifico contesto implementativo prima di affidartici. Ci sono workaround robusti che aggirano del tutto il problema: per `HALT`, struttura il processo in modo che si *concluda naturalmente* alla fine della sua routine invece di forzare uno stop netto; per `WAITUSERINPUT`, *spezza il processo in due* — una parte prima dell'input umano e una dopo, con trigger diversi e I/O diversi.

### HALT — il pulsante rosso

`HALT` ferma l'**intera** esecuzione, sessione dell'agente inclusa. Il controllo *non* viene restituito verso l'alto; tutto termina. È intenzionale e controllato, ma globale — riservalo a stati davvero irrecuperabili, non al completamento ordinario.

```json
{ "HALT": "Cannot write the summary without velocity data — fix the script and re-run." }
```

La differenza tra `RETURN` e `HALT` è la differenza tra "questo sottocompito è concluso, prosegui sopra" e "fermati, non c'è nulla di sensato a cui continuare".

### ONERROR — il percorso d'errore

`ONERROR` definisce cosa fare quando un passo fallisce. Puoi attaccarlo a una singola istruzione (locale) o dichiararlo alla radice (fallback globale); il locale vince quando esistono entrambi.

```json
{
  "RUN": "python3 scripts/compute_velocity.py projects/",
  "ONERROR": [
    { "TODO": "Report that velocity computation failed and identify the cause" },
    { "HALT": "Cannot write the summary without velocity data — fix the script and re-run." }
  ]
}
```

Due cose da notare. Primo, `HALT` non ha una condizione incorporata — si ferma e basta quando viene raggiunto. La *condizione* vive nell'`ONERROR` che lo innesca: due costrutti, ognuno con un solo compito. Secondo, la scelta del recupero è tua ed è espressiva — qui il fallimento è fatale, quindi diagnostica e si ferma; altrove potrebbe loggare e proseguire:

```json
{
  "RUN": "main.py vault-scan {{repository}}",
  "ONERROR": [
    { "TODO": "Log the error line by line and continue" }
  ]
}
```

Stesso costrutto, intento opposto: uno ferma l'esecuzione, l'altro assorbe il fallimento e prosegue. Un errore non è automaticamente fatale — `ONERROR` è dove dici quale dei due è.

### WAITUSERINPUT — il cancello umano

A volte il processo ha bisogno di una persona: un'approvazione, una decisione, un dato che solo un umano possiede.

```json
{ "WAITUSERINPUT": "Review the draft above and type APPROVE to continue, or describe changes:" }
```

Questo mette in pausa l'esecuzione e rende la risposta dell'umano disponibile ai passi successivi. Ma porta con sé una condizione ferma: **usalo solo in contesti davvero interattivi.** In un'esecuzione batch o pianificata non c'è nessuno a rispondere, e il processo resterà semplicemente appeso. Il pattern corretto lì è *dividere il processo in due*: la prima parte fa il suo lavoro e termina normalmente con ciò che ha; la seconda riparte da zero, con l'input dell'umano come contesto iniziale. Il cancello umano diventa un confine tra due processi anziché una pausa dentro uno.

---

## Il vocabolario completo di una routine

Ecco fatto — il kit completo per una singola routine:

- **`TODO` / `RUN`** — il lavoro, delegato al giudizio o eseguito alla lettera
- **`IF` / `WHEN` / `REPEAT`** — diramazione e iterazione, tirate fuori dalla prosa in una struttura
- **`RETURN` / `HALT`** — terminare in modo deliberato, localmente o globalmente
- **`ONERROR`** — il percorso d'errore, fatale o recuperabile a tua scelta
- **`WAITUSERINPUT`** — il cancello umano, solo per contesti interattivi

Con questi puoi scrivere a mano qualsiasi processo che gira in un solo posto, in un solo contesto. Tutto è ispezionabile: ogni punto di diramazione, ogni ciclo, ogni percorso d'errore è un costrutto visibile, non un'istruzione che l'agente deve ricostruire ogni volta.

Ciò che *non* puoi ancora esprimere è il lavoro che deve girare altrove — un contesto pulito, uno specialista riutilizzabile, un compito secondario una tantum con un proprio confine. Questa è la delega, ed è dove SOL passa da script a sistema. È il tema del prossimo articolo: `CALL`, `SPAWN` e `DELEGATE`.

Repository: https://github.com/jtplugin/sol

---
*Autore: Gianni Tommasi*
