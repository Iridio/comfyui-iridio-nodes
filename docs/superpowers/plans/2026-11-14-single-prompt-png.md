# Single-prompt PNG correction

The supplied PNG proves that 0.2.1 writes the whole TXT into both the API
`prompt` and visual `workflow` chunks. The selected-text property is correct,
but that does not satisfy the user's confirmed requirement: a PNG must retain
only its selected prompt; reopening it restores a one-prompt workflow. The
browser's working workflow and ordinary workflow exports retain the full TXT.

Resolve literal Iridio TXT inputs in ComfyUI's existing on-prompt hook, before
validation/execution. Replace the queued input and saved workflow text with the
selected line and set their next position to 1. Carry original index/total as
per-job metadata so existing integer outputs and the live display stay correct.
Do not mutate a running graph or patch ComfyUI core. Keep invalid requests on
the existing validation/error path, and keep headless requests supported.

- [x] Add failing tests for pre-queue resolution, no other prompt in either
  metadata graph, original index/total, ordinary API/invalid input behavior.
- [x] Register the hook through the existing extension entry point; share the
  selection logic with execution; preserve existing frontend queue semantics.
- [x] Change the 100-PNG verifier to reject every unselected line in every
  saved text chunk and assert single-prompt reload behavior.
- [x] Verify a fresh real-browser 100-job queue and the user's two-line TXT,
  reopen representative PNGs and verify the live browser retains its sequence.
- [x] Run all suites, diff check and independent review; document the result.

During implementation, do not alter the installed plugin, original user PNG/TXT,
version, tags or publication. Baseline: clean main at 0fd1646 (v0.2.1).
Follow-up authorization: release 0.2.2, create commit and tag v0.2.2, integrate
into main, close the feature branch and push main/tag. The installed plugin
remains protected and unchanged.

## Evidence

- First real 100-PNG attempt failed the new exclusion check: the frontend also
  serializes `widgets_values_named.prompt_text`. Fixed both positional and named
  fields, with a regression test that first failed.
- Independent review found convertible/wrapped API values, null optional metadata,
  muted source nodes and a later-line BOM edge. Root-level cases were reproduced
  by failing tests, then fixed. Literal BOMs are file-encoded for exact PNG/API
  replay without dropping the original leading character.
- Final browser run: 100 jobs queued before execution, two cycles of 50 prompts.
  All 100 native SaveImage PNGs contain only their selected line; every other
  line is absent from all text fields and raw PNG bytes. No sequence/output/save
  cache hits. Original index/total and pixel marker match for every image.
- Browser working workflow and ordinary export retained all 50 lines and next=1.
- Browser upload of the supplied `aria_test.txt`: both resulting test PNGs
  contain only their respective line, including named fields and API metadata.
- Native PNG imports of jobs 1, 37, 100, 101, 102 restore exactly one prompt at
  position 1. Requeueing PNG 102 produces the same second user prompt as 1/1;
  the first user prompt is absent from that new PNG as well.
- Applying preparation in memory to the supplied real PNG's complete API and
  workflow graphs removes the first line everywhere, retaining exact second-line
  output and original index/total 2/2. The original file was never modified.
- Final suites: 19 Python and 15 JavaScript tests. Installed runtime files and
  original user PNG/TXT hashes match their pre-change values.

## Scope ruling

Subgraph source nodes remain unsupported for this guarantee. Review verified that
flattened API IDs use instance paths, while workflow definitions are shared;
correct rewriting requires instance-aware mapping and replay tests. The supplied
PNG's Iridio source is top-level (other subgraph definitions in its workflow do
not contain this source). Its complete graphs passed the exclusion check. This
limit is documented in source and README; no unsafe final-ID rewrite was added.
