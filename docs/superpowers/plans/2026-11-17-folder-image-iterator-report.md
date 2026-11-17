# Folder Image Iterator — rapporto di sviluppo

17 novembre 2026. Design, piano e scelte approvati dall'utente; successiva correzione della dicitura del pulsante da Pick images a **Select images** applicata a interfaccia, tooltip, test e documentazione.

Chiusura successiva autorizzata dall'utente: integrazione su main e release **0.3.0**, senza aggiungere il supporto alle sottocartelle. I riferimenti a 0.2.2 e alla mancata pubblicazione nelle sezioni seguenti descrivono la fase di sviluppo precedente alla release.

## Risultato

Nodo V3 autonomo in Iridio Nodes, ID `IridioFolderImageIterator`. Legge una sola immagine da una cartella del server per run, avanza all'accodamento riuscito e ritorna alla prima dopo l'ultima. Navigazione cartelle e selezione grafica non richiedono Pixaroma. Accento #90F208, Select images, Refresh, Next image, Reset e Last executed separato dalla prossima immagine.

Nessuna nuova dipendenza, modifica al core ComfyUI, installazione nel plugin attivo o pubblicazione. Versione di release invariata a 0.2.2: il codice nuovo appartiene al branch di sviluppo, non a una release Registry già pubblicata. Non sono state copiate porzioni sostanziali del codice Pixaroma; il riferimento ha guidato l'interazione, non introduce una dipendenza o un pacchetto redistribuito.

## Verifiche osservate

- **35 test Python passati**, inclusi i 19 test preesistenti del nodo stringa.
- **24 test JavaScript passati**, inclusi i 15 preesistenti del nodo stringa.
- Browser ComfyUI reale: Browse sul server, selezione, paginazione, Cancel, modifica da tastiera, Reset, 100 invii con worker inizialmente fermo e successive modifiche del nodo che non alterano i job già inviati.
- **100 esecuzioni / 100 PNG distinti**: 50 immagini per due giri. Pixel, dimensioni, indice e totale corretti; nessun hit cache dell'iteratore o del salvataggio. Un'immagine sorgente per job e assenza degli altri nomi nei metadati PNG.
- Prova centrale: eseguito solo il primo job, PNG già presente e leggibile con gli altri **99 job ancora fermi**, poi rilascio della coda restante.
- Reimportazione nativa di un PNG tramite `app.handleFile`: selezione singola, Next image 1 e Last executed con indice originale 37/50 ripristinati.
- Altre **3 esecuzioni con una sola immagine**: tre salvataggi senza cache, contatore sempre 1.
- Tema chiaro e scuro osservati e screenshot ispezionati; pulsante Select images confermato nel nodo reale. Controllati focus, dialoghi, anteprima e dimensione compatta del nodo.
- Nessun errore JavaScript runtime nel flusso browser principale. Il server di test temporaneo mostra i 404 iniziali delle risorse utente assenti e i blocchi CSP del controllo release del frontend; non sono errori del plugin.

Ambiente osservato: ComfyUI 0.45.5, frontend 1.58.5, Python 3.13.12, PyTorch 2.10.0, Node 26.13.1, CPU/macOS. AVFFrameReceiver/AVFAudioReceiver duplicati nelle librerie av/cv2 producono avvisi già presenti nel baseline; le suite e le esecuzioni sono terminate con successo.

## Revisione indipendente e correzioni

Revisione del codice completo con un agente in contesto separato; correzioni verificate con test RED→GREEN e suite completa, senza basarsi soltanto sulla lettura del diff:

1. Nodo disattivato presente solo nel workflow: eliminazione della selezione e dell'ultimo file dai metadati PNG; niente creazione di metadati nelle richieste estranee a Iridio.
2. Last executed scritto soltanto quando il nodo viene eseguito, non durante la preparazione di un ramo potenzialmente scollegato.
3. Prima pagina della galleria caricata su richiesta, senza leggere tutte le pagine; lato server si raccolgono/ordinano i nomi, ma si risolvono/statano le immagini della pagina richiesta. I symlink richiedono comunque il controllo di contenimento.
4. Select all, Refresh e conferma possono richiedere l'elenco completo dei soli nomi/metadati, per ordine e controllo dei mancanti; l'annullamento interrompe ulteriori richieste, non soltanto l'applicazione del risultato.
5. Preparazione del job senza accesso al disco; validazione filesystem asincrona su thread, controlli nuovamente eseguiti al caricamento effettivo.
6. Indice/totale originali conservati anche se un link interno cambia destinazione prima della lettura; destinazioni esterne alla cartella ancora rifiutate. Il contratto congela il nome selezionato, non byte o destinazione del link.
7. Annullare la selezione di un'altra cartella ripristina anche il percorso visibile. Notifiche di esecuzione e avanzamento non sovrascrivono un percorso ancora in modifica.
8. Ordinamento con caratteri numerici Unicode non decimali (ad esempio `²1.png`) senza errori. Conversione a 8 bit condivisa da miniature e caricamento per i file interi a 16 bit.

Nessun rilievo minore rinviato dalla revisione. Non è stata effettuata una seconda revisione indipendente dopo le correzioni: il controllo successivo è costituito dai test di regressione, dalla suite completa e dalle prove browser/integrate ripetute.

## Scelte esecutive e limiti

- Usato il Python effettivo di ComfyUI (`ComfyUI/.venv/bin/python`), perché standalone-env non contiene torch; i test richiedono `COMFYUI_PATH`. Node 26 usa `node --test` senza il vecchio flag experimental-default-type.
- Passato esplicitamente `api` alla funzione di costruzione del pannello, così frontend e test usano lo stesso contratto HTTP senza import browser nei test Node.
- Il nome relativo viene fissato all'invio. Sorgenti o link modificati possono fornire contenuti aggiornati all'esecuzione. Non si offre uno snapshot di file o una garanzia contro un amministratore che modifica link simultaneamente ai controlli.
- Nessun recupero automatico della posizione dopo crash: vale il valore nell'ultimo workflow salvato. Annullare un job già accodato consuma la sua posizione.
- Solo cartella non ricorsiva e nodi top-level. Nessuna generazione con modelli o prova GPU: la verifica riguarda caricamento/coda/salvataggio reali su CPU.
- **RunPod reale e proxy di produzione non verificati**: non era disponibile un pod da usare. Le chiamate frontend utilizzano l'API ComfyUI standard; un doppio API nei test controlla il prefisso URL delle miniature, ma non sostituisce una verifica sul proxy del pod.
- Minimo dichiarato ComfyUI >=0.45.2 mantenuto; verificato qui 0.45.5, non tutte le versioni intermedie o gli altri sistemi operativi.

## Riproduzione

```sh
COMFYUI_PATH=/path/to/ComfyUI /path/to/ComfyUI/.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/*.test.mjs
COMFYUI_PATH=/path/to/ComfyUI /path/to/ComfyUI/.venv/bin/python tests/comfyui_server.py --port 8189
```

Aprire il server temporaneo, creare Folder Image Iterator → Save Image (ID 1 e 2), Browse → input/iridio-images → Select images → Select all → Apply selection, accodare 100 run senza avviare il worker. Eseguire con il Python ComfyUI `tests/verify_image_queue.py`; usa `/iridio-test/run?count=1` per la prova del primo salvataggio prima di liberare la coda.
