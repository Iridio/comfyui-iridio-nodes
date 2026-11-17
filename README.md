# Iridio Nodes

Custom nodes for ComfyUI. No additional Python or JavaScript dependencies.
Requires ComfyUI 0.45.2 or newer with the V3 custom-node API and its browser
frontend. Verified with frontend 1.58.5.

## Registry publishing

Registry metadata targets **iridio-nodes 0.3.0**, publisher **@iridio**.
Published versions are immutable; increase `version` in `pyproject.toml` for each release.

To publish a release:

1. Create a Registry publishing API key for publisher `iridio`.
2. In this GitHub repository's **Settings → Secrets and variables → Actions**,
   add a repository secret named `REGISTRY_ACCESS_TOKEN` with that key.
3. Commit the release files, tag the commit as `v0.3.0`, and push that tag.
   **Publish to Comfy Registry** starts automatically on pushes of `v*` tags.
   Branch pushes do not publish. Manual **Run workflow** remains available.
4. Confirm the action succeeded and the Registry shows version `0.3.0` before
   announcing availability through ComfyUI Manager.

Never commit the key. `.comfyignore` excludes tests,
internal documents and CI configuration while keeping Python and browser files.
The minimum ComfyUI version is the tested baseline, not a claim that earlier
versions are incompatible. No frontend upgrade dependency is added.

See the [Registry publishing guide](https://docs.comfy.org/registry/publishing).

## 0.3.0

Add **Folder Image Iterator**: select images from a server folder, process one
image per run and loop back to the first after the last. Includes a paged
thumbnail gallery, Next image, Reset, isolated PNG source metadata and Evoluzione
green accents (`#90F208`). Uses **Select images**; subfolders are not included.
No additional dependencies or Pixaroma installation required.

## 0.2.2

Save only the selected TXT prompt in both API and workflow image metadata,
including named widget values. The browser and ordinary workflow exports keep
the full sequence; reopening a PNG restores its single prompt at position 1.

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

The full TXT and position are retained in ordinary workflow JSON exports.
Save/export the workflow to keep the sequence. The filename is only a display label: ComfyUI never needs the
original local path. This design also supports a ComfyUI server on RunPod;
upload is through the browser and the normal workflow request, with no extra
port or upload service. Sharing a workflow JSON includes its full TXT content.

Before execution, each submitted Iridio node is resolved to its selected line.
The queued API graph and the workflow embedded in the image contain **only that
prompt**, never the other TXT lines. Original index/total are retained as metadata;
the browser's full TXT and advancing counter remain unchanged. With native
**Save Image** and metadata enabled, reopening the PNG restores that image's
prompt in a one-prompt workflow at position 1. Use the ordinary workflow JSON
to resume the full sequence. Older workflows without
this information show an empty prompt box until execution. Custom image savers
must preserve workflow metadata for this behavior.

PNG isolation currently covers top-level Iridio nodes. Iridio nodes inside
subgraphs are not covered: shared definitions need per-instance metadata mapping
and dedicated replay tests before they can offer the same guarantee.

The counter belongs to each browser workflow/node, using ComfyUI's queue-widget
hooks (including partial submissions). Separate tabs/users do not share a
counter. Headless API clients must supply `prompt_text` and `next_prompt` and
advance their own index; resubmitting the same API JSON selects the same line.
As with ComfyUI's seed controls, successful submissions also advance a node
that is unused by the selected output. Reset does not rewrite queue/history.

## Folder Image Iterator

Add **Iridio Nodes → Folder Image Iterator** and connect `image` to your
processing workflow, ending in a Save Image node. This node loads **one file
per run**, never an image list. Use ComfyUI's queue batch count to run it many
times: 100 runs with 50 selected files processes `1…50, 1…50`.

- Enter an absolute **Server folder** or use **Browse**. Browse explores the
  ComfyUI server, including on RunPod; it does not select your browser computer's
  files. Use **Select images**, select thumbnails, then **Apply selection**.
- Files directly in that folder are ordered naturally by name (`1, 2, 10`).
  **Select all**, **Clear** and gallery pages control the selection; there are no
  subfolders, resize or crop operations.
- **Next image** is editable and starts at 1. A successful queue submission
  advances it, wrapping after the last file. **Reset to 1** changes future
  submissions only. A rejected submission does not advance; cancelling an
  already queued job or an execution error consumes its reserved position.
- **Next to queue** and **Last executed** are separate. Changing the selection
  or folder, or applying **Refresh**, resets Next image to 1. Gallery/Browse
  edits are drafts until confirmed; Cancel preserves the current sequence.
  Refresh retains existing selections and identifies missing files; it does not
  automatically select new images.
- Outputs: `image`, `mask`, `width`, `height`, `filename` (no extension), `index`,
  `total`, `path` (absolute resolved source path). The mask is inverted alpha,
  or zero for an opaque image. PNG/JPEG/WebP/BMP/TIFF/GIF are supported; animated
  files and multi-page TIFFs use only the first frame/page. EXIF orientation is
  applied; integer 16-bit images are scaled to 8-bit values. No implicit resize.
- Each submitted job retains its selected path and original index/total.
  Files are read **at execution**, not copied when queued: changing a source
  changes what will be loaded. Missing, unreadable or denied files fail that job
  explicitly; there is no automatic skip/retry. ComfyUI owns whether remaining
  queued jobs continue. Later nodes may still create their own batches.

### Server folder access

ComfyUI's input/output directories are allowed by default. To use another
directory, create `<ComfyUI user directory>/iridio/allowed_folders.json` on the
server, for example:

```json
{"folders": ["/workspace/images"]}
```

Use an absolute path. This file is read live; a malformed file fails closed.
Browse/list/thumbnail/execution use the same policy. Links escaping the selected
folder are refused. There is no web endpoint that grants filesystem access.
On RunPod keep images and the user directory on persistent storage, and protect
the ComfyUI server through its normal access controls. This is not a multi-user
filesystem sandbox against an administrator changing files or links concurrently.

### Workflow persistence

Ordinary workflow JSON keeps the selected filenames and next position, without
embedding images. Save the workflow to retain that position across restarts.
The counter is per browser workflow/node; API callers provide their own index.
There is no global deduplication across browsers and no crash recovery ledger.

With native Save Image and metadata enabled, each PNG contains only its source
file selection with Next image 1, plus the original index/total in metadata.
Reopening it restores that single-image workflow; the original source file must
still exist. Paths/names remain visible in PNG metadata. Use an ordinary workflow
JSON to resume the complete sequence. Custom savers must retain workflow metadata.
Folder Image Iterator is currently **top-level only**; subgraphs are rejected.

### Image integration check

Start a fresh temporary test server as below. It creates 50 small test images
under input/iridio-images; its location is also returned by `/iridio-test/images`.
Create Folder Image Iterator → Save Image with node IDs 1 and 2, use Browse to
select that directory and Select all, then queue 100 runs. Before releasing the
queue, change/reset the browser node to confirm already queued jobs stay fixed.
Run `python tests/verify_image_queue.py` with the ComfyUI Python environment.
It releases just the first job, checks its saved PNG while the other 99 remain
paused, then verifies both complete cycles, pixels, dimensions, metadata, unique
filenames and absence of iterator/save cache hits. The test server is local-only
and all its writable directories are temporary.

## Verification

Run from this repository using an existing ComfyUI Python environment:

```sh
COMFYUI_PATH=/path/to/ComfyUI /path/to/ComfyUI/.venv/bin/python -m unittest discover -s tests -v
node --test tests/*.test.mjs
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
   selected input and image marker in each, and rejects any unselected TXT line
   in any PNG text chunk. `--save-dir /tmp/iridio-pngs` retains
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

Folder Image Iterator development checks: 35 Python tests and 24 JavaScript tests passed;
100 browser-queued image jobs saved 100 individual PNGs, plus three single-image
cycle checks. Native PNG reimport and light/dark themes verified with ComfyUI
0.45.5 / frontend 1.58.5. RunPod, production proxies and GPU/model inference
remain unverified. See the [development report](docs/superpowers/plans/2026-11-17-folder-image-iterator-report.md).
