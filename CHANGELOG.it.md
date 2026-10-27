# Changelog

Dalla 0.2.1 ogni release elenca qui le sue modifiche (la pagina della release su GitHub mostra la sezione della sua versione).
Versione inglese: [CHANGELOG.md](CHANGELOG.md).

## 0.2.2
- **Build**: nuova vista *Loadout di gioco* che segue la schermata dei loadout del gioco: i tuoi loadout con nome, con
  Warframe, primaria, secondaria, mischia e arma esaltata, il compagno, l'Archwing e il Necramech (con rank, i nomi che
  hai dato e la configurazione di mod usata da ogni loadout). Clicca una riga per vedere mod, Arcani, Archon Shard e
  Helminth. La lista precedente resta come *Per oggetto*. Letto dal file di AlecaFrame; scuola di Focus e K-Drive non sono mostrati.

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
