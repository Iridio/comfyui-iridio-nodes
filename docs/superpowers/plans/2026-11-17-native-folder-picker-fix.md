# Browse — correzione del selettore cartelle

La release 0.3.0 saltava il primo passaggio del riferimento Pixaroma: provare il dialogo nativo del sistema operativo. Mostrava direttamente il navigatore delle radici consentite, con input/output come pulsanti. L'utente ha chiesto esplicitamente il comportamento di Pixaroma, senza quel passaggio intermedio.

## Comportamento corretto

- Browse locale apre il selettore nativo del server desktop: macOS osascript, Windows PowerShell/WinForms, Linux zenity/kdialog quando disponibile un display.
- Alla conferma si memorizza solo la cartella restituita dal dialogo OS; una nuova cartella viene impostata con tutte le sue immagini selezionate. Select images rimane l'azione separata per modificarne la selezione. Nessuna galleria o finestra delle radici intermedia.
- Annullare il dialogo nativo non modifica il nodo e non apre il fallback.
- Client remoti, proxy e server headless ricevono il navigatore delle cartelle server, con righe-cartella e percorso, senza Allowed roots e i vecchi pulsanti input/output. Le cartelle remote aggiuntive restano configurabili sul server.
- Una risposta del dialogo arrivata dopo sostituzione/rimozione del workflow viene ignorata. Coda e metadati dell'iteratore non sono modificati da questa correzione.

## Confine filesystem

Endpoint POST con JSON; i client remoti/proxied ricevono unavailable prima del controllo Origin (anche con TLS terminato dal proxy). Solo richieste locali e same-origin possono aprire il dialogo. Il percorso di partenza deve essere già consentito; non autorizza se stesso. Solo il risultato OS viene aggiunto alle radici. Nessun comando shell e nessuna interpolazione del percorso nel sorgente AppleScript/PowerShell: si usano argv e variabile d'ambiente.

Scrittura della configurazione atomica, sotto lock del picker; chiavi esistenti preservate, JSON corrotto non sovrascritto e limite di dimensione verificato prima della sostituzione.

## Verifiche

- 41 test Python e 27 test JavaScript passati; suite preesistenti incluse.
- Test RED→GREEN per assenza originaria del dialogo, annullamento, scelta di una cartella esterna, proxy HTTPS, risposta nativa obsoleta e aggiornamento troppo grande della configurazione.
- AppleScript effettivo compilato con osacompile su macOS; un'invocazione reale di osascript è rimasta in attesa del dialogo, poi il processo di test è stato terminato. Il tool di computer use non riesce a ispezionare il processo non registrato osascript: non si dichiara una selezione visuale end-to-end confermata.
- Revisione indipendente di sicurezza: tre rilievi corretti, ciascuno riprodotto con test prima della correzione. Nessun bypass di autorizzazione del percorso o command injection identificato.
- Non verificati dialoghi reali Windows/Linux, RunPod live e integrazione nel Comfy Desktop installato. Nessuna modifica all'installazione dell'utente o pubblicazione automatica di una nuova versione.

La release Registry 0.3.0 è immutabile: la correzione richiede una nuova patch release, non la sostituzione dell'archivio già pubblicato.
