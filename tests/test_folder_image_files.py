import asyncio
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.environ['COMFYUI_PATH'])
from PIL import Image
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import folder_paths
from iridio_test_support import module
files = module('folder_image_files')
register_folder_image_routes = module('folder_image_routes').register_folder_image_routes


class FolderFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.input = self.root / 'input'
        self.output = self.root / 'output'
        self.user = self.root / 'user'
        for p in (self.input, self.output, self.user):
            p.mkdir()
        for getter, value in [('get_input_directory', self.input),
                              ('get_output_directory', self.output),
                              ('get_user_directory', self.user)]:
            mock = patch.object(folder_paths, getter, return_value=str(value))
            mock.start()
            self.addCleanup(mock.stop)
        self.config = self.user / 'iridio' / 'allowed_folders.json'
        for name in ('10.png', '2.png', '1.png', 'café.png'):
            Image.new('RGB', (300, 180), 'red').save(self.input / name)


class ImageFolderTests(FolderFixture, unittest.TestCase):
    def test_natural_paging_no_decode_and_approved_external_root(self):
        (self.input / 'secret.txt').write_text('not an image')
        with patch.object(Image, 'open', side_effect=AssertionError('listing decoded an image')):
            self.assertEqual([f['file'] for f in files.list_images(str(self.input), 0, 2)['files']], ['1.png', '2.png'])
            self.assertEqual([f['file'] for f in files.list_images(str(self.input), 2, 2)['files']], ['10.png', 'café.png'])
        self.config.parent.mkdir()
        self.config.write_text(json.dumps({'folders': [str(self.root / 'external')]}))
        (self.root / 'external').mkdir()
        self.assertEqual(files.resolve_folder(str(self.root / 'external')), self.root / 'external')
        self.assertEqual(files.list_images(str(self.input))['total'], 4)

    def test_reject_traversal_absolute_names_prefix_and_symlink_escape(self):
        other = self.root / 'input-secret'
        other.mkdir()
        Image.new('RGB', (1, 1)).save(other / 'secret.png')
        (self.input / 'link.png').symlink_to(other / 'secret.png')
        for name in ('../input-secret/secret.png', str(other / 'secret.png'), 'link.png', '..\\secret.png', 'x/../../secret.png'):
            with self.subTest(name=name), self.assertRaises((ValueError, PermissionError)):
                files.resolve_image(str(self.input), name)
        with self.assertRaises(PermissionError):
            files.resolve_folder(str(other))
        self.assertNotIn('link.png', [f['file'] for f in files.list_images(str(self.input))['files']])

    def test_invalid_config_and_invalid_paging_fail_closed(self):
        self.config.parent.mkdir()
        self.config.write_text('{bad')
        with self.assertRaises(ValueError):
            files.resolve_folder(str(self.input))
        self.config.write_text('{"folders": "not-an-array"}')
        with self.assertRaises(ValueError):
            files.resolve_folder(str(self.input))
        self.config.unlink()
        for offset, limit in ((-1, 20), (0, 201), (True, 20), (0, 0)):
            with self.assertRaises(ValueError):
                files.list_images(str(self.input), offset, limit)

    def test_browse_keeps_parent_inside_roots_and_thumbnail_is_small(self):
        (self.input / 'sub').mkdir()
        root = files.browse_folders(None)
        self.assertEqual({d['path'] for d in root['dirs']}, {str(self.input), str(self.output)})
        listing = files.browse_folders(str(self.input))
        self.assertIsNone(listing['parent'])
        self.assertEqual([d['name'] for d in listing['dirs']], ['sub'])
        self.assertEqual(files.browse_folders(str(self.input / 'sub'))['parent'], str(self.input))
        with Image.open(BytesIO(files.make_thumbnail(str(self.input), '1.png'))) as image:
            self.assertEqual(image.size, (192, 115))
        with self.assertRaises(ValueError):
            files.make_thumbnail(str(self.input), 'secret.txt')

    def test_http_routes_enforce_same_policy(self):
        async def exercise():
            server = type('Server', (), {'routes': web.RouteTableDef()})()
            register_folder_image_routes(server)
            register_folder_image_routes(server)
            app = web.Application()
            app.add_routes(server.routes)
            async with TestClient(TestServer(app)) as client:
                response = await client.get('/iridio/folder-images/list', params={'path': str(self.input), 'limit': '2'})
                self.assertEqual(response.status, 200)
                self.assertEqual((await response.json())['total'], 4)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                for suffix in ('secret', 'absent'):
                    response = await client.get('/iridio/folder-images/list', params={'path': str(self.root / suffix)})
                    self.assertEqual(response.status, 403)
                    self.assertEqual((await response.json())['message'], 'Folder is not allowed. Configure iridio/allowed_folders.json on the server.')
                response = await client.get('/iridio/folder-images/thumb', params={'path': str(self.input), 'file': '../secret.png'})
                self.assertEqual(response.status, 400)
                response = await client.get('/iridio/folder-images/list', params={'path': str(self.input), 'offset': 'bad'})
                self.assertEqual(response.status, 400)
                response = await client.get('/iridio/folder-images/thumb', params={'path': str(self.input), 'file': '1.png'})
                self.assertEqual(response.content_type, 'image/jpeg')
        asyncio.run(exercise())

    def test_unicode_nonnumeric_digit_name_and_16_bit_thumbnail(self):
        Image.new('RGB', (1, 1)).save(self.input / '²1.png')
        self.assertIn('²1.png', [entry['file'] for entry in files.list_images(str(self.input))['files']])
        Image.new('I;16', (1, 1), 32768).save(self.input / 'gray.png')
        with Image.open(BytesIO(files.make_thumbnail(str(self.input), 'gray.png'))) as image:
            self.assertLess(abs(image.getpixel((0, 0))[0] - 128), 3)

    def test_listing_stats_only_requested_page(self):
        with patch.object(files, '_image_path', wraps=files._image_path) as access:
            files.list_images(str(self.input), 0, 1)
        self.assertEqual(access.call_count, 1)
