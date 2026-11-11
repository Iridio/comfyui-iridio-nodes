export function parsePrompts(text) {
    // Match Python str.strip(); JS trim() handles BOM and Unicode whitespace differently.
    return text.replace(/^\uFEFF/, "").split(/\r\n?|\n/)
        .map(line => line.replace(/^[\p{White_Space}\u001c-\u001f]+|[\p{White_Space}\u001c-\u001f]+$/gu, ""))
        .filter(Boolean);
}

export function setupPromptFile(node) {
    const text = node.widgets.find(widget => widget.name === "prompt_text");
    const next = node.widgets.find(widget => widget.name === "next_prompt");
    text.hidden = true;
    const panel = document.createElement("div");
    panel.style.cssText = "display:flex;flex-direction:column;gap:8px;padding:8px;height:100%;overflow:auto;" +
        "box-sizing:border-box;color:var(--input-text);font:13px sans-serif;";
    const controls = document.createElement("div");
    controls.style.cssText = "display:flex;gap:8px;flex-wrap:wrap";
    const picker = document.createElement("input");
    picker.type = "file";
    picker.accept = ".txt,text/plain";
    picker.hidden = true;
    const upload = document.createElement("button");
    upload.type = "button";
    upload.textContent = "Upload TXT";
    const reset = document.createElement("button");
    reset.type = "button";
    reset.textContent = "Reset to 1";
    for (const button of [upload, reset]) {
        button.style.cssText = "padding:6px 12px;border:1px solid var(--border-color);" +
            "border-radius:4px;background:var(--comfy-input-bg);color:var(--input-text);cursor:pointer";
    }
    const status = document.createElement("div");
    status.style.cssText = "overflow-wrap:anywhere";
    status.setAttribute("aria-live", "polite");
    const error = document.createElement("div");
    error.setAttribute("role", "alert");
    const preview = document.createElement("textarea");
    preview.readOnly = true;
    preview.setAttribute("aria-label", "Next prompt preview");
    preview.placeholder = "Upload a TXT file to preview the next prompt.";
    preview.style.cssText = "width:100%;min-height:100px;flex:1;resize:none;box-sizing:border-box;" +
        "background:var(--comfy-input-bg);color:var(--input-text);border:1px solid var(--border-color)";
    controls.append(upload, reset, picker);
    panel.append(controls, status, error, preview);
    node.addDOMWidget("iridio_prompt_file", "iridio_prompt_file", panel, {
        serialize: false, getMinHeight: () => 200,
    });
    node.setSize([Math.max(340, node.size[0]), node.computeSize()[1]]);

    let revision = 0;
    let queued;
    const refresh = () => {
        const prompts = parsePrompts(text.value);
        const requested = Number.isFinite(Number(next.value)) ? Math.trunc(Number(next.value)) : 1;
        next.value = prompts.length ? ((Math.max(1, requested) - 1) % prompts.length) + 1 : 1;
        preview.value = prompts[next.value - 1] ?? "";
        status.textContent = prompts.length
            ? `${node.properties.iridioFileName || "Embedded TXT"} · ${prompts.length} prompts · Next: ${next.value}`
            : "No TXT loaded";
        node.setDirtyCanvas(true, true);
    };
    upload.addEventListener("click", () => picker.click());
    picker.addEventListener("change", async () => {
        const file = picker.files?.[0];
        if (!file) return;
        upload.disabled = true;
        try {
            if (!/\.txt$/i.test(file.name)) throw new Error("Choose a .txt file.");
            const content = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
            if (content.includes("\0")) throw new Error("The TXT file contains null bytes.");
            if (!parsePrompts(content).length) throw new Error("The TXT file has no non-empty prompt lines.");
            text.value = content;
            node.properties.iridioFileName = file.name;
            next.value = 1;
            revision++;
            error.textContent = "";
            refresh();
        } catch (cause) {
            error.textContent = `Upload failed: ${cause.message}. Choose a UTF-8 TXT file.`;
        } finally {
            upload.disabled = false;
            picker.value = "";
        }
    });
    reset.addEventListener("click", () => {
        next.value = 1;
        revision++;
        refresh();
    });
    const callback = next.callback;
    next.callback = function () {
        callback?.apply(this, arguments);
        revision++;
        refresh();
    };
    text.serializeValue = () => {
        refresh();
        queued = { revision, index: next.value };
        return text.value;
    };
    // Keep text/index from the same snapshot even if an upload finishes between serializers.
    next.serializeValue = () => queued?.index ?? next.value;
    next.beforeQueued = refresh;
    next.afterQueued = () => {
        if (queued?.revision !== revision) return;
        next.value = queued.index + 1;
        refresh();
    };
    const onConfigure = node.onConfigure;
    node.onConfigure = function () {
        onConfigure?.apply(this, arguments);
        revision++;
        refresh();
    };
    refresh();
}
