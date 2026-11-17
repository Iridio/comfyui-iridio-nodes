import copy
import asyncio
import json
import math
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import threading

sys.path.insert(0, os.environ['COMFYUI_PATH'])
from comfy.cli_args import args
args.cpu = True
from comfy_api.latest import io
import numpy as np
from PIL import Image
from iridio_test_support import module
from test_folder_image_files import FolderFixture

iterator = module('folder_image_iterator')


class IteratorTests(FolderFixture, unittest.TestCase):
    def test_circular_selection_and_invalid_inputs(self):
        selection = '["1.png","2.png","10.png"]'
        for position, name, index in ((1, '1.png', 1), (2, '2.png', 2), (3, '10.png', 3), (4, '1.png', 1), (8, '2.png', 2)):
            used = iterator.select_image(str(self.input), selection, position)
            self.assertEqual((used['file'], used['index'], used['total']), (name, index, 3))
        for selection, position in (('[]', 1), ('["1.png","1.png"]', 1), ('[null]', 1), ('{}', 1), ('["1.png"]', True), ('["1.png"]', 0), ('["../secret.png"]', 1)):
            with self.subTest(selection=selection, position=position), self.assertRaises((ValueError, PermissionError)):
                iterator.select_image(str(self.input), selection, position)

    def execute_file(self, name):
        return iterator.FolderImageIterator.execute(str(self.input), json.dumps([name]), 1)

    def test_decode_batch_one_alpha_exif_integer_and_first_frame(self):
        Image.new('RGBA', (4, 3), (255, 0, 0, 64)).save(self.input / 'alpha.png')
        result = self.execute_file('alpha.png').result
        self.assertEqual(tuple(result[0].shape), (1, 3, 4, 3))
        self.assertEqual(tuple(result[1].shape), (1, 3, 4))
        self.assertAlmostEqual(result[1][0, 0, 0].item(), 1 - 64 / 255, places=6)
        self.assertEqual(result[2:7], (4, 3, 'alpha', 1, 1))
        palette = Image.new('P', (2, 2), 0)
        palette.putpalette([255, 0, 0] + [0, 0, 0] * 255)
        palette.save(self.input / 'palette.png', transparency=0)
        self.assertEqual(self.execute_file('palette.png').result[1].min().item(), 1)
        exif = Image.Exif()
        exif[274] = 6
        Image.new('RGB', (2, 3), 'blue').save(self.input / 'exif.jpg', exif=exif)
        self.assertEqual(self.execute_file('exif.jpg').result[2:4], (3, 2))
        Image.fromarray(np.array([[0, 32768, 65535]], dtype=np.uint16)).save(self.input / 'integer.png')
        values = self.execute_file('integer.png').result[0][0, 0, :, 0].tolist()
        self.assertEqual(values[0], 0)
        self.assertAlmostEqual(values[1], 128 / 255, places=6)
        self.assertEqual(values[2], 1)
        Image.new('RGB', (2, 2), 'red').save(self.input / 'animated.gif', save_all=True, append_images=[Image.new('RGB', (2, 2), 'blue')], duration=100)
        image, mask = self.execute_file('animated.gif').result[:2]
        self.assertEqual(tuple(image.shape), (1, 2, 2, 3))
        self.assertEqual(image[0, 0, 0].tolist(), [1, 0, 0])
        self.assertEqual(mask.max().item(), 0)

    def request(self):
        selection = '["1.png","2.png","10.png"]'
        return {'prompt': {'7': {'class_type': 'IridioFolderImageIterator', 'inputs': {
            'folder': str(self.input), 'selection_json': selection, 'next_image': 2}},
            '9': {'class_type': 'IridioSequentialPromptFile', 'inputs': {'prompt_text': 'first\nsecond', 'next_prompt': 2}}},
            'extra_data': {'extra_pnginfo': {'workflow': {'nodes': [{'id': 7, 'type': 'IridioFolderImageIterator',
                'widgets_values': [str(self.input), selection, 2, ''],
                'widgets_values_named': {'folder': str(self.input), 'selection_json': selection, 'next_image': 2},
                'properties': {'keep': True}}]}}}}

    def test_queue_snapshot_isolation_idempotency_and_mixed_nodes(self):
        request = self.request()
        metadata = request['extra_data']['extra_pnginfo']
        iterator.prepare_image_prompt(request)
        self.assertEqual(request['prompt']['7']['inputs']['selection_json'], '["2.png"]')
        self.assertEqual(request['prompt']['7']['inputs']['next_image'], 1)
        saved = metadata['workflow']['nodes'][0]
        self.assertEqual(saved['widgets_values'][:3], [str(self.input), '["2.png"]', 1])
        self.assertEqual(saved['widgets_values_named']['selection_json'], '["2.png"]')
        self.assertEqual(saved['properties']['keep'], True)
        self.assertNotIn('10.png', str(request))
        self.assertNotIn('1.png', str(request))
        before = copy.deepcopy(request)
        iterator.prepare_image_prompt(request)
        self.assertEqual(request, before)
        node = iterator.FolderImageIterator.PREPARE_CLASS_CLONE({'hidden_inputs': {
            io.Hidden.unique_id: '7', io.Hidden.extra_pnginfo: metadata}})
        result = node.execute(**request['prompt']['7']['inputs'])
        self.assertEqual(result.result[5:7], (2, 3))
        self.assertEqual(result.ui['used_image'][0]['file'], '2.png')
        self.assertEqual(request['prompt']['9']['inputs']['prompt_text'], 'first\nsecond')
        self.assertTrue(math.isnan(node.fingerprint_inputs(**request['prompt']['7']['inputs'])))

    def test_headless_two_nodes_and_removed_file_after_submission(self):
        request = self.request()
        request.pop('extra_data')
        request['prompt']['8'] = copy.deepcopy(request['prompt']['7'])
        request['prompt']['8']['inputs']['next_image'] = 3
        iterator.prepare_image_prompt(request)
        self.assertEqual(request['prompt']['8']['inputs']['selection_json'], '["10.png"]')
        (self.input / '2.png').unlink()
        with self.assertRaises(FileNotFoundError):
            iterator.FolderImageIterator.execute(**request['prompt']['7']['inputs'])

    def test_changed_bytes_are_read_at_execution_and_subgraphs_rejected(self):
        request = self.request()
        iterator.prepare_image_prompt(request)
        Image.new('RGB', (5, 7), 'blue').save(self.input / '2.png')
        result = iterator.FolderImageIterator.execute(**request['prompt']['7']['inputs']).result
        self.assertEqual(result[2:4], (5, 7))
        self.assertEqual(result[0][0, 0, 0].tolist(), [0, 0, 1])
        request = self.request()
        request['extra_data']['extra_pnginfo']['workflow']['definitions'] = {'subgraphs': [
            {'id': 'sub', 'nodes': [{'type': 'IridioFolderImageIterator'}]}]}
        iterator.prepare_image_prompt(request)
        self.assertIn('subgraph', asyncio.run(iterator.FolderImageIterator.validate_inputs(**request['prompt']['7']['inputs'])))

    def test_inactive_only_iterator_is_scrubbed_from_png_workflow(self):
        request = self.request()
        request['prompt'].pop('7')
        request['extra_data']['extra_pnginfo']['workflow']['nodes'][0]['properties']['iridioUsedImage'] = {'file': 'private.png'}
        iterator.prepare_image_prompt(request)
        self.assertNotIn('10.png', str(request))
        self.assertNotIn('private.png', str(request))
        self.assertEqual(request['extra_data']['extra_pnginfo']['workflow']['nodes'][0]['widgets_values'][:3], ['', '[]', 1])

    def test_queued_node_does_not_claim_execution_and_invalid_old_metadata_is_replaced(self):
        request = self.request()
        request['extra_data']['extra_pnginfo']['iridioImageSelections'] = [{'invalid': 'metadata'}]
        iterator.prepare_image_prompt(request)
        self.assertNotIn('iridioUsedImage', request['extra_data']['extra_pnginfo']['workflow']['nodes'][0]['properties'])
        self.assertNotIn('10.png', str(request))

    def test_prepare_is_disk_free_and_validation_runs_off_event_loop(self):
        request = self.request()
        with patch.object(iterator, 'resolve_image', side_effect=AssertionError('filesystem in prepare')):
            iterator.prepare_image_prompt(request)
        main_thread = threading.get_ident()
        threads = []
        original = iterator.resolve_image
        def record(*args):
            threads.append(threading.get_ident())
            return original(*args)
        with patch.object(iterator, 'resolve_image', side_effect=record):
            self.assertIs(asyncio.run(iterator.FolderImageIterator.validate_inputs(**request['prompt']['7']['inputs'])), True)
        self.assertTrue(threads)
        self.assertNotIn(main_thread, threads)

    def test_symlink_retarget_preserves_original_queue_index(self):
        (self.input / 'alias.png').symlink_to(self.input / '1.png')
        request = self.request()
        request['prompt']['7']['inputs']['selection_json'] = '["2.png","alias.png","10.png"]'
        iterator.prepare_image_prompt(request)
        (self.input / 'alias.png').unlink()
        (self.input / 'alias.png').symlink_to(self.input / '10.png')
        metadata = request['extra_data']['extra_pnginfo']
        node = iterator.FolderImageIterator.PREPARE_CLASS_CLONE({'hidden_inputs': {
            io.Hidden.unique_id: '7', io.Hidden.extra_pnginfo: metadata}})
        result = node.execute(**request['prompt']['7']['inputs'])
        self.assertEqual(result.result[5:7], (2, 3))
