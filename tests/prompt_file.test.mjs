import assert from "node:assert/strict";
import { test } from "node:test";
import { parsePrompts, setupPromptFile } from "../web/prompt_file.mjs";

class Element extends EventTarget {
    children = [];
    value = "";
    style = {};
    append(...elements) { this.children.push(...elements); }
    setAttribute(name, value) { this[name] = value; }
    click() { this.dispatchEvent(new Event("click")); }
}
globalThis.document = { createElement: () => new Element() };

function createNode(text = "", index = 1) {
    const node = {
        widgets: [{ name: "prompt_text", value: text, options: {} },
                  { name: "next_prompt", value: index, options: {} }],
        properties: {},
        size: [360, 340],
        setDirtyCanvas() {},
        computeSize() { return [360, 340]; },
        setSize() {},
        addDOMWidget(name, type, element, options) {
            const widget = { name, element, options };
            this.widgets.push(widget);
            return widget;
        },
    };
    setupPromptFile(node);
    return node;
}

function elements(node) {
    const all = [];
    const visit = (e) => { all.push(e); e.children.forEach(visit); };
    visit(node.widgets[2].element);
    return all;
}

async function upload(node, name, content) {
    const picker = elements(node).find(e => e.type === "file");
    picker.files = [{ name, arrayBuffer: async () => new TextEncoder().encode(content).buffer }];
    picker.dispatchEvent(new Event("change"));
    await new Promise(resolve => setImmediate(resolve));
}

function serialize(node) {
    return { prompt_text: node.widgets[0].serializeValue?.() ?? node.widgets[0].value,
             next_prompt: node.widgets[1].serializeValue?.() ?? node.widgets[1].value };
}

test("parser handles BOM, mixed newlines, empty lines and Unicode", () => {
    assert.deepEqual(parsePrompts("\ufeff first \r\n\t\r\nsecond café\rthird\n \n"),
                     ["first", "second café", "third"]);
});

test("upload sets embedded text, next 1 and preview without a server path", async () => {
    const node = createNode();
    await upload(node, "prompts.txt", "first\n\nsecond");
    assert.equal(node.widgets[0].value, "first\n\nsecond");
    assert.equal(node.widgets[1].value, 1);
    assert.equal(elements(node).find(e => e.readOnly).value, "first");
    assert.match(elements(node).map(e => e.textContent).join(" "), /2 prompts/);
});

test("50 prompts reserve two exact cycles for 100 queued graphs", () => {
    const text = Array.from({ length: 50 }, (_, i) => `Prompt ${i + 1}`).join("\n\n");
    const node = createNode(text);
    const snapshots = [];
    for (let i = 0; i < 100; i++) {
        node.widgets[1].beforeQueued?.();
        snapshots.push(serialize(node));
        node.widgets[1].afterQueued();
    }
    assert.deepEqual(snapshots.map(s => s.next_prompt),
                     [...Array.from({ length: 50 }, (_, i) => i + 1),
                      ...Array.from({ length: 50 }, (_, i) => i + 1)]);
    assert.equal(node.widgets[1].value, 1);
    assert.equal(snapshots[49].prompt_text, text);
});

test("manual index, normalization, reset and independent nodes", () => {
    const node = createNode("first\nsecond\nthird");
    const other = createNode("other");
    node.widgets[1].value = 5;
    node.widgets[1].callback(5);
    assert.equal(node.widgets[1].value, 2);
    assert.equal(elements(node).find(e => e.readOnly).value, "second");
    const snapshot = { text: node.widgets[0].value, index: node.widgets[1].value };
    elements(node).find(e => e.textContent === "Reset to 1").click();
    assert.equal(node.widgets[1].value, 1);
    assert.equal(snapshot.index, 2);
    assert.equal(other.widgets[1].value, 1);
    assert.equal(other.widgets[0].value, "other");
});

test("failed upload keeps the previous text and position", async () => {
    const node = createNode("first\nsecond", 2);
    for (const [name, text] of [["empty.txt", "\n  \n"], ["wrong.csv", "bad"],
                                ["binary.txt", "abc\x00def"]]) {
        await upload(node, name, text);
        assert.equal(node.widgets[0].value, "first\nsecond");
        assert.equal(node.widgets[1].value, 2);
        assert.ok(elements(node).find(e => e.role === "alert").textContent);
    }
});

test("restored workflow preserves position and preview without advancing on save", () => {
    const node = createNode("first\nsecond", 2);
    node.onConfigure?.({});
    assert.equal(node.widgets[1].value, 2);
    assert.equal(elements(node).find(e => e.readOnly).value, "second");
    assert.equal(node.widgets[2].options.serialize, false);
});

test("manual reset or edit during queue submission wins over its completion", () => {
    const node = createNode("first\nsecond\nthird", 1);
    node.widgets[1].beforeQueued();
    serialize(node);
    elements(node).find(e => e.textContent === "Reset to 1").click();
    node.widgets[1].afterQueued();
    assert.equal(node.widgets[1].value, 1);
    node.widgets[1].beforeQueued();
    serialize(node);
    node.widgets[1].value = 3;
    node.widgets[1].callback(3);
    node.widgets[1].afterQueued();
    assert.equal(node.widgets[1].value, 3);
});

test("preparing or saving a graph never consumes a prompt without queue success", () => {
    const node = createNode("first\nsecond", 2);
    node.widgets[1].beforeQueued();
    serialize(node);
    assert.equal(node.widgets[1].value, 2);
    node.widgets[1].beforeQueued();
    serialize(node);
    assert.equal(node.widgets[1].value, 2);
    node.widgets[1].afterQueued();
    assert.equal(node.widgets[1].value, 1);
});

test("invalid UTF-8 and unreadable files preserve the previous sequence", async () => {
    const node = createNode("first\nsecond", 2);
    const picker = elements(node).find(e => e.type === "file");
    for (const arrayBuffer of [async () => new Uint8Array([0xff]).buffer,
                               async () => { throw new Error("Cannot read file"); }]) {
        picker.files = [{ name: "bad.txt", arrayBuffer }];
        picker.dispatchEvent(new Event("change"));
        await new Promise(resolve => setImmediate(resolve));
        assert.equal(node.widgets[0].value, "first\nsecond");
        assert.equal(node.widgets[1].value, 2);
        assert.match(elements(node).find(e => e.role === "alert").textContent, /Upload failed/);
    }
});

test("uploading a replacement does not mutate snapshots already queued", async () => {
    const node = createNode("first\nsecond", 2);
    node.widgets[1].beforeQueued();
    const snapshot = serialize(node);
    await upload(node, "replacement.txt", "new first\nnew second");
    node.widgets[1].afterQueued();
    assert.deepEqual(snapshot, { prompt_text: "first\nsecond", next_prompt: 2 });
    assert.equal(node.widgets[0].value, "new first\nnew second");
    assert.equal(node.widgets[1].value, 1);
});

test("browser and Python agree on Unicode whitespace and a later-line BOM", () => {
    assert.deepEqual(parsePrompts("first\n\u0085\n\u001c\nsecond\n\ufeffthird"),
                     ["first", "second", "\ufeffthird"]);
});

test("replacement finishing before serialization advances its actual submitted index", async () => {
    const node = createNode("first\nsecond", 2);
    node.widgets[1].beforeQueued();
    await upload(node, "replacement.txt", "new first\nnew second");
    assert.deepEqual(serialize(node), { prompt_text: "new first\nnew second", next_prompt: 1 });
    node.widgets[1].afterQueued();
    assert.equal(node.widgets[1].value, 2);
});

test("replacement between widget serializers cannot mix old text with a new index", async () => {
    const node = createNode("first\nsecond", 2);
    node.widgets[1].beforeQueued();
    const content = node.widgets[0].serializeValue?.() ?? node.widgets[0].value;
    await upload(node, "replacement.txt", "new first\nnew second");
    const index = node.widgets[1].serializeValue?.() ?? node.widgets[1].value;
    assert.deepEqual({ content, index }, { content: "first\nsecond", index: 2 });
    node.widgets[1].afterQueued();
    assert.equal(node.widgets[1].value, 1);
});
