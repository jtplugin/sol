# Quindici modi in cui un banco di prova dà ragione a chi l'ha costruito

*Terzo di tre articoli. Il primo presenta SOL; il secondo riporta i risultati di una campagna di
4.871 esecuzioni su sette modelli. Questo elenca gli errori che quella campagna ha nascosto, e come
si trovano. Per chi valuta sistemi di AI. v1, 2026-09-01.*

> **Una nota sul testo.** Testo e analisi sono di un'AI, la stessa da cui viene il secondo articolo.
> Di questi errori una parte li ha trovati lei, rifacendo i conti dai dati grezzi senza vedere quello
> che avevo già scritto; una parte li ho trovati io contestandone i risultati. Nessuno dei due li
> avrebbe trovati tutti. Dati e notebook stanno nel repository.

---

Un banco di prova non è un termometro: è un artefatto, e porta dentro le convinzioni di chi l'ha
fatto. Nei denominatori, nelle etichette, nell'ordine in cui i confronti vengono in mente. Nessuna di
quelle convinzioni si annuncia: si presentano tutte come numeri.

Quindici errori, tutti trovati nella stessa campagna, tutti generici. Ognuno ha dato per un po' un
risultato che sembrava buono.

---

# Il denominatore

## 1. L'unità che si traveste da effetto

Lo stesso processo passava l'**1,5%** delle volte consegnato in un modo e il **35,6%** consegnato in
un altro. Un fattore venti.

Le due cifre non hanno la stessa unità. L'1,5% è la quota di *code intere* — sei-undici decisioni
consecutive — risolte tutte correttamente. Il 35,6% è la quota di *singole* richieste corrette. Sullo
stesso banco a coda, la quota media di richieste corrette è **0,732**.

```
0,732 per richiesta → elevato a ~8,7 decisioni consecutive → 0,066
                    → osservato                            → 0,015
```

Fra i due numeri non c'era un effetto: c'era un esponente. Sull'unità comparabile il verso si
rovescia, 0,732 contro 0,356.

> Due tassi con denominatori diversi differiscono per definizione prima che per fenomeno. Un compito
> *tutto-o-niente* ripetuto *k* volte trasforma una differenza modesta in un abisso apparente.
> Riportate i due lati alla stessa unità; se non si può, non è un risultato.

## 2. I casi che misurano il banco, non il trattamento

Tre casi di prova su venti non li risolve nessuno: nessun modello, nessuna forma, nessuna replica.
Tolgono il 15% al denominatore di ogni condizione e non discriminano niente.

Con quelli dentro, il modello commerciale più piccolo segna 78,9%. Senza, **94,1%**. Stavo
difendendo il sistema con la cifra più bassa delle due, contro un riferimento accademico
dell'82,7%.

> Un caso che nessuna condizione supera non è difficile: non partecipa. Vale anche il contrario.
> Riportateli a parte e pubblicate entrambi i denominatori.

## 3. La selezione che ha un verso

Una misura era leggibile solo su 643 esecuzioni su 1.236. Non è un problema di potenza: quelle righe
le emette chi il protocollo non ha strozzato, cioè i modelli che andavano meglio. La configurazione
peggiore contribuisce con **tre** esecuzioni.

> Quando una misura è disponibile solo su parte del campione, chiedetevi cosa determina la
> disponibilità. Se è correlata all'esito, la misura è distorta nella direzione comoda.

## 4. Il derivato che diverge dalla fonte

La pipeline scrive un punteggio grezzo per esecuzione, poi rigenera un indice CSV. L'indice **diverge
su 17 esecuzioni** — lo 0,3%, irrilevante per qualunque media. Ma è la prova che è stato rigenerato in
un momento diverso, e nulla lo verificava. Inoltre binarizza la qualità e butta via il tasso continuo,
cioè l'informazione che il fallimento medio ha due terzi del lavoro corretto.

> Analizzate dalla fonte. Se tenete un derivato, mettete un controllo che ne verifichi l'accordo.

---

# L'etichetta

## 5. La metrica che non varia

Lo scorer produce un verdetto di *fedeltà*. Nel terzo studio vale **`fail` su tutte le 1.959
esecuzioni**, compreso il modello che risolve il 96,9% dei casi.

Il terzo studio è quello costruito senza il tracing: il controllo di sequenza non ha nulla da
controllare, quindi fallisce sempre. Non è una misura, è una costante — e una costante travestita da
misura si legge come uniformità.

> Guardate la distribuzione prima di citare. Una metrica con un solo valore non dimostra uniformità:
> non partecipa.

## 6. Non consegnare e consegnare sbagliato

Sommate in un unico tasso di fallimento, due modelli risultano pari: 0,595 e 0,584.

| | resa grezza | quando risponde | quota muta |
|---|---:|---:|---:|
| `qwen3.5-9b-think` | 0,595 | **0,777** | 23,4% |
| `ministral-8b` | 0,584 | 0,584 | 0,0% |

Il primo è il migliore del gruppo quando parla e tace un quarto delle volte. Rimedi opposti: finestra
e meno cerimonia contro formato migliore.

> *Non ha risposto*, *ha rifiutato*, *è andato in timeout* e *ha risposto male* sono quattro guasti
> con quattro rimedi. Riportate la quota di consegna accanto alla resa.

## 7. «È il peggiore» non è «peggiora»

Il livello più ricco non è mai il migliore in diciannove celle ed è il peggiore in cinque. Sembrava
sufficiente per scrivere che *peggiora*.

Testato testa a testa contro i livelli economici, su 42 confronti: **zero peggioramenti
significativi**. In un gruppo di sette qualcuno è ultimo per costruzione, anche se sono tutti
equivalenti.

L'affermazione è caduta; la raccomandazione no, ma l'argomento è diventato il costo — quattro volte
il prompt, mai un beneficio.

> Un ordinamento non è un effetto. Se il test non conclude, avete un ordinamento e un argomento di
> costo, che spesso basta.

## 8. Le misure abbandonate

Due colonne del punteggio — quale ramo era prescritto e quale è stato preso — sono vuote su tutte e
**4.871** le esecuzioni. Mai valorizzate, in nessuno dei tre studi.

Non è un guasto: è una strada immaginata e non percorsa. Ma è rimasta nello schema, indistinguibile da
una misura che non ha trovato niente da segnalare.

> Elencate le misure tentate e lasciate. Chi le trova da solo si chiede cos'altro non gli avete detto.

---

# La forma dei confronti

## 9. L'asse che non c'è

Sette forme di consegna: cinque sono una scala crescente, due sono riscritture in linguaggio
naturale. Ho calcolato una correlazione fra quantità di contesto e resa **su tutte e sette** e
ottenuto −0,893.

Il documento di disegno lo vietava, scritto mesi prima. Ristretta alle cinque che un asse ce l'hanno,
la correlazione è −0,700 e non è significativa.

Stesso errore in forma più subdola: ho correlato la resa dei sette modelli con la loro sensibilità al
formato, ottenendo *più il modello è capace, meno la forma conta*. Fondato sull'assunto che i sette
modelli stiano su una scala di potenza. Non ci stanno: sono architetture e addestramenti diversi.
Rifatta senza quell'assunto, la tendenza sparisce — il modello locale più forte è terzo su sette per
insensibilità al formato, dietro uno dei più deboli.

> Prima di correlare, verificate che la variabile indipendente sia una variabile. Categorie
> qualitativamente diverse, messe in fila e numerate, danno correlazioni aritmeticamente valide e
> prive di referente.

## 10. La compressione al bordo

Il modello commerciale mostra nove punti di escursione fra la forma migliore e la peggiore, contro i
cinquantatré del locale che oscilla di più. Conclusione ovvia: è indifferente al formato. Obiezione
ovvia: sta al 94% e non ha spazio per differire.

Nessun confronto di escursioni grezze separa le due letture. Serve simulare il mondo in cui il formato
non ha effetto, tenendo la difficoltà di ogni caso com'è, e misurare quanta escursione il caso produce
comunque a quel livello.

```
commerciale : osservata 0,0882   attesa dal caso 0,0882
sei locali  : osservata > attesa
```

L'indifferenza è reale. Ma prima della simulazione non c'era diritto di dirlo.

> Le dispersioni non sono confrontabili fra livelli di prestazione diversi: vicino a un bordo la
> varianza si comprime da sola. Simulate il nullo a quel livello.

## 11. La media di un soggetto che non esiste

Togliendo un obbligo di protocollo i modelli guadagnano **in media tre punti e mezzo**. Aperta: tre
salgono, tre scendono senza che il test lo confermi. Il modello medio che guadagna tre punti e mezzo
non esiste.

Stesso schema sul risultato che mi interessava di più. Sull'aggregato, il costrutto che porta stato
fra i passi è il modo di fallimento dominante: 540 esecuzioni su 1.236, il 44%. Modello per modello:

```
0,958   0,768   0,643   |   0,110   0,101   0,010
```

Tre su sei. Sugli altri tre il guasto è altrove.

> Guardate la distribuzione dei soggetti prima di pubblicare una media. Se cambia segno, la media è un
> artefatto della composizione del campione, e lo spaccato ha ragione.

---

# L'analista

## 12. La regola circolare

Avevo una scorciatoia: misuri una certa penalità di un modello e sai quale famiglia di formati gli
conviene. Nel terzo studio azzecca **sette su sette**.

Penalità e famiglia vincente sono calcolate sugli stessi sedici casi: se per un modello la prosa batte
il JSON, è già più probabile che il massimo cada fra le forme in prosa. La corrispondenza è quasi
aritmetica.

Fuori campione: **4/6**. Il segno si inverte su tre modelli su sei.

> Se predittore ed esito sono calcolati sulle stesse osservazioni, non avete una regola: avete
> un'identità con del rumore. La prova è fuori campione, ed è economica.

## 13. Il contrasto specificato dopo aver visto i dati

Il risultato più solido della campagna è emerso da **tre contrasti successivi**, ciascuno specificato
dopo aver visto l'esito del precedente. Il terzo conclude; i primi due no.

Non è un imbroglio — la soglia era fissata prima e non è stata toccata — ma non sono tre conferme
indipendenti.

> Tracciate l'ordine in cui i confronti vi sono venuti in mente. Un contrasto specificato dopo è
> legittimo se etichettato come tale.

## 14. La famiglia di test

Cambiando l'ampiezza della famiglia — cioè quanti confronti contano come la stessa domanda — uno dei
miei risultati passa da significativo a non significativo. Non c'è una scelta oggettiva. C'è una
scelta onesta: fissarla prima di guardare i p-value.

> L'ampiezza della famiglia è un grado di libertà dell'analista, e come tutti tende a essere usato
> nella direzione che piace.

## 15. La trappola superata per la ragione sbagliata

Nel banco c'è un caso costruito perché fosse insidioso: la squadra competente è satura e la risposta
corretta è comunque non deviare. Un modello lo supera tre volte su tre.

Lo supera perché **non devia mai**. Dei nove casi che richiedono di spostare o rimandare non ne
risolve nemmeno uno. La trappola presupponeva un modello capace di vedere la scorciatoia; questo non
l'ha mai vista.

Lo stesso metodo — guardare l'insieme, non il conteggio — dà il risultato più netto della campagna. Su
venti richieste, con cinque livelli crescenti di documentazione e un convertitore deterministico, un
modello ne risolve otto. Con tutti e sei. E sono **gli stessi identici otto**, caso per caso. Un
conteggio avrebbe detto "nessuna differenza"; solo l'insieme dice perché.

> Conta quali casi passano, non quanti. Un tasso aggregato non distingue fra un sistema che ha capito
> la regola e uno che per caso non sbaglia.

---

# I controlli

**Sul dato**

- analizzare dalla fonte, non da un derivato; e un controllo che verifichi l'accordo
- la distribuzione di ogni metrica prima di citarla
- i casi che nessuna condizione supera, e quelli che tutte superano, riportati a parte
- le misure tentate e abbandonate, elencate

**Sul confronto**

- ogni tasso col suo denominatore; mai accostare tassi con denominatori diversi
- la quota di consegna accanto alla resa
- lo spaccato per soggetto accanto a ogni media
- niente correlazioni su categorie che non stanno su un asse
- niente confronti di dispersione fra livelli di prestazione diversi senza un nullo simulato

**Sull'analista**

- l'ordine in cui i confronti sono venuti in mente
- l'ampiezza della famiglia di test, fissata prima
- ogni regola predittiva, verificata fuori campione
- l'esito per caso, non solo la percentuale

E una domanda, ogni volta che un risultato piace:

> **Se questo numero fosse un artefatto del modo in cui l'ho contato, come me ne accorgerei?**

Se non c'è una risposta, non è ancora un risultato.

---

Protocollo, risultati grezzi e notebook di analisi sono pubblici: ogni numero citato qui si ricalcola
da lì, comprese le correzioni.

Repository: https://github.com/jtplugin/sol

---
*Gianni Tommasi*
