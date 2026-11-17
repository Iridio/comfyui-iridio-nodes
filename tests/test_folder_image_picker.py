import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, os.environ['COMFYUI_PATH'])
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from iridio_test_support import module
from test_folder_image_files import FolderFixture

picker = module('folder_image_picker')
routes = module('folder_image_routes')
files = module('folder_image_files')


class PickerTests(FolderFixture, unittest.TestCase):
    def test_native_pick_persists_only_os_result_and_preserves_existing_roots(self):
        outside = self.root / 'external "images"'
        outside.mkdir()
        self.config.parent.mkdir()
        self.config.write_text(json.dumps({'folders': [str(self.output)], 'custom': 'keep'}))
        with patch.object(picker, 'native_folder_dialog', return_value={'path': str(outside)}) as dialog:
            result = picker.pick_folder(str(self.input))
        self.assertEqual(result['path'], str(outside))
        self.assertEqual(files.resolve_folder(str(outside)), outside)
        saved = json.loads(self.config.read_text())
        self.assertEqual(saved['custom'], 'keep')
        self.assertEqual(saved['folders'], [str(self.output), str(outside)])
        self.assertEqual(dialog.call_args.args, (str(self.input),))

    def test_cancel_or_unavailable_does_not_grant_request_path_or_overwrite_bad_config(self):
        outside = self.root / 'unapproved'
        outside.mkdir()
        for answer in ({'cancelled': True}, {'unavailable': True}):
            with patch.object(picker, 'native_folder_dialog', return_value=answer) as dialog:
                self.assertEqual(picker.pick_folder(str(outside)), answer)
            self.assertEqual(dialog.call_args.args, ('',))
            self.assertFalse(self.config.exists())
        self.config.parent.mkdir()
        self.config.write_text('{broken')
        with patch.object(picker, 'native_folder_dialog', return_value={'path': str(outside)}):
            with self.assertRaises(ValueError):
                picker.pick_folder('')
        self.assertEqual(self.config.read_text(), '{broken')

    def test_macos_start_path_is_argument_not_applescript_source(self):
        start = '/tmp/folder "quoted"'
        with patch.object(picker.sys, 'platform', 'darwin'), patch.object(picker.shutil, 'which', return_value='/usr/bin/osascript'), \
                patch.object(picker.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '/tmp/chosen folder/\n', '')) as run:
            self.assertEqual(picker.native_folder_dialog(start), {'path': '/tmp/chosen folder/'})
        command = run.call_args.args[0]
        self.assertEqual(command[-1], start)
        self.assertNotIn(start, command[2])
        self.assertFalse(run.call_args.kwargs.get('shell', False))

    def test_oversized_update_preserves_readable_original_config(self):
        self.config.parent.mkdir()
        original = json.dumps({'folders': [], 'padding': 'x' * 65500})
        self.assertLessEqual(len(original), 65536)
        self.config.write_text(original)
        with patch.object(picker, 'native_folder_dialog', return_value={'path': str(self.output)}):
            with self.assertRaises(ValueError):
                picker.pick_folder('')
        self.assertEqual(self.config.read_text(), original)

    def test_macos_cancel_and_headless_linux_are_distinct_from_failure(self):
        with patch.object(picker.sys, 'platform', 'darwin'), patch.object(picker.shutil, 'which', return_value='/usr/bin/osascript'), \
                patch.object(picker.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'User canceled. (-128)')):
            self.assertEqual(picker.native_folder_dialog(''), {'cancelled': True})
        with patch.object(picker.sys, 'platform', 'linux'), patch.dict(os.environ, {'DISPLAY': '', 'WAYLAND_DISPLAY': ''}), \
                patch.object(picker.subprocess, 'run', side_effect=AssertionError('headless desktop accessed')):
            self.assertEqual(picker.native_folder_dialog(''), {'unavailable': True})

    def test_route_is_post_only_same_origin_local_and_runs_in_thread(self):
        async def exercise():
            server = type('Server', (), {'routes': web.RouteTableDef()})()
            routes.register_folder_image_routes(server)
            app = web.Application()
            app.add_routes(server.routes)
            async with TestClient(TestServer(app)) as client:
                url = str(client.make_url('/')).rstrip('/')
                main_thread = threading.get_ident()
                def picked(start):
                    self.assertNotEqual(threading.get_ident(), main_thread)
                    return {'cancelled': True}
                with patch.object(routes, 'pick_folder', side_effect=picked) as run:
                    response = await client.get('/iridio/folder-images/pick-native')
                    self.assertEqual(response.status, 405)
                    response = await client.post('/iridio/folder-images/pick-native', json={'path': str(self.input)}, headers={'Origin': 'https://other.example'})
                    self.assertEqual(response.status, 403)
                    self.assertEqual(run.call_count, 0)
                    response = await client.post('/iridio/folder-images/pick-native', json={'path': str(self.input)}, headers={'Origin': url, 'X-Forwarded-For': '203.0.113.1'})
                    self.assertEqual(await response.json(), {'unavailable': True})
                    self.assertEqual(run.call_count, 0)
                    response = await client.post('/iridio/folder-images/pick-native', json={'path': str(self.input)}, headers={'Origin': 'https://pod.example', 'X-Forwarded-Proto': 'https', 'X-Forwarded-For': '203.0.113.1'})
                    self.assertEqual(await response.json(), {'unavailable': True})
                    self.assertEqual(run.call_count, 0)
                    response = await client.post('/iridio/folder-images/pick-native', json={'path': str(self.input)}, headers={'Origin': url})
                    self.assertEqual(await response.json(), {'cancelled': True})
                    self.assertEqual(run.call_count, 1)
        asyncio.run(exercise())
