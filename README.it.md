# WF Vendor Overlay

[🇬🇧 English](README.md) · 🇮🇹 Italiano

Un compagno per Warframe su Windows. Il cuore: quando apri un vendor, mostra accanto a ogni oggetto il **prezzo in
platino** (a destra del nome) e il **volume di scambio delle ultime 24 ore** (sotto il nome; rosso = poco scambiato,
verde = molto scambiato), da warframe.market, leggendo lo schermo con l'OCR. Intorno:

- **Attività** (in gioco, F6): cosa comprare con lo standing e come guadagnarlo, le offerte settimanali dei vendor che
  segui, le sfide Nightwave della settimana e il Calendario 1999, spuntate man mano che le completi.
- **Finestra del listino** (F7): tutti gli oggetti scambiabili che costano standing, i consigli, il tuo inventario con
  consigli di vendita e ordini di vendita, il flip dei Riven, le tue build di gioco, i limiti settimanali dei vendor, lo
  standing, lo stato del mondo.

Il programma non legge mai memoria, traffico di rete o file del gioco. Ciò che sa del tuo account (standing, inventario,
loadout, acquisti, sfide) viene dal `lastData.dat` di **AlecaFrame**, letto quando AlecaFrame lo aggiorna; senza
AlecaFrame l'overlay dei prezzi e le funzioni di mercato funzionano comunque.

**Indice:** [Per iniziare](#per-iniziare) · [Overlay dei prezzi](#overlay-dei-prezzi-in-gioco) ·
[Attività](#attività-in-gioco-f6) · [Finestra del listino](#finestra-del-listino-f7) · [Fonti dei dati](#fonti-dei-dati) ·
[Aggiornamenti](#aggiornamenti-versione-attuale-031) · [File e impostazioni](#file-e-impostazioni) ·
[Prestazioni](#prestazioni) · [Per sviluppatori](#per-sviluppatori) · [Note e limiti](#note-e-limiti)

## Per iniziare
1. Scarica `WFVendorOverlay-windows.zip` dall'[ultima release](https://github.com/ZioLadro/wf-vendor-overlay/releases/latest),
   estrailo dove vuoi e avvia `WFVendorOverlay.exe` (l'exe non è firmato, quindi Windows SmartScreen può avvisare).
2. Avvia Warframe in finestra senza bordi (**Borderless**). Se Warframe gira come amministratore, avvia anche l'overlay
   come amministratore.
3. Facoltativo: tieni aperto **AlecaFrame**; il suo file viene trovato da solo (`%LOCALAPPDATA%\AlecaFrame`).
4. Lingua: inglese di default; Impostazioni → Generale → Lingua (English / Italiano), poi riavvia.

| Tasto | Azione |
|---|---|
| **F6** | mostra/nasconde **Attività** |
| **F7** | apre/chiude la finestra del **listino** |
| **F8** | scansiona subito (e riprende se in pausa) |
| **F9** | pausa |
| **F10** | esci |

Le stesse azioni sono nel menu dell'icona vicino all'orologio (clic sull'icona = listino). I tasti si cambiano nelle
Impostazioni.

## Overlay dei prezzi (in gioco)
Etichetta prezzo: `12p` = platino · `–` = nessun venditore online · `n/d` = errore / dati non disponibili.
Per **mod e arcane** mostra due prezzi: `12p · max 45p` = prezzo a rank 0 (quello che vende il vendor) e prezzo a
**rank massimo**. Il volume è il totale degli scambi di tutti i rank.

- **Parte già attivo**: apri un vendor e, quando lo schermo si ferma, l'overlay scansiona da solo.
- **Dati salvati** in `prices.json`: compaiono subito gli ultimi valori noti, poi si aggiornano in background.
  All'apertura di un vendor si aggiornano i dati più vecchi di 30 s; i prezzi dei vendor mostrati ogni 180 s.
- **Scroll** con la rotellina: le etichette spariscono subito e tornano ~0,5 s dopo la fine dello scroll. Altri
  cambiamenti della lista (barra trascinata, tastiera) vengono rilevati confrontando i pixel sotto i nomi.
- **Uscita dal vendor**: appena chiudi il vendor o cambi pagina le etichette spariscono.
- L'OCR legge **solo la finestra di Warframe**, e solo quando è la finestra attiva (impostazione *Leggi solo la finestra
  di Warframe*; disattivala se il gioco non viene rilevato, es. cloud gaming). Nelle altre finestre le etichette si
  nascondono.
- **Stelle**: *★ Migliore qui ★* segna il miglior acquisto tra **tutti gli oggetti del vendor che stai guardando**
  (anche quelli fuori vista: la riga di stato lo nomina, *Miglior acquisto da …*); *★ Consigliato ★* segna gli oggetti
  tra i migliori acquisti **di tutti i vendor** (la classifica dei Consigli). Impostazioni *Stelle sugli oggetti
  consigliati* / *Oggetti consigliati segnati*.

**Riconoscere la schermata del vendor.** Dopo aver letto i nomi, il programma controlla a quale catalogo di vendor
appartengono (da `vendors.json` e dalla lista di Baro). Le etichette compaiono solo se almeno 3 oggetti riconosciuti
(impostazione *Oggetti per riconoscere un vendor*) e il 60 % di tutto ciò che è stato riconosciuto appartengono **allo
stesso vendor**; i nomi fuori dal suo catalogo vengono scartati. Così non appaiono etichette su inventario, chat o codex
che mostrano solo alcuni nomi. Il programma **legge anche il nome del vendor** nel 20 % in alto della finestra di gioco
(impostazione *Zona del nome vendor*; es. *Cephalon Simaris*, *Red Veil*): se c'è e almeno un oggetto è di quel vendor,
le etichette compaiono anche con pochi oggetti. *Richiedi il nome del vendor* lo rende obbligatorio (più rigido, ma i
vendor la cui intestazione non è il loro nome non corrisponderebbero mai). F8 scrive tutto ciò che ha letto in
`last_scan.txt` nella cartella dei dati, per capire perché un vendor è stato o non è stato riconosciuto. Si disattiva
con *Riconosci la schermata del vendor*.

## Attività (in gioco, F6)
Una piccola finestra sempre in primo piano sopra il gioco, in stile quest tracker, spostabile (trascina il titolo) e
ridimensionabile (angolo). ⚙ regola opacità, dimensione del testo e cosa elencare. Mostra, per sindacato:

- gli **acquisti suggeriti dai Consigli**, lo standing che manca, i giorni che servono al tuo limite giornaliero
  (16.000 + 500 × grado di maestria) e le **attività che fanno guadagnare quello standing**. Un oggetto sparisce solo
  quando il file di gioco mostra che l'hai comprato;
- le **offerte settimanali dei vendor che segui** (acquistate / limite, conto alla rovescia del reset; vedi la scheda
  Settimanali);
- **Nightwave**: le sfide della settimana (elite ★, con il loro standing) e quante giornaliere sono ancora aperte; quelle
  completate sono spuntate ✔ (esatto: abbinate tramite l'id della sfida nel file di gioco);
- **Calendario 1999**: le sfide della stagione corrente, quella in corso e quante sono fatte (fatte = i giorni fino
  all'ultimo giorno completato nel file di gioco).

**Clic destro** su un oggetto per nasconderlo o aprirlo su warframe.market, sul titolo di un sindacato o su un'attività
per smettere di seguirla (*Segui di nuovo tutte le attività* in ⚙). Con *Attività: cliccabile solo col cursore* (attiva
di default) la finestra lascia passare i clic quando Warframe nasconde il cursore (in missione), così non dà mai
fastidio. Quando viene riconosciuta la schermata di un vendor, Attività si spegne (subentrano le etichette dei prezzi)
finché non premi F6. Impostazioni: *Tasto attività*, *Attività: Nightwave e Calendario 1999*, *Nascondi Operational
Supply* (il sindacato degli eventi è escluso finché non c'è un evento).

## Finestra del listino (F7)
**Si apre da sola all'avvio** (impostazione *Apri il listino all'avvio*). È una finestra normale: viene davanti quando la
apri e non resta sopra il gioco (impostazione *Finestra sempre in primo piano* per tenercela). Quando è sopra il gioco la
sua area viene oscurata prima dell'OCR, quindi non legge mai i propri nomi.

In cima a ogni scheda:
- **Barra del giocatore**: nome (dal `lastUsername.txt` di AlecaFrame, oppure clicca per scriverlo), grado di maestria,
  scambi rimasti (⚠ quando l'ultima sync è precedente al reset giornaliero), portafoglio (Endo, platino, ducati, Aya;
  compatti, valore esatto nel tooltip) e un badge per sindacato con rank e standing (mouse sopra: standing rimasto oggi).
  I logo dei sindacati vengono scaricati una volta dalla wiki; senza, i badge sono disegnati con i colori del sindacato.
- **Barra del mondo**: fessure Omnia Steel Path, cicli di Terra / Cetus / Orb Vallis, Baro Ki'Teer, Prime Resurgence e
  l'**Arbitrato** attuale con il suo tier di [arbi.guide](https://arbi.guide), tutti con conto alla rovescia.

### Prezzi e consigli
La prima scheda: listino sopra, consigli sotto (trascina il divisore; viene ricordato).

**Listino.** Tutti gli **oggetti scambiabili che costano standing** (da `vendors.json`: vendor e sindacati) più tutto ciò
che vende **Baro Ki'Teer**, elencati fin dall'inizio anche senza dati (prezzo `–`, aggiornato `mai`). Colonne: nome,
vendor, **costo in standing**, tipo (Mod / Arcane / Altro), prezzo, prezzo a rank massimo, volume 24 h (colorato come
nell'overlay), ultimo aggiornamento. Clic sulle intestazioni per ordinare; ricerca e filtri per vendor e tipo.

- Il costo in standing è quello base dei dati di gioco (senza sconti di rank); `min – max` se lo vendono più vendor, il
  tooltip mostra vendor, costo e rank richiesto.
- **Passando il mouse** sul nome: quanti ne puoi comprare con il tuo standing, per sindacato, e se il tuo rank basta.
- **Nascondi volume zero** nasconde gli oggetti senza scambi nelle 24 h (quelli senza dati restano).
- **Clic destro** sul nome (qui e nei Consigli): aprilo su warframe.market o sulla wiki, o copia il nome.
- **Aggiorna elenco mostrato** aggiorna tutte le righe visibili (saltando i dati più recenti di `refresh_skip_age`);
  **Aggiorna selezionati** aggiorna le righe selezionate; **Stop** interrompe. Il limite è 3 richieste/s (2 per
  oggetto): circa 2 minuti ogni 100 oggetti, ~20 per tutto il catalogo; oltre `refresh_confirm_over` oggetti chiede prima.
- **Aggiorna elenco Baro**: Baro non è nei dati del gioco; la sua lista viene letta dalla wiki (e dal suo inventario
  attuale) e si ricarica da sola ogni `baro_refresh_days` giorni.

**Consigli.** Cosa conviene comprare con lo standing, per ogni coppia (oggetto, vendor) con un costo in standing:

```
plat per 1000 standing = prezzo / costo in standing × 1000
copie al giorno        = min(limite giornaliero / costo in standing, max(1, volume × 0,25))
~plat al giorno (punteggio) = prezzo × copie al giorno   (limite giornaliero = 16.000 + 500 × grado di maestria)
```
Quante copie compra un giorno di standing, ma non più di quante ne assorbe il mercato (circa un quarto del volume
24 h). Un prezzo sopra la media a 30 giorni viene avvicinato a essa, e un oggetto che richiede un rank del sindacato più
alto del tuo conta la metà (⚠). Gli oggetti sotto il **volume minimo** o il **prezzo minimo** (modificabili nella
scheda) sono esclusi; i prezzi sono a rank 0. *Migliore per vendor* mostra una riga per vendor. Gli oggetti ancora senza
dati di mercato non si possono valutare: **Scarica i dati mancanti** li scarica (scegli prima un vendor per fare prima).

### Inventario
I tuoi oggetti con i prezzi di mercato, consigli di vendita e ordini di vendita in un clic (ispirato alla scheda
Inventario di AlecaFrame).

- **Origine**: il `lastData.dat` di AlecaFrame, trovato e riletto da solo (decifrato in locale). Puoi anche **Importa
  file…** (sostituisce l'inventario), **Incolla lista…**, oppure **Aggiungi oggetto…** / **Modifica** a mano. Oltre a
  `lastData.dat` sono accettati: un JSON di inventario in stile Warframe (`MiscItems`, `RawUpgrades`… con percorsi
  `ItemType`), qualunque JSON che abbini nomi e quantità (`{"Serration": 2}`), e righe CSV/TXT come `Serration, 2, 10`,
  `3x Mirage Prime Set` o `Ash Prime Blueprint x2`. I nomi vengono abbinati al catalogo del mercato (piccoli errori
  tollerati); quelli non abbinati vengono elencati.
- **Categorie** (Set, Parti Warframe, Parti armi, Mod, Arcane, Reliquie, Altro) e **filtri** come quelli di AlecaFrame:
  platino minimo, più di una copia, prime / normale, vaulted, messi in vendita da qui, *Escludi mod/arcane a rank
  massimo*, *Escludi installate* (mod e Arcane in uno dei tuoi loadout: mai suggerite per la vendita), *Vol. min*
- **Valore** = copie × prezzo a rank 0 + copie a rank massimo × prezzo a rank massimo. **Aggiorna prezzi** aggiorna gli
  oggetti mostrati. Il programma tiene anche il prezzo medio a 7/30/90 giorni (colonna *vs 30 g*); un picco sopra la
  media a 30 giorni viene avvicinato a essa secondo *Consigli: peso del trend* (default 50 %).
- **Consiglio: ducat** elenca le parti prime per ducati ottenuti per platino a cui rinunci
  (`ducati / max(prezzo × liquidità, 0,5)`, con `liquidità = min(1, volume / volume liquido)`): *Ducati* dal rapporto
  minimo in su (default 10), altrimenti *Vendi*. **Consiglio: vendita** ordina il resto per
  `prezzo × copie che puoi aspettarti di vendere (≈ ¼ del volume giornaliero)`. Entrambi possono selezionare le righe,
  pronte per *Vendi*.
- **Sali di rank…**: quali mod conviene portare a rank massimo per venderle: platino guadagnato per copia (prezzo a rank
  massimo − prezzo attuale) ogni 1000 Endo, con Endo e Crediti necessari (`base × (2^max − 2^rank)`, secondo la
  [wiki](https://wiki.warframe.com/w/Fusion)). Scrivi l'Endo che hai e vengono selezionate le righe migliori che ci stanno.
- **Vendi…** piazza un **ordine di vendita** su warframe.market per ogni oggetto selezionato. Prima accedi (email e
  password, inviate solo a warframe.market; **viene salvato solo il token di sessione**, *Esci* lo cancella). Una
  finestra mostra quantità, rank, prezzo (prezzo di mercato + `sell_price_offset`) e **la richiesta esatta**; non viene
  inviato nulla finché non premi *Piazza ordine*. Attenzione: usa l'API REST v1 come documentata dalle librerie della
  community; controlla il primo ordine sul sito. Gli account che accedono con Discord/Google potrebbero non funzionare.
- **Immagini degli oggetti** passando il mouse sul nome (immagini di warframe.market, scaricate una volta; si disattiva
  nelle Impostazioni).

**Quantframe.** Gli oggetti si possono passare a [Quantframe](https://github.com/Kenya-DK/quantframe-react) tramite il
suo server HTTP locale (in Quantframe: Settings > Advanced > HTTP Server; qui: *Indirizzo di Quantframe*, default
`127.0.0.1:4808`, solo indirizzi di questo computer):
- **Inventario > Invia a Quantframe…**: le righe selezionate (tutte quelle mostrate se nessuna) nel suo **stock**, le
  mod con rank divise per rank;
- **Build > Mancanti → Quantframe**: le mod che ti mancano per una build nella sua **wish list**;
- **Inventario > Riven → Quantframe…**: i tuoi riven **rivelati** (arma, nome, rank, re-roll, polarità, statistiche
  ricalcolate da `rivens.json`; i valori possono differire di un decimale dal gioco) nel suo stock di riven.

Prima compare una finestra di controllo; gli oggetti già inviati partono non spuntati perché le quantità si sommano. Non
viene inviato alcun prezzo d'acquisto. Il Live Scraper di Quantframe potrebbe poi mettere in vendita gli oggetti dello
stock o piazzare ordini d'acquisto, secondo le sue impostazioni.

### Riven flip
**Scansiona il mercato** legge gli annunci di riven delle armi successive su warframe.market (prima quelle scansionate
meno di recente; *Armi per scansione* e *Solo queste armi* nelle Impostazioni) ed elenca i riven messi in vendita **sotto
il valore di quelli comparabili**, dal profitto migliore:

- **Prezzo**: il prezzo di acquisto diretto contro un *prezzo equo* = mediana degli annunci comparabili della stessa arma
  (punteggio statistiche entro ±15, almeno 3) × *Rivendita attesa* (default 85 %). warframe.market restituisce al massimo
  i 100 annunci più economici per arma, il che tiene il prezzo equo sul prudente per le armi popolari.
- **Vendite**: una **stima** (warframe.market non pubblica le vendite di riven): gli annunci che spariscono tra una
  scansione e l'altra negli ultimi 7 giorni. Servono scansioni ripetute; "–" finché un'arma non è osservata da un giorno.
- **Statistiche**: un punteggio 0–100 da quanto è utile ogni statistica e da quanto bene è uscita. Pesi personalizzati in
  `riven_weights.json` nella cartella dei dati, es. `{"WeaponFireRateMod": 0.9}` (da 0 a 1; chiavi di `rivens.json`).

Le richieste di riven hanno un loro limitatore (*Richieste riven al minuto*, default 12, mai sopra 20, come chiede
warframe.market); a un "troppe richieste" aspetta e si ferma dopo tre di fila. La scheda legge soltanto: non pubblica
nulla. *Apri l'asta* e *Copia whisper* aiutano a contattare il venditore. Profitto e prezzo equo sono stime.

### Build
I tuoi loadout di gioco, mostrati come nella schermata dei loadout, da `lastData.dat` (*Ricarica dal file* dopo che
AlecaFrame l'ha aggiornato).

- **Loadout di gioco** (vista predefinita): i tuoi loadout con Warframe, armi, arma exalted, compagno, Archwing e
  Necramech; clicca una riga per la build di quell'oggetto. **Per oggetto**: le configurazioni di ogni oggetto,
  raggruppate per tipo, con miniature e filtro per nome/tipo. Scuola Focus e K-Drive non sono mostrati.
- **Carte** come nella schermata build del gioco: slot Aura, Exilus e Stance, otto slot mod (polarità dello slot,
  polarità e consumo della mod, rank), Arcane, **Frammenti Arconte** (colore, tauforgiato, effetto), abilità
  **Helminth**, numero di forma, **Reattore / Catalizzatore** Orokin (dal file, *dedotto* per gli oggetti vecchi i cui
  loadout ci stanno solo con uno). Le carte **si adattano alla finestra** e mostrano l'immagine della mod al passaggio
  del mouse.
- **Capacità** = rank (40 per armi Kuva/Tenet/Coda e Necramech) × 2 con Reattore/Catalizzatore + aura; le polarità
  innate sono messe dove fanno risparmiare più consumo (il file non dice dove sono). Un **riepilogo statistiche**
  approssimato conta solo le mod (non Arcane, frammenti, Helminth, bonus dei set o effetti condizionali).
- I **Riven** mostrano nome, statistiche, polarità e consumo e contano nel riepilogo; i **Riven spliced** sono mostrati
  congelati (❄) con la statistica spliced come "?".
- **Pianificatore build** (terza vista): scegli un Warframe o un'arma, clicca una carta per scegliere mod, rank e
  polarità dello slot (Forma); capacità, consumo e statistiche si aggiornano. *Salva* tiene i piani in
  `build_plans.json`; *Copia da un mio loadout…* parte da uno dei tuoi.

Le immagini di questa scheda vengono **solo dalla wiki di Warframe** (API MediaWiki, una richiesta alla volta); quelle
mancanti vengono scaricate in background all'avvio e tenute nella cartella dei dati. Nomi e statistiche vengono dal
`loadout_data.json` incluso (dati pubblici del gioco e WFCD/warframe-items, ricostruito con `build_loadouts.py`). Una
**cartella delle icone** facoltativa (Impostazioni > Inventario; gli `assets` estratti di AlecaFrame vengono trovati da
soli) aggiunge le immagini dei Frammenti Arconte e del portafoglio; quei file vengono solo letti dove sono, mai copiati.

### Settimanali
Le offerte dei vendor con un limite di acquisto (Teshin, Ironwake, Nightcap, Archimedean, Acrithis…), quanto hai
comprato in questo periodo e quando si azzera. Il file di gioco registra ogni acquisto limitato ma non quale offerta
fosse, quindi il programma lo ricava da ciò che il `deltas.dat` di AlecaFrame ha registrato come guadagnato e
dall'inventario rispetto alla sync precedente; quando è ambiguo ti chiede di sceglierla (★ = candidate probabili).
Spunta *Segui* per seguire un'offerta in Attività.

### Profilo
Standing e rank per sindacato e grado di maestria, **letti da `lastData.dat`** (riletto quando cambia, impostazione
*Controllo file AlecaFrame*, ogni 10 s). AlecaFrame riscrive il file quando entri o esci da una missione, quindi i numeri
si aggiornano in quei momenti. Il file contiene lo standing *totale*; il programma sottrae l'inizio del rank attuale, così
i numeri coincidono con il gioco. *Rimasto oggi* è lo standing che puoi ancora guadagnare oggi. Puoi scrivere o correggere
qualunque valore a mano (resta fino alla lettura successiva). Standing negativo = sei nella fazione opposta.

### Mondo, Console
**Mondo**: fessure, invasioni, sortie, cicli e l'inventario attuale di Baro con i prezzi in platino (si aggiorna mentre
la scheda è aperta, impostazione *Aggiornamento mondo*). **Console**: cosa gira in background e ogni errore.

### Impostazioni
Una sotto-scheda per categoria. **Salva** applica e memorizza in `config.json`; **Salva e riavvia** riavvia anche il
programma; le impostazioni segnate ⟳ (lingua, tasti, OCR…) richiedono un riavvio. **Ripristina predefiniti** carica i
valori predefiniti (premi Salva per applicarli). **Tema e carattere**: temi colore ispirati a fazioni, alleati e nemici di
Warframe (più *Classico*), ognuno con il suo motivo di sfondo, un altro motivo, una tua immagine o niente; famiglia e
dimensione del carattere. Anteprima immediata, mantenuta solo quando premi Salva. Gli overlay in gioco tengono i loro
colori.

## Fonti dei dati
| Cosa | Da dove |
|---|---|
| Prezzi, volumi, catalogo, ordini di vendita, annunci di riven | [warframe.market](https://warframe.market) (API v1 e v2, max 3 richieste/s) |
| Il tuo standing, inventario, loadout, acquisti, sfide | `lastData.dat` / `deltas.dat` di AlecaFrame sul tuo PC |
| Vendor, costi in standing, nomi, offerte settimanali, nomi delle sfide | dati pubblici del gioco, inclusi (`build_*.py`) |
| Immagini (build, logo dei sindacati), lista di Baro | [wiki.warframe.com](https://wiki.warframe.com) |
| Stato del mondo (fessure, cicli, Baro…) | [api.warframestat.us](https://api.warframestat.us) |
| Nightwave e Calendario 1999 | world state pubblico di DE (`content.warframe.com`), ogni 10 min |
| Tier / calendario degli Arbitrati | [arbi.guide](https://arbi.guide) / browse.wf |
| Aggiornamenti | release GitHub di questo repository |

Ogni richiesta identifica il programma con il suo `User-Agent` (nome, versione, repository) e i risultati sono in cache.

## Aggiornamenti (versione attuale 0.3.1)
All'avvio il programma cerca (in background, impostazione *Cerca aggiornamenti all'avvio*) una **release GitHub** più
recente. La finestra di aggiornamento elenca **cosa è cambiato rispetto alla tua versione** (tutte le versioni
intermedie, dal changelog nella tua lingua) e offre *Installa ora* / *Più tardi* / *Salta questa versione*. Puoi anche
controllare da **Impostazioni → Aggiornamenti**.

L'installazione scarica `WFVendorOverlay-windows.zip`, ne verifica lo SHA-256 con il file `.sha256` della release,
sostituisce i file del programma dopo la sua chiusura e lo riavvia. I tuoi dati (`%LOCALAPPDATA%\WFVendorOverlay`) non
vengono mai toccati. Ogni passaggio va in `update.log` nella cartella dei dati; come ripiego manuale chiudi il programma ed
estrai la release sopra la sua cartella. Solo la versione Windows pacchettizzata si aggiorna da sola; dai sorgenti usa
`git pull`. Il checksum dimostra solo che il download non è corrotto: si fida delle release di questo repository.

Cosa è cambiato in ogni versione: [CHANGELOG.it.md](CHANGELOG.it.md) (dalla 0.2.1).

## File e impostazioni
Tutto sta in `%LOCALAPPDATA%\WFVendorOverlay`:

| File | Contenuto |
|---|---|
| `config.json` | impostazioni |
| `prices.json`, `items_cache.json`, `baro.json` | prezzi e volumi raccolti, catalogo del mercato, lista di Baro |
| `inventory.json`, `standing.json`, `loadouts.json` | inventario e ordini piazzati dall'app, standing, cache delle build |
| `goals.json`, `weekly_state.json`, `worldstate_de.json` | piano di Attività, acquisti settimanali e offerte seguite, copia del world state di DE |
| `build_plans.json`, `riven_weights.json` | piani del pianificatore, pesi riven personalizzati (facoltativo) |
| `market_session.json` | token di sessione di warframe.market |
| `vendors.json`, `gamenames.json` | facoltativi: sostituiscono quelli inclusi |
| `img\`, `icons\`, `backdrop\` | immagini scaricate, logo dei sindacati, sfondi generati |
| `overlay.log`, `riven.log`, `update.log`, `last_scan.txt` | errori, richieste del Riven flip, passaggi dell'aggiornamento, ultima lettura OCR (F8) |

Chiavi principali di `config.json` (tutte sono nelle Impostazioni, con spiegazione):

| chiave | significato (default) |
|---|---|
| `language` | `en` o `it` |
| `key_goals` / `key_menu` / `key_scan` / `key_clear` / `key_quit` | tasti (`<f6>` `<f7>` `<f8>` `<f9>` `<f10>`) |
| `start_active` / `auto_detect` | parte già attivo / riconosce i vendor da solo (true) |
| `refresh_interval` | secondi tra gli aggiornamenti automatici (180) |
| `open_max_age` | all'apertura di un vendor, aggiorna i dati più vecchi di N s (30) |
| `show_cached_max_age` | mostra subito i dati salvati più recenti di N s (3600) |
| `refresh_skip_age` / `refresh_confirm_over` / `baro_refresh_days` | salto in "Aggiorna elenco mostrato" (300 s) / conferma oltre N oggetti (150) / aggiornamento Baro (7 giorni) |
| `volume_low` / `volume_high` | volume rosso fino a `low`, verde da `high` (10 / 50) |
| `match_threshold` | soglia di somiglianza dei nomi (90) |
| `watch_interval`, `watch_interval_moving`, `ocr_threads`, `ocr_priority`, `publish_throttle` | rilevamento e prestazioni |
| `rec_min_volume`, `rec_min_price`, `rec_top` | filtri dei consigli |
| `sell_price_offset` | aggiunto al prezzo di mercato quando vendi (0) |

## Prestazioni
La scansione (OCR) è la parte pesante. Per non disturbare il gioco:
- OCR e abbinamento dei nomi girano in un **processo separato** (`ocr_worker.py`) a priorità "sotto il normale" e con
  pochi thread (circa 1/4 dei core, da 1 a 3); overlay, tasti e rotellina restano sempre reattivi.
- Se lo schermo non è cambiato dall'ultima scansione, il risultato viene riusato senza rifare l'OCR.
- Mentre giochi, lo schermo viene controllato meno spesso (`watch_interval_moving`).
- Ancora rallentamenti? `ocr_priority` = `idle`, `ocr_threads` = 1, un `watch_interval` più alto (1.0), oppure
  `auto_detect` disattivato e scansione solo con F8.

## Per sviluppatori
**Dai sorgenti** (Windows, Python 3.12 a 64 bit):
```
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

**Costruire l'eseguibile** (i modelli OCR sono inclusi):
```
powershell -ExecutionPolicy Bypass -File build.ps1            # cartella dist\WFVendorOverlay (consigliato)
powershell -ExecutionPolicy Bypass -File build.ps1 -Console   # con console (per vedere gli errori)
powershell -ExecutionPolicy Bypass -File build.ps1 -OneFile   # singolo .exe (avvio più lento)
```

**Pubblicare una versione**: cambia `version.py`, aggiungi la sezione della versione a `CHANGELOG.md` e
`CHANGELOG.it.md`, fai il commit, poi `git tag vX.Y.Z && git push origin vX.Y.Z`. Il workflow in
`.github/workflows/release.yml` costruisce il pacchetto Windows e crea la release (zip, checksum, note dal changelog).

**File sorgente**

| Area | File |
|---|---|
| Avvio, scansione, OCR | `main.py`, `scanner.py`, `ocr_worker.py`, `ocr.py`, `winrect.py`, `matcher.py`, `wheel.py`, `overlay.py` |
| Mercato e prezzi | `market.py`, `refresher.py`, `market_auth.py`, `recommend.py`, `recommend_tab.py`, `advice.py`, `advice_dialog.py` |
| Vendor e standing | `vendors.py`, `standing.py`, `profile_tab.py`, `weekly.py`, `weekly_tab.py` |
| Attività | `goals.py`, `goals_overlay.py`, `quests.py` |
| Inventario, riven, Quantframe | `inventory.py`, `inventory_tab.py`, `aleca.py`, `rivens.py`, `riven_dialog.py`, `riven_flip_tab.py`, `rivenmarket.py`, `quantframe.py`, `quantframe_dialog.py` |
| Build | `loadouts.py`, `builds_tab.py`, `buildcards.py`, `buildcalc.py`, `planner_tab.py`, `icons.py`, `previews.py` |
| Mondo | `world.py`, `world_tab.py`, `world_strip.py`, `arbi.py` |
| Finestra e interfaccia | `menu.py`, `player_bar.py`, `logos.py`, `settings_tab.py`, `console_tab.py`, `logbus.py`, `theme.py`, `uiutil.py`, `i18n.py`, `config.py` |
| Aggiornamenti | `version.py`, `updater.py`, `update_box.py` |
| Generatori di dati | `build_vendors.py`, `build_loadouts.py`, `build_rivens.py`, `build_weekly.py`, `build_nodes.py`, `build_challenges.py`, `build_icon.py`, `prepare_models.py`, `build.ps1` |

## Note e limiti
- I volumi usano l'endpoint statistiche v1 di warframe.market (deprecato ma attivo); se smette di funzionare viene
  mostrato solo il prezzo.
- Prezzo a rank massimo = mediana dei 3 ordini di vendita più bassi di utenti online con quel rank; `–` se nessuno vende
  a quel rank.
- L'elenco dei vendor viene dai dati pubblici del gioco: i vendor che mancano (es. Varzia) non sono inclusi. Si rigenera
  con `python build_vendors.py` (una copia nella cartella dei dati ha la precedenza).
- AlecaFrame aggiorna `lastData.dat` solo quando sincronizza (entrando o uscendo da una missione, al login): ciò che hai
  fatto nel frattempo compare alla sync successiva. AlecaFrame segnala 0 Aya, quindi scrivili in Impostazioni > Inventario
  (*Aya (scritti a mano)*).
- Il completamento di Nightwave e Calendario dipende da ciò che registra il file di gioco; il Calendario è segnato per
  giorno.
