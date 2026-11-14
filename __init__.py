from comfy_api.latest import ComfyExtension
from server import PromptServer

from .sequential_prompt_file import SequentialPromptFile, prepare_prompt

WEB_DIRECTORY = "./web"


class IridioNodes(ComfyExtension):
    async def get_node_list(self):
        return [SequentialPromptFile]


async def comfy_entrypoint():
    PromptServer.instance.add_on_prompt_handler(prepare_prompt)
    return IridioNodes()
