"""Verify 100 browser-queued jobs on tests/comfyui_server.py, then execute them."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--url", default="http://127.0.0.1:8189")
parser.add_argument("--save-dir", type=Path, help="Optionally retain the checked PNGs for browser reload.")
options = parser.parse_args()


def get(path):
    with urlopen(options.url + path, timeout=10) as response:
        return json.load(response)


queue = get("/queue")
assert not queue["queue_running"], "Use a fresh, paused test server."
pending = sorted(queue["queue_pending"], key=lambda item: item[0])
assert len(pending) == 100, f"Expected 100 queued jobs, got {len(pending)}"
expected = list(range(1, 51)) * 2
for item, index in zip(pending, expected):
    assert item[2]["1"]["inputs"]["next_prompt"] == index, item

with urlopen(Request(options.url + "/iridio-test/run", data=b"", method="POST"), timeout=10):
    pass
deadline = time.monotonic() + 60
while True:
    history = get("/history")
    if len(history) == 100:
        break
    assert time.monotonic() < deadline, f"Only {len(history)} jobs completed in 60s"
    time.sleep(0.1)

for item, index in zip(pending, expected):
    result = history[item[1]]
    assert result["status"]["completed"], result
    assert result["status"]["status_str"] == "success", result
    assert result["outputs"]["2"] == {
        "prompt": [f"Prompt {index:02d}: test scene {index:02d}"],
        "index": [index], "total": [50],
    }, result
    expected_text = f"Prompt {index:02d}: test scene {index:02d}"
    used = {"text": expected_text, "index": index, "total": 50}
    assert result["outputs"]["1"] == {"used_prompt": [used]}, result
    images = result["outputs"]["3"]["images"]
    assert len(images) == 1, images
    with urlopen(options.url + "/view?" + urlencode(images[0]), timeout=10) as response:
        png = response.read()
    with Image.open(BytesIO(png)) as image:
        workflow = json.loads(image.info["workflow"])
        source = next(node for node in workflow["nodes"] if node["id"] == 1)
        assert source["properties"]["iridioUsedPrompt"] == used, source
        assert source["widgets_values"][:2] == [item[2]["1"]["inputs"]["prompt_text"], index], source
        api_prompt = json.loads(image.info["prompt"])
        assert api_prompt["1"]["inputs"]["next_prompt"] == index, api_prompt
        assert image.getpixel((0, 0)) == (index, index, index), images
    if options.save_dir:
        options.save_dir.mkdir(parents=True, exist_ok=True)
        (options.save_dir / images[0]["filename"]).write_bytes(png)
    for event, data in result["status"]["messages"]:
        if event == "execution_cached":
            assert not set(data["nodes"]) & {"1", "2", "3"}, "Sequence or save was cached"

queue = get("/queue")
assert not queue["queue_pending"] and not queue["queue_running"], queue
get("/api/jobs")
print("PASS: 100 jobs queued before execution, indices 1–50 twice, exact prompt/index/total,")
print("100 successful executions with no sequence/output cache hits; queue empty.")
print("All 100 saved PNGs contain the exact used prompt/index/total and matching input snapshot/pixels.")
