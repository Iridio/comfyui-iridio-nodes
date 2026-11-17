"""Check 100 browser-queued image jobs on the temporary CPU test server."""
import argparse
from io import BytesIO
import json
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', default='http://127.0.0.1:8189')
options = parser.parse_args()


def get(path):
    with urlopen(options.url + path, timeout=10) as response:
        return json.load(response)


def run(suffix=''):
    with urlopen(Request(options.url + '/iridio-test/run' + suffix, data=b'', method='POST'), timeout=10):
        pass


def wait_for(count):
    deadline = time.monotonic() + 60
    while True:
        history = get('/history')
        if len(history) == count:
            return history
        assert time.monotonic() < deadline, f'Expected {count} completed jobs; got {len(history)}'
        time.sleep(.1)


def check_png(result, index, names):
    assert result['status']['completed'], result
    assert result['status']['status_str'] == 'success', result
    used = result['outputs']['1']['used_image'][0]
    assert (used['file'], used['index'], used['total']) == (names[index - 1], index, 50), used
    images = result['outputs']['2']['images']
    assert len(images) == 1
    with urlopen(options.url + '/view?' + urlencode(images[0]), timeout=10) as response:
        png = response.read()
    with Image.open(BytesIO(png)) as image:
        assert image.size == (8 + index % 3, 9 + index % 2)
        assert image.getpixel((0, 0)) == (index, 0, 0)
        prompt = json.loads(image.info['prompt'])
        assert prompt['1']['inputs']['selection_json'] == json.dumps([names[index - 1]])
        assert prompt['1']['inputs']['next_image'] == 1
        workflow = json.loads(image.info['workflow'])
        source = next(node for node in workflow['nodes'] if node['id'] == 1)
        assert source['widgets_values'][:3] == [used['folder'], json.dumps([names[index - 1]]), 1]
        assert source['properties']['iridioUsedImage']['index'] == index
        if 'widgets_values_named' in source:
            assert source['widgets_values_named']['selection_json'] == json.dumps([names[index - 1]])
        text = '\n'.join(value for value in image.info.values() if isinstance(value, str))
        assert all(name not in text for name in names if name != names[index - 1])
    for event, data in result['status']['messages']:
        if event == 'execution_cached':
            assert not set(data['nodes']) & {'1', '2'}, data
    return images[0]['filename']


queue = get('/queue')
assert not queue['queue_running']
pending = sorted(queue['queue_pending'], key=lambda item: item[0])
assert len(pending) == 100, f'Expected 100 browser-queued jobs; got {len(pending)}'
fixture = get('/iridio-test/images')
names = fixture['names']
for position, item in enumerate(pending):
    assert item[2]['1']['inputs'] == {
        'folder': fixture['folder'], 'selection_json': json.dumps([names[position % 50]]), 'next_image': 1}, item

run('?count=1')
first = wait_for(1)
check_png(first[pending[0][1]], 1, names)
assert len(get('/queue')['queue_pending']) == 99
print('PASS: first PNG exists and is readable while the other 99 jobs remain paused.', flush=True)
run()
history = wait_for(100)
filenames = [check_png(history[item[1]], position % 50 + 1, names) for position, item in enumerate(pending)]
assert len(set(filenames)) == 100
assert not get('/queue')['queue_pending']
print('PASS: 100 executions, 50 images × 2 cycles, batch 1, pixels/dimensions/index/total match.')
print('PASS: 100 distinct saved PNGs with single-source replay metadata and no iterator/save cache hits.')
