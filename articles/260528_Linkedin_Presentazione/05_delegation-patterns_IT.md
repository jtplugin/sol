# Delega in SOL: CALL, SPAWN, DELEGATE — da script a sistema

L'articolo precedente ha messo insieme l'intero vocabolario di una *singola* routine: le foglie che fanno il lavoro (`TODO`, `RUN`), il controllo del flusso che le organizza (`IF`, `WHEN`, `REPEAT`) e i modi deliberati di fermarsi (`RETURN`, `HALT`, `ONERROR`, `WAITUSERINPUT`). Tutto ciò vive in *un solo contesto* e gira in *un solo posto*.

Restava una cosa fuori portata: il lavoro che deve girare **altrove**. Un contesto pulito, separato da quello che lo invoca. Uno specialista riutilizzabile a cui affidare una fase. Un compito secondario una tantum con un proprio confine. Questa è la delega, ed è il punto in cui SOL smette di essere uno script lineare e diventa un sistema di agenti che collaborano.

SOL ha tre costrutti per delegare. La scelta tra loro non dipende da quanto è "grande" il compito, né da quanto è importante. Dipende da **una sola domanda**.

---

## La domanda che decide tutto: il contesto

Quando deleghi una porzione di lavoro, l'unica cosa che conta davvero è questa:

**Il lavoro delegato ha bisogno di vedere il contesto di chi lo chiama, oppure ha bisogno di un contesto pulito?**

Dipende solo da questo:

- Se il lavoro ha bisogno di **tutto ciò che vede chi lo chiama** — gli stessi file, le stesse variabili, lo stato già costruito nella conversazione — allora condivide il contesto. È un `SUB`, invocato con `CALL`.
- Se il lavoro ha bisogno di **un contesto pulito** — vede solo ciò che gli passi esplicitamente e restituisce solo ciò che dichiara — allora attraversa un confine. È un `AGENT`, invocato con `SPAWN`; oppure, se serve una sola volta e non vale una definizione con nome, un `DELEGATE` inline.

Tutto il resto — i contratti, i tier di modello, i ruoli — discende da questa scelta. Vediamo i tre costrutti uno alla volta.

---

## CALL — la subroutine che condivide il contesto

Un `SUB` definisce una subroutine: un blocco di passi con un nome, da richiamare più volte senza riscriverlo. Si invoca con `CALL`.

```json
{
  "SUB": {
    "name": "normalize-entry",
    "ROUTINE": [
      { "TODO": "Trim whitespace and lowercase the entry key" },
      { "TODO": "Drop the entry if its key is empty" }
    ]
  }
}
```

```json
{ "CALL": "normalize-entry" }
```

La proprietà che definisce un `SUB` è che **condivide il contesto di chi lo chiama**. Non riceve dati: i dati su cui lavora sono già in scope. Per questo un `SUB` **non ha contratto** — niente `accepts`, niente `returns`. Non c'è alcun confine da attraversare, quindi non c'è nulla da contrattare: è il caso più semplice, e l'assenza di contratto non è una dimenticanza, è la conseguenza diretta del condividere il contesto.

Un dettaglio che vale per `SUB`, `AGENT` e tutto il resto: la definizione può comparire **ovunque** nella `ROUTINE`. L'agente legge l'intero documento prima di eseguire, quindi l'ordine di definizione non conta — puoi definire un `SUB` in fondo e chiamarlo all'inizio.

Usa `CALL` quando la logica si ripete e tutto ciò che le serve è già sotto gli occhi di chi la chiama.

---

## SPAWN — lo specialista in un contesto isolato

Un `AGENT` dichiara un agente con nome che gira in un **contesto separato**. A differenza di un `SUB`, non vede la conversazione di chi lo invoca: riceve **solo** ciò che gli passi via `with`, e restituisce **solo** ciò che descrive il suo `returns`. Si invoca con `SPAWN`.

```json
{
  "AGENT": {
    "name": "security-auditor",
    "description": "Audit a code diff for security issues.",
    "accepts": {
      "git_diff": { "required": true, "desc": "diff vs the merge-base with main" }
    },
    "returns": {
      "findings": { "json": true, "desc": "{severity, file, line_range, fix}" }
    },
    "model": "smart",
    "role": "Senior application security engineer",
    "ROUTINE": [
      { "TODO": "Review the diff for injection, authz, and secret-handling flaws" },
      { "RETURN": { "findings": "..." } }
    ]
  }
}
```

```json
{
  "SPAWN": "security-auditor",
  "with": "The files modified in this sprint and their diffs.",
  "ONERROR": [{ "TODO": "Log that the audit produced no usable result and continue" }]
}
```

Qui succedono diverse cose, ed è qui che SOL diventa davvero multi-agent:

- **L'isolamento è il punto.** Lo specialista parte pulito. Non eredita la cronologia, le ipotesi o il rumore della conversazione padre: vede esattamente il diff che gli passi e niente altro. Questo è ciò che rende un `AGENT` *componibile* — lo puoi riusare in processi diversi senza che si trascini dietro contesto estraneo.
- **Il contratto è esplicito.** `accepts` dice cosa deve arrivare, `returns` cosa torna indietro. Il padre, una volta concluso lo `SPAWN`, ha a disposizione l'output dichiarato come contesto. Ne parliamo tra un attimo.
- **`with` è il ponte.** È l'informazione che estrai dal contesto corrente per consegnarla all'agente. Se ometti `with`, l'agente parte senza alcun contesto trasferito e lavora dalla sola `description` e dalla sua `ROUTINE`.
- **`model` e `role` vivono dove ha senso.** Lo specialista può girare su un tier diverso (`smart`) e con una persona dichiarata, senza che chi lo invoca debba saperne nulla.

Usa `SPAWN` quando il lavoro è uno specialista riutilizzabile, con una routine strutturata, che ha bisogno di un contesto pulito.

---

## DELEGATE — la delega inline, una tantum

A volte serve isolare un compito ma non vale la pena dargli un nome e una definizione: lo usi una volta sola, qui e ora. È il `DELEGATE`.

```json
{
  "DELEGATE": {
    "task": "Scan the modified files for hardcoded credentials and report each occurrence",
    "with": "List of files modified in this sprint and their diffs",
    "returns": { "findings": { "json": true, "desc": "{severity, file, line_range, fix}" } }
  }
}
```

Un `DELEGATE` è uno `SPAWN` senza definizione con nome: il compito è descritto direttamente nel campo `task`. Eredita la stessa proprietà cruciale — **contesto isolato** — e gli stessi strumenti di confine: `with` per ciò che entra, `returns` per ciò che esce. La differenza è solo l'assenza di una definizione riutilizzabile.

La regola pratica: `DELEGATE` per le deleghe una tantum; `AGENT` + `SPAWN` quando l'agente è riutilizzabile o ha una routine strutturata che merita di stare in piedi da sola.

---

## I tre costrutti a colpo d'occhio

|  | `CALL` | `SPAWN` | `DELEGATE` |
|---|---|---|---|
| Definizione | `SUB` | `AGENT` | inline (`task`) |
| Contesto | **condiviso** | **isolato** | **isolato** |
| Riutilizzabile | sì (con nome) | sì (con nome) | no (una tantum) |
| Contratto | nessuno | `accepts` / `returns` | `with` / `returns` |

Tutta la tabella si legge da sinistra: prima decidi il contesto (condiviso o isolato), poi se la cosa è riutilizzabile. Il contratto compare solo dove c'è un confine da attraversare — ed è esattamente il prossimo tema.

---

## I contratti: la membrana tra due agenti

`accepts` e `returns` descrivono **ciò che attraversa un confine di contesto** — la membrana tra due agenti che non condividono lo stato. Esistono sulla radice del processo (il suo confine esterno verso chi lo invoca), su ogni `AGENT`, e nelle versioni di override lato invocazione di `SPAWN` e `DELEGATE`. **Non** esistono su `SUB`, per la ragione che abbiamo già visto: condividendo il contesto, non c'è nulla da trasferire.

Un contratto può assumere due forme:

- **Aperta (stringa)** — una descrizione in linguaggio naturale. Va bene quando il confine porta informazione che l'agente interpreta, e sbagliare un dettaglio non rompe nulla di meccanico.

  ```json
  "returns": "Findings with severity, file path, line range, and suggested fix."
  ```

- **Strutturata (mappa di campi)** — quando un campo va azzeccato esattamente, perché a valle qualcosa fa affidamento sulla sua forma. I vincoli si compongono: `required`, `anyof`, `number`, `json`, più un `desc` libero.

  ```json
  "accepts": {
    "env":      { "anyof": ["coding", "staging", "production"], "required": true },
    "git_diff": { "required": true, "desc": "diff vs the merge-base with main" }
  }
  ```

Il test per scegliere è netto: **aggiungi struttura solo dove sbagliare un campo romperebbe la macchina, non la conversazione.** Tutto il resto resta una stringa. Un contratto non è decorazione: o serve e lo disegni bene, o non serve e lo ometti.

E i contratti vanno onorati **da entrambi i lati**: chi definisce un `AGENT` con un `accepts` controlla l'input in cima alla propria routine; chi lo invoca con `SPAWN` scrive un `with` che soddisfa quel contratto. È un accordo, non un suggerimento decorativo — ma *come* venga fatto rispettare è proprio il punto delicato che affrontiamo adesso.

---

## La non-prescrittività: SOL non può forzare nulla

Qui arriviamo al cuore di SOL, e a un'onestà che vale la pena rendere esplicita.

La prima riga della specifica non è uno slogan, è un vincolo: *nessun runtime esterno è richiesto — l'agente è il runtime.* Non c'è un parser che obbliga a prendere un ramo, non c'è uno scheduler che garantisce che uno `SPAWN` diventi davvero una sessione isolata, non c'è un type checker che imponga un contratto. La specifica lo dice a chiare lettere: i contratti sono *"onorati dalla comprensione dell'agente, non da un type checker a runtime"*, e `model` è *"un suggerimento, non un imperativo"*.

**Questa è una scelta deliberata, non una lacuna.** È ciò che permette a un `TODO` di dire *"identifica la causa radice più probabile"* — qualcosa che nessun motore deterministico potrebbe valutare. Lo stesso vale per la delega: è ciò che permette a un `AGENT` di *interpretare* il proprio compito invece di eseguire una tabella di transizioni fissa. Il prezzo è che **nulla, nel linguaggio, può obbligare un agente a comportarsi come vuoi tu.**

Quindi la domanda giusta non è mai "come rendo SOL prescrittivo?". È: *"se ho bisogno che un certo comportamento sia prevedibile, a quale livello inietto quella prevedibilità, e quanto mi costa?"*

### Un'asimmetria che vale la pena capire

Non tutti gli intenti di SOL sono ugualmente forzabili, e la delega offre l'esempio più pulito di questa asimmetria.

- **L'isolamento del contesto è implicato dal contratto.** SOL dice che un `AGENT` *"riceve solo ciò che `SPAWN` passa via `with`, e restituisce solo ciò che descrive `returns`. Non condivide il contesto di chi lo chiama."* Questa è un'affermazione sul *flusso di informazione*. Qualunque livello faccia rispettare fedelmente *"il chiamato vede solo `with`"* è **costretto** a creare un contesto pulito — non c'è altro modo di garantire che il chiamato non veda lo stato del chiamante. Quindi l'isolamento si può **far emergere** semplicemente prendendo sul serio il contratto.
- **La scelta del modello non è implicata da nulla.** Non esiste alcuna proprietà di flusso d'informazione che richieda un modello diverso. È esattamente per questo che `model` è *solo* un suggerimento: è ortogonale al contratto. Forzare un modello specifico richiede sempre un livello *esterno* al giudizio dell'agente.

La conseguenza pratica: **puoi far pressione sull'isolamento dall'interno della disciplina stessa di SOL; non puoi far pressione sulla scelta del modello senza un risolutore esterno.** Tienilo a mente quando deleghi: l'isolamento di uno `SPAWN` è molto più "a portata di mano" del tier di modello che gli hai assegnato.

### Le strategie esistono — e meritano un articolo a parte

La buona notizia è che la prevedibilità non si ottiene snaturando il linguaggio, ma **iniettandola a un livello scelto** attorno ad esso: una direttiva in prosa che spiega all'agente come trattare ogni `SPAWN`; le funzionalità native dell'ambiente di esecuzione (in Claude Code, ad esempio, registrare ogni `AGENT` come sub-agente nativo con il suo modello); un piccolo runtime deterministico affianco a SOL; fino, all'estremo, all'incapsulamento dentro un orchestratore esterno. Ogni livello compra più determinismo al prezzo di più portabilità e più lavoro — e la regola ricorrente è scegliere **il livello più superficiale che soddisfa il bisogno reale di determinismo**.

Questa è una mappa a sé, con i suoi compromessi misurati uno per uno, e sarà il tema di **un prossimo articolo dedicato**. Qui basti il principio: SOL resta il livello dell'*intento*; la prevedibilità è una decisione di deployment presa *attorno* ad esso, non una proprietà avvitata dentro il linguaggio. Proprio perché tutto questo poggia sull'interpretazione dell'agente, sono in corso test approfonditi per verificare che le varie istruzioni dedicate — `SPAWN`, `DELEGATE`, i contratti, i tier di modello — producano davvero la configurazione agentica che descrivono; gli utilizzi concreti in ambiente Claude Code, intanto, sono più che soddisfacenti.

---

## Da script a sistema

Con la delega, il vocabolario è completo. Dentro una routine sai organizzare foglie, diramazioni, cicli ed errori; tra una routine e l'altra sai scegliere il confine giusto:

- **`CALL` / `SUB`** — stesso contesto, logica condivisa e riutilizzabile, nessun contratto.
- **`SPAWN` / `AGENT`** — contesto isolato, specialista riutilizzabile, contratto `accepts` / `returns`.
- **`DELEGATE`** — contesto isolato, delega inline una tantum, confine `with` / `returns`.

E la regola che li attraversa tutti è sempre la stessa: **decidi prima il contesto.** Il resto — riutilizzo, contratti, modello, ruolo — discende da lì.

Resta altro da raccontare: SOL non vive come JSON nudo, ma come JSON *dentro* un documento markdown — codice e documentazione nello stesso file, tabelle di configurazione citate dai cicli, diff leggibili, skill autoesplicative. Cosa abilita questo pattern è il tema del prossimo articolo.

Repository: https://github.com/jtplugin/sol

---
*Autore: Gianni Tommasi*
