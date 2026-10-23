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

## Finestra del listino (F7)
Tre schede. Mentre la finestra è aperta le scansioni sono sospese e le etichette nascoste (altrimenti
l'OCR leggerebbe i nomi del listino); alla chiusura riprende da sola.

### Listino prezzi
Tutti gli **oggetti scambiabili venduti dai vendor** (84 vendor e sindacati, ~3500 voci da
`vendors.json`, più Baro Ki'Teer): ci sono già tutti fin dall'inizio, anche senza dati (prezzo `–`,
aggiornato `mai`). Colonne: nome, vendor che lo vendono, **costo in standing**, tipo (Mod / Arcane / Altro),
prezzo, prezzo a rank massimo (mod e arcane), volume 24 h (colorato come nell'overlay), ultimo
aggiornamento. Clic sulle intestazioni per ordinare; ricerca e filtri per vendor e tipo.

- Il costo in standing viene dai dati del gioco. È il costo base, senza sconti di rank. Se un oggetto
  costa standing a più vendor vedi `min – max`; il tooltip mostra vendor, costo e rank richiesto.
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
(scegli prima un vendor per fare in fretta). Il programma non conosce il tuo standing: controlla tu il rank richiesto.

### Impostazioni
Tutte le impostazioni del programma, raggruppate (generali, tasti, rilevamento, dati, aspetto,
prestazioni, consigli). **Salva** le applica e le scrive in `config.json`; **Salva e riavvia** riavvia anche
il programma. Quelle con ⟳ (lingua, tasti, OCR, parti attivo, soglia nomi) richiedono il riavvio; le altre
valgono subito. **Ripristina predefiniti** carica i valori di default (premi Salva per applicarli).

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
  `baro.json` elenco di Baro · `vendors.json` (facoltativo, ha la precedenza su quello incluso) ·
  `overlay.log` errori (utile con l'exe).

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
| `match_threshold` | soglia di somiglianza dei nomi (90) |
| `watch_interval`, `watch_interval_moving`, `auto_settle_polls`, `auto_motion_frac`, `auto_min_gap`, `scroll_debounce` | sensibilità del rilevamento |
| `ocr_threads`, `ocr_priority`, `publish_throttle`, `menu_refresh_ms` | prestazioni |
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
`ocr.py` cattura e OCR · `matcher.py` riconoscimento nomi · `market.py` catalogo, prezzi, volumi, archivio JSON ·
`vendors.py` / `build_vendors.py` / `vendors.json` catalogo dei vendor e costi in standing ·
`menu.py` finestra del listino · `recommend.py` + `recommend_tab.py` consigli ·
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
- Il tuo standing non viene letto: Warframe lo tiene sui server di DE, non in file locali.
