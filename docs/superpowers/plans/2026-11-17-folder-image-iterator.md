# Folder Image Iterator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elaborare una sola immagine da cartella server per run, con selezione grafica e sequenza circolare.

**Architecture:** Nodo V3 autonomo, contatore nel browser e selezione fissata all'accodamento come Sequential Prompt File. Servizio filesystem locale condiviso fra route read-only e loader. Nessuna dipendenza runtime da Pixaroma.

**Tech Stack:** Python, ComfyUI V3, aiohttp/Pillow/NumPy/PyTorch già disponibili; JavaScript ES modules, DOM widget, node:test e unittest esistenti.

**Spec:** `docs/superpowers/specs/2026-11-17-folder-image-iterator-design.md`.

**Stato:** approvato dall’utente, sviluppo autorizzato e implementato nel branch dedicato. Verifiche e limitazioni in `2026-11-17-folder-image-iterator-report.md`; RunPod reale resta da verificare. Nessuna installazione o release.

## Global Constraints

- Nome `Folder Image Iterator`, categoria `Iridio Nodes`, ID `IridioFolderImageIterator`.
- Accento `#90F208`, RGB `144/242/8`; testo scuro sul verde.
- Una sola immagine, ritorno alla prima; nessun `OUTPUT_IS_LIST`.
- ComfyUI >=0.45.2 e Python >=3.10, nessuna nuova dipendenza; verificare sul baseline prima di rivendicarlo.
- Cartella sul server, anche RunPod, nessun upload browser; nessuna modifica a ComfyUI o Pixaroma.
- Nodo stringa e workflow esistenti devono conservare il comportamento attuale.
- Tutte le scelte non confermate restano proposte della spec finché l'utente non le approva.

## Review Focus

1. Path traversal, symlink e richieste costruite a mano: medesima policy per HTTP, accodamento e lettura (Task 1/2).
2. Accodamento rapido, Reset e Refresh concorrenti: nessuna desincronizzazione fra indice e file (Task 3/4).
3. File modificato/rimosso dopo l'invio e ciclo di una sola immagine: esecuzione reale o errore esplicito, nessun replay cache (Task 2/4).
4. PNG e workflow nominati: assenza della lista completa nel PNG e ripristino corretto (Task 2/4).
5. RunPod con prefisso proxy e cartella grande: browser server, paging e decode non bloccante (Task 1/3/4).

## Mappa dei file

| File | Responsabilità |
|---|---|
| `folder_image_files.py` (nuovo) | Policy delle radici, percorsi validati, ordine, elenco/pagine e miniature |
| `folder_image_routes.py` (nuovo) | Browse/list/thumb aiohttp e registrazione idempotente |
| `folder_image_iterator.py` (nuovo) | Schema V3, selezione, hook di preparazione, decode di un file e metadati |
| `web/folder_image_iterator.js` (nuovo) | Registrazione estensione e collegamento widget |
| `web/folder_image_panel.js` (nuovo) | UI, galleria, richieste API e snapshot del contatore |
| `__init__.py` | Registrare nodo, route e secondo handler senza sostituire quello stringa |
| `tests/test_folder_image_files.py`, `tests/test_folder_image_iterator.py`, `tests/folder_image_panel.test.mjs` (nuovi) | Contratti filesystem, esecuzione/metadati e coda frontend |
| `tests/comfyui_server.py` | Riutilizzare harness temporaneo, aggiungere solo quanto serve alle prove immagine |
| `tests/verify_image_queue.py` (nuovo) | Prova integrata coda, salvataggi e PNG |
| `README.md`, `pyproject.toml` | Uso, limiti e descrizione; versione invariata fino a una release autorizzata |
| `THIRD_PARTY_NOTICES.md` (se necessario) | Attribuzione MIT per porzioni effettivamente riutilizzate |

Non estrarre un framework condiviso dal nodo stringa; riprendere il suo pattern senza refactoring estranei.

## Task 1: Accesso alle immagini e route server

**Files:** `folder_image_files.py`, `folder_image_routes.py`, `tests/test_folder_image_files.py`.

**Interfaces:**
- `resolve_folder(folder: str) -> pathlib.Path`: verifica radici configurate.
- `resolve_image(folder: str, relative_name: str) -> pathlib.Path`: verifica anche contenimento nella cartella ed estensione.
- `list_images(folder: str, offset: int = 0, limit: int = 100) -> dict`: `folder`, `files` con `file/name/size/mtime_ns`, `total`, `offset`; limite massimo 200, offset >=0.
- `browse_folders(folder: str | None, offset: int = 0, limit: int = 100) -> dict`: radici consentite se None; altrimenti cartella, genitore consentito e sottocartelle, paginando se necessario con lo stesso limite.
- `make_thumbnail(folder: str, relative_name: str) -> bytes`: JPEG, lato massimo 192 px, primo frame orientato EXIF.
- `register_folder_image_routes(server)`: `/iridio/folder-images/browse`, `/list`, `/thumb`, solo GET. Path e file sono parametri; browse/list aggiungono offset/limit. Nessuna route modifica la policy.

- [x] Scrivere test con TemporaryDirectory: default input/output, radice esterna autorizzata, config malformata, Unicode, nomi 1/2/10, file non immagine, traversal, percorsi assoluti, prefisso simile, symlink esterno e cartella negata.
- [x] Eseguire i test nuovi e osservarli fallire per funzionalità mancanti.
- [x] Implementare le funzioni con pathlib/os e una sola verifica condivisa; ordine naturale con spareggio stabile, nessuna ricorsione. Validare interi e dimensioni dei parametri; non interpretare i parametri thumbnail come file arbitrari.
- [x] Aggiungere route con `asyncio.to_thread` per operazioni bloccanti. Browse/list `Cache-Control: no-store`; miniature con chiave mtime e senza cache persistente di immagini. Errori HTTP 400/403/404 con JSON breve, 403 senza rivelare esistenza dei percorsi negati.
- [x] Verificare paging senza duplicati e che la lista non invochi decode; una miniatura deve aprire solo il file richiesto. Usare lo stesso controllo per richieste HTTP dirette.
- [x] Eseguire `python -m unittest discover -s tests -p 'test_folder_image_files.py' -v` nel Python ComfyUI con PYTHONPATH impostato al core; atteso PASS.
- [ ] Commit opzionale solo durante implementazione autorizzata: `Add folder image browsing`.

## Task 2: Nodo V3 e isolamento del job

**Files:** `folder_image_iterator.py`, `__init__.py`, `tests/test_folder_image_iterator.py`.

**Interfaces:**
- `select_image(folder: str, selection_json: str, next_image: int) -> dict`: ritorna `folder`, `file`, `index`, `total`; JSON array non vuoto di nomi relativi unici ordinati, indice intero positivo. Indice effettivo `(next_image - 1) % total`.
- `prepare_image_prompt(request: dict) -> dict`: risolve nodi top-level, serializza selezione singola/indice 1 nel job e aggiunge `iridioImageSelections` per nodo. Gestire in modo idempotente una seconda invocazione: non perdere indice/totale originali.
- `FolderImageIterator.define_schema()`: input socketless `folder: STRING`, `selection_json: STRING`, `next_image: INT` 1…2147483647, senza incremento nativo; output nell'ordine della spec, hidden unique_id/extra_pnginfo.
- `FolderImageIterator.execute(folder, selection_json, next_image)`: `io.NodeOutput` con otto output e `ui={"used_image": [used]}`; `used` contiene percorso, nome relativo, indice/totale, dimensioni.
- `fingerprint_inputs(...) -> NaN`.

- [x] Test iniziali: selezione 1/2/3/1, indice oltre il totale, input invalidi; shape IMAGE `[1,H,W,3]`, MASK `[1,H,W]`; PNG trasparente/palette, JPEG con EXIF, immagine intera 16 bit e GIF multipla con primo frame soltanto.
- [x] Confermare fallimento, poi implementare decode minimo usando Pillow e helper ComfyUI applicabili. Non delegare ciecamente a LoadImage nativo: la versione installata può emettere tutti i frame di file animati.
- [x] Testare handler: due tipi di nodi nello stesso workflow, due istanze immagine, metadati assenti, input headless e doppia preparazione; nessuna mutazione del nodo stringa.
- [x] Implementare isolamento del PNG in API graph, widgets_values, widgets_values_named e proprietà salvate. Non inserire l'elenco completo in un secondo campo. Conservare solo file scelto e `iridioUsedImage` con indice/totale originali.
- [x] Testare file rimosso/permessi negati dopo preparazione; ripetere resolve al decode. Nessuna sostituzione silenziosa. Input annidati/subgraph: rilevare e rifiutare con messaggio breve, evitando avanzamenti silenziosi del frontend.
- [x] Registrare nodo, route e handler in `__init__.py`, mantenendo `prepare_prompt` esistente. Testare che gli handler, nell'ordine registrato, conservino entrambi i metadati.
- [ ] Eseguire nuovi test Python e `test_sequential_prompt_file.py`; atteso PASS. Commit opzionale: `Add single image iterator execution`.

## Task 3: Interfaccia e avanzamento della coda

**Files:** `web/folder_image_iterator.js`, `web/folder_image_panel.js`, `tests/folder_image_panel.test.mjs`.

**Interfaces:** `setupFolderImageIterator(node, api)` collega gli input schema e un DOM widget non serializzato; proprietà `iridioUsedImage` contiene solo l'ultimo file eseguito. Cartella/selezione/indice risiedono nei rispettivi widget serializzati, non duplicati in proprietà private del workflow.

- [x] Scrivere test node:test per selezione e indice serializzati dalla stessa revisione, submit riuscito/fallito, wrap 6→1, Reset e modifica durante submit, due nodi indipendenti, annullamento delle finestre e Refresh con file mancanti.
- [x] Eseguire `node --test tests/folder_image_panel.test.mjs`, osservare fallimenti prima dell'implementazione.
- [x] Implementare caricamento API tramite `api.fetchApi` e URL coerenti con il proxy; Browse mostra cartelle del server, non picker del computer browser. Galleria paginata, miniature lazy, draft Apply/Cancel; scartare risposte asincrone obsolete quando cambia cartella.
- [x] Implementare `serializeValue`, `beforeQueued`, `afterQueued` e revisione come nel nodo stringa. Validare il numero prima della serializzazione; non avanzare da `onExecuted`. Il callback di esecuzione aggiorna solo Last executed, con associazione al job corretto.
- [x] Renderizzare percorso, Browse, Select images, Refresh, Next image, Reset to 1, anteprima successiva e Last executed come nel mockup approvato. Tutti i selettori/stili sono scoped Iridio; verde #90F208 e focus visibile. Usare `.js` per evitare il problema di cache già risolto nel plugin.
- [x] Ripristino workflow ordinario: mantenere selezione/indice, non fare refresh mutante all'apertura; PNG: selezione singola e indice 1, indicazione originale Last executed.
- [ ] Eseguire tutti i test JS con `node --test tests/*.test.mjs`; atteso PASS. Commit opzionale: `Add folder image iterator controls`.

## Task 4: Accettazione integrata e documentazione

**Files:** `tests/comfyui_server.py`, `tests/verify_image_queue.py`, `README.md`, `pyproject.toml`, eventuale notice MIT.

- [x] Estendere l'harness temporaneo esistente senza modificare installazione o workflow dell'utente; generare 50 immagini distinguibili in TemporaryDirectory, dimensioni e alpha variabili.
- [x] Accodare dal frontend 100 job prima di eseguirli: verificare sequenza 1…50 due volte, un solo file sorgente per richiesta, nessun hit cache del nodo iteratore, 100 salvataggi con nomi unici. Fra invio ed esecuzione cambiare cartella/Reset e provare che i job restano invariati.
- [x] Prova centrale: dopo il primo salvataggio tenere fermo il job seguente con un gate dell'harness e verificare che il PNG esista e sia leggibile. Solo dopo proseguire. Non richiede GPU o generazioni lunghe.
- [x] Verificare tutti i PNG: pixel attesi, lista dei file estranei assente dai metadati, workflow singolo riapribile, indice/totale originali corretti. Un ciclo con una sola immagine deve comunque eseguire e salvare più volte.
- [x] Provare mancanti e file modificati dopo invio, invio rifiutato, job cancellato e doppio browser; documentare i risultati coerenti con il contratto.
- [x] Test browser del nodo reale a larghezza compatta, tastiera, tema chiaro/scuro, galleria grande, caricamento workflow e assenza errori console, sul frontend baseline 1.58.5 se disponibile e su quello installato.
- [ ] Smoke RunPod reale: cartella in volume persistente e radice consentita, Browse remoto, miniatura, almeno due run con Save Image, prefisso proxy e ricaricamento workflow. Senza accesso a quel pod registrare esplicitamente accettazione RunPod in sospeso; Linux locale non vale come prova equivalente.
- [x] Aggiornare README con configurazione cartelle, batch count di coda, differenza prenotato/eseguito, annullamenti, wrap, primo frame, file mutabili, PNG con percorso e limiti subgraph. Aggiornare solo la descrizione progetto in pyproject.toml, senza inventare una versione di release.
- [ ] Rieseguire suite Python/JS del plugin e verifica integrata nuova; registrare comandi, versioni e risultati. Nessuna pubblicazione automatica. Commit opzionale: `Verify folder image iterator workflows`.

## Comandi di riferimento per l'implementazione

Dal repo `/Users/alessandro/Progetti/comfyui-iridio-nodes`, usare il Python dell'installazione ComfyUI. Percorsi locali osservati nella fase di piano, da ricontrollare prima dell'esecuzione:

```sh
COMFYUI_PATH=/Users/alessandro/ComfyUI-Installs/ComfyUI/ComfyUI /Users/alessandro/ComfyUI-Installs/ComfyUI/ComfyUI/.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/*.test.mjs
COMFYUI_PATH=/Users/alessandro/ComfyUI-Installs/ComfyUI/ComfyUI /Users/alessandro/ComfyUI-Installs/ComfyUI/ComfyUI/.venv/bin/python tests/comfyui_server.py --port 8189
```

Il verificatore `tests/verify_image_queue.py` usa di default `http://127.0.0.1:8189` e accetta `--url`. I comandi di test e la prova integrata sono stati eseguiti; risultati e versioni effettive nel rapporto di sviluppo.

## Esito della revisione del piano

Coperti flusso cartella, policy percorsi, UI/proxy, coda, wrap, decode, metadati, regressione stringa e accettazione locale/RunPod. Spec e mockup approvati. Il rapporto riporta verifiche runtime effettive e limiti; accettazione RunPod reale ancora aperta.
