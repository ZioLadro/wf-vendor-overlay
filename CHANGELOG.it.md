# Changelog

Dalla 0.2.1 ogni release elenca qui le sue modifiche (la pagina della release su GitHub mostra la sezione della sua versione).
Versione inglese: [CHANGELOG.md](CHANGELOG.md).

## 0.2.9
- **Riven spliced** (una statistica fusa da altre due con un Riven Splicer) riconosciute e mostrate "ghiacciate" in
  Build: card azzurra, etichetta ❄ *Spliced*, la statistica spliced evidenziata. I dati del gioco non hanno ancora i
  valori delle statistiche spliced, quindi il loro valore appare come "?"; le altre statistiche sono calcolate come
  sempre. (La 0.2.8 le chiamava per errore statistiche vecchie.)
- **I valori delle Riven usano la disposizione unica** dell'Hotfix 44.1.3 (ogni Riven ora usa la vecchia disposizione
  1.2), in Build, Quantframe e nel punteggio del Riven flip.
- **Armi esaltate in Build** (Exalted Blade, Iron Staff, Artemis Bow, Balefire Charger, Regulators, Noctua…): un loro
  gruppo in *Per oggetto*, la Warframe a cui appartengono, mod, Arcani e Riven; la riga *Esaltata* dei *Loadout di
  gioco* ora le apre. La capacità non è mostrata per loro (le polarità dei loro slot non sono nei dati pubblici).
- **Arbitrato con il suo tier** nella barra del mondo: l'Arbitrato attuale (missione, nodo, tempo rimasto) con il tier di
  **arbi.guide** (Arbitration Goons: S 12+ Vitus Essence/min … D, Special, F; * = valido con Saryn off-meta), tramite
  l'API documentata della guida (`tierlist.json`), in cache 15 minuti, ultima copia valida conservata, link alla guida
  sul tier.
  Quale nodo è l'Arbitrato viene dal calendario orario di browse.wf (`arbys.txt`, letto una volta al giorno e conservato),
  perché lo stato del mondo spesso non lo riporta; i nomi dei nodi dai dati del gioco (`nodes.json`, creato da
  `build_nodes.py`).
- Correzione: dopo l'aggiornamento, Build continuava a mostrare i loadout salvati dalla versione precedente (niente Riven
  spliced, niente armi esaltate) finché il file di gioco non cambiava; ora la copia salvata viene riletta dopo ogni
  aggiornamento.

## 0.2.8
- **Barra del mondo** sotto la barra del giocatore: le fessure Omnia Steel Path aperte ora, i cicli di Terra / Cetus /
  Orb Vallis, quando torna (o parte) Baro Ki'Teer e quando cambia l'offerta della Prime Resurgence, con conto alla
  rovescia (da api.warframestat.us, letto ogni 5 minuti). Impostazione *Barra del mondo sotto la barra giocatore*.
- **Scheda Console**: cosa fa il programma in background (immagini e loghi dalla wiki, aggiornamento prezzi, scansioni
  Riven, file letti, stato del mondo, messaggi dell'overlay) e ogni errore, con i lavori in corso in alto; filtro per
  fonte o solo errori, salvataggio su file.
- **Niente più lampeggi mentre si scaricano le immagini**: vengono messe dove mancano invece di ricostruire elenchi e
  card ogni pochi secondi.
- **Build: Reattore / Catalizzatore Orokin** sotto il titolo: installato, non installato, non indicato dal file, oppure
  dedotto (gli oggetti più vecchi non lo dicono, ma un loro loadout ci sta solo con esso).
- **Riven con una statistica vecchia** (Gas, Efficienza munizioni: tiri che i dati del gioco non hanno più) ora mostrano
  le altre statistiche, con "?" per quella vecchia, invece di nessuna; una statistica che il tipo d'arma non tira più
  (es. Zoom su un fucile a pompa) usa i valori di un altro tipo.
- **Sfondi**: sette motivi originali (reticolo Orokin, volute Tenno, piastre Grineer, circuiti Corpus, cellule Infested,
  onde, anelli Entrati), ognuno abbinato a un tema; oppure scegline uno qualsiasi, **una tua immagine** (ritagliata sulla
  finestra e fusa col tema perché il testo resti leggibile) o nessuno. Impostazioni *Sfondo* e *La tua immagine di sfondo*.
- La polarità Unairu delle Riven veniva inviata a Quantframe come Zenurik.

## 0.2.7
- **Immagini delle Build solo dalla wiki di Warframe** (card delle mod e oggetti), tramite l'API MediaWiki della wiki
  (l'immagine principale della pagina, altrimenti `File:<nome>.png`). All'avvio il programma chiede in background le
  immagini che mancano per le mod dei tuoi loadout e per gli oggetti, una alla volta; restano nella cartella dati.
- **Immagini degli oggetti** (Warframe, armi, compagni) accanto al titolo del loadout, sulle righe di *Loadout di gioco* e
  nell'elenco *Per oggetto*.
- **Elenco Per oggetto diviso per tipo**: Warframe, primarie, secondarie, mischia, Archwing, arch-gun, Necramech,
  compagni, ognuno sotto la sua intestazione.
- **Sfondo a tema**: un motivo originale nei colori del tema (sottile reticolo dorato, rombi e archi) dietro le schede;
  tabelle, elenchi, campi e pulsanti restano a tinta unita, così il testo resta ben leggibile. Impostazioni *Sfondo a
  tema* e *Visibilità dello sfondo*.
- **Revisione di Build e planner**, correzioni:
  - la capacità delle mod è il rank dell'oggetto (30, o 40 per armi Kuva, Tenet e Coda e Necramech), raddoppiata da un
    Reactor / Catalyst; prima era 30 punti troppo alta;
  - una mod usata come copia senza rank veniva contata al rank massimo;
  - la polarità "universale" del file di gioco (Aura Forma) va bene per ogni mod: verificato su una build reale, la
    capacità totale ora coincide con quella del gioco (60 + Aura 7 × 2 = 74);
  - le polarità innate vengono messe sugli slot dove fanno risparmiare più drain (il file di gioco non dice dove sono);
  - gli oggetti più vecchi, il cui file non dice se hanno un Reactor / Catalyst, vengono contati con uno quando la build
    ci sta solo così;
  - una Riven copiata nel planner si perdeva aprendo e confermando il suo slot;
  - scrivere il nome di un oggetto nel planner (maiuscole qualsiasi, anche solo una parte) funziona; i nomi a metà sono
    ignorati;
  - il file di gioco viene riletto se è cambiato dopo la copia salvata (e se cambia mentre la scheda è aperta);
  - i pulsanti delle configurazioni non accumulano più un oggetto invisibile a ogni ridisegno; il conteggio dei loadout
    non conta più le intestazioni dei gruppi.

## 0.2.6
- **Prezzi e consigli in un'unica scheda**: il listino sopra, i consigli sotto, con un divisore trascinabile (la
  posizione viene ricordata).
- **La finestra non è più sempre in primo piano**: viene davanti quando la apri (tasto rapido o icona) e poi si comporta
  come una finestra normale, quindi il gioco o altri programmi possono coprirla. L'impostazione *Finestra sempre in primo
  piano* riporta il comportamento di prima (serve il riavvio). Le etichette sul gioco restano in primo piano come prima.
- **Inventario: volume minimo** (*Vol. min*): nasconde gli oggetti scambiati meno di così nelle ultime 24 ore (gli
  oggetti ancora senza dati di volume restano). Viene ricordato.
- **Loghi delle fazioni dalla wiki di Warframe** nella barra in alto: l'immagine di ogni sindacato viene chiesta una
  volta tramite l'API MediaWiki della wiki (l'immagine principale della pagina, altrimenti un file chiamato Sigil / Icon
  / Logo), salvata nella cartella dati (`icons`) e riusata; fino ad allora resta il badge disegnato. Un logo non trovato
  viene richiesto di nuovo dopo un giorno. Si disattiva insieme a *Immagini degli oggetti nei tooltip*.

## 0.2.5
Uso delle risorse, stessi risultati:
- **`prices.json` circa 18 volte più piccolo**: conteneva uno storico dei prezzi per oggetto che nessuna parte del
  programma leggeva (48 voci per oggetto). Viene eliminato al primo salvataggio; caricamento e salvataggio sono più
  veloci e usano meno memoria.
- **Controllo dello schermo più leggero mentre le etichette sono mostrate**: per capire se il venditore è ancora
  aperto viene catturato solo il rettangolo attorno ai nomi degli oggetti (non tutta la finestra del gioco); il
  confronto è lo stesso.
- **Meno controlli con il gioco in secondo piano**: quando Warframe non è la finestra attiva il programma lo cerca ogni
  1,2 s invece che ogni 0,6 s (torna normale appena è attivo).
- **Tabelle**: la lista prezzi e l'inventario non vengono più ricostruiti ogni 30 secondi solo per aggiornare la colonna
  "x min fa": si aggiorna solo quella colonna. Il controllo delle immagini della scheda Build si ferma quando la scheda
  è nascosta.
- **OCR**: con *Salta il pannello sinistro del vendor* attivo, lo screenshot viene rimpicciolito prima di applicare la
  maschera, quindi l'immagine a piena risoluzione non viene più copiata (stesso testo letto, verificato su uno screenshot
  di prova).

## 0.2.4
- **La scheda Build si adatta alla finestra**: le card crescono e si riducono con la finestra (larghezza e altezza),
  mantenendo le stesse proporzioni tra card delle mod e degli Arcani, simboli di polarità e drain e testo. Lo stesso
  vale per il build planner.
- **Passando sopra una card** si vede l'immagine della mod (più grande), con nome e rank.
- **Più leggero sulle risorse**: la scheda Consigli non ricostruisce più la tabella ogni 2 secondi se non è cambiato
  nulla; il file di AlecaFrame non viene più letto e controllato ogni 10 secondi (solo se data o dimensione sono
  cambiate); il controllo dello schermo rallenta a ogni 1,2 s dopo circa 12 s senza novità (torna normale al primo
  cambiamento, e mai mentre le etichette sono mostrate); le immagini delle card sono in cache durante il ridimensionamento.
- **Ordine di scansione delle Riven**: le armi le cui inserzioni continuano a vendersi vengono riscansionate prima, quelle
  osservate da 3+ giorni senza vendite e con poche inserzioni più tardi, così le richieste vanno dove i prezzi si muovono.

## 0.2.3
- **Build, stile delle card del gioco**: Aura ed Exilus in alto, le otto mod in due righe da quattro, gli Arcani a destra;
  ogni card mostra la polarità dello slot, la polarità e il drain della mod (verde = polarità uguale, rosso = diversa) e il
  rank a rombi. Le polarità messe con le Forma sono lette dal file di gioco, quelle innate dai dati pubblici del gioco.
- **Capacità e riepilogo statistiche** accanto alla build: capacità libera / totale (rank e Reactor/Catalyst dal file,
  capacità dell'Aura inclusa) e Salute, Scudo, Armatura, Energia, Velocità di corsa, Durata, Efficienza, Raggio e Potenza
  delle abilità. Approssimato: contano solo le mod (niente Arcani, Archon Shard, Helminth, bonus di set o effetti condizionali).
- **Nomi delle build**: i nomi che hai dato alle configurazioni in gioco (es. "Zombie") vengono importati e mostrati come
  pulsanti per passare da una configurazione all'altra di un oggetto.
- **Build planner** (Build > Build planner): scegli una Warframe o un'arma, clicca una card per scegliere mod, rank e
  polarità dello slot (Forma), vedi capacità, drain e statistiche; salva, carica ed elimina i piani, oppure parti dalla
  copia di un tuo loadout.
- **Cartella delle icone trovata da sola**: il programma cerca le icone di AlecaFrame nelle cartelle di Overwolf e segue
  la nuova cartella di versione che Overwolf crea a ogni aggiornamento (impostazione *Trova da solo la cartella delle
  icone*; una cartella scritta nelle impostazioni, se esiste, ha la precedenza). Le immagini delle polarità vengono da
  quella cartella, con un disegno di riserva.
- **Riven nelle build**: una Riven installata mostra nome (es. "Toxi-argidra"), statistiche, polarità e drain
  (10 + rank) sulla card; i suoi bonus contano nel riepilogo. Le armi hanno un riepilogo *Bonus delle mod* (somma dei
  bonus percentuali di mod e Riven; le statistiche base dell'arma non sono mostrate).
- **Aya**: il file di gioco non contiene gli Aya che possiedi (indica 0), quindi la nuova impostazione *Aya (scritti a
  mano)* li fornisce; gli Aya sono nascosti finché sono 0.

## 0.2.2
- **Build**: nuova vista *Loadout di gioco* che segue la schermata dei loadout del gioco: i tuoi loadout con nome, con
  Warframe, primaria, secondaria, mischia e arma esaltata, il compagno, l'Archwing e il Necramech (con rank, i nomi che
  hai dato e la configurazione di mod usata da ogni loadout). Clicca una riga per vedere mod, Arcani, Archon Shard e
  Helminth. La lista precedente resta come *Per oggetto*. Letto dal file di AlecaFrame; scuola di Focus e K-Drive non sono mostrati.
- **Barra in alto**: Endo, platino, ducat e Aya che possiedi (in forma compatta: 3k, 30k, 1.2M; valore esatto nel suggerimento),
  con le icone della cartella icone se impostata.
- Gli Arcani nelle schede Build usano l'immagine generica della rarità (bronzo, argento, oro, primed) della cartella icone:
  nessun download da market o wiki. Con la cartella icone impostata, le Archon Shard mostrano solo l'immagine e l'effetto (non il nome del colore).
- Nuova icona del programma: la silhouette di un uomo con i dreadlock, mezzo cibernetico, con un fucile da cecchino, con una piccola W e O.

## 0.2.1
- Nuova icona del programma (una W e una O disegnata come mirino), usata da eseguibile, finestra, barra delle applicazioni
  e tray. È disegnata da `build_icon.py`, quindi si può rigenerare.
- La barra delle applicazioni ora raggruppa e mostra il programma con una sua identità invece di quella di Python.
- Questo changelog; la pagina della release ora mostra le note della sua versione.

## 0.2.0
- **Inventario**: consiglio *Sali di rank…* (quali mod conviene portare a rank massimo per venderle, in base al platino per
  Endo, con costi in Endo e Crediti); *Escludi installate* esclude le mod e gli Arcani che sono in un loadout; bottoni su
  due righe.
- I consigli tengono conto dell'andamento del prezzo (medie a 7/30/90 giorni, colonna *vs 30 g*, impostazione *peso del trend*).
- **Build**: solo i tuoi loadout, disposti come nella schermata del gioco con Archon Shard e Helminth; immagini di mod e
  Arcani (warframe.market, poi la wiki di Warframe); cartella icone facoltativa per le Archon Shard. Rimossi Overframe e i
  creator YouTube.
- Scambi rimasti: avviso quando la sincronizzazione di AlecaFrame è precedente al reset giornaliero.
- Immagini degli oggetti nei suggerimenti delle tabelle.
- Correzione: errore all'avvio `WinError 5` (il processo OCR ora parte come programma normale con connessione locale autenticata).
- Correzione: errore all'avvio `WinError 87` dopo un riavvio o un aggiornamento.

## 0.1.13 e precedenti
Vedi le [release](https://github.com/ZioLadro/wf-vendor-overlay/releases) e la cronologia dei commit.
