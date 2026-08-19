# Abstract — bizanalysis.org (IIBA Italia): SOL e l'orchestrazione AI per l'analista di business

## Tipo
Articolo singolo long-form (~2.000 parole)

## Piattaforma
bizanalysis.org — blog della IIBA Italia

## Target
Analisti di business (community IIBA / BABOK). Non sviluppatori: familiari con
modellazione di processo, requisiti, regole di business, governance, tracciabilità,
ponte business↔IT. Non si presume background di programmazione.

## Obiettivo
Presentare SOL agli analisti di business inquadrandolo nel loro mestiere: un formato
di *definizione di processo* leggibile ed eseguibile direttamente da un agente AI.
Far emergere applicabilità, casi d'uso e inserimento in altri contesti di orchestrazione,
con onestà sui limiti.

## Taglio
Concettuale / posizionamento. I processi sono mostrati come **diagrammi di flusso**,
non come JSON. Nessun blocco di codice nel corpo.

## Messaggi chiave
- Esiste un livello intermedio di automazione tra la prosa e il codice: SOL lo occupa.
- "L'agente è il runtime": nessun SDK, nessun motore da installare.
- Il cambio di paradigma profondo è un'**inversione di controllo**: non un'orchestrazione
  deterministica che chiama l'AI, ma un'AI che orchestra e *scende* nel deterministico
  (RUN) quando serve.
- SOL è "BPMN che si esegue": una sola fonte di verità, diagramma per lo stakeholder e
  specifica per l'IT (convertibilità verso mermaid/draw.io).
- SOL esprime *intento*; alcune garanzie (isolamento, selezione del modello, pausa
  interattiva) dipendono dal contesto d'esecuzione, non dal linguaggio. Onestà sui limiti.

## Figure
- Diagramma portante: processo `weekly-closure` (chiusura settimanale dei progetti).
- Tabella di posizionamento: "quando SOL / quando un framework".

## Lingua
Italiano — [[01_sol-per-analisti]]
