import re

from comfy_api.latest import io


def parse_prompts(text):
    if not isinstance(text, str) or "\x00" in text:
        raise ValueError("Upload a UTF-8 TXT file without null bytes.")
    prompts = [line.strip() for line in re.split(r"\r\n?|\n", text.removeprefix("\ufeff"))
               if line.strip()]
    if not prompts:
        raise ValueError("Upload a TXT file with at least one non-empty prompt line.")
    return prompts


def select_prompt(prompt_text, next_prompt):
    prompts = parse_prompts(prompt_text)
    if type(next_prompt) is not int or next_prompt < 1:
        raise ValueError("Next prompt must be a positive integer starting at 1.")
    index = (next_prompt - 1) % len(prompts)
    return {"text": prompts[index], "index": index + 1, "total": len(prompts)}


def prompt_file_text(text):
    # A literal leading BOM needs a file BOM prefix to survive one-line TXT replay.
    return "\ufeff" + text if text.startswith("\ufeff") else text


def prepare_prompt(request):
    metadata = request.get("extra_data", {}).get("extra_pnginfo") or {}
    metadata.pop("iridioPromptSelections", None)
    selections = {}
    for node_id, node in request.get("prompt", {}).items():
        if node.get("class_type") != "IridioSequentialPromptFile":
            continue
        inputs = node.get("inputs", {})
        if not {"prompt_text", "next_prompt"} <= inputs.keys():
            continue
        text, position = inputs["prompt_text"], inputs["next_prompt"]
        if isinstance(text, list) or isinstance(position, list):
            continue
        if isinstance(text, dict):
            text = text.get("__value__", text)
        if isinstance(position, dict):
            position = position.get("__value__", position)
        try:
            position = int(position)
            if position > 2147483647:
                continue
            selections[node_id] = select_prompt(str(text), position)
        except (TypeError, ValueError, OverflowError):
            # Leave invalid or linked inputs to ComfyUI's normal execution/validation path.
            continue
    if not selections:
        return request
    request.setdefault("extra_data", {})["extra_pnginfo"] = metadata
    metadata["iridioPromptSelections"] = selections
    for node_id, used in selections.items():
        request["prompt"][node_id]["inputs"].update(prompt_text=prompt_file_text(used["text"]), next_prompt=1)
    # shortcut: subgraph definitions need instance-aware mapping before nested nodes are supported.
    for node in (metadata.get("workflow") or {}).get("nodes", []):
        used = selections.get(str(node["id"]))
        if used is None and node.get("type") != "IridioSequentialPromptFile":
            continue
        text = prompt_file_text(used["text"]) if used is not None else ""
        node.setdefault("widgets_values", [])[:2] = [text, 1]
        if "widgets_values_named" in node:
            node["widgets_values_named"].update(prompt_text=text, next_prompt=1)
        if used is not None:
            node.setdefault("properties", {})["iridioUsedPrompt"] = used
        else:
            node.setdefault("properties", {}).pop("iridioUsedPrompt", None)
    return request


class SequentialPromptFile(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="IridioSequentialPromptFile",
            display_name="Sequential Prompt File (Iridio)",
            category="Iridio Nodes",
            description="Load a UTF-8 TXT file in the browser. One prompt per non-empty line. "
                        "Next prompt advances after each successful queue submission and wraps to 1. "
                        "Reset affects future submissions only. The used prompt is displayed after execution "
                        "and preserved in the image workflow when metadata is enabled.",
            inputs=[
                io.String.Input("prompt_text", default="", multiline=True,
                                dynamic_prompts=False, socketless=True,
                                tooltip="Embedded TXT content: one prompt per non-empty line. "
                                        "Workflow JSON exports retain the full TXT; saved images retain "
                                        "only the selected prompt."),
                io.Int.Input("next_prompt", display_name="Next prompt", default=1,
                             min=1, max=2147483647, step=1, socketless=True,
                             control_after_generate=False,
                             tooltip="One-based position for the next queue submission. Advances after "
                                     "each successful submission and wraps to 1 after the last prompt. "
                                     "Editing it affects future submissions only."),
            ],
            outputs=[
                io.String.Output("prompt", tooltip="Selected prompt text sent downstream. Connect to a "
                                 "text encoder or another node that accepts a prompt string."),
                io.Int.Output("index", tooltip="One-based position of the prompt used by this execution."),
                io.Int.Output("total", tooltip="Total number of non-empty prompt lines in this execution's TXT."),
            ],
            hidden=[io.Hidden.unique_id, io.Hidden.extra_pnginfo],
        )

    @classmethod
    def fingerprint_inputs(cls, prompt_text, next_prompt):
        # A single prompt or a completed cycle must still trigger downstream execution.
        return float("nan")

    @classmethod
    def execute(cls, prompt_text, next_prompt):
        metadata = cls.hidden.extra_pnginfo if cls.hidden is not None else None
        selection = (metadata or {}).get("iridioPromptSelections", {}).get(
            cls.hidden.unique_id if cls.hidden is not None else None)
        if (selection is not None and prompt_file_text(selection["text"]) == prompt_text
                and type(next_prompt) is int and next_prompt == 1):
            used = selection
        else:
            used = select_prompt(prompt_text, next_prompt)
        # Patch this job's workflow, never the browser's advancing counter.
        if metadata is not None:
            workflow = metadata.get("workflow") or {}
            for node in workflow.get("nodes", []):
                if str(node["id"]) == cls.hidden.unique_id:
                    node.setdefault("properties", {})["iridioUsedPrompt"] = used
                    break
        return io.NodeOutput(used["text"], used["index"], used["total"], ui={"used_prompt": [used]})
