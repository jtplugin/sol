# Dalla prosa al processo: scrivere SOL con la skill di conversione

Nei primi due articoli ho descritto cos'è SOL e ho letto un processo reale riga per riga. La domanda naturale che segue è: come si scrive uno da zero?

La risposta onesta è che non devi farlo a mano. C'è una skill per questo.

## Il punto di partenza: un paragrafo

Si comincia da dove si comincerebbe con qualsiasi collega — una descrizione di quello che vuoi ottenere.

> Ogni venerdì pomeriggio, prima delle 17, fai una chiusura settimanale dei progetti attivi.
>
> Inizia leggendo tutti i file di stato nella cartella `projects/` — ogni progetto ha un file `status.md` con le attività della settimana. Poi lancia `scripts/compute_velocity.py`, passandogli `projects/` come argomento; lo script calcola la velocità settimanale di ogni progetto (task chiusi / task aperti) e scrive i risultati in `reports/velocity.json`.
>
> Sulla base di quello che hai letto e dei dati di velocità, scrivi un riepilogo settimanale in `reports/weekly-summary.md`. Ogni progetto ha una sezione con: stato generale (verde / giallo / rosso), i tre punti più rilevanti della settimana, e le priorità per la prossima. Se un progetto è in rosso — velocità sotto 0.3 o task critici bloccati da più di 5 giorni — aggiungi una nota di allerta esplicita.
>
> A questo punto aggiorna la todo list: sposta nella sezione "Completati" di `todo.md` tutti i task che risultano chiusi nei file di stato, e aggiungi in cima a "Questa settimana" le priorità che hai appena identificato.
>
> Infine, manda una mail a `team@company.com` con oggetto `Weekly Summary — [data di oggi]` e come corpo il contenuto del riepilogo appena scritto. Prima di mandarla, se almeno un progetto è in rosso, aggiungi in cima al corpo una riga di allerta in grassetto con i nomi dei progetti critici.

Nessun JSON, nessuna sintassi, nessun nome di campo. Solo intento.

Incolli questo in Claude Code con `/sol`, incolli la descrizione, e la skill si mette al lavoro.

## Cosa la distingue da un semplice formatter

Un formatter prende struttura in input e produce struttura in output. La skill fa qualcosa di diverso: legge per significato.

Identifica che `scripts/compute_velocity.py projects/` è un comando verbatim — diventa un `RUN`, non un `TODO`. Un `TODO` chiederebbe all'agente di decidere come calcolare la velocità; un `RUN` dice: esegui esattamente questo. Nota anche che se lo script fallisce, il riepilogo non può essere scritto — quindi avvolge il `RUN` in un `ONERROR` che segnala il problema e ferma l'esecuzione in modo pulito.

Identifica che "per ogni progetto" è un ciclo — diventa un `REPEAT`. Vede due condizioni distinte nella descrizione: una per progetto ("se questo progetto è in rosso, aggiungi una nota di allerta") e una globale ("se almeno un progetto è in rosso, prepend una riga alla mail"). Genera due blocchi `IF` distinti nei posti giusti — uno dentro il ciclo, uno fuori.

Nota anche un passaggio che la descrizione lasciava implicito: prima di poter aggiungere condizionalmente l'allerta alla mail, serve avere un corpo della mail su cui operare. La skill aggiunge un passo esplicito "prepara il corpo della mail" che non è letteralmente nella prosa, perché senza di esso la condizione non avrebbe nulla su cui agire.

Invece di indovinare su qualsiasi cosa, la skill porta in superficie le ambiguità genuine come domande numerate prima di scrivere un singolo file. Tu rispondi, poi genera.

## L'output, letto come lo legge un agente

Ecco il file che produce la skill — `examples/weekly-closure.json`:

```json
{
  "name": "weekly-closure",
  "version": "1.0",
  "description": "Chiusura settimanale — da eseguire ogni venerdì prima delle 17:00. Legge i file di stato dei progetti, calcola la velocità, scrive il riepilogo per progetto, aggiorna la todo list e invia il riepilogo per email al team.",
  "role": "Project manager che esegue il ciclo di reporting settimanale.",
  "ROUTINE": [
    { "TODO": "Leggi tutti i file status.md in projects/", "model": "fast" },
    {
      "RUN": "python3 scripts/compute_velocity.py projects/",
      "ONERROR": [
        { "TODO": "Segnala che il calcolo della velocità è fallito e identifica la causa" },
        { "HALT": "Impossibile scrivere il riepilogo senza i dati di velocità — correggi scripts/compute_velocity.py e riavvia." }
      ]
    },
    { "TODO": "Leggi reports/velocity.json", "model": "fast" },
    {
      "REPEAT": {
        "foreach": "project nella cartella projects/",
        "ROUTINE": [
          {
            "TODO": "Scrivi la sezione per {{project}} in reports/weekly-summary.md: stato generale (verde / giallo / rosso), i tre punti più rilevanti della settimana e le priorità per la prossima",
            "model": "smart"
          },
          {
            "IF": {
              "when": "{{project}} ha velocità sotto 0.3 o ha task critici bloccati da più di 5 giorni",
              "then": [
                { "TODO": "Aggiungi una nota di allerta esplicita alla sezione di {{project}} in reports/weekly-summary.md" }
              ]
            }
          }
        ]
      }
    },
    { "TODO": "In todo.md, sposta tutti i task risultati chiusi nei file di stato nella sezione Completati", "model": "fast" },
    { "TODO": "In todo.md, aggiungi le priorità identificate nel riepilogo in cima alla sezione Questa settimana", "model": "fast" },
    { "TODO": "Prepara il corpo della mail dal contenuto di reports/weekly-summary.md", "model": "fast" },
    {
      "IF": {
        "when": "almeno un progetto ha stato rosso",
        "then": [
          { "TODO": "Aggiungi in cima al corpo della mail una riga di allerta in grassetto con i nomi dei progetti in rosso" }
        ]
      }
    },
    {
      "TODO": "Manda una mail a team@company.com con oggetto 'Weekly Summary — {{today}}' e corpo uguale al corpo della mail preparato",
      "ONERROR": [
        { "TODO": "Salva il corpo della mail preparato in reports/weekly-email-draft.md e segnala che la mail non è stata inviata" }
      ]
    }
  ]
}
```

Alcune cose vale la pena notare.

**`RUN` vs `TODO` per lo script Python.** La descrizione nomina un comando esatto: `scripts/compute_velocity.py projects/`. Questo è un `RUN` — passato verbatim, senza interpretazione. Se la descrizione avesse detto "calcola la velocità per tutti i progetti", sarebbe stato un `TODO`: l'agente avrebbe deciso come farlo. La distinzione conta perché `RUN` garantisce uno step deterministico e verificabile; `TODO` delega il metodo all'agente. La skill applica questa scelta automaticamente in base al fatto che il comando sia specificato o solo il risultato.

**`ONERROR` con `HALT` dentro.** Lo script di velocità può fallire. Senza il suo output, il riepilogo sarebbe incompleto — quindi il comportamento corretto è fermarsi in modo pulito, non saltare silenziosamente. Il blocco `ONERROR` prima diagnostica (un `TODO` che identifica la causa), poi si ferma con un messaggio leggibile. `HALT` non ha un predicato incorporato; si limita a fermare tutto quando viene raggiunto. La condizione vive nell'`ONERROR` che lo attiva — due costrutti, ciascuno che fa una cosa sola.

**Due blocchi `IF`, in scope diversi.** L'allerta per progetto ("se questo progetto è in rosso") vive dentro il `REPEAT`, quindi scatta una volta per progetto. L'allerta per la mail ("se almeno un progetto è in rosso") vive fuori dal ciclo, dopo che tutte le sezioni sono state scritte. La skill posiziona ogni condizione al livello giusto — non perché tu abbia specificato "dentro o fuori dal ciclo", ma perché ha letto cosa valuta ogni condizione.

**I model tier sono funzionali, non estetici.** Leggere file e preparare il corpo della mail sono operazioni di I/O: `fast`. Scrivere le sezioni per progetto del riepilogo — valutare lo stato, selezionare i tre punti più rilevanti, articolare le priorità per la settimana successiva — è sintesi: `smart`. Non si sta nominando un modello che sarà obsoleto il prossimo trimestre; si dichiara quanto ragionamento merita ogni step e si lascia all'agente esecutore il compito di tradurlo in qualsiasi modello abbia a disposizione.

## Cosa decide anche la skill

Oltre alle istruzioni vere e proprie, la skill risolve due cose a cui non hai dovuto pensare.

**La struttura dei file.** Un processo di questa dimensione — nove nodi di primo livello, nessun agente riutilizzabile — rimane in un singolo file. Se la tua descrizione avesse contenuto due comportamenti agentici distinti invocati da un orchestratore condiviso, la skill li avrebbe separati: un file per agente sotto `agents/`, un entry point principale che li importa via `IMPORT`.

**I diagrammi.** Dopo aver scritto il JSON, la skill chiede se vuoi una rappresentazione visuale. Puoi ottenere un flowchart Mermaid (`.mmd`) — utile se lavori su GitHub, VS Code o Obsidian — oppure un file draw.io (`.drawio`) se vivi in Confluence o Notion. Entrambi usano lo stesso schema cromatico semantico: blu per `TODO`, verde per `RUN`, giallo per il flusso di controllo, rosso per gli errori. Lo stesso processo si legge in modo coerente in entrambi i formati, ed entrambi sono rigenerabili dal JSON in qualsiasi momento.

## Cosa significa in pratica

Il JSON che produce la skill è immediatamente eseguibile. Un agente può leggerlo ed eseguirlo senza alcuna modifica. Ma è anche ispezionabile e modificabile — puoi leggere ogni campo, cambiare un model tier, aggiungere uno step, ristrutturare un ramo. Non è una scatola nera che ha prodotto qualcosa che non riesci a ragionare.

La skill abbassa la soglia per iniziare. Non abbassa il livello di controllo che hai una volta che sei partito.

L'esempio completo si trova in [`examples/weekly-closure.json`](https://github.com/jtplugin/sol/blob/main/examples/weekly-closure.json) nel repository.

Repository: https://github.com/jtplugin/sol

---
*Autore: Gianni Tommasi*
