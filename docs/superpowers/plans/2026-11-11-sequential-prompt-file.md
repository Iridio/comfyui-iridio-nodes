# Sequential Prompt File Implementation Plan

**Goal:** Start Iridio Nodes with a browser-loaded, circular TXT prompt sequence.

**Architecture:** A V3 ComfyUI node selects a prompt from embedded text and a
one-based index. A browser extension reads UTF-8 TXT files and advances the
index after each successful queue submission, using the widget `afterQueued`
hook. No server file paths, custom upload routes, shared counters or dependencies.

**Decisions:** The user chose advancement at queue time. Each queued graph owns
its text/index snapshot; cancellation consumes the reserved position. Reset and
replacement files start at 1 and affect future submissions. The preview shows
the next prompt. Saved workflows contain the text and the next index; API
clients must supply/increment their own index. Whitespace around lines is
trimmed, empty lines ignored, UTF-8 BOM and CR/LF line endings supported.

**Constraints:** Work only in this repository; English interface; no installation,
other-plugin changes, commits, push or publication. Use the existing local
ComfyUI environment for isolated tests; do not register the plugin permanently.

## Tasks

- [x] Backend: write failing tests for parsing, circular selection, invalid/empty
  input, outputs and extension discovery; implement `sequential_prompt_file.py`
  and `__init__.py`; run the Python suite.
- [x] Browser: write failing Node tests for upload, preview, manual index, reset,
  failed upload preservation, serialization and 100 queue snapshots with 50
  prompts; implement `web/prompt_file.mjs` and the registration entry point.
- [x] Integration: load the plugin explicitly in a temporary CPU ComfyUI server;
  test the real browser and queue 100 requests before executing them, verify
  prompt/index/total and two exact cycles in history. Add reusable integration
  harness and a 50-prompt fixture, and document commands/results in README.
- [x] Review and final verification: fresh read-only review; fix consequential
  defects; run both suites and integration again when code changes require it.

**Review focus:** queue-time snapshots and partial execution, cache behavior on
wrap/single prompt, failed file reads preserving state, saved workflow restore,
independent node instances, API inputs, local versus remote browser file access.

## Evidence

- Python: 7 tests passed with the existing ComfyUI virtual environment.
- JavaScript: 13 Node tests passed. Initial missing implementation failed both
  suites; the three Unicode/serialization regression cases failed before their fix.
- Browser: real file chooser upload, batch 100 with a paused server, editable
  index 37, Reset, native export/reimport and restored preview checked.
- Final isolated integration: 100 jobs were queued before execution; all 100
  emitted the exact expected prompt/index/total, indices 1–50 twice, no cache
  skips, empty queue, and a healthy `/api/jobs` response.
- Fresh review found Unicode trimming differences and a replacement-upload race
  during asynchronous graph serialization. Both fixed with regression tests.
  Text and index now share a serialization snapshot; advancement remains after
  queue success only. Node UI sizing was also checked in the real browser.
- Decision: standard ComfyUI queue-widget hooks apply to partial and unused
  nodes too; documented in README. Cost: a submission unrelated to this node
  can consume its next position. No application/global API patch was added.
- Tested core `6e8488ef`, frontend `1.58.5`, Python `3.13.12`, Node `26.13.0`.
  No live RunPod deployment or image-generation workflow was exercised.
- All changes remain uncommitted in this repository. No installation, other
  plugin changes, push or publication.

**API references:** [ComfyUI hooks](https://docs.comfy.org/custom-nodes/js/javascript_hooks),
[Comfy objects](https://docs.comfy.org/custom-nodes/js/javascript_objects_and_hijacking).
