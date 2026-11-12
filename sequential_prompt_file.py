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


class SequentialPromptFile(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="IridioSequentialPromptFile",
            display_name="Sequential Prompt File",
            category="Iridio Nodes",
            description="Load a UTF-8 TXT file in the browser. One prompt per non-empty line. "
                        "Next prompt advances after each successful queue submission and wraps to 1. "
                        "Reset affects future submissions only. The used prompt is displayed after execution "
                        "and preserved in the image workflow when metadata is enabled.",
            inputs=[
                io.String.Input("prompt_text", default="", multiline=True,
                                dynamic_prompts=False, socketless=True,
                                tooltip="Embedded TXT content: one prompt per non-empty line. "
                                        "Included when saving or sharing the workflow."),
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
        prompts = parse_prompts(prompt_text)
        if type(next_prompt) is not int or next_prompt < 1:
            raise ValueError("Next prompt must be a positive integer starting at 1.")
        index = (next_prompt - 1) % len(prompts)
        used = {"text": prompts[index], "index": index + 1, "total": len(prompts)}
        # Patch this job's workflow, never the browser's advancing counter.
        if cls.hidden is not None and cls.hidden.extra_pnginfo is not None:
            workflow = cls.hidden.extra_pnginfo.get("workflow", {})
            for node in workflow.get("nodes", []):
                if str(node["id"]) == cls.hidden.unique_id:
                    node.setdefault("properties", {})["iridioUsedPrompt"] = used
                    break
        return io.NodeOutput(prompts[index], index + 1, len(prompts), ui={"used_prompt": [used]})
