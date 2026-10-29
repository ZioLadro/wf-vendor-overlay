# Changelog

Dalla 0.2.1 ogni release elenca qui le sue modifiche (la pagina della release su GitHub mostra la sezione della sua versione).
Versione inglese: [CHANGELOG.md](CHANGELOG.md).

## 0.5.5
- **Cornici delle carte come nel gioco**: disposte sui file veri della wiki: il FrameTop (l'ornamento della rarità) in
  alto, il FrameBottom (la vaschetta curva) in basso, le loro gambe fanno i lati, l'immagine dentro, il drain sul
  riquadro del gioco, le tacche di rank sulla riga di rank. I pezzi vengono chiesti per nome (Bronze / Silver / Gold /
  Legendary / Riven / Galvanized / Peculiar…); le cornici Avionic della Railjack e le luci laterali / d'angolo non sono
  più usate. I pezzi scaricati dalla 0.5.3–0.5.4 vengono sostituiti una volta.

## 0.5.4
- **Le cornici delle carte ora compaiono**: i pezzi sono riconosciuti dalla didascalia sulla pagina della wiki («Rare Mod
  Top Border»…), non solo dal nome del file, e le carte a schermo vengono ridisegnate appena arrivano. La Console dice
  cosa è stato trovato e salvato («mod frames…»); dopo un errore riprova un'ora dopo.

## 0.5.3
- **Build: mod nell'ordine del gioco.** Il gioco numera gli otto slot dal basso a destra (l'ultimo slot del file è in
  alto a sinistra): le carte erano disegnate ruotate. Verificato su una build reale (Cyte-09). Il primo Arcano ora è
  all'altezza della riga di Aura / Stance, come nel gioco.
- **Capacità**: 39 mod mancavano dai dati (contavano 0 di drain): Cull the Weak e le altre nuove mod degli artigli, i
  Bane e i Primed Bane, Mark of the Beast… Polarità, drain base e rank massimo ora vengono dall'export del gioco (DE
  Public Export tramite public-export-plus): Quick Thinking (10 / rank 5), Maglev (rank 5) e Pressure Point (rank 5)
  erano sbagliati.
- **Le cornici delle carte del gioco** nei Build: bordi, sfondo, luci, il riquadro del drain e le tacche di rank per
  rarità (Common … Legendary, Riven, Galvanized, Amalgam, Peculiar), scaricati una volta dalla pagina
  [Mod/Assets](https://wiki.warframe.com/w/Mod/Assets) della wiki. Impostazione *Build: cornici delle carte del gioco*
  (Tema); senza, restano le carte semplici.

## 0.5.2
- **Attività non prende più clic per sbaglio**: il mouse passa attraverso fino al gioco finché non premi **Ctrl+F5** (come
  in AlecaFrame). Sbloccata, si contorna e mostra i pulsanti; di nuovo Ctrl+F5, o pochi secondi dopo che il mouse esce
  (mai mentre è aperto un suo menu), si riblocca. Premuto con Attività nascosta, il tasto la mostra già sbloccata.
  Impostazioni: *Attività e mouse* (combinazione di tasti / quando si vede un cursore / sempre, anche in ⚙ → Mouse),
  *Attività: tasto di sblocco*, *Attività: blocca di nuovo dopo*. Chi aveva spento «cliccabile solo col cursore» resta su
  «sempre cliccabile».
- Le impostazioni rifiutano una scorciatoia che ne contiene un'altra (Ctrl+F6 premerebbe anche F6).

## 0.5.1
- **Correzione**: la 0.5.0 non partiva (si chiudeva subito, senza messaggi): i nuovi font venivano caricati prima che il
  sistema grafico del programma esistesse, cosa che fa andare in crash Qt. Ora vengono caricati quando è pronto.

## 0.5.0
- **Nuovo aspetto**: le sezioni sono una barra laterale a sinistra (come AlecaFrame), riquadri con angoli arrotondati,
  schede piatte sottolineate nel colore d'accento, barre di scorrimento sottili, caselle spuntate nell'accento; il
  carattere dei testi del gioco **Noto Sans** e **Rajdhani** per titoli, schede e intestazioni, entrambi inclusi (SIL Open
  Font License). Il "Segoe UI" salvato diventa Noto Sans.
- **27 temi** (erano 13), ognuno con un accento e un secondo accento: nuovi per la Lotus, il Vuoto, il Drifter, Arbiters
  of Hexis, Cephalon Suda, la Perrin Sequence, Solaris United, gli Holdfasts, Duviri, Höllvania, le Lich Kuva, il
  Mormorio, Scaldra e lo Stalker.
- **Condividi le build** (scheda Build e pianificatore): un codice della build da incollare, un file `.wfbuild`,
  un'immagine della schermata della build (salva o copia); importa un codice o un file nel pianificatore.
- **Riven flip, da Quantframe**: gli scambi di riven letti dal log del gioco entrano da soli nel diario (comprato /
  venduto, col platino); combinazioni di statistiche richieste per arma (★, pannello di dettaglio, filtro).

## 0.4.10
- **Overlay Attività: attività del Mondo** che segui (scheda Mondo > *Segui*): cicli, Baro, Sortita, Caccia all'Arconte,
  l'Arbitrato attuale / il prossimo di un tier, tipi di Fenditure del Vuoto, ricompense delle invasioni, con conti alla
  rovescia aggiornati ogni secondo.
- **Settimanali**: filtro per tipo di offerta (anche più insieme) e per nome; seleziona più offerte per seguirle / smettere
  di seguirle in una volta.
- **Prezzi di Acrithis** (10 Pathos Clamp) e degli altri vendor il cui prezzo è scelto da una lista (Hivemind del
  Necralisk, equipaggio Railjack, commissioni Archimedean…) ora visibili: i dati del gioco li tengono per "bin", non per
  offerta. Le offerte giornaliere mostrano il loro reset.
- **Riven flip, controllo dal vivo**: un'asta che non esiste più (warframe.market risponde 400 "not_exist", non 404)
  viene segnata *non più in vendita* invece di essere richiesta ogni 30 secondi; un controllo fallito aspetta il suo turno.
- **Build**: le arch-melee non venivano lette (i loro loadout mancavano); le mod dei Necramech ora contano nella capacità;
  compaiono le armi dei Necramech (Ironbride, Arquebex); le arch-gun hanno due slot Arcano (il secondo Arcano del
  Mausolon appariva come Exilus) — uno slot che contiene un Arcano viene sempre letto come tale.

## 0.4.9
- **Settimanali, acquisti da identificare**: prima di chiedere viene usato ciò che si sa già. Le offerte col limite sotto
  il numero acquistato, già prese da un altro acquisto del vendor o mostrate in vendita dopo l'acquisto vengono escluse
  (✗); un gruppo di acquisti che può essere solo un insieme di offerte viene assegnato in una volta (i tuoi 4 acquisti da
  10 da Palladino = le quattro reliquie Requiem); le offerte viste esaurite sullo schermo e gli oggetti di negozio nominati
  nel log del gioco contano come prove; "quale NON hai comprato?" risponde per un gruppo intero; l'intestazione mostra
  dove ti mette il log del gioco.
- **Build: immagini delle mod**: dentro le carte l'illustrazione della mod (CDN WFCD), al passaggio del mouse la carta
  intera (wiki). Le immagini salvate dalla 0.4.7-0.4.8 col tipo sbagliato vengono sistemate da sole.
- **Dati delle mod corretti**: quando più mod hanno lo stesso nome (Vital Sense, Intensify, Heavy Impact, Hell's
  Chamber… hanno varianti Beginner / Expert nei dati del gioco) veniva usato il rank massimo della variante (10 invece di
  5), così queste mod contavano meno di quanto fanno al loro rank (82 mod). I tag di danno nei testi delle mod hanno il
  loro nome ("chance to apply Slash on Critical").
- **Armi dei compagni**: 8 slot (ne compariva un 9° vuoto), *Catalizzatore Orokin* invece del Reattore, lo slot degli
  artigli è la *Postura*.
- **Riven flip**: più filtri (prezzo, prezzo equo, profitto, profitto al giorno, punteggio, popolarità in gioco, vendite,
  re-roll, giorni in vendita, venditore online adesso); prezzo equo dai riven con la stessa combinazione di statistiche
  per primi, le copie di un venditore contano una volta; voto del roll (S-D) di ogni statistica nel pannello di dettaglio.

## 0.4.8
Riven flip:
- **Scambi in gioco settimanali di DE** (`weeklyRivensPC.json` ufficiale, verificato: ancora pubblicato ogni settimana;
  archivio della comunità come riserva): nuova colonna *In gioco* e terza parte del prezzo equo.
- **Pesi delle statistiche per arma**: le armi critiche, da stato e da taglio valutano le loro statistiche; negativi
  innocui sui tipi di danno fisico minori.
- Colonna e ordine **Profitto al giorno** (profitto / giorni attesi per vendere).
- **Diario** dei flip: comprato, in vendita (visto dalle scansioni), venduto (visto quando la tua inserzione sparisce, o
  a mano), profitto e giorni; le tue rivendite correggono il prezzo equo.
- **Ordine di scansione più furbo**: armi seguite riscansionate entro 2,5 giorni; prima quelle che vendono, danno affari
  o si scambiano molto.
- **Avvisi** (suono + Console) per affari sopra un profitto con il venditore online; facoltative le aste su cui fare
  offerte.
- **Pannello di dettaglio** (parti del prezzo equo, riven confrontabili, grafico dello storico), filtri per tipo / arma,
  segno di contattato, nascondi arma / venditore.
- **Verifica del prezzo equo**: di quanto sbaglia sui riven probabilmente venduti.

## 0.4.7
- **Dove ti trovi, dal log del gioco** (`EE.log`, solo in lettura): un vendor che si trova in un solo luogo (Cetus,
  Fortuna, il Necralisk / Sanctum, il Chrysalith, Höllvania, Iron Wake, Duviri, il campo del Drifter, Simaris e Baro in
  un Relay) non viene più riconosciuto dall'OCR mentre sei altrove, né per i prezzi né per il controllo Settimanali; in
  missione o in un open world non parte nessuna scansione automatica. Teshin, i sindacati dei Relay, Nightwave e gli
  eventi contano ovunque.
- **Riconoscimento del vendor più rigido**: il 75 % degli oggetti letti deve essere di un vendor (era 60 %; nuova
  impostazione *Quota degli oggetti*), oltre al controllo del luogo.
- **Riven flip, controllo dal vivo**: i 10 affari migliori vengono ricontrollati su warframe.market ogni ~3 minuti, una
  richiesta per affare: la colonna *Venditore* mostra se il venditore è in gioco / online adesso, e i riven non più in
  vendita. Limitatore proprio (6 al minuto, mai più di 10), in pausa durante le scansioni dei riven; 15 minuti di stop
  dopo ripetuti "troppe richieste".
- **Build: armi dei compagni**: le armi di Sentinelle / MOA / Hound venivano lette come compagni, gli artigli delle
  bestie erano saltati: ora compaiono entrambi con le loro mod (gli artigli con lo slot Postura).
- **Barra del giocatore**: crediti tracciati, emblema del grado di maestria più piccolo davanti all'MR, immagine del
  profilo in un riquadro accanto al nome, valute dal bordo sinistro del riquadro; Impostazioni > Generali > *Valute
  mostrate* sceglie quali. "230k" non appare più come "23k".
- **Mondo > Arbitrati**: le prossime 72 ore (programma di browse.wf) con nodo, missione, fazione e tier di arbi.guide,
  filtro per tier.
- **Impostazioni riorganizzate**: *Overlay* e *Overlays* sono una sola scheda; ogni scheda divisa in riquadri con un
  nome; molti nomi resi più chiari (le voci degli overlay perdono i prefissi "Overlay prezzi:" / "Attività:", ora titoli
  dei riquadri).
- **Immagini degli oggetti da cdn.warframestat.us** (immagini WFCD): una richiesta per immagine, provata prima della wiki
  per la scheda Build e quando warframe.market non ha l'immagine.

## 0.4.6
- **Statistiche dei Warframe al rank 30**: salute, scudi ed energia partivano dai valori al rank 0 dei dati pubblici;
  ora vengono aggiunti i guadagni dei rank (+100 salute, +100 scudi, +50 energia al rank 30, distribuiti sui rank
  inferiori). Cyte-09 con la tua build: 325 / 235 / 150 / 655, 226 % / 45 % / 34 % / 298 %, come nel gioco.
- **Mod sotto il rank massimo**: una mod dà (rank + 1) / (rank massimo + 1) del suo effetto, come nel gioco (Serration
  +15 % al rank 0); era contata come rank / rank massimo (0 al rank 0, troppo poco a ogni rank sotto il massimo). Build e
  pianificatore.
- **Valori fissi**: Primed Reach e simili (+3 portata) ora si sommano alla portata in mischia.
- Le statistiche vengono troncate, non arrotondate, come le mostra il gioco (655,5 -> 655).
- **Frammenti Archon nelle statistiche**: Cremisi (potenza, durata +10 %) insieme alle mod, Azzurri (salute / scudi /
  armatura +150, energia +50) dopo ogni altro bonus, Tauforgiati ×1,5; niente scudi per Inaros / Nidus / Kullervo,
  niente energia per Hildryn / Lavos. Build e pianificatore (5 slot frammento sotto le opzioni; *Copia dal mio
  equipaggiamento* porta i tuoi).
- **Perk Incarnon nelle statistiche delle armi**: i perk scelti dall'Evoluzione II in su vengono letti dalla pagina wiki
  dell'arma (danno, probabilità critico / stato, moltiplicatore critico, cadenza, caricatore, ricarica, portata…, con i
  valori per variante come "(Prisma)"); gli effetti con una condizione (con colpo alla testa, dopo un'uccisione…) sono
  esclusi. Il pannello statistiche elenca i perk contati.

## 0.4.5
- **Capacità corretta per gli slot segnati `AP_UNIVERSAL`**: il file di gioco lo scrive sugli slot senza polarità (uno
  slot Exilus mai formato), ed era contato come polarità universale che dimezza il consumo di ogni mod. Universale è
  solo `AP_ANY` (la Forma Aura). Cyte-09 con Sure Footed rank 3 nell'Exilus: 6 / 74 come nel gioco (diceva 10).

## 0.4.4
- **Le icone di AlecaFrame nella schermata build** (cartella icone, `img/builds` e `img/damageTypes`): un'icona per
  ogni statistica (salute, scudi, armatura, energia, scatto, statistiche delle abilità, cadenza, multicolpo, caricatore,
  ricarica, critico, status) e ogni tipo di danno, l'icona dell'elemento bonus; le immagini di Forma, Reattore /
  Catalizzatore Orokin, adattatori Exilus e Arcano accanto al titolo (sbiadite se non installati) e sugli interruttori
  del pianificatore; gli slot Aura / Exilus / Postura vuoti mostrano la loro immagine e uno slot Arcano vuoto il
  contorno di AlecaFrame; titoli Frammenti Arconte ed Helminth con la loro icona. Icone di Steel Essence e Pathos Clamp
  nella barra del giocatore. Senza la cartella tutto resta com'era.

## 0.4.3
- **Aya contati come fa AlecaFrame**: l'oggetto Aya tra le tue risorse (`SchismKey`); quello che prima appariva come
  Aya (il campo `PrimeTokens`) sono gli Aya Regali, ora mostrati come tali. *Aya (scritti a mano)* serve solo quando il
  file non ne ha.
- **Attività: comprimere una categoria**: un clic sul titolo di un sindacato, Settimanali, Nightwave, Calendario,
  Giornaliere e settimanali o Acquistati di recente la riduce al titolo (▸) o la riapre (▾); ricordato tra una sessione
  e l'altra.
- **Capacità**: ora conta la polarità propria dello slot Exilus dei Warframe che ce l'hanno (Gauss, Hildryn, Baruuk,
  Inaros…). Il tooltip della capacità elenca ogni slot: polarità e da dove viene (Forma nel file di gioco o propria
  dell'oggetto), mod, rank, consumo. **Copia i dati per un controllo della capacità** (Build) copia cosa dice il file di
  gioco sull'oggetto e come è stato letto, per segnalare una capacità diversa da quella del gioco.
- Icona degli Aya nella barra del giocatore.

## 0.4.2
- **Arcani disegnati come nel gioco** (Build e pianificatore): senza carta, l'immagine generica della rarità
  dell'Arcano, il nome centrato sotto, il rank come ◈ / ◇. Solo gli slot Arcano che l'oggetto può avere; uno slot vuoto
  mostra il contorno di un Arcano, con un 🔒 quando non è sbloccato (un'arma senza adattatore Arcano, dal file di gioco).
- **Tooltip con l'effetto al rank** su ogni mod e Arcano (slot e libreria): cosa fa al suo rank e al rank massimo, dai
  moduli dati della wiki (letti una volta in background, tenuti in `wiki_mods.json`); i rank più bassi ricavati dai dati
  del gioco, usati anche finché la wiki non è stata letta.

## 0.4.1
- **Settimanali: controllo sullo schermo del vendor tarato su schermate vere** (Palladino, Archimedean Yonta, Acrithis,
  Kaya Velasco, Flare Varleon, Teshin): un'offerta con **PURCHASE LIMIT REACHED** sulla carta viene letta come esaurita
  (il gioco la lascia nella lista); le quantità scritte prima del nome vengono capite ("35.000 X Kuva", "150,000
  Credits", "6.000 Endo"); i nomi su due righe e le parole che l'OCR attacca ("Requiem IRelic") vengono riconosciuti; le
  reliquie Requiem sono riconosciute col nome che mostra il gioco (anche nella scheda Settimanali); nomi vicini (Requiem
  I / II Relic) non vengono più confusi; il vendor nominato nell'intestazione (letta in modo tollerante: l'OCR spesso ne
  tiene solo una parte) decide di quale vendor cercare le offerte.
- **Incarnon**: l'Evoluzione V compare solo sulle armi che ce l'hanno (Incarnon integrata); le armi con Genesis mostrano
  i loro quattro livelli (decide la tabella della wiki quando è stata letta). Il livello di evoluzione del pianificatore
  si adegua.

## 0.4.0
- **Build: disposte come la schermata potenziamenti del gioco.** *POTENZIAMENTI / OGGETTO [rank]* con il numero di
  Forma, le schede delle configurazioni (Config A, B, C…), la barra della capacità (rimasta / totale, come la mostra il
  gioco) e le statistiche a sinistra, Aura / Postura / Exilus sopra le otto mod, gli Arcani (e l'Exilus delle armi da
  fuoco) a destra, la riga *Tratto unico* delle armi Kuva / Tenet / Coda. Carte orizzontali come quelle del gioco:
  immagine dietro il nome, consumo e polarità, rank a pallini, cornice del colore della rarità.
- **Statistiche delle armi** in Build e nel pianificatore: cadenza / velocità d'attacco, multicolpo, caricatore, ricarica,
  probabilità e danno critico, status, ogni tipo di danno con gli elementi combinati nell'ordine delle mod (l'elemento
  bonus Kuva / Tenet / Coda contato come proprio dell'arma), totale e un danno al secondo approssimato, *base ▸ con le mod*.
- **Pianificatore: un simulatore.** Una libreria di mod sotto la build (ricerca, filtro per polarità, ordinamento, *Solo
  le mod che possiedo* con le copie che hai); clicca uno slot e poi una mod, o trascina una mod su uno slot; le mod che il
  gioco non lascia combinare vengono rifiutate. Clic destro su uno slot per rank, polarità (Forma) e rimozione.
  Interruttori per Reattore / Catalizzatore Orokin, adattatori Exilus e Arcano (gli slot bloccati mostrano 🔒), elemento
  bonus e percentuale Kuva / Tenet / Coda (Fusione di valenza), Incarnon Genesis e livello di evoluzione, con il perk di
  ogni livello scelto sul percorso di evoluzione. Configurazioni A, B, C… per oggetto; *Azioni*: copia / rinomina /
  elimina una configurazione, togli tutte le Forma, Forma ogni slot alla polarità della sua mod. Gli slot Exilus prendono
  solo mod Exilus. Si possono pianificare anche le armi dei compagni (armi robotiche, artigli delle bestie con la loro
  postura). I piani delle versioni precedenti si aprono com'erano.
- **Simula nel pianificatore** (Build): apre l'oggetto mostrato, con tutte le sue configurazioni, nel pianificatore.
- **Incarnon**: i livelli di evoluzione disegnati come un percorso (ogni perk, quelli scelti illuminati e uniti). I nomi
  dei perk vengono letti dalla tabella delle evoluzioni della pagina wiki (prima la pagina renderizzata, poi il
  wikitext), sia righe *EVO1…* sia righe *Evolution I…*, anche con l'etichetta del livello su più righe; il livello I
  delle armi integrate (senza nome del perk sulla wiki) è mostrato come forma Incarnon. Le pagine lette dal vecchio
  lettore vengono rilette da sole, così spariscono le "opzione 1 / 2" rimaste.
- **Settimanali: controllo sullo schermo del vendor.** Mentre un vendor viene scansionato vengono lette anche le offerte
  limitate che elenca: un'offerta esaurita sparisce dalla lista. Un'offerta ancora elencata viene esclusa per un acquisto
  da identificare (e un acquisto attribuito a lei per errore viene chiesto di nuovo); una sparita rispetto a uno sguardo
  precedente in questo periodo (non uno scorrimento: il resto della lista è rimasto fermo) identifica l'acquisto, o viene
  mostrata acquistata **(OCR)** finché il file di gioco non si aggiorna.
- **Attività: cosa puoi comprare entro il reset.** Lo standing che puoi ancora guadagnare oggi (limite giornaliero, mai
  oltre quanto ne tiene il tuo rank) viene speso come quello che hai: *Entro il reset: compra 2× Martyr Symbiosis
  (guadagnane altri 13.000)*, in azzurro, con il tempo che manca alle 00:00 UTC. Colore e attivazione nelle Impostazioni.
- **Kuva** nella barra del giocatore, con la sua icona.

## 0.3.9
- **Perk Incarnon letti di nuovo**: la tabella delle evoluzioni della wiki (righe *EVO1…EVO5*) ora viene capita, quindi
  Build mostra il perk scelto in ogni livello (Torid: Incarnon Form, Final Fusillade…); le pagine fallite prima vengono
  rilette.
- **Build: l'arma giusta per ogni companion**: tutti i companion mostravano la stessa arma; ora Sentinelle / MOA mostrano
  la loro arma robotica e le bestie i loro artigli.
- **Barra del giocatore: più valute, con icone**, sotto nome e MR: Pathos Clamp, Riven Sliver, Live Heartcell e Vitus
  Essence accanto a Steel Essence, ognuna con la sua icona di gioco (cartella icone di AlecaFrame, altrimenti browse.wf).
- **Settimanali: le tue valute** per i vendor mostrati (Steel Essence per Teshin, Pathos Clamp per Acrithis, Riven Sliver
  per Palladino…).
- **Suoni**: suono opzionale quando parte una scansione di vendor, riven o prezzi (Impostazioni → Suoni).
- **Riven flip: Copia whisper** (clic destro): `/w <venditore> Hi, I would like to buy <arma> <riven> for <prezzo>
  platinum`, modello modificabile nelle Impostazioni.

## 0.3.8
- **Attività: compra con tutto il tuo standing**: lo standing di ogni sindacato va ai suoi oggetti migliori, quante
  copie ne paga (*Compra 2× Martyr Symbiosis (20.000 standing)* con 27.000), il resto all'oggetto dopo, mai più copie di
  quante il mercato ne prende in un giorno. Un oggetto comprato resta in lista per domani (impostazione *Attività: tieni
  un oggetto dopo averlo comprato*).
- **Acquisti di Attività → Quantframe**: ogni acquisto che Attività conferma dal file di gioco viene tenuto; *Acquistati
  (Attività) → Quantframe…* (scheda Settimanali, e menu ⚙ di Attività) invia allo stock di Quantframe quelli non ancora
  inviati. (Sostituisce il pulsante della 0.3.6, che inviava tutti gli acquisti settimanali.)
- **Pianificatore build: loadout interi**: Warframe, armi, compagno, Archwing, Arch-gun e Arch-melee in un solo piano,
  salvati insieme; *Copia da un mio loadout…* copia un loadout di gioco intero. Aggiunti ai dati inclusi oggetti e mod di
  compagni, Archwing, Arch-gun e Arch-melee.
- **Build: più dati dal file di gioco**: i nomi che dai agli oggetti, lente Focus, elemento bonus Kuva / Tenet / Coda e
  percentuale, dorata, slot Exilus / Arcano sbloccati, Fusione di valenza.
- **Settimanali: vendor degli eventi solo mentre l'evento è in corso** (Jade Shadows, Duviri Murmur, Triad…, dal world
  state di DE; *Mostra eventi finiti* per vederli comunque); le loro offerte escono anche da Attività.
- **Steel Essence** nella barra del giocatore.
- **Scansione automatica dei riven attiva di default** (ogni 6 ore) e **mai insieme a un aggiornamento dei prezzi**: il
  secondo aspetta il primo (uno automatico riprova più tardi), così non si superano i limiti di warframe.market.
- **Profilo spostato nelle Impostazioni** (una sua pagina), e una nuova pagina **Overlay**: dimensioni, sfondo e colori
  delle etichette dell'overlay prezzi; sfondo, carattere, colori e contenuti di Attività.

## 0.3.7
- **Le blueprint non vengono più valutate come l'oggetto finito**: un vendor che vende una blueprint (Purified Heciphron
  Blueprint, Zymos Blueprint…) veniva abbinato all'oggetto finito su warframe.market quando la blueprint non è
  scambiabile, e così era consigliata al prezzo dell'oggetto. Ora una blueprint conta solo come sé stessa, sia negli
  elenchi dei vendor sia nel tuo inventario; solo le parti Prime (i cui oggetti sul mercato sono le blueprint) tengono il
  nome dell'oggetto come alternativa.
- **Build: sezione Incarnon**: adattatore Genesis installato / integrata / su un'altra variante, livello di evoluzione
  raggiunto e perk scelto in ogni livello (dal file di gioco), nomi dei perk e immagine dalla pagina wiki dell'arma; il
  livello compare anche sotto il titolo.
- **Niente più finestre bianche**: la barra del mondo veniva mostrata prima di essere messa nella finestra, e si apriva
  per un attimo come finestra separata (bianca); i widget tolti da un layout ora vengono nascosti prima di essere
  eliminati invece di essere staccati.
- Nomi dei perk Incarnon: quando il wikitext della pagina richiama solo un template, viene letta la pagina renderizzata;
  una pagina che ancora non si riesce a interpretare viene salvata nella cartella `incarnon_debug` della cartella dei dati.

## 0.3.6
- **File di AlecaFrame letto una volta, in background**: ogni scheda controllava, decifrava e analizzava `lastData.dat`
  per conto suo sul thread della finestra ogni volta che AlecaFrame lo riscriveva. Ora un solo controllore aspetta che il
  file abbia finito di cambiare, un thread in background lo decifra e analizza una volta (niente se il contenuto è
  identico) e fa lì il lavoro di ogni scheda (abbinamento dell'inventario, standing, loadout, acquisti settimanali); la
  finestra mostra solo i risultati. La Console dice quanto ci ha messo.
- **Settimanali: Acquistati → Quantframe…** invia allo stock di Quantframe ciò che hai comprato dai vendor a limite in
  questo periodo.
- **Barra del giocatore: glifo del profilo ed emblema del grado di maestria** (immagini da browse.wf, scaricate una volta).
- **Attività: scambi rimasti oggi** nella sezione giornaliere e settimanali.
- **Via i prezzi a rank massimo che non significano nulla**: mod con solo 3 rank il cui rank massimo vale al massimo 3p
  più del rank 0, e rank massimi scambiati meno di *Prezzo a rank massimo: scambi minimi al giorno* (media di 7 giorni,
  default 0,5): il prezzo a rank massimo non viene mostrato né contato (overlay, listino, valore dell'inventario,
  consigli di rank up e vendita).
- **Prezzi vecchi aggiornati da soli**: le righe di listino e consigli più vecchie di 2 ore (impostazione *Aggiorna i dati
  più vecchi di (ore)*) vengono aggiornate automaticamente, 150 alla volta, prima i consigliati e i più vecchi.
- **Consigli e consigli di vendita con segnali di trading** (`signals.py`): prezzo di vendita atteso dalla media a 30
  giorni, un andamento EMA 7 / EMA 30, la calibrazione da backtest dell'oggetto e il miglior ordine di acquisto online
  (bid); colonna *Andamento* con *vendi ora* (in calo o picco di Bollinger) / *aspetta* (in salita), e colonna *Segnale*
  nei consigli di vendita.
- **Riven flip: età delle inserzioni**: colonna *In vendita da* (data di creazione su warframe.market); le inserzioni più
  vecchie di 14 giorni (impostazione) non sono mostrate come affari e quelle più vecchie di 28 sono escluse dal prezzo
  equo, che ora conta anche le inserzioni dei venditori offline.

## 0.3.5
- **Completamento di Nightwave letto dal posto giusto**: *SeasonChallengeHistory* nel file di gioco elenca tutte le sfide
  che ti vengono assegnate (le elite della settimana ci sono prima che tu le faccia), quindi segnava tutto come fatto. Ora
  il completamento viene dai contatori delle sfide (*ChallengeProgress*) confrontati con quanto richiede ogni sfida;
  quelle non finite mostrano l'avanzamento (14/15). La Console elenca cosa è stato letto.
- **Sfide giornaliere di Nightwave** (☼) elencate anche loro, con il tempo rimasto; la sfida attiva del Calendario mostra
  l'avanzamento.
- **Netracells** nella sezione giornaliere e settimanali (fatte su 5 questa settimana, dal file di gioco).

## 0.3.4
- **Completamento di Nightwave corretto**: una sfida conta come fatta quando il suo id è nella cronologia del file di
  gioco, oppure quando c'è la stessa sfida con un id della stessa stagione e settimana (world state e file possono
  scrivere gli id in modo diverso; vengono letti anche gli id `$id`). La Console dice quante sfide attive risultano fatte
  e quali id sono stati confrontati.
- **Attività: sezione giornaliere e settimanali**: Sortie e Caccia all'Arconte (missioni fatte su 3, dalle missioni che il
  file di gioco elenca come completate), Elite Deep / Temporal Archimedea (iniziata e punteggio; se è finita il file non
  lo dice: (?), clic destro per spuntarla a mano fino al reset) e Descendia (piani raggiunti, normale e Percorso
  d'Acciaio). Impostazione *Attività: Sortie, Caccia all'Arconte, Archimedea, Descendia* e opzione in ⚙.

## 0.3.3
- **Riven flip: storico e andamento dei prezzi.** Ogni scansione registra, per arma e per giorno, il prezzo mediano
  richiesto, il più basso e il numero di inserzioni (180 giorni), mostrati nella nuova colonna *Andamento* (7 / 30
  giorni). Un'arma i cui prezzi scendono ha il prezzo equo abbassato della discesa (⚠), così le armi in calo non
  sembrano affari.
- **Riven flip: prezzo equo dalle probabili vendite.** Le inserzioni che spariscono entro 5 giorni dalla pubblicazione
  vengono tenute con prezzo e statistiche (30 giorni); con almeno 3 confrontabili il prezzo equo si basa su di esse
  (✔, tooltip con le due cifre e quanto restano in vendita i riven di quell'arma).
- **Riven flip: scansioni programmate** ogni N ore mentre il programma è aperto (impostazione *Scansiona da solo ogni
  (ore)*, 0 = spento; la scheda mostra quando tocca alla prossima).
- **Attività: dove comprare.** Sotto ogni oggetto da comprare, il personaggio e il luogo che lo vendono (⌖ *Hok, Cetus*
  per i pezzi Zaw e gli arcani Exodia, *Rude Zuud, Fortuna* per i pezzi dei kitgun e gli arcani Pax, *Father,
  Necralisk* per le armi Entrati, *qualsiasi Relay* per i sindacati delle fazioni…). Impostazione *Attività: dove
  comprare* e opzione in ⚙.
- **Attività: obiettivi di Nightwave e Calendario a colpo d'occhio.** Ogni sfida mostra il suo obiettivo su una riga
  breve sotto il nome (*Uccidi 1.000 Nemici ne Il Percorso d'Acciaio*), nella lingua del programma (nomi e descrizioni
  italiani presi dai testi italiani del gioco).

## 0.3.2
- **Attività: cliccabile con il cursore del gioco.** In molti menu Warframe nasconde il cursore di Windows e disegna il
  suo, quindi l'overlay credeva che fossi in missione e lasciava passare ogni clic. Ora diventa cliccabile anche quando il
  cursore ci arriva sopra muovendosi liberamente (in missione la telecamera tiene il cursore nascosto fermo e confinato,
  quindi lì i clic vanno ancora al gioco).
- **Nightwave e Calendario 1999 di nuovo letti**: Digital Extremes ha spostato il world state su
  `api.warframe.com/cdn/worldState.php` (il vecchio indirizzo risponde 404); il vecchio resta come riserva, e la Console
  indica l'errore di ciascuno.
- **Codice sorgente riorganizzato** in cartelle: `app/core`, `app/scan`, `app/trade`, `app/game`, `app/ui`, con i dati
  inclusi in `data/`, l'icona in `assets/` e i generatori di dati in `tools/` (vedi *Struttura del progetto* nel README).
  Per te non cambia nulla: stesso programma, stessa cartella dei dati.

## 0.3.1
- **La finestra di aggiornamento mostra cosa è cambiato**: tutte le versioni tra quella che hai e la nuova (dalla più
  recente, dal changelog nella tua lingua), in un elenco scorrevole sopra Installa / Più tardi / Salta.
- **Stelle dell'overlay**: *★ Migliore qui ★* ora è il miglior acquisto tra **tutti** gli oggetti del vendor che stai
  guardando (non solo le righe a schermo; se è fuori vista lo nomina la riga di stato), e *★ Consigliato ★* segna gli
  oggetti tra i migliori acquisti **di tutti i vendor** (la classifica dei Consigli).
- **Piano standing rinominato *Attività*** (titolo dell'overlay, impostazioni, tray, tasto).
- **Attività: Nightwave e Calendario 1999**: le sfide settimanali di Nightwave (elite segnate ★, standing indicato,
  giornaliere aperte contate) e le sfide della stagione corrente del Calendario 1999 (quella in corso segnata), lette
  dal world state pubblico di Digital Extremes (content.warframe.com, ogni 10 minuti, copia salvata se offline). Il
  completamento viene da lastData.dat: Nightwave dall'id della sfida in *SeasonChallengeHistory* (esatto), il Calendario
  da *CalendarProgress* (giorni fino all'ultimo completato). Impostazione *Attività: Nightwave e Calendario 1999* e opzione in ⚙.
- **Consigli rivisti**: il punteggio ora è *~plat al giorno*: prezzo × le copie che compra un giorno di standing (limite
  16.000 + 500 × Mastery Rank), ma non più di quante ne assorbe il mercato (≈ ¼ del volume 24 h); un prezzo sopra la
  media a 30 giorni viene avvicinato a essa, come nei consigli dell'inventario; gli oggetti che richiedono un rank del
  sindacato più alto del tuo contano la metà (⚠). Il piano standing usa la stessa classifica.
- **Consigli dell'inventario**: *Vendi* e *Rank up* non penalizzano più due volte gli oggetti poco scambiati (le copie
  vendibili seguono già il volume).
- **Nascondi Operational Supply** (impostazione, attiva di default): il sindacato degli eventi (Plague Star e altri) è
  escluso da listino, consigli, stelle dell'overlay, piano standing e barra del giocatore finché non c'è un evento.
- **Piano standing in stile quest tracker**: niente pannello pesante (una banda leggera che sfuma a destra), titoli dei
  sindacati in oro con **?** (qualcosa da comprare ora) o **!** (standing ancora da guadagnare), obiettivi in bianco,
  quelli pronti in verde, come guadagnare lo standing in grigio, ogni testo con contorno per leggerlo sopra il gioco.
- **Scheda Settimanali: offerte limitate dei vendor** (offerte Steel Path di Teshin, Ironwake, Nightcap, Archimedean,
  Acrithis, vendor degli eventi…; dai dati del gioco, `weekly.json` creato da `build_weekly.py`): costo, limite, quanti
  ne hai comprati in questo periodo e quando si azzera, con filtro per vendor, solo settimanali, solo seguite. Gli
  acquisti vengono da lastData.dat; siccome il file non dice quale offerta è stata comprata, il programma guarda cosa
  AlecaFrame ha registrato come guadagnato in **deltas.dat** (l'ultima missione o visita, oggetto per oggetto: vince
  l'offerta il cui oggetto è arrivato esattamente nella sua quantità, es. Kuva +10.000 = l'offerta ×10.000) e l'inventario
  rispetto alla sync precedente, e la assegna quando una sola offerta torna; altrimenti te lo chiede, con prima le offerte il cui oggetto è aumentato (★) e l'ultimo luogo in cui sei
  stato come indizio. Le risposte valgono fino al reset del limite.
- **Piano standing: sezione settimanale** con le offerte che segui (acquistate/limite, conto alla rovescia del reset) e
  gli acquisti da identificare (clic per scegliere). **Segui / non seguire** dall'overlay: clic destro su un'attività,
  sul titolo di un sindacato o su un'offerta settimanale; impostazioni *Piano standing: segui/non seguire col clic
  destro*, *offerte settimanali* e *attività seguite* (un elenco da spuntare, sindacato per sindacato).
- **Piano standing cliccabile solo col cursore**: in missione Warframe nasconde il cursore, e il piano lascia allora
  passare ogni clic al gioco (i suoi pulsanti spariscono); torna utilizzabile appena il cursore ricompare (menu, console,
  vendor). Impostazione *Piano standing: cliccabile solo col cursore* (attiva di default), anche in ⚙.

## 0.3.0
- **Overlay piano standing** (in gioco, F6 lo mostra/nasconde; impostazione *Tasto piano standing*): una piccola
  finestra sempre in primo piano con gli acquisti suggeriti dai Consigli, divisi per sindacato, con il tuo standing, il
  rank e quanto resta del limite di oggi; per ogni oggetto quanti puoi comprarne adesso o quanto standing manca (e il
  rank richiesto); per i sindacati in cui manca standing, cosa lo fa guadagnare (taglie, missioni col sigillo,
  Medaglioni, gettoni…).
  - **Interattivo e spostabile**: trascina la barra del titolo, ridimensiona dall'angolo, comprimilo (doppio clic sul
    titolo), chiudilo; ⚙ imposta opacità, dimensione del testo, quanti acquisti, uno per vendor, mostra le attività,
    solo i sindacati in cui manca standing. Posizione, dimensione e opzioni vengono ricordate. Clic destro su un oggetto
    per nasconderlo o aprirlo su warframe.market.
  - **Si aggiorna col file di gioco**: viene riletto ogni volta che AlecaFrame riscrive lastData.dat (standing e
    inventario).
  - **Gli acquisti vengono verificati prima di togliere un oggetto dalla lista**: il programma ricorda quante copie
    avevi quando l'oggetto è entrato in lista e lo toglie solo quando il file di gioco mostra una copia nuova
    (*Acquistati di recente* tiene gli ultimi). Spuntare un oggetto lo segna solo come "comprato? in attesa del file di
    gioco". *Mostra di nuovo nascosti e acquistati* azzera.
  - La sua area non viene mai letta dall'OCR, e mostrarlo non toglie il focus al gioco.
  - **Si spegne sui vendor**: appena l'OCR riconosce un vendor il piano si spegne, e resta spento finché non lo
    riaccendi col tasto rapido (F6).
  - **Conta lo standing che puoi ancora guadagnare**: ogni sindacato mostra quanto è guadagnabile oggi sul limite
    giornaliero (16.000 + 500 × Mastery Rank; di nuovo tutto il limite dopo il reset delle 00:00 UTC), e ogni oggetto dice
    se lo standing che manca è raggiungibile oggi o quanti giorni servono al limite giornaliero. Oggetti e sindacati sono
    ordinati per quello che puoi comprare prima.

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
