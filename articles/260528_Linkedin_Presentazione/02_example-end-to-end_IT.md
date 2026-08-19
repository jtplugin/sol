# Un processo SOL dal vivo: leggere l'orchestrazione riga per riga

Nel primo articolo ho fatto un'affermazione che merita una dimostrazione: con SOL l'agente legge un documento JSON minimale e lo esegue direttamente — niente SDK, niente motore di orchestrazione, niente runtime da installare. Le affermazioni costano poco. Guardiamo un processo reale e seguiamo cosa accade davvero quando un agente lo legge.

## Lo scenario, in una frase

Ogni mattina, prima di iniziare a lavorare, voglio un briefing che legga lo stato dei miei progetti, faccia emergere ciò che è in ritardo o vicino a una scadenza, e mi scriva un riassunto.

È il tipo di cosa che affideresti a un collega capace con una sola frase. La domanda è quanto poco devi scrivere per affidarla invece a un agente. Ecco il processo per intero:

```json
{
  "name": "daily-briefing",
  "version": "1.0",
  "description": "Generate a daily briefing from project status files. Run each morning before starting work.",
  "ROUTINE": [
    { "TODO": "Read all status files in projects/" },
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
        {
          "when": "any project has been inactive for more than 7 days",
          "then": [{ "TODO": "Flag stale projects for review" }]
        }
      ]
    },
    { "TODO": "Summarize progress since yesterday for each active project", "model": "fast" },
    { "TODO": "Write the final briefing to output/daily-briefing.md", "model": "smart" }
  ]
}
```

È tutto qui. Nessun import, nessuna definizione di classe, nessun codice di collegamento. Mostrare l'intero file serve proprio a questo: non c'è nulla nascosto fuori scena.

## Leggerlo come lo legge l'agente

**Il primo passo è un'istruzione, non un comando.**

```json
{ "TODO": "Read all status files in projects/" }
```

Nota cosa manca: nessun glob di file, nessuna scelta di parser, nessuna assunzione sul formato. Un `TODO` dichiara l'esito desiderato e lascia all'agente decidere il *come* — quali file contano come file di stato, come leggerli, cosa fare se uno è malformato. Stai delegando il metodo, non abdicando al controllo.

**Le condizioni sono giudizi, non predicati.**

```json
{ "when": "any project has overdue tasks", "then": [ ... ] }
```

"Un progetto qualsiasi ha task in ritardo" non è qualcosa che un motore di workflow tradizionale potrebbe valutare — non c'è un predicato calcolabile dietro. Ma è esattamente il genere di cosa che un modello capace legge e risolve correttamente rispetto al contenuto reale di quei file. Le condizioni dei rami vivono in linguaggio naturale perché è lì che l'interpretazione deve stare.

**Il tier del modello esprime l'intento, non l'identità.**

```json
{ "TODO": "Summarize progress...", "model": "fast" }
{ "TODO": "Write the final briefing...", "model": "smart" }
```

Il riassunto meccanico gira su `fast`; la stesura finale — dove la qualità del ragionamento si vede davvero — gira su `smart`. Non stai nominando un modello che sarà obsoleto il trimestre prossimo. Stai dichiarando quanto ragionamento merita ciascun passo, e lasci all'agente esecutore mapparlo su ciò che ha a disposizione.

## Cosa non c'è nel file

È la parte su cui vale la pena soffermarsi. Non c'è un grafo di stati. Nessuna funzione registrata. Nessun motore di runtime che interpreti le transizioni. Nessuna dichiarazione esplicita di sequenza o parallelismo. Il processo dice *cosa* deve accadere e *a quali condizioni*; tutto ciò che riguarda il *come eseguirlo* — ordine di lettura, cosa può sovrapporsi, come recuperare da un errore — è lasciato all'agente, che legge l'intero documento prima di agire e lo ragiona come un'unità.

Questa inversione è l'idea intera. Gli altri formati descrivono una macchina che un motore deve guidare. SOL descrive un intento che un agente deve realizzare.

## La precisazione onesta

Questa espressività ha un prezzo, e vale la pena dirlo chiaramente: due esecuzioni dello stesso processo possono differire, perché l'agente esercita giudizio invece di eseguire una tabella di transizioni fissa. Per i passi in cui questo è inaccettabile — invoca esattamente questo comando, esegui esattamente questa suite — SOL ha una controparte letterale al `TODO`. È `RUN`, ed è l'argomento del prossimo articolo.

## Un livello più su

Il briefing qui sopra è volutamente semplice. I processi reali aggiungono comandi letterali, cicli, subroutine e gestione degli errori — come questo frammento da un esempio più corposo nel repo:

```json
{
  "REPEAT": {
    "foreach": "entry in queue (max 5, sorted by detected desc)",
    "ROUTINE": [{ "CALL": "process-entry" }]
  }
}
```

Stessa filosofia, più struttura. Ci arriveremo.

Gli esempi eseguibili sono in [`examples/`](https://github.com/jtplugin/sol/tree/main/examples) — clona il repo e leggili come li leggerebbe l'agente.

Repository: https://github.com/jtplugin/sol

---
*Autore: Gianni Tommasi*
