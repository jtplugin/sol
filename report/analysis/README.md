# report/analysis/ — i fatti della campagna, e da dove vengono

Questa cartella è la risposta alla domanda che gli articoli lasciano aperta: *e i numeri, da
dove escono?* Ogni cifra citata in un pezzo si ricalcola qui, da una sola tabella.

## I file

| file | cos'è |
|---|---|
| `tidy.csv` | **La sorgente.** Una riga per run, 5431 righe: identificatori, configurazione della cella, verdetti e tassi continui. Nessun testo libero. |
| `load_raw.py` | Il produttore di `tidy.csv`, che legge gli artefatti grezzi della campagna. Serve l'albero grezzo, che non è pubblicato (vedi sotto). |
| `build_notebook.py` | Assembla `01_fatti.ipynb`. Il notebook non si edita a mano: si edita questo e si rigenera. |
| `nbtool.py` | Il minimo indispensabile per scrivere celle da Python. |
| `01_fatti.ipynb` | Il notebook. Legge `tidy.csv`, fa i conti, scrive `FACTSHEET.md`. Su GitHub si legge già eseguito, grafici compresi, senza installare niente. |
| `FACTSHEET.md` | Il foglio dei fatti. **Generato**: non si corregge a mano, si rigenera. |

## Rifare i conti

```
py report/analysis/build_notebook.py
cd report/analysis && jupyter nbconvert --to notebook --execute --inplace 01_fatti.ipynb
```

Serve `pandas`, `numpy`, `matplotlib`, `statsmodels`, `jupyter`. Il notebook riscrive
`FACTSHEET.md` a ogni esecuzione: se il file cambia, sono cambiati i dati o il codice, mai
la prosa.

Il primo passo — `py report/analysis/load_raw.py`, che ricostruisce `tidy.csv` — richiede
gli artefatti grezzi per run, che **non sono pubblicati**: contengono il prompt somministrato
al modello, quindi il testo delle segnalazioni di terzi. Il perimetro e il motivo stanno in
[`tests/results-main/README.md`](../../tests/results-main/README.md). Chi parte da `tidy.csv`
salta quel passo e rifà tutti i conti lo stesso.

## Cosa leggere, e in che ordine

- Le **misure** — cosa significa ciascun numero e come è calcolato: [`doc/measures.md`](../../doc/measures.md).
- Il **protocollo**, depositato prima di lanciare: [`doc/experiment-minimum-context.md`](../../doc/experiment-minimum-context.md).
- I **fatti**: `FACTSHEET.md` qui accanto, o `01_fatti.ipynb` se vuoi vedere anche i grafici e i
  conti che li producono.

Il disegno è **tre studi in sequenza, non un fattoriale**: nessuna media li attraversa. Il
notebook lo verifica nel capitolo 1 prima di calcolare qualunque cosa, ed è il vincolo che
rende sbagliata la lettura più naturale — «prendo la media per modello».
