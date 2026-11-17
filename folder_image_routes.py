import asyncio
import ipaddress
from urllib.parse import urlsplit

from aiohttp import web

from .folder_image_files import browse_folders, list_images, make_thumbnail, DENIED
from .folder_image_picker import pick_folder


def register_folder_image_routes(server):
    if getattr(server, '_iridio_folder_routes', False):
        return
    server._iridio_folder_routes = True

    async def respond(request, operation):
        try:
            folder = request.query.get('path')
            if operation == 'thumb':
                data = await asyncio.to_thread(make_thumbnail, folder, request.query.get('file'))
                return web.Response(body=data, content_type='image/jpeg', headers={'Cache-Control': 'no-store'})
            offset = int(request.query.get('offset', '0'))
            limit = int(request.query.get('limit', '100'))
            function = browse_folders if operation == 'browse' else list_images
            data = await asyncio.to_thread(function, folder, offset, limit)
            return web.json_response(data, headers={'Cache-Control': 'no-store'})
        except PermissionError:
            status, message = 403, DENIED
        except FileNotFoundError:
            status, message = 404, 'Folder or image not found. Refresh the selection.'
        except (ValueError, TypeError):
            status, message = 400, 'Invalid folder, image, configuration or page parameters.'
        except OSError:
            status, message = 400, 'Could not read the folder or image.'
        return web.json_response({'message': message}, status=status, headers={'Cache-Control': 'no-store'})

    @server.routes.get('/iridio/folder-images/browse')
    async def browse(request):
        return await respond(request, 'browse')

    @server.routes.get('/iridio/folder-images/list')
    async def listing(request):
        return await respond(request, 'list')

    @server.routes.get('/iridio/folder-images/thumb')
    async def thumbnail(request):
        return await respond(request, 'thumb')

    @server.routes.post('/iridio/folder-images/pick-native')
    async def native_picker(request):
        headers = {'Cache-Control': 'no-store'}
        try:
            peer = ipaddress.ip_address(request.remote or '')
            hostname = urlsplit(f'{request.scheme}://{request.host}').hostname
            local_host = hostname == 'localhost' or ipaddress.ip_address(hostname).is_loopback
            local_peer = peer.is_loopback or bool(getattr(peer, 'ipv4_mapped', None) and peer.ipv4_mapped.is_loopback)
        except ValueError:
            local_host = local_peer = False
        if not local_peer or not local_host or any(name in request.headers for name in ('Forwarded', 'X-Forwarded-For', 'X-Forwarded-Host')):
            return web.json_response({'unavailable': True}, headers=headers)
        if (request.content_type != 'application/json'
                or request.headers.get('Origin') != f'{request.scheme}://{request.host}'):
            return web.json_response({'message': 'Use Browse from the local ComfyUI interface.'}, status=403, headers=headers)
        try:
            if request.content_length is not None and request.content_length > 8192:
                raise ValueError('Picker request too large.')
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError('Invalid picker request.')
            result = await asyncio.to_thread(pick_folder, data.get('path', ''))
            return web.json_response(result, headers=headers)
        except (OSError, ValueError, TypeError):
            return web.json_response({'message': 'Could not save the selected folder. Check permissions and iridio/allowed_folders.json.'}, status=400, headers=headers)
