function element(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = text;
    return item;
}

function button(text, action, primary = false) {
    const item = element('button', primary ? 'iridio-fi-primary' : '', text);
    item.type = 'button';
    item.addEventListener('click', action);
    return item;
}

function installStyle() {
    if (document.getElementById('iridio-folder-style')) return;
    const style = element('style');
    style.id = 'iridio-folder-style';
    style.textContent = `
    .iridio-fi,.iridio-fi-dialog{--fi-accent:#90f208;color:var(--input-text,#ddd);font:13px/1.45 system-ui,sans-serif;box-sizing:border-box}
    .iridio-fi{display:flex;flex-direction:column;gap:10px;padding:12px;height:100%;overflow:auto;border-top:3px solid var(--fi-accent)}
    .iridio-fi [hidden]{display:none!important}
    .iridio-fi *, .iridio-fi-dialog *{box-sizing:border-box}
    .iridio-fi button,.iridio-fi input,.iridio-fi-dialog button,.iridio-fi-dialog input{font:inherit;min-height:34px;border:1px solid var(--border-color,#555);border-radius:5px;padding:6px 10px;background:var(--comfy-input-bg,#222);color:var(--input-text,#ddd);max-width:100%}
    .iridio-fi button,.iridio-fi-dialog button{cursor:pointer}
    .iridio-fi button:disabled,.iridio-fi-dialog button:disabled{opacity:.5;cursor:default}
    .iridio-fi button:focus-visible,.iridio-fi input:focus-visible,.iridio-fi-dialog button:focus-visible,.iridio-fi-dialog input:focus-visible{outline:2px solid var(--fi-accent);outline-offset:2px}
    .iridio-fi .iridio-fi-primary,.iridio-fi-dialog .iridio-fi-primary{background:var(--fi-accent);border-color:var(--fi-accent);color:#172005;font-weight:600}
    .iridio-fi-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
    .iridio-fi label,.iridio-fi-muted{font-size:12px;opacity:.8}
    .iridio-fi label{display:block;margin-bottom:5px}
    .iridio-fi-folder{flex:1;min-width:140px;width:100%;font-family:ui-monospace,monospace!important;font-size:12px!important}
    .iridio-fi-position{width:75px}
    .iridio-fi-preview{display:block;width:100%;height:135px;object-fit:contain;background:var(--comfy-input-bg,#222);border-radius:5px}
    .iridio-fi-filename,.iridio-fi-error{overflow-wrap:anywhere}
    .iridio-fi-error{color:var(--error-text,#e86666)}
    .iridio-fi-used{padding-top:10px;border-top:1px solid var(--border-color,#555);overflow-wrap:anywhere}
    .iridio-fi-dialog{background:var(--comfy-menu-bg,#292929);border:1px solid var(--border-color,#555);border-top:3px solid var(--fi-accent);border-radius:10px;padding:20px;width:min(680px,calc(100vw - 24px));max-height:85vh;overflow:auto}
    .iridio-fi-dialog::backdrop{background:#0008}
    .iridio-fi-dialog h3{font-size:16px;margin:0 0 12px}
    .iridio-fi-dialog p{overflow-wrap:anywhere}
    .iridio-fi-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:12px;margin:16px 0}
    .iridio-fi-tile{display:flex;flex-direction:column;gap:7px;text-align:left;overflow-wrap:anywhere;min-width:0}
    .iridio-fi-tile img{width:100%;height:95px;object-fit:contain;background:var(--comfy-input-bg,#222)}
    .iridio-fi-tile[aria-pressed=true]{outline:2px solid var(--fi-accent);outline-offset:1px}
    .iridio-fi-dirlist{display:flex;flex-direction:column;gap:8px;margin:14px 0}
    .iridio-fi-dialog .iridio-fi-folder-row{border:0;background:transparent;border-radius:0;text-align:left;display:flex;align-items:center;gap:9px;padding:8px}
    .iridio-fi-dialog .iridio-fi-folder-row:hover{background:var(--comfy-input-bg,#222)}
    @media(pointer:coarse){.iridio-fi button,.iridio-fi input,.iridio-fi-dialog button{min-height:44px}}
    `;
    document.head.append(style);
}

export function setupFolderImageIterator(node, api) {
    installStyle();
    const [folder, selection, next] = ['folder', 'selection_json', 'next_image']
        .map(name => node.widgets.find(widget => widget.name === name));
    for (const widget of [folder, selection, next]) widget.hidden = true;
    node.properties ??= {};
    let revision = 0;
    let queued;
    let displayedFolder;
    let session = 0;
    let activeDialog;
    const metadata = new Map();
    const panel = element('div', 'iridio-fi');
    const error = element('div', 'iridio-fi-error');
    error.hidden = true;
    error.setAttribute('role', 'alert');
    const path = element('input', 'iridio-fi-folder');
    path.type = 'text';
    path.setAttribute('aria-label', 'Server folder');
    path.title = 'Absolute path on the ComfyUI server, including on RunPod. Confirm a new path with Select images.';
    const count = element('div', 'iridio-fi-muted');
    count.setAttribute('aria-live', 'polite');
    const index = element('input', 'iridio-fi-position');
    index.type = 'number'; index.min = '1'; index.max = '2147483647'; index.step = '1';
    index.setAttribute('aria-label', 'Next image');
    const total = element('span', 'iridio-fi-muted');
    const preview = element('img', 'iridio-fi-preview');
    preview.alt = 'Next image to queue';
    const filename = element('div', 'iridio-fi-filename');
    const used = element('div', 'iridio-fi-used');
    used.setAttribute('aria-live', 'polite');
    const read = () => {
        try {
            const names = JSON.parse(selection.value);
            return Array.isArray(names) && names.every(name => typeof name === 'string') ? names : [];
        } catch { return []; }
    };
    const thumb = (base, name) => api.apiURL('/iridio/folder-images/thumb?' + new URLSearchParams({
        path: base, file: name, mt: metadata.get(name)?.mtime_ns ?? '',
    }));
    const render = () => {
        const names = read();
        const requested = Number(next.value);
        next.value = names.length ? ((Math.max(1, Number.isFinite(requested) ? Math.trunc(requested) : 1) - 1) % names.length) + 1 : 1;
        index.value = next.value;
        if (displayedFolder !== folder.value) {
            path.value = folder.value;
            displayedFolder = folder.value;
        }
        count.textContent = names.length ? `${names.length} selected · Name ↑ · One image per run` : 'No images selected';
        total.textContent = `of ${names.length} · loops to 1`;
        const name = names[next.value - 1];
        preview.hidden = !name;
        if (name) {
            const source = thumb(folder.value, name);
            if (preview.getAttribute?.('src') !== source) preview.src = source;
        }
        filename.textContent = name ?? 'Choose a server folder and select images.';
        const last = node.properties.iridioUsedImage;
        used.textContent = last ? `Last executed · ${last.file} · ${last.index}/${last.total}` +
            (last.width ? ` · ${last.width} × ${last.height}` : '') : 'Last executed · No execution yet';
        node.setDirtyCanvas(true, true);
    };
    const close = () => {
        session++;
        activeDialog?.close?.(); activeDialog?.remove(); activeDialog = undefined;
    };
    const dialog = (title, onCancel = () => {}) => {
        close();
        const box = element('dialog', 'iridio-fi-dialog');
        box.setAttribute('aria-label', title);
        box.append(element('h3', '', title));
        box.addEventListener('cancel', () => {onCancel(); close();});
        document.body.append(box); activeDialog = box; box.showModal?.();
        return box;
    };
    const request = async (operation, params) => {
        const response = await api.fetchApi(`/iridio/folder-images/${operation}?` + new URLSearchParams(params));
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || 'Could not read the server folder.');
        return data;
    };
    const allFiles = async (base, isCurrent) => {
        const files = [];
        let resolved;
        let expected;
        do {
            if (!isCurrent()) throw new Error('Selection cancelled.');
            const data = await request('list', {path: base, offset: files.length, limit: 200});
            if (!isCurrent()) throw new Error('Selection cancelled.');
            if (expected !== undefined && data.total !== expected) throw new Error('Folder changed while loading. Refresh and try again.');
            expected = data.total; resolved = data.folder;
            if (expected > 100000) throw new Error('Select a folder containing at most 100000 images.');
            if (data.files.length !== Math.min(200, expected - files.length)) throw new Error('Folder changed while loading. Refresh and try again.');
            files.push(...data.files);
        } while (files.length < expected);
        if (new Set(files.map(file => file.file)).size !== files.length) throw new Error('Folder changed while loading. Refresh and try again.');
        return {files, folder: resolved};
    };
    const openGallery = async (refresh = false, candidate = path.value.trim()) => {
        const requested = candidate;
        const restorePath = () => {path.value = folder.value;};
        const box = dialog('Select images', restorePath);
        const token = session;
        const status = element('p', 'iridio-fi-muted', 'Loading server folder…');
        const cancel = button('Cancel', () => {restorePath(); close();});
        box.append(status, cancel);
        try {
            const isCurrent = () => session === token;
            let allEntries = refresh ? (await allFiles(requested, isCurrent)).files : undefined;
            let data = await request('list', {path: requested, offset: 0, limit: 24});
            if (session !== token) return;
            for (const file of data.files) metadata.set(file.file, file);
            let draft = new Set(folder.value === data.folder ? read() : []);
            let page = 0;
            const pageSize = 24;
            let loading = false;
            const grid = element('div', 'iridio-fi-grid');
            const summary = element('p'); summary.setAttribute('aria-live', 'polite');
            const loadAll = async () => {
                allEntries ??= (await allFiles(data.folder, isCurrent)).files;
                return allEntries;
            };
            const apply = button('Apply selection', async () => {
                loading = true; draw();
                try {
                    const entries = await loadAll();
                    if (!isCurrent()) return;
                    const names = entries.filter(file => draft.has(file.file)).map(file => file.file);
                    if (names.length !== draft.size) {loading = false; draw(); return;}
                    const changed = folder.value !== data.folder || selection.value !== JSON.stringify(names);
                    if (refresh || changed) {
                        folder.value = data.folder; selection.value = JSON.stringify(names); next.value = 1; revision++;
                    }
                    error.textContent = ''; close(); render();
                } catch (cause) {
                    if (isCurrent()) {loading = false; draw(); summary.textContent = cause.message;}
                }
            }, true);
            const loadPage = async target => {
                loading = true; draw();
                try {
                    const response = await request('list', {path: data.folder, offset: target * pageSize, limit: pageSize});
                    if (!isCurrent()) return;
                    if (response.total !== data.total) throw new Error('Folder changed while loading. Refresh and try again.');
                    data = response; page = target;
                    for (const file of data.files) metadata.set(file.file, file);
                    loading = false; draw();
                } catch (cause) {if (isCurrent()) {loading = false; draw(); summary.textContent = cause.message;}}
            };
            const back = button('Previous page', () => loadPage(page - 1));
            const forward = button('Next page', () => loadPage(page + 1));
            const pages = element('span', 'iridio-fi-muted');
            const draw = () => {
                const available = allEntries && new Set(allEntries.map(file => file.file));
                const missing = available ? [...draft].filter(name => !available.has(name)) : [];
                summary.textContent = `${draft.size} selected · ${data.total} available` +
                    (missing.length ? ` · Missing: ${missing.join(', ')}. Clear or select all to remove missing files.` : '') +
                    ' · Applying changes or Refresh resets Next image to 1.';
                apply.disabled = loading || !draft.size || !!missing.length;
                selectAll.disabled = loading;
                grid.replaceChildren();
                for (const file of data.files) {
                    const tile = button('', () => { draft.has(file.file) ? draft.delete(file.file) : draft.add(file.file); draw(); });
                    tile.className = 'iridio-fi-tile'; tile.setAttribute('aria-pressed', draft.has(file.file));
                    tile.setAttribute('aria-label', file.file);
                    const image = element('img'); image.loading = 'lazy'; image.alt = ''; image.src = thumb(data.folder, file.file);
                    tile.append(image, element('span', '', `${draft.has(file.file) ? '✓ ' : ''}${file.file}`)); grid.append(tile);
                }
                back.disabled = loading || page === 0; forward.disabled = loading || (page + 1) * pageSize >= data.total;
                pages.textContent = `${page + 1}/${Math.max(1, Math.ceil(data.total / pageSize))}`;
            };
            const selectAll = button('Select all', async () => {
                loading = true; draw();
                try {
                    const entries = await loadAll();
                    if (!isCurrent()) return;
                    draft = new Set(entries.map(file => file.file)); loading = false; draw();
                } catch (cause) {if (isCurrent()) {loading = false; draw(); summary.textContent = cause.message;}}
            });
            const controls = element('div', 'iridio-fi-row');
            controls.append(selectAll, button('Clear', () => { draft.clear(); draw(); }));
            const pager = element('div', 'iridio-fi-row'); pager.append(back, pages, forward);
            const actions = element('div', 'iridio-fi-row'); actions.append(apply, cancel);
            box.replaceChildren(element('h3', '', 'Select images'), element('p', 'iridio-fi-muted', data.folder), controls, summary, grid, pager, actions);
            draw(); controls.children[0].focus();
        } catch (cause) {
            if (session === token) { status.textContent = cause.message; status.setAttribute('role', 'alert'); }
        }
    };
    const useFolder = async candidate => {
        close();
        const token = session;
        const data = await allFiles(candidate, () => session === token);
        if (session !== token) return;
        if (folder.value !== data.folder) {
            folder.value = data.folder;
            selection.value = JSON.stringify(data.files.map(file => file.file));
            next.value = 1; revision++;
        }
        for (const file of data.files) metadata.set(file.file, file);
        error.hidden = true; render();
    };
    const browse = async (base = null, offset = 0) => {
        const box = dialog('Choose a folder', () => {path.value = folder.value;});
        const token = session;
        const status = element('p', 'iridio-fi-muted', 'Loading server folders…');
        const cancel = button('Cancel', () => {path.value = folder.value; close();}); box.append(status, cancel);
        try {
            const data = await request('browse', { ...(base ? {path: base} : {}), offset, limit: 100 });
            if (session !== token) return;
            const list = element('div', 'iridio-fi-dirlist');
            for (const dir of data.dirs) {
                const row = button('', () => browse(dir.path));
                row.className = 'iridio-fi-folder-row';
                row.setAttribute('aria-label', dir.name);
                const icon = element('span', '', '📁'); icon.setAttribute('aria-hidden', 'true');
                row.append(icon, element('span', '', dir.name)); list.append(row);
            }
            const navigation = element('div', 'iridio-fi-row');
            if (data.parent) navigation.append(button('Parent folder', () => browse(data.parent)));
            else if (data.path) navigation.append(button('Locations', () => browse()));
            if (offset) navigation.append(button('Previous page', () => browse(base, Math.max(0, offset - 100))));
            if (offset + 100 < data.total) navigation.append(button('Next page', () => browse(base, offset + 100)));
            const actions = element('div', 'iridio-fi-row');
            if (data.path) actions.append(button('Use this folder', async () => {
                try {await useFolder(data.path);} catch (cause) {error.textContent = cause.message; error.hidden = false;}
            }, true));
            actions.append(cancel);
            box.replaceChildren(element('h3', '', 'Choose a folder'), element('p', '', data.path ? `Location: ${data.path}` : 'Server folders'), navigation, list, actions);
        } catch (cause) { if (session === token) {status.textContent = cause.message; status.setAttribute('role', 'alert');} }
    };
    const browseButton = button('Browse', async () => {
        const pickerSession = session, pickerRevision = revision;
        browseButton.disabled = true;
        error.hidden = true;
        try {
            const response = await api.fetchApi('/iridio/folder-images/pick-native', {
                method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({path: folder.value}),
            });
            const result = await response.json();
            if (session !== pickerSession || revision !== pickerRevision) return;
            if (!response.ok) throw new Error(result.message || 'Could not select a folder.');
            if (result.path) await useFolder(result.path);
            else if (result.unavailable) await browse(path.value.trim() || null);
            else if (result.busy) throw new Error('A folder selection window is already open.');
        } catch (cause) {
            error.textContent = cause.message; error.hidden = false;
        } finally {
            browseButton.disabled = false;
        }
    });
    const folderGroup = element('div'); folderGroup.append(element('label', '', 'Server folder'));
    const folderRow = element('div', 'iridio-fi-row'); folderRow.append(path, browseButton); folderGroup.append(folderRow);
    const actions = element('div', 'iridio-fi-row');
    actions.append(button('Select images', () => openGallery(), true), button('Refresh', () => openGallery(true)));
    const position = element('div'); position.append(element('label', '', 'Next image'));
    const positionRow = element('div', 'iridio-fi-row');
    positionRow.append(index, total, button('Reset to 1', () => {next.value = 1; revision++; render();})); position.append(positionRow);
    const imageGroup = element('div'); imageGroup.append(element('label', '', 'Next to queue'), preview, filename);
    panel.append(folderGroup, actions, count, error, position, imageGroup, used);
    node.addDOMWidget('iridio_folder_images', 'iridio_folder_images', panel, {serialize: false, getMinHeight: () => 450});
    node.setSize([Math.max(370, node.size[0]), node.computeSize()[1]]);
    index.addEventListener('change', () => {next.value = Number(index.value); revision++; render();});
    const callback = next.callback;
    next.callback = function () {callback?.apply(this, arguments); revision++; render();};
    folder.serializeValue = () => {
        render(); queued = {revision, folder: folder.value, selection: selection.value, index: next.value};
        return queued.folder;
    };
    selection.serializeValue = () => queued?.selection ?? selection.value;
    next.serializeValue = () => queued?.index ?? next.value;
    next.beforeQueued = render;
    next.afterQueued = () => {
        if (queued?.revision !== revision) return;
        next.value = queued.index + 1; render();
    };
    const onConfigure = node.onConfigure;
    node.onConfigure = function () {onConfigure?.apply(this, arguments); revision++; close(); render();};
    const onExecuted = node.onExecuted;
    node.onExecuted = function (message) {
        onExecuted?.apply(this, arguments);
        if (message.used_image?.[0]) {node.properties.iridioUsedImage = message.used_image[0]; render();}
    };
    const onRemoved = node.onRemoved;
    node.onRemoved = function () {close(); onRemoved?.apply(this, arguments);};
    render();
}
