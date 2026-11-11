# Iridio Nodes

Custom nodes for ComfyUI. No additional Python or JavaScript dependencies.
Requires ComfyUI with the V3 custom-node API and its browser frontend.

## Sequential Prompt File

Add **Iridio Nodes → Sequential Prompt File** and connect `prompt` to a text
input, for example CLIP Text Encode. `index` and `total` are integer outputs.

- **Upload TXT** selects a UTF-8 `.txt` file from your browser's computer.
  Each non-empty line is one prompt; surrounding whitespace is trimmed.
  LF, CRLF, CR, Unicode and an initial UTF-8 BOM are supported.
- **Next prompt** is editable, one-based and starts at **1**. Values past the
  total wrap around. The preview shows the next prompt and the total count.
- Every successful queue submission reserves that prompt and advances the
  counter, circling back to 1 after the last line. A batch of 100 with 50 lines
  reserves `1…50, 1…50`, even while earlier jobs are still waiting.
- **Reset to 1** and replacement files affect future submissions. Already
  queued jobs retain their original text and index. Removing a queued job
  consumes its reserved position; submission failures do not advance it.
- Empty, unreadable, invalid UTF-8 or null-containing files show an error and
  preserve the previous file and position.

The text and position are embedded in the workflow. Save/export the workflow
to retain them. The filename is only a display label: ComfyUI never needs the
original local path. This design also supports a ComfyUI server on RunPod;
upload is through the browser and the normal workflow request, with no extra
port or upload service. The TXT content is included when sharing a workflow.

The counter belongs to each browser workflow/node, using ComfyUI's queue-widget
hooks (including partial submissions). Separate tabs/users do not share a
counter. Headless API clients must supply `prompt_text` and `next_prompt` and
advance their own index; resubmitting the same API JSON selects the same line.
As with ComfyUI's seed controls, successful submissions also advance a node
that is unused by the selected output. Reset does not rewrite queue/history.

## Verification

Run from this repository using an existing ComfyUI Python environment:

```sh
COMFYUI_PATH=/path/to/ComfyUI /path/to/ComfyUI/.venv/bin/python -m unittest discover -s tests -v
node --test tests/prompt_file.test.mjs
```

For an isolated integration check, start:

```sh
COMFYUI_PATH=/path/to/ComfyUI /path/to/ComfyUI/.venv/bin/python tests/comfyui_server.py
```

This serves only Iridio, core nodes and a test output at
`http://127.0.0.1:8189`; all writable server directories are temporary and the
queue starts paused. It does not install the plugin or load other plugins.

1. Open that URL; load `tests/fixtures/queue-test.json` in ComfyUI.
2. Use **Upload TXT** to select `tests/fixtures/50-prompts.txt`.
3. Set ComfyUI's batch count to **100**, click **Run**, and wait for 100 queued jobs.
4. Run `python3 tests/verify_queue.py` to check the frozen indices, release the
   worker, and assert 100 successful jobs, exact prompt/index/total outputs,
   two complete cycles, no sequence/output cache hits and an empty queue.
5. Stop the test server with Ctrl-C. Its test output node is not part of the plugin.

Validated locally with ComfyUI `6e8488ef`, frontend `1.58.5`, Python `3.13.12`
and Node `26.13.0`. Browser checks cover TXT selection, a 100-job batch, manual
index 37, Reset, and native workflow export/reimport with text/index/preview
preserved. Unit tests also cover failed uploads and concurrent replacement
during serialization. No live RunPod deployment or image generation was tested.

Frontend integration follows the [ComfyUI JavaScript hooks](https://docs.comfy.org/custom-nodes/js/javascript_hooks).
