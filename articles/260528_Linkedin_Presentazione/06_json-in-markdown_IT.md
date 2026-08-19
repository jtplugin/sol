# SOL dentro Markdown: perché il formato del file non è un dettaglio

Finora questa serie ha parlato di SOL quasi fosse soltanto JSON: foglie, controllo del flusso, delega, contratti. Tutto vero, e tutto indipendente da dove quel JSON vive davvero. In pratica, però, un documento SOL è raramente un file `.json` a sé stante. È un blocco JSON incorporato in un documento Markdown — e questa scelta non è un dettaglio di packaging. È ciò che rende possibili diverse cose che un file JSON isolato non potrebbe dare.

---

## Il pattern

Un file SOL ha questo aspetto:

```markdown
# Processo: weekly-closure

**Trigger:** programmato, ogni venerdì alle 18:00.
**Owner:** team ops.

## Tabelle di origine

| env        | endpoint                      |
|------------|--------------------------------|
| staging    | https://stg.api.internal/close |
| production | https://prod.api.internal/close |

## Processo

​```json
{
  "name": "weekly-closure",
  "ROUTINE": [
    {
      "REPEAT": {
        "foreach": "row in Source tables",
        "ROUTINE": [
          { "RUN": "curl -X POST {{endpoint}}/close" },
          { "TODO": "Record the response status against {{env}}" }
        ]
      }
    },
    { "TODO": "Summarize successes and failures by environment" }
  ]
}
​```

## Note

- I fallimenti su `staging` non sono bloccanti; quelli su `production` interrompono l'esecuzione.
```

Prosa attorno al blocco, una tabella sopra, il JSON eseguibile in mezzo. Niente di esotico — è lo stesso Markdown che chiunque scrive già per la documentazione. L'unica differenza è che una parte di esso è anche il programma.

---

## Cosa abilita questo singolo fatto

**Documentazione e codice smettono di divergere.** Non esiste un file di specifica separato che descrive cosa fa il JSON e diventa obsoleto la settimana dopo che qualcuno modifica la `ROUTINE`. Il trigger, l'owner, le avvertenze — vivono nello stesso file, accanto ai passi che descrivono. Leggi il file una volta e hai entrambe le vista.

**Le tabelle di configurazione diventano input di prima classe.** Il `foreach` qui sopra non ha bisogno di un array inline sepolto nel JSON; può puntare a una tabella Markdown posizionata proprio sopra di lui, una riga per ambiente. Aggiungere un nuovo ambiente significa modificare una tabella, non toccare la routine. L'agente legge il documento nel suo insieme — tabella e JSON insieme — quindi il riferimento si risolve naturalmente.

**I diff restano leggibili.** Cambia il testo di un TODO e il diff mostra una riga. Aggiungi un ambiente e il diff mostra una riga di tabella. Confrontalo con un formato binario dedicato o con uno YAML pesantemente annidato, dove un cambiamento concettualmente minimo può propagarsi attraverso l'indentazione. Chi revisiona — umano o agente — vede esattamente cosa è cambiato.

**Le skill diventano autoesplicative.** L'articolo precedente di questa serie ha già mostrato questo pattern sotto un altro nome: una skill di Claude Code con un wrapper Markdown (trigger, prerequisiti, note) e un blocco SOL che porta la logica eseguibile. Non è un caso speciale aggiunto a SOL — è lo stesso pattern di JSON-dentro-Markdown, applicato a un file di skill invece che a un processo standalone.

**La visualizzazione arriva gratis.** Poiché il JSON è un blocco autocontenuto, gli strumenti possono estrarlo e proiettarlo su qualcos'altro — un flowchart Mermaid, un diagramma draw.io — senza toccare la prosa circostante. Gli strumenti di SOL fanno esattamente questo (`sol2mermaid.py`, `sol2drawio.py`): ogni costrutto si mappa su una primitiva di flowchart standard, così un processo può essere *letto* da un agente e *visto* da un umano partendo dalla stessa fonte, senza un secondo file da mantenere sincronizzato.

---

## Generato, non solo scritto a mano

Tutto quanto sopra descrive un file che qualcuno scrive a mano. Lo stesso pattern vale, senza nessun meccanismo extra, quando il file viene prodotto al volo.

Il Markdown è banale da generare dinamicamente: si prendono dati da un database, da una risposta di un'API, da un file di configurazione, dall'output di un passo precedente — si versano in titoli, tabelle, prosa — e si appende il blocco SOL che opera su di essi. Il risultato è un solo documento che porta sia il contesto sia le istruzioni per agire su di esso, assemblato in un solo passaggio, senza nulla da mantenere sincronizzato dopo, perché non c'è un "dopo" — contesto e processo vengono generati insieme.

È questo che rende il pattern un target naturale per strumenti, script o altri agenti che devono fornire a un agente un brief più strutturato di un prompt a una riga: una specifica dettagliata assemblata da dati live, un documento di passaggio con esattamente le righe su cui un `foreach` deve iterare, un report generato che si chiude con "ed ecco cosa fare a riguardo." Niente di tutto questo richiede una logica di generazione specifica per SOL — è lo stesso templating che chiunque già usa per produrre un report Markdown, con un blocco JSON appeso in fondo.

---

## Perché non potrebbe essere "solo JSON"

Niente di tutto questo dipende da una caratteristica del JSON in sé — dipende dal fatto che il JSON vive *dentro* qualcosa che ha già un posto per la prosa, le tabelle, la struttura: Markdown. Un file `.json` nudo non ha commenti, non ha titoli, non ha tabelle, niente a cui attaccare una motivazione. Finiresti per mantenere un secondo file per il perché, e i due file divergerebbero nel momento in cui uno viene modificato senza l'altro. Incorporare il JSON nel Markdown comprime tutto questo in un solo file, un solo diff, una sola lettura.

Questo è anche il motivo per cui il pattern non costa nulla di extra da adottare: qualunque strumento che già fa il parsing dei blocchi di codice — un renderer Markdown, un generatore di siti statici, un tool per un vault, il loader delle skill di Claude Code — ottiene il blocco SOL gratis. SOL non chiede un'estensione di file dedicata né un parser su misura. Chiede di essere un blocco di codice in un formato che tutti già leggono.

---

## Cosa resta

Il vocabolario, il modello di delega e ora la forma del file sono tutti sul tavolo. Resta una cosa: questo è un progetto open source, licenza MIT, e la serie si chiude dicendo chiaramente cosa significa in pratica — cosa c'è, cosa manca ancora, come contribuire.

Repository: https://github.com/jtplugin/sol

---
*Autore: Gianni Tommasi*
