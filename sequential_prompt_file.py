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
                        "Reset affects future submissions only.",
            inputs=[
                io.String.Input("prompt_text", default="", multiline=True,
                                dynamic_prompts=False, socketless=True),
                io.Int.Input("next_prompt", display_name="Next prompt", default=1,
                             min=1, max=2147483647, step=1, socketless=True,
                             control_after_generate=False),
            ],
            outputs=[io.String.Output("prompt"), io.Int.Output("index"), io.Int.Output("total")],
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
        return io.NodeOutput(prompts[index], index + 1, len(prompts))
