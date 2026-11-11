"""Verify 100 browser-queued jobs on tests/comfyui_server.py, then execute them."""
import argparse
import json
import time
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--url", default="http://127.0.0.1:8189")
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
    for event, data in result["status"]["messages"]:
        if event == "execution_cached":
            assert not set(data["nodes"]) & {"1", "2"}, "Sequence was cached"

queue = get("/queue")
assert not queue["queue_pending"] and not queue["queue_running"], queue
get("/api/jobs")
print("PASS: 100 jobs queued before execution, indices 1–50 twice, exact prompt/index/total,")
print("100 successful executions with no sequence/output cache hits; queue empty.")
