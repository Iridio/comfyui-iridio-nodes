# Used Prompt Metadata Implementation Plan

> **For agentic workers:** Execute inline with superpowers:executing-plans, TDD and a final independent review.

**Goal:** Show the executed TXT prompt in the source node and preserve that exact text in each image's embedded workflow, including 100 queued jobs.

**Architecture:** Keep existing inputs, outputs and queue hooks. At execution, select from the job's frozen inputs, write `{text, index, total}` to this node's `properties.iridioUsedPrompt` in `EXTRA_PNGINFO`, and return the same object as UI data. The frontend shows only the used-prompt text box and restores it from node properties. The next counter remains; remove its text preview. Add hover help to every visible control and output.

**Tech Stack:** Existing ComfyUI V3 API, JavaScript, unittest, Node test runner, Pillow and native SaveImage.

**Spec:** User-approved design in the current chat (2026-11-12): integrated used-prompt display, persistent per-image text, unchanged next counter, 100-job queue verification.

## Global Constraints

- No dependencies, new public inputs, output changes or edits to ComfyUI core.
- Old workflows and headless requests without workflow metadata must still execute.
- Only the matching node's metadata changes; queued jobs retain independent snapshots.
- Work in the clean project checkout on a feature branch. Follow-up authorization: create the 0.2.0 release commit and tag; publish automatically on a future tag push.

## Review Focus

- Old workflows without saved used-prompt properties.
- Requests without workflow metadata or without a matching workflow node.
- Multiple prompt nodes: preserve unrelated node properties.
- Reset/upload while jobs wait: preserve each submitted job's text.
- Saving/reloading a PNG must restore used text without advancing the next counter.

### Task 1: Persist and display executed prompt

**Files:** `sequential_prompt_file.py`, `web/prompt_file.mjs`, `tests/test_sequential_prompt_file.py`, `tests/prompt_file.test.mjs`.

**Interfaces:** Existing `execute(prompt_text, next_prompt)` returns unchanged outputs plus `ui.used_prompt = [{text, index, total}]`. Persist that object as `properties.iridioUsedPrompt` for the matching unique ID.

- [x] Add backend tests for UI data, metadata ownership/preservation, repeated snapshots and absent metadata; add frontend tests for execution display, persistence/reload and independence from next-preview/reset/upload.
- [x] Run both suites and observe new tests fail for the missing behavior.
- [x] Implement the metadata update and used-prompt display using existing node lifecycle hooks.
- [x] Run both complete suites; expect zero failures.

### Task 2: Verify 100 saved PNGs and document behavior

**Files:** `tests/comfyui_server.py`, `tests/fixtures/queue-test.json`, `tests/verify_queue.py`, `README.md`.

**Interfaces:** Test output produces a small CPU image downstream of the prompt; native SaveImage embeds the actual workflow. Verifier downloads all 100 PNGs and checks each saved property, frozen text/index, used-prompt UI data and image marker.

- [x] Extend the integration fixture to feed native SaveImage through the prompt-dependent test output.
- [x] Queue 100 browser submissions before allowing execution; verify two cycles of 50 prompts in all saved PNGs.
- [x] Reopen saved PNGs in the real frontend and check the prompt field and counter, with no next-prompt preview.
- [x] Update README and run complete suites, diff checks and independent code review.

## Execution record

- Baseline: 7 Python and 13 JavaScript tests passed. Checkout clean at d60dfc8; feature branch `feature/used-prompt-metadata`.
- Scope: use temporary isolated CPU server for validation; do not restart or change running user workflows.
- User steering: remove next-prompt preview and add hover help for every property. Use native schema tooltips and DOM titles, without dependencies.
- Task 1 first pass: RED observed missing UI/metadata, then GREEN (10 Python, 15 JavaScript).
- Task 2 first pass: 100 jobs queued in real frontend before execution; TXT replaced while queued; all 100 native SaveImage PNGs verified for prompt/index/total, frozen widgets and pixel marker.
- User steering RED→GREEN: removal tests first failed on the old preview; final suites pass (10 Python, 15 JavaScript).
- Final integration: repeated 100-job paused-queue test after UI/help changes; all PNG checks passed. Native PNG import of jobs 1, 37, 100 restored their respective used text and input position. Real canvas hover showed Next prompt help; DOM controls use native title help, outputs use schema tooltips.
- Independent final review: no actionable findings; reviewer reran both suites and diff check.
- Local copy was briefly updated, then restored byte-for-byte from verified v0.1.0 backups at the user's request. Keep it on 0.1.0 for the user's update test; no further installed-file changes.
- Follow-up: label renamed to `prompt`; all 15 JavaScript tests passed.
- Release preparation: metadata version 0.2.0, automatic Registry publication on v* tag pushes, existing manual trigger retained. User authorized a commit and version tag; no push requested.
