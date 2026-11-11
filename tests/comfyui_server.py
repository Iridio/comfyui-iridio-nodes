"""Temporary CPU ComfyUI server: only Iridio and a test output, no installation.

Run with COMFYUI_PATH set, using ComfyUI's Python. The queue starts paused;
POST /iridio-test/run releases it. All writable directories are temporary.
"""
import argparse
import asyncio
import os
from pathlib import Path
import sys
import tempfile
import threading

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--port", type=int, default=8189)
options = parser.parse_args()
sys.path.insert(0, os.environ["COMFYUI_PATH"])

from comfy.cli_args import args

temporary = tempfile.TemporaryDirectory(prefix="iridio-comfyui-")
args.cpu = True
args.base_directory = temporary.name
args.disable_assets = True
args.offline = True

import comfyui_frontend_package

args.front_end_root = str(Path(comfyui_frontend_package.__file__).parent / "static")

from aiohttp import web
from app.assets.manager import NoAssets
from comfy_api.latest import io
import execution
import nodes
from server import PromptServer


class TestPromptOutput(io.ComfyNode):
    RELATIVE_PYTHON_MODULE = "tests.iridio"

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="IridioTestPromptOutput", display_name="Test Prompt Output",
            category="Iridio Tests", is_output_node=True,
            inputs=[io.String.Input("prompt", force_input=True),
                    io.Int.Input("index", force_input=True),
                    io.Int.Input("total", force_input=True)],
        )

    @classmethod
    def execute(cls, prompt, index, total):
        return io.NodeOutput(ui={"prompt": [prompt], "index": [index], "total": [total]})


async def main():
    server = PromptServer(asyncio.get_running_loop(), NoAssets(args))
    assert await nodes.load_custom_node(str(Path(__file__).resolve().parents[1]))
    nodes.NODE_CLASS_MAPPINGS["IridioTestPromptOutput"] = TestPromptOutput
    gate = threading.Event()

    @server.routes.post("/iridio-test/run")
    async def run_queue(request):
        gate.set()
        return web.json_response({"running": True})

    def worker():
        executor = execution.PromptExecutor(
            server, cache_type=execution.CacheType.CLASSIC,
            cache_args={"ram": 0, "ram_inactive": 0},
        )
        while True:
            gate.wait()
            task = server.prompt_queue.get(timeout=0.1)
            if task is None:
                continue
            item, item_id = task
            executor.execute(item[2], item[1], item[3], item[4])
            status = execution.PromptQueue.ExecutionStatus(
                status_str="success" if executor.success else "error",
                completed=executor.success, messages=executor.status_messages,
            )
            server.prompt_queue.task_done(item_id, executor.history_result, status,
                                          process_item=lambda item: item[:5])
            server.send_sync("executing", {"node": None, "prompt_id": item[1]}, server.client_id)

    server.add_routes()
    await server.setup()
    threading.Thread(target=worker, daemon=True).start()
    await server.start("127.0.0.1", options.port)
    print(f"Iridio test server: http://127.0.0.1:{options.port} (queue paused)", flush=True)
    try:
        await server.publish_loop()
    finally:
        await server.client_session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        temporary.cleanup()
