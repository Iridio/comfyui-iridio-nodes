import asyncio

from aiohttp import web

from .folder_image_files import browse_folders, list_images, make_thumbnail, DENIED


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
