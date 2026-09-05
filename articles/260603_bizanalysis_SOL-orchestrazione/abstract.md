# Abstract — bizanalysis.org (IIBA Italia): SOL e l'orchestrazione AI per l'analista di business

## Tipo
Serie di tre articoli long-form, da pubblicare in sequenza. ~7.900 parole in tutto
(3.300 + 2.500 + 2.000). Il primo si regge da solo e si chiude su tre domande; il
secondo le misura; il terzo racconta come quelle misure hanno provato a ingannare
chi le ha prese.

## Piattaforma
bizanalysis.org — blog della IIBA Italia

## Target
Analisti di business (community IIBA / BABOK). Non sviluppatori: familiari con
modellazione di processo, requisiti, regole di business, governance, tracciabilità,
ponte business↔IT. Non si presume background di programmazione.

## Obiettivo
Presentare SOL agli analisti di business partendo da un problema che riconoscono:
quando è un'AI a eseguire, la regola di business finisce dentro un prompt, e un
prompt non è un posto dove una regola possa vivere in modo governabile. SOL è la
proposta di tenerla in un posto solo e generare da lì le sue rappresentazioni.
Poi le misure: a quali condizioni un processo scritto una volta viene eseguito
davvero, e cosa costa scoprirlo.

## I tre articoli

### 1 — L'agente è il runtime: scrivere processi che un'AI esegue
[01_sol-per-analisti](01_sol-per-analisti.md) · ~3.300 parole · concettuale

Diagrammi di flusso, nessun JSON nel corpo. Apre sul fossato fra descrivere un
processo e farlo eseguire, e sul fatto che lungo il percorso le regole si
ritraducono a mano una volta per formato. Presenta SOL, l'inversione di controllo
(l'agente orchestra e *scende* nel deterministico, invece del contrario), la
portabilità delle regole con gli strumenti che la realizzano, e i limiti detti per
primi. Si chiude sulle tre domande che aprono il secondo articolo, senza bruciarne
i risultati.

### 2 — A che condizioni un processo scritto viene davvero eseguito
[02_business-sol](02_business-sol.md) · ~2.500 parole · cinque tabelle di dati

I risultati: 5.421 esecuzioni concluse, sei configurazioni locali più tre modelli
commerciali (Haiku 4.5, Sonnet 5, Opus 5), sette forme dello stesso identico
algoritmo, ipotesi depositate prima di lanciare. Risponde alle tre domande, riporta
il risultato che non era nelle domande di partenza, e chiude con una ricetta
operativa per chi governa processi e con i limiti dello studio.

Dei tre commerciali si dice una cosa sola e si passa oltre: da Haiku in su la resa
si appiattisce, i tre casi che nessuno risolve sono gli stessi per tutti e tre, e
salire di modello non compra niente. Era l'attesa dichiarata non verificata della
versione precedente; ora è verificata e chiusa in un paragrafo.

### 3 — Quindici modi in cui un banco di prova dà ragione a chi l'ha costruito
[03_metodo-sol](03_metodo-sol.md) · ~2.000 parole · metodologico

Per chi valuta sistemi di AI. Quindici errori trovati nella stessa campagna,
raggruppati per dove si annidano — il denominatore, l'etichetta, la forma dei
confronti, l'analista — più i controlli che li fanno emergere. Ognuno ha dato per
un po' un risultato che sembrava buono.

## Messaggi chiave
- Il prompt è diventato **il posto dove vive la regola di business**, e non si
  versiona in modo utile, non si firma, non si confronta con la versione approvata.
  È un problema di governance prima che di tecnica.
- La regola sta in un posto solo; diagramma, prosa e prompt sono **proiezioni che si
  rigenerano**, non copie da tenere allineate. Verso i diagrammi la conversione è
  deterministica; verso la prosa esistono due rese, una deterministica e una prodotta
  da un modello sotto prompt congelato.
- Esiste un livello intermedio di automazione fra la prosa e il codice: SOL lo occupa.
- "L'agente è il runtime": nessun SDK, nessun motore da installare.
- Il cambio di paradigma è un'**inversione di controllo**: non un'orchestrazione
  deterministica che chiama l'AI, ma un'AI che orchestra e *scende* nel deterministico
  (RUN) quando l'esattezza conta.
- SOL esprime *intento*; alcune garanzie (isolamento, selezione del modello, pausa
  interattiva) dipendono dal contesto d'esecuzione, non dal linguaggio. Onestà sui limiti.

## Nota editoriale
I tre articoli **dichiarano in apertura di essere stati stesi da un'AI**, con la
divisione del lavoro esplicitata pezzo per pezzo e la firma sulle affermazioni che
resta di una persona. Non è un disclaimer ricopiato: in ciascuno la dichiarazione è
riscritta sul contenuto di quel pezzo.

## Figure
- Articolo 1 — diagramma portante: processo `weekly-closure` (chiusura settimanale
  dei progetti), con legenda dei colori; tabella di posizionamento "quando SOL /
  quando un framework"; schema della catena requisito → SOL → proiezioni.
- Articolo 2 — cinque tabelle di risultati.
- Articolo 3 — un blocco di calcolo e una tabella.

## Lingua
Italiano.
