# WF Vendor Overlay

[🇬🇧 English](README.md) · 🇮🇹 Italiano

Mostra accanto agli oggetti dei vendor di Warframe il **prezzo in platino** (a destra del nome) e il
**volume di scambio delle ultime 24 ore** (sotto il nome, al centro; rosso = poco scambiato,
verde = molto scambiato), con dati di warframe.market letti tramite OCR dello schermo.
Usa solo screenshot: non tocca memoria o file del gioco.

Etichetta prezzo: `12p` = platino · `–` = nessun venditore online · `n/d` = errore/dati non disponibili.
Per **mod e arcane** l'etichetta mostra due prezzi: `12p · max 45p` = prezzo a rank 0 (quello che compri
nel vendor) e prezzo a **rank massimo**. Il volume resta il totale degli scambi di tutti i rank.

## Come funziona
- **Parte già attivo**: apri un vendor e, quando lo schermo si ferma, l'overlay scansiona da solo.
- **Dati salvati** in `prices.json`: alla scansione compaiono subito gli ultimi valori noti, poi
  vengono aggiornati in background. All'apertura di un vendor si aggiornano i dati più vecchi di 30 s.
- **Ogni 180 secondi** prezzi e volumi dei vendor mostrati si aggiornano da soli.
- **Scroll** con la rotellina: le etichette spariscono subito e tornano ~0,5 s dopo la fine dello scroll.
  Se la lista cambia in altro modo (barra trascinata, tastiera, chiusura del vendor) il cambiamento
  viene rilevato confrontando i pixel sotto i nomi.
- **Uscita dal vendor**: appena chiudi il vendor o cambi pagina le etichette spariscono.
- **F7** apre/chiude il **listino prezzi** · **F8** scansiona subito (e riprende se in pausa) ·
  **F9** pausa · **F10** esci. Le stesse azioni sono nel menu dell'icona vicino all'orologio
  (clic sull'icona = listino).
- Warframe deve essere in finestra senza bordi (**Borderless**).

L'OCR legge **solo la finestra di Warframe**, e solo quando è la finestra attiva (Windows; impostazione *Leggi solo la finestra di Warframe*, disattivala se il gioco non viene rilevato, es. cloud gaming). Le etichette si nascondono quando passi a un'altra finestra.

Sullo schermo di gioco, i **primi 10 oggetti consigliati** (stessa classifica della scheda Consigli, dai prezzi salvati) ricevono una piccola etichetta gialla *★ Consigliato ★* sopra il nome (impostazioni *Stelle sugli oggetti consigliati* / *Oggetti consigliati segnati*).

Ogni scheda mostra una **barra del giocatore**: nome (clicca per impostarlo, i file del gioco non lo contengono), grado di maestria, scambi rimasti e un badge per fazione con rank e standing (mouse sopra: standing giornaliero rimasto). I badge sono disegnati con i colori delle fazioni; per i logo veri metti file `<TagFazione>.png` (es. `CetusSyndicate.png`) nella cartella `icons` della cartella dei dati. Le serie Nightwave non sono mostrate.

**Riconoscere la schermata del vendor.** Dopo aver letto i nomi, il programma controlla a quale catalogo di vendor appartengono (da `vendors.json` e dalla lista di Baro). Le etichette compaiono solo se almeno 3 oggetti riconosciuti (impostazione) e il 60 % di tutto ciò che è stato riconosciuto appartengono **allo stesso vendor**; i nomi che non sono nel catalogo di quel vendor vengono scartati. Così non appaiono etichette su inventario, chat o codex che mostrano solo alcuni nomi, e l'overlay dice quale vendor ha riconosciuto. Il programma **legge anche il nome del vendor** a schermo (solo nel 20 % in alto della finestra di gioco, impostazione *Zona del nome vendor*; con più nomi vince il testo più alto; una riga uguale al nome del vendor, es. *Cephalon Simaris*, *Red Veil*): se c'è e almeno un oggetto è di quel vendor, le etichette compaiono anche con pochi oggetti. *Richiedi il nome del vendor* lo rende obbligatorio (più rigido, ma i vendor la cui intestazione non è il loro nome non corrisponderebbero mai). F8 scrive tutto ciò che ha letto in `last_scan.txt` nella cartella dei dati, per capire perché un vendor è stato o non è stato riconosciuto. Si disattiva con *Riconosci la schermata del vendor*, oppure abbassa *Oggetti per riconoscere un vendor* per vendor con pochissimi oggetti scambiabili.

## Finestra del listino (F7)
La finestra **si apre da sola all'avvio del programma** (impostazione *Apri il listino all'avvio*). Sei schede. L'overlay continua a funzionare con la finestra aperta: l'area della finestra viene oscurata prima dell'OCR, quindi non legge mai i propri nomi.

### Listino prezzi
Tutti gli **oggetti scambiabili che costano standing** (da `vendors.json`: vendor e sindacati), più tutto
ciò che vende **Baro Ki'Teer**: ci sono già tutti fin dall'inizio, anche senza dati (prezzo `–`,
aggiornato `mai`). Gli oggetti che non costano standing (e non sono di Baro) non sono elencati. Colonne: nome, vendor che lo vendono, **costo in standing**, tipo (Mod / Arcane / Altro),
prezzo, prezzo a rank massimo (mod e arcane), volume 24 h (colorato come nell'overlay), ultimo
aggiornamento. Clic sulle intestazioni per ordinare; ricerca e filtri per vendor e tipo.

- Il costo in standing viene dai dati del gioco. È il costo base, senza sconti di rank. Se un oggetto
  costa standing a più vendor vedi `min – max`; il tooltip mostra vendor, costo e rank richiesto.
- **Passando il mouse** sul nome (o sul costo in standing): quanti ne puoi comprare con il tuo standing, per
  fazione (`floor(standing / costo)`), e se il tuo rank basta. Usa i numeri della scheda Profilo.
- **Nascondi volume zero** nasconde gli oggetti senza scambi nelle ultime 24 ore (quelli senza dati restano visibili).
- **Clic destro** sul nome di un oggetto (qui e in Consigli): aprilo su warframe.market, apri la sua pagina
  sulla wiki di Warframe (una ricerca che va dritta alla pagina se il titolo esiste) o copia il nome.
- Sono elencati solo gli oggetti **scambiabili**: i nomi vengono associati al catalogo di warframe.market,
  quindi tutto ciò che non si può scambiare resta fuori.
- **Aggiorna elenco mostrato** aggiorna prezzo e volume di tutte le righe visibili (filtri compresi;
  salta i dati più recenti di `refresh_skip_age` secondi). Filtra per un vendor per aggiornare solo i suoi oggetti.
- **Aggiorna selezionati** aggiorna sempre le righe selezionate (Ctrl/Maiusc per più righe).
- **Ferma** interrompe; una barra mostra l'avanzamento. Il limite è 3 richieste/s (2 per oggetto):
  ~2 minuti per 100 oggetti, ~20 per tutto il catalogo dei vendor. Sopra `refresh_confirm_over` oggetti
  chiede conferma. Chiudere la finestra ferma l'aggiornamento. I dati restano salvati in `prices.json`.
- **Aggiorna elenco Baro**: Baro non è nei dati del gioco; il suo elenco storico si legge dalla wiki
  (e dal suo inventario attuale) e si ricarica da solo all'avvio ogni `baro_refresh_days` giorni.

### Inventario
I tuoi oggetti con i prezzi di mercato e gli ordini di vendita con un clic (ispirato alla scheda Inventory di AlecaFrame).

- **Da dove vengono gli oggetti.** Warframe tiene il tuo inventario sui server di DE, non in un file locale,
  quindi non si può leggere da disco (e questo programma non legge mai la memoria o il traffico di rete del
  gioco). Lo costruisci con **Importa file…** (sostituisce l'inventario), **Incolla lista…**, oppure
  **Aggiungi oggetto…** / **Modifica** a mano. File accettati: un **`lastData.dat`** (il file di inventario cifrato in stile AlecaFrame; decifrato in locale con il
  pacchetto `cryptography`; la finestra di importazione si apre in `%LOCALAPPDATA%\AlecaFrame` se la cartella esiste),
  un JSON di *inventario grezzo in stile Warframe*
  (`MiscItems`, `RawUpgrades`, `Upgrades`, `Recipes`… con percorsi `ItemType`, risolti con `gamenames.json`
  incluso), qualunque JSON che abbini nomi e quantità (liste `{"name": …, "count": …}` o `{"Serration": 2}`),
  e righe CSV/TXT come `Serration, 2, 10` (nome, quantità, rank facoltativo), `3x Mirage Prime Set` oppure
  `Ash Prime Blueprint x2`. **Ricarica file** rilegge l'ultimo file importato, comodo quando un altro tuo strumento lo aggiorna.
  I nomi vengono associati al catalogo del market (piccoli errori sono tollerati);
  quelli non riconosciuti vengono elencati dopo l'importazione. Non provato con vere esportazioni del gioco,
  solo con file di queste forme.
- **Categorie**: Set, Parti di Warframe, Parti di armi, Mod, Arcane, Reliquie, Altro (ricavate dai tag di
  warframe.market). **Filtri** come quelli di AlecaFrame: platino minimo (5 / 10 / 15), più di uno posseduto,
  tipo di parte (prime / normale), vaulted (quando lo dicono i dati del market), in vendita da qui, più
  **Escludi mod/arcane a rank massimo** (escono dalla lista e dal totale).
- **Prezzi**: valore = copie × prezzo a rank 0 + copie a rank massimo × prezzo a rank massimo;
  **Aggiorna prezzi** aggiorna gli oggetti mostrati. Clic destro sul nome per la pagina del market / wiki.
- **Vendi…** piazza un **ordine di vendita** su warframe.market per ogni oggetto selezionato. Prima accedi
  (email e password, inviate solo a warframe.market; **si salva solo il token di sessione** in
  `market_session.json`; *Esci* lo cancella). Per ogni ordine una finestra mostra quantità, rank
  (mod/arcane), prezzo (prezzo di mercato + `sell_price_offset`) e **la richiesta esatta che verrà inviata**;
  non parte nulla finché non premi *Piazza ordine*. Il programma ricorda gli ordini che ha piazzato
  (colonna *In vendita*); non legge gli altri tuoi ordini.
  **Attenzione:** accesso e creazione degli ordini usano le API REST v1 come documentate dalle librerie
  della community e non si sono potuti provare sul sito vero durante lo sviluppo: controlla il primo ordine
  su warframe.market. Gli account che accedono con Discord/Google potrebbero non funzionare.

**Ducat e consigli.** La colonna *Ducat* mostra quanto dà ogni parte prime se scambiata (dai dati del gioco). *Consiglio: ducat* elenca le tue parti prime per ducat guadagnati per ogni platino a cui rinunci (`ducat / max(prezzo × liquidità, 0,5)`, con `liquidità = min(1, volume / volume liquido)`); da un rapporto minimo (default 10) in su dice *Ducat*, altrimenti *Vendi*. I totali usano tutte le tue copie. *Consiglio: vendita* ordina il resto per `prezzo × copie che puoi sperare di vendere (≈ ¼ del volume giornaliero) × liquidità`, escludendo gli oggetti sotto il prezzo minimo o con poco volume. Entrambi possono selezionare le righe scelte nella tabella, pronte per *Vendi*. Qui c'è anche *Nascondi volume zero*. Le soglie sono nelle Impostazioni (gruppo Consigli).

### Consigli
Cosa conviene comprare con lo standing, per ogni coppia (oggetto, vendor) con un costo in standing:

```
plat per 1000 standing = prezzo / costo in standing × 1000
punteggio              = plat per 1000 standing × min(1, volume / impostazione «volume alto»)
```
Il punteggio penalizza gli oggetti che si vendono poco: un prezzo alto non serve se nessuno compra.
Gli oggetti scambiati meno del **volume minimo** o che costano meno del **prezzo minimo** (modificabili
nella scheda) sono esclusi. I prezzi sono a rank 0 (ciò che vende davvero il vendor). Filtra per vendor
o tipo. Gli oggetti senza dati di mercato non si possono valutare: **Scarica i dati mancanti** li scarica
(scegli prima un vendor per fare in fretta).

Passando il mouse su una riga vedi quanti ne puoi permettere con il tuo standing (scheda Profilo).

### Profilo
Standing e rank per fazione, più il grado di maestria, **letti dal `lastData.dat` di AlecaFrame** (o dal JSON
dell'app companion) con **Importa lo standing da file…**; *Ricarica il file* lo rilegge dopo che AlecaFrame l'ha
aggiornato. Puoi anche scrivere o correggere ogni valore a mano (restano fino alla prossima importazione). È
un'istantanea: ricaricala dopo aver speso standing. Il file viene **riletto da solo** quando cambia (controllo ogni 10 s, impostazione *Controllo file AlecaFrame*, 0 = spento; serve il riavvio). AlecaFrame riscrive il file ogni volta che entri o esci da una missione, quindi standing e inventario si aggiornano negli stessi momenti (solo con AlecaFrame in esecuzione). La colonna *Rimasto oggi* è lo standing che puoi ancora guadagnare oggi (limite giornaliero).
Il file contiene lo standing *totale*; il programma sottrae l'inizio del tuo rank attuale, così i numeri coincidono con il gioco (es. 68 195 / 132 000). Scrivi i valori come li mostra il gioco.
Lo standing negativo indica la fazione opposta (ne puoi comprare 0).

### Mondo
Fenditure, invasioni, sortita, cicli e inventario attuale di Baro Ki'Teer (con i prezzi in platino se noti),
dal mirror della community `api.warframestat.us`. Si aggiorna mentre la scheda è aperta (impostazione *Aggiornamento mondo*).

*Non inclusi:* inventario/foundry completo (esiste solo il JSON dell'app companion: usa l'importazione dell'Inventario), standing giornaliero rimasto, tabelle drop, lettura di EE.log.

### Impostazioni
Tutte le impostazioni del programma, raggruppate (generali, tasti, rilevamento, dati, aspetto,
prestazioni, consigli). **Salva** le applica e le scrive in `config.json`; **Salva e riavvia** riavvia anche
il programma. Quelle con ⟳ (lingua, tasti, OCR, parti attivo, soglia nomi) richiedono il riavvio; le altre
valgono subito. **Ripristina predefiniti** carica i valori di default (premi Salva per applicarli).

## Aggiornamenti (versione attuale 0.1.4)
All'avvio il programma cerca (in background, impostazione *Cerca aggiornamenti all'avvio*) una **release GitHub** più
recente e ti chiede se vuoi installarla (*Installa ora* / *Più tardi* / *Salta questa versione*). Se la release esiste ma il suo pacchetto non è ancora pronto (costruzione ancora in corso o fallita) te lo dice. In **Impostazioni → Aggiornamenti** puoi controllare a mano e, se sei d'accordo,
scarica `WFVendorOverlay-windows.zip`, ne verifica lo SHA-256 con il file `.sha256` della stessa release, sostituisce i
file del programma dopo la chiusura e lo riavvia. Impostazioni e dati (`%LOCALAPPDATA%\WFVendorOverlay`) non vengono toccati.
Il passaggio di installazione scrive `update.log` nella cartella dei dati (ogni passo e gli eventuali errori di copia). Se un aggiornamento non fa nulla, quel file dice perché; come alternativa manuale chiudi il programma e decomprimi la release sopra la sua cartella. Si aggiorna da solo solo la versione Windows pacchettizzata; dai sorgenti usa `git pull`. La verifica dimostra solo che il
download non è corrotto: ci si fida delle release del repository (l'exe non è firmato, quindi SmartScreen può avvisare).

**Pubblicare una versione** (manutentore): cambia `version.py`, fai commit, poi `git tag v0.1.1 && git push origin v0.1.1`.
Il workflow in `.github/workflows/release.yml` costruisce il pacchetto Windows e crea la release con zip e checksum.

## Lingua
Inglese di default. Si cambia in Impostazioni → Generali → Lingua (English / Italiano) e si riavvia.
Codice, commenti e README esistono in inglese; l'interfaccia è tradotta per intero.

## Da sorgente (Windows, Python 3.12 a 64 bit)
```
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

## Creare l'eseguibile
```
powershell -ExecutionPolicy Bypass -File build.ps1            # cartella dist\WFVendorOverlay (consigliato)
powershell -ExecutionPolicy Bypass -File build.ps1 -Console   # con console (per vedere gli errori)
powershell -ExecutionPolicy Bypass -File build.ps1 -OneFile   # singolo .exe (avvio più lento)
```
I modelli OCR sono inclusi. Se Warframe gira come amministratore, avvia l'overlay come amministratore.

## File e impostazioni
Tutto sta in `%LOCALAPPDATA%\WFVendorOverlay`:
- `config.json` impostazioni · `prices.json` prezzi e volumi raccolti · `items_cache.json` catalogo del market ·
  `baro.json` elenco di Baro · `inventory.json` il tuo inventario e gli ordini piazzati dal programma ·
  `market_session.json` token di sessione di warframe.market · `vendors.json` / `gamenames.json` (facoltativi,
  hanno la precedenza su quelli inclusi) · `overlay.log` errori (utile con l'exe).

| chiave | significato (default) |
|---|---|
| `language` | `en` oppure `it` |
| `key_menu` / `key_scan` / `key_clear` / `key_quit` | tasti (`<f7>` `<f8>` `<f9>` `<f10>`) |
| `start_active` / `auto_detect` | parte già in scansione / rileva i vendor da solo (true) |
| `refresh_interval` | secondi tra gli aggiornamenti automatici (180) |
| `open_max_age` | all'apertura di un vendor aggiorna i dati più vecchi di N s (30) |
| `show_cached_max_age` | mostra subito i dati salvati più recenti di N s (3600) |
| `refresh_skip_age` / `refresh_confirm_over` / `baro_refresh_days` | soglia di «aggiorna mostrato» (300 s) / conferma sopra N oggetti (150) / aggiornamento Baro (7 giorni) |
| `volume_low` / `volume_high` | volume rosso fino a `low`, verde da `high` (10 / 50) |
| `volume_offset_y` / `show_volume` | distanza dell'etichetta del volume (2 px) / mostrala |
| `hide_zero_volume` | nasconde gli oggetti a volume zero nel listino (false) |
| `match_threshold` | soglia di somiglianza dei nomi (90) |
| `watch_interval`, `watch_interval_moving`, `auto_settle_polls`, `auto_motion_frac`, `auto_min_gap`, `scroll_debounce` | sensibilità del rilevamento |
| `ocr_threads`, `ocr_priority`, `publish_throttle`, `menu_refresh_ms` | prestazioni |
| `inv_exclude_maxed`, `sell_price_offset` | inventario: esclude mod/arcane a rank massimo / scostamento sul prezzo di vendita (0) |
| `rec_min_volume`, `rec_min_price`, `rec_top` | filtri dei consigli |

## Prestazioni
La scansione (OCR) è la parte pesante. Per non disturbare il gioco:
- OCR e riconoscimento dei nomi girano in un **processo separato** (`ocr_worker.py`) a priorità
  "inferiore al normale" e con pochi thread (circa 1/4 dei core, da 1 a 3); il processo principale,
  che gestisce overlay, tasti e rotellina, resta sempre reattivo. Una scansione dura qualche secondo
  in più, ma senza rubare CPU al gioco.
- Se lo schermo non è cambiato dall'ultima scansione, il risultato viene riusato senza rifare l'OCR.
- Durante il gioco in movimento lo schermo viene controllato meno spesso (`watch_interval_moving`),
  e l'overlay si ridisegna al massimo ogni `publish_throttle` secondi durante gli aggiornamenti.
- Hai ancora lag? `ocr_priority` = `idle`, `ocr_threads` = 1, `watch_interval` più alto (1.0), oppure
  `auto_detect` = `false` e scansione solo con F8.

## File del codice
`main.py` avvio · `scanner.py` scansioni, rilevamento automatico, aggiornamenti · `ocr_worker.py` processo OCR ·
`version.py` · `updater.py` · `update_box.py` auto-aggiornamento · `ocr.py` cattura e OCR · `winrect.py` posizione della finestra del gioco · `matcher.py` riconoscimento nomi · `market.py` catalogo, prezzi, volumi, archivio JSON ·
`vendors.py` / `build_vendors.py` / `vendors.json` catalogo dei vendor e costi in standing ·
`menu.py` finestra del listino · `recommend.py` + `recommend_tab.py` consigli ·
`inventory.py` + `inventory_tab.py` inventario e importazioni · `market_auth.py` accesso e ordini di vendita ·
`settings_tab.py` impostazioni · `refresher.py` aggiornamenti in blocco · `uiutil.py` parti comuni dell'interfaccia ·
`overlay.py` grafica · `config.py` impostazioni · `i18n.py` traduzioni ·
`build.ps1` / `prepare_models.py` eseguibile.

## Note
- I volumi usano l'endpoint v1 di warframe.market (deprecato ma attivo); se smette di funzionare resta il prezzo.
- Il rilevamento automatico controlla lo schermo ogni 0,6 s (poco carico, ma non nullo): aumenta
  `watch_interval` o metti `auto_detect` a `false` se noti cali di prestazioni.
- Prezzo a rank massimo = mediana dei 3 ordini di vendita più bassi di utenti online con quel rank;
  se nessuno vende a quel rank mostra `–`.
- La lista dei vendor viene dai dati pubblici del gioco: i vendor assenti (es. Varzia, onori Arbitrations)
  non sono inclusi. Si rigenera con `python build_vendors.py` (una copia in
  `%LOCALAPPDATA%\WFVendorOverlay\vendors.json` ha la precedenza).
- Il tuo standing e il tuo inventario non vengono letti dal gioco: Warframe li tiene sui server di DE, non in file locali.
