from comfy_api.latest import ComfyExtension

from .sequential_prompt_file import SequentialPromptFile

WEB_DIRECTORY = "./web"


class IridioNodes(ComfyExtension):
    async def get_node_list(self):
        return [SequentialPromptFile]


async def comfy_entrypoint():
    return IridioNodes()
