# Folder Image Iterator — design approvato

Data: 17 novembre 2026. Stato: approvato; sviluppo autorizzato nella conversazione del 17 novembre 2026.

## Obiettivo e decisioni confermate

Nuovo nodo **Folder Image Iterator**, categoria **Iridio Nodes**. Sorgente: cartella sul server ComfyUI, anche su RunPod; nessun caricamento delle immagini dal browser. Ogni esecuzione emette una sola immagine. Dopo l'ultima si riparte dalla prima, come Sequential Prompt File. Accento Evoluzione **#90F208**, RGB 144/242/8, verificato nella variabile `--ground-color-primary` del CSS di https://evoluzione.agency/.

L'utente ha chiesto piano e mockup prima dello sviluppo. Le scelte successive sono state approvate dall'utente insieme al piano e al mockup, prima dell'implementazione.

## Approcci

- Estendere Pixaroma: riusa l'interfaccia ma accoppia Iridio a dettagli privati e aggiornamenti di un altro plugin.
- **Proposta: nodo autonomo Iridio**, con interazione ispirata a Pixaroma e avanzamento basato sul nodo stringa esistente. Nessuna dipendenza runtime da Pixaroma. Se si riusa codice sostanziale, conservarne copyright e licenza MIT in `THIRD_PARTY_NOTICES.md`.
- Contatore globale nel backend: scartato, perché client, nodi e workflow finirebbero per condividere una sequenza implicita.

## Esperienza proposta

Interfaccia in inglese, coerente con il nodo stringa. Percorso editabile, pulsante **Browse** che esplora il filesystem del server dentro il browser, **Select images**, **Refresh**, selezione multipla con miniature e **Select all / Clear**. Nessun dialogo nativo del sistema: non risolverebbe la selezione su RunPod.

Ordine naturale deterministico per nome, numeri ordinati numericamente, spareggio sul nome originale; la sequenza memorizza l'ordine esplicitamente. La versione iniziale considera solo i file direttamente nella cartella. Selezionare o togliere immagini non cambia l'ordine; confermare una selezione diversa, cambiare cartella o applicare Refresh riporta Next image a 1, con indicazione prima della conferma. Annullare lascia intatto lo stato precedente.

**Next image** è editabile, indice da 1, **Reset to 1** agisce sui futuri invii. Anteprima e nome della prossima immagine separati dall'indicazione **Last executed**. Prima dell'esecuzione non si mostra un'immagine come già elaborata. Browse e Select images usano bozze locali fino alla conferma.

Refresh rilegge i file senza cambiare i job già accodati; conserva le selezioni esistenti, evidenzia quelle mancanti e richiede una selezione valida prima di confermare. Le nuove immagini non vengono aggiunte automaticamente alla selezione. Aprire la galleria può aggiornare l'elenco visibile ma non applica implicitamente modifiche alla sequenza.

Accento #90F208 su azione primaria, selezioni e dettagli del nodo; testo scuro sul verde. Tema chiaro/scuro, focus visibile, controlli da tastiera, etichette testuali per selezione, errori annunciati. Il nodo rimane compatto: galleria solo quando richiesta. Mockup illustrativo con sei immagini fittizie, non screenshot di un nodo funzionante.

## Contratto di esecuzione

- Un invio riuscito alla coda riserva la posizione e avanza il contatore del nodo nel browser; un invio rifiutato non avanza. Annullare un job già accodato consuma la posizione; un errore di esecuzione non riavvolge gli invii successivi.
- Esempio: 50 immagini e 100 invii producono `1…50, 1…50`. Il nodo non crea autonomamente 100 job: si usa il numero di run della coda ComfyUI. Un click con una sola run elabora una sola immagine.
- Ogni richiesta fissa cartella, lista ordinata e indice. Il backend riduce il job al solo file scelto prima di metterlo in coda, conservando indice/totale originali come metadati. Reset, nuove selezioni e modifiche al workflow non toccano i job precedenti.
- Si fissa il **percorso**, non una copia dei byte: il file viene letto al momento dell'esecuzione. Se modificato nel frattempo, si legge la versione corrente. Nessuna promessa di snapshot dei contenuti.
- Output scalari, mai OUTPUT_IS_LIST: `image: IMAGE`, `mask: MASK`, `width: INT`, `height: INT`, `filename: STRING` senza estensione, `index: INT`, `total: INT`, `path: STRING` assoluto risolto. Immagine con batch 1; maschera nello stesso formato spaziale. I nodi successivi possono comunque creare batch propri.
- PNG/JPEG/WebP/BMP/TIFF/GIF; primo frame o prima pagina soltanto. Orientamento EXIF, RGB normalizzato, alpha invertita secondo la convenzione MASK; senza alpha maschera zero. Definire e testare la conversione a 8 bit dei formati interi a 16 bit senza overflow. Nessun resize implicito.
- Cache: l'iteratore deve rieseguire anche con una sola immagine o dopo un giro completo; `fingerprint_inputs = NaN`, come il nodo stringa. Non conservare tensori in stato persistente.
- File mancante, illeggibile o fuori dalle cartelle consentite: errore chiaro per quel job, senza saltare silenziosamente alla prossima immagine. Non si promette di arrestare gli altri job già in coda: questo dipende dalla coda ComfyUI.
- Il nodo non salva risultati: un Save Image collegato viene eseguito nella stessa run; la prova di accettazione deve mostrare il primo file salvato prima della seconda elaborazione.
- Due nodi o due browser mantengono contatori indipendenti. Non è un sistema di assegnazione esclusiva dei file. Client API senza frontend forniscono esplicitamente selezione e indice.

## Filesystem e RunPod

Non riutilizzare le route private Pixaroma. Route Iridio read-only per navigazione, elenco e miniature; lavoro disco/decodifica fuori dall'event loop e miniature ridotte a massimo 192 px, su richiesta. Per grandi cartelle, elenco e galleria paginati; non decodificare tutte le immagini per selezionare il file successivo.

Proposta di confine: directory input/output ComfyUI consentite di default; percorsi aggiuntivi in `<ComfyUI user directory>/iridio/allowed_folders.json`, formato `{"folders": ["/workspace/images"]}`. Configurazione amministrativa sul server, senza endpoint web che conceda accesso a nuove radici. Configurazione assente = sole radici predefinite; malformata = errore esplicito, mai accesso illimitato. Usare un volume persistente per cartella immagini e directory user su RunPod.

Le stesse verifiche valgono per browse/list/thumbnail, preparazione del job e lettura effettiva: tipi e dimensioni dei parametri, estensioni consentite, contenimento per componenti con percorsi risolti, rifiuto di traversal e symlink che escono dalla radice. File selezionati contenuti anche nella cartella scelta; nessun percorso assoluto come voce relativa. Non servire file arbitrari tramite la route miniature, né usare prefissi stringa come controllo di contenimento. Directory selezionabili solo se accessibili secondo questa policy; niente informazioni sui percorsi negati. Evitare cicli dei link. Un server amministrato da terzi che modifica simultaneamente symlink e file non è un confine di isolamento garantito.

Non aggiungere autenticazione o proxy propri: le route restano dietro lo stesso accesso del server ComfyUI. Chiamate frontend tramite API ComfyUI, rispettando eventuale prefisso URL del proxy. Verificare davvero sul RunPod dell'utente prima di dichiarare compatibilità end-to-end.

## Persistenza e metadati

Workflow JSON ordinario: cartella, selezione completa ordinata e prossima posizione. Non salvare l'intero elenco di cartella, miniature o byte. Il contatore riparte dal valore dell'ultimo workflow salvato; non si promette recupero automatico delle prenotazioni dopo crash.

PNG con metadati: solo il file usato, riportato come selezione singola con Next image 1, più indice/totale originali per la visualizzazione. Isolare sia API graph sia workflow, incluse eventuali proprietà e widget nominati. Il PNG non incorpora l'immagine sorgente: per rieseguirlo serve ancora quel file. Percorso e nome del file possono essere visibili nei metadati; la lista degli altri file non deve esserlo. I saver personalizzati devono conservare i metadati.

Supporto iniziale ai nodi top-level. Non dichiarare supportati i subgraph: impedire un comportamento parziale dell'iteratore e mostrare la limitazione prima dell'invio, finché non esiste una mappatura per istanza verificata.

## Fuori scope

Resize/crop, ricorsione, shuffle, ordinamento per data, filtri avanzati, skip dei risultati già presenti, avvio automatico di una run per ogni file, retry automatico, copia/snapshot delle sorgenti, armonizzazione con la lunghezza di un TXT. Nessun restyling del nodo stringa, modifica al core ComfyUI, installazione o pubblicazione in questa fase.

## Scelte approvate

Oltre alle decisioni confermate: nodo autonomo, ordine per nome e cartella non ricorsiva, uscite, errore sul file mancante, policy delle cartelle consentite, isolamento PNG e layout del mockup. Scelte approvate; le evidenze di implementazione e i limiti verificati sono nel rapporto di sviluppo.
