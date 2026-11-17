from comfy_api.latest import ComfyExtension
from server import PromptServer

from .sequential_prompt_file import SequentialPromptFile, prepare_prompt
from .folder_image_iterator import FolderImageIterator, prepare_image_prompt
from .folder_image_routes import register_folder_image_routes

WEB_DIRECTORY = "./web"


class IridioNodes(ComfyExtension):
    async def get_node_list(self):
        return [SequentialPromptFile, FolderImageIterator]


async def comfy_entrypoint():
    PromptServer.instance.add_on_prompt_handler(prepare_prompt)
    PromptServer.instance.add_on_prompt_handler(prepare_image_prompt)
    register_folder_image_routes(PromptServer.instance)
    return IridioNodes()
