# WF Vendor Overlay

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
- **Uscita dal vendor**: appena chiudi il vendor o cambi pagina le etichette spariscono (il controllo
  confronta il testo sotto i nomi e funziona anche mentre i prezzi si stanno ancora caricando).
- **F7** apre/chiude il **listino prezzi** · **F8** scansiona subito (e riprende se in pausa) ·
  **F9** pausa · **F10** esci. Le stesse azioni sono nel menu dell'icona vicino all'orologio
  (clic sull'icona = listino).
Warframe deve essere in finestra senza bordi (Borderless).

## Listino prezzi (F7)
Finestra con **tutti gli oggetti scambiabili venduti dai vendor** (84 vendor e sindacati, ~3500 voci
da `vendors.json`, più Baro Ki'Teer): appena la apri ci sono già tutti, anche senza prezzo
(prezzo «–», aggiornato «mai»). Colonne: nome, vendor che lo vendono, tipo (Mod / Arcane / Altro),
prezzo, prezzo a rank massimo (mod e arcane), volume 24 h (colorato come nell'overlay), ultimo
aggiornamento. Clic sulle intestazioni per ordinare; ricerca, filtro per **vendor** e per tipo.

**Aggiornare i dati dal listino**
- **Aggiorna elenco mostrato**: aggiorna prezzo e volume di tutte le righe visibili (filtri compresi;
  salta i dati più recenti di `refresh_skip_age` secondi). Filtra per un vendor per aggiornare solo i suoi oggetti.
- **Aggiorna selezionati**: sempre, per le righe selezionate (Ctrl/Maiusc per più righe).
- **Ferma** interrompe; barra di avanzamento. Il limite è 3 richieste/s (2 per oggetto): ~2 minuti per
  100 oggetti, ~20 per tutto il catalogo dei vendor. Sopra `refresh_confirm_over` oggetti chiede conferma.
  Chiudere il listino ferma l'aggiornamento. I dati restano salvati in `prices.json`.
- **Aggiorna elenco Baro**: Baro non è nei dati del gioco; il suo elenco storico si legge dalla wiki
  (e dal suo inventario attuale) e si ricarica da solo all'avvio ogni `baro_refresh_days` giorni.

Mentre il listino è aperto le scansioni sono sospese e le etichette nascoste (altrimenti l'OCR
leggerebbe i nomi del listino); alla chiusura riprende da sola.

**Limiti**: la lista dei vendor viene dai dati pubblici del gioco; vendor assenti da quei dati
(es. Varzia, onori Arbitrations) non sono inclusi. `vendors.json` si rigenera con
`python build_vendors.py`; una copia in `%LOCALAPPDATA%\WFVendorOverlay\vendors.json` ha la precedenza.

## Da sorgente (Windows, Python 3.12 a 64 bit)
```
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

## Creare l'eseguibile
```
powershell -ExecutionPolicy Bypass -File build.ps1
```
Risultato: cartella `dist\WFVendorOverlay` con `WFVendorOverlay.exe` (copia/zippa tutta la cartella).
`-Console` mostra gli errori in una console · `-OneFile` crea un singolo .exe (avvio più lento).

## Cartella dati: `%LOCALAPPDATA%\WFVendorOverlay`
- `config.json`: impostazioni (creato al primo avvio; se esiste già da una versione precedente non
  viene riscritto: cancellalo per rigenerarlo con tutte le opzioni nuove).
- `prices.json`: per ogni oggetto (slug) ultimo prezzo, prezzo a rank massimo, ultimo volume, istante di
  rilevazione e uno storico (max 48 voci, una ogni 15 minuti). Gli oggetti non aggiornati da 30 giorni vengono eliminati.
- `items_cache.json` catalogo di warframe.market · `overlay.log` errori (utile con l'exe).

## Impostazioni principali (`config.json`)
| chiave | significato |
|---|---|
| `key_menu` | tasto del listino prezzi (`<f7>`) |
| `refresh_skip_age` | «Aggiorna elenco mostrato» salta dati più recenti di N secondi (300) |
| `refresh_confirm_over` | chiede conferma se si aggiornano più di N oggetti (150) |
| `baro_refresh_days` | ogni quanti giorni riscaricare l'elenco di Baro (7) |
| `menu_refresh_ms` | ogni quanto il listino aperto si aggiorna (2000) |
| `refresh_interval` | secondi tra gli aggiornamenti periodici (180) |
| `open_max_age` | all'apertura aggiorna i dati più vecchi di N secondi (30) |
| `volume_low` / `volume_high` | rosso fino a `low`, verde da `high` in su (10 / 50) |
| `volume_offset_y` | distanza in pixel tra nome e volume (2) |
| `start_active` | parte già attivo (true) |
| `auto_detect` | rilevamento automatico di apertura/cambio vendor (true) |
| `watch_interval`, `auto_settle_polls`, `auto_motion_frac`, `auto_min_gap` | sensibilità del rilevamento |
| `scroll_debounce` | attesa dopo l'ultimo giro di rotellina (0,45 s) |
| `ocr_threads` | thread dell'OCR (0 = automatico) |
| `ocr_priority` | `normal` / `below_normal` / `idle` (priorità del processo OCR) |
| `watch_interval_moving` | controllo schermo mentre c'è movimento continuo (1,5 s) |
| `publish_throttle` | secondi minimi tra due ridisegni dell'overlay (0,15) |
| `show_volume`, `match_threshold`, `key_*` | volume on/off, soglia nomi, tasti |

## Prestazioni
La scansione (OCR) è la parte pesante. Per non disturbare il gioco:
- OCR e riconoscimento dei nomi girano in un **processo separato** (`ocr_worker.py`) a priorità
  "inferiore al normale" e con pochi thread (circa 1/4 dei core, da 1 a 3); il processo principale,
  che gestisce overlay, tasti e rotellina, resta sempre reattivo. Una scansione dura qualche secondo
  in più, ma senza rubare CPU al gioco.
- Se lo schermo non è cambiato dall'ultima scansione, il risultato viene riusato senza rifare l'OCR.
- Durante il gioco in movimento lo schermo viene controllato meno spesso (`watch_interval_moving`),
  e l'overlay si ridisegna al massimo ogni `publish_throttle` secondi durante gli aggiornamenti.
- Se hai ancora lag: `ocr_priority` = `"idle"` (l'OCR lavora solo a CPU libera, ma può rallentare molto
  se il gioco usa tutti i core), `ocr_threads` = 1, `watch_interval` più alto (1.0), oppure
  `auto_detect` = `false` e scansione solo con F8.

## File
`main.py` avvio · `scanner.py` scansioni, rilevamento automatico, aggiornamenti · `ocr_worker.py` processo OCR ·
`ocr.py` cattura e OCR · `matcher.py` riconoscimento nomi · `menu.py` listino prezzi ·
`market.py` catalogo, prezzi, volumi, archivio JSON · `overlay.py` grafica · `config.py` impostazioni ·
`build.ps1` / `prepare_models.py` eseguibile.

## Note
- I volumi usano l'endpoint v1 di warframe.market (deprecato ma attivo); se smette di funzionare resta il prezzo.
- Il rilevamento automatico controlla lo schermo ogni 0,6 s (poco carico, ma non nullo): aumenta
  `watch_interval` o metti `auto_detect` a `false` se noti cali di prestazioni.
- Se Warframe gira come amministratore, avvia l'overlay come amministratore (tasti e rotellina globali).
- Aggiornando da una versione precedente, i prezzi salvati di mod e arcane vengono scartati e raccolti di
  nuovo (prima mescolavano tutti i rank); il catalogo si riscarica da solo una volta (ora include rank e tipo).
- Prezzo a rank massimo = mediana dei 3 ordini di vendita più bassi di utenti online con quel rank;
  se nessuno vende a quel rank mostra `–`.
