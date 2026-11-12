# Iridio Nodes

Custom nodes for ComfyUI. No additional Python or JavaScript dependencies.
Requires ComfyUI 0.45.2 or newer with the V3 custom-node API and its browser
frontend. Verified with frontend 1.58.5.

## Registry publishing

Registry metadata targets **iridio-nodes 0.2.1**, publisher **@iridio**.
Published versions are immutable; increase `version` in `pyproject.toml` for each release.

To publish a release:

1. Create a Registry publishing API key for publisher `iridio`.
2. In this GitHub repository's **Settings → Secrets and variables → Actions**,
   add a repository secret named `REGISTRY_ACCESS_TOKEN` with that key.
3. Commit the release files, tag the commit as `v0.2.1`, and push that tag.
   **Publish to Comfy Registry** starts automatically on pushes of `v*` tags.
   Branch pushes do not publish. Manual **Run workflow** remains available.
4. Confirm the action succeeded and the Registry shows version `0.2.1` before
   announcing availability through ComfyUI Manager.

Never commit the key. `.comfyignore` excludes tests,
internal documents and CI configuration while keeping Python and browser files.
The minimum ComfyUI version is the tested baseline, not a claim that earlier
versions are incompatible. No frontend upgrade dependency is added.

See the [Registry publishing guide](https://docs.comfy.org/registry/publishing).

## 0.2.1

Fix stale node interfaces after updates by serving the browser helper as `.js`,
which ComfyUI marks `Cache-Control: no-store`. No workflow changes are required.

## Sequential Prompt File

Add **Iridio Nodes → Sequential Prompt File** and connect `prompt` to a text
input, for example CLIP Text Encode. `index` and `total` are integer outputs.

- **Upload TXT** selects a UTF-8 `.txt` file from your browser's computer.
  Each non-empty line is one prompt; surrounding whitespace is trimmed.
  LF, CRLF, CR, Unicode and an initial UTF-8 BOM are supported.
- **Next prompt** is editable, one-based and starts at **1**. Values past the
  total wrap around. The status shows the loaded filename, total and next position.
- **prompt** shows the exact text emitted during the last execution, with
  its one-based index and total. It is read-only and stays unchanged by uploading
  another file, editing Next prompt or resetting the counter.
- Hover over the counter, buttons, file status, used-prompt box or output sockets
  for help explaining their behavior.
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

Each execution also writes its used prompt/index/total into its own workflow
metadata. With native **Save Image** and metadata enabled, reopening the PNG
restores that image's used-prompt display and input position, even if many later
jobs were queued or the browser loaded a replacement TXT. Older workflows without
this information show an empty prompt box until execution. Custom image savers
must preserve workflow metadata for this behavior.

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
4. Run `tests/verify_queue.py` using the server's Python environment to check the frozen indices, release the
   worker, and assert 100 successful jobs, exact prompt/index/total outputs,
   two complete cycles, no sequence/output cache hits and an empty queue. It
   downloads all 100 PNGs saved by native Save Image and checks the used prompt,
   input snapshot and image marker in each. `--save-dir /tmp/iridio-pngs` retains
   those files for browser reload checks; `--url` selects a different server port.
5. Stop the test server with Ctrl-C. Its test output node is not part of the plugin.

Validated locally with ComfyUI `6e8488ef`, frontend `1.58.5`, Python `3.13.12`
and Node `26.13.0`. Browser checks cover TXT selection, a 100-job batch, manual
index 37, Reset, and native workflow export/reimport. The used-prompt check uses
100 small CPU test images saved through native Save Image, including replacing
the browser's TXT before releasing the queue. Every PNG's embedded workflow and
prompt are checked. Unit tests also cover failed uploads, concurrent replacement
during serialization, used-prompt restoration and metadata ownership. No live
RunPod deployment or model inference was tested.

Frontend integration follows the [ComfyUI JavaScript hooks](https://docs.comfy.org/custom-nodes/js/javascript_hooks).
