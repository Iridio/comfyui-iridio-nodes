from io import BytesIO
import json
import os
from pathlib import Path, PureWindowsPath
import re

from PIL import Image, ImageOps
import numpy as np
import folder_paths

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff', '.tif'}
DENIED = 'Folder is not allowed. Configure iridio/allowed_folders.json on the server.'


def validate_folder_path(value):
    if not isinstance(value, str) or not value or len(value) > 4096 or '\0' in value:
        raise ValueError('Choose an absolute server folder path.')
    if value.startswith(('\\\\', '//')) or not Path(value).is_absolute():
        raise ValueError('Choose an absolute local server folder path.')
    return Path(value)


def _absolute_path(value):
    return validate_folder_path(value).resolve()


def allowed_roots():
    roots = [Path(folder_paths.get_input_directory()).resolve(),
             Path(folder_paths.get_output_directory()).resolve()]
    config = Path(folder_paths.get_user_directory()) / 'iridio' / 'allowed_folders.json'
    try:
        content = config.read_text(encoding='utf-8')
    except FileNotFoundError:
        return roots
    if len(content) > 65536:
        raise ValueError('iridio/allowed_folders.json is too large.')
    try:
        data = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError('Fix invalid JSON in iridio/allowed_folders.json.') from error
    if not isinstance(data, dict) or not isinstance(data.get('folders'), list):
        raise ValueError('iridio/allowed_folders.json needs a folders array.')
    roots.extend(_absolute_path(value) for value in data['folders'])
    return list(dict.fromkeys(roots))


def resolve_folder(folder):
    path = _absolute_path(folder)
    if not any(path.is_relative_to(root) for root in allowed_roots()):
        raise PermissionError(DENIED)
    if not path.is_dir():
        raise FileNotFoundError('Server folder not found.')
    return path


def resolve_image(folder, relative_name):
    base = resolve_folder(folder)
    return _image_path(base, relative_name)


def _image_path(base, relative_name):
    validate_image_name(relative_name)
    path = (base / relative_name).resolve()
    if not path.is_relative_to(base):
        raise PermissionError(DENIED)
    if not path.is_file():
        raise FileNotFoundError(f'Image not found: {relative_name}')
    return path


def validate_image_name(relative_name):
    if (not isinstance(relative_name, str) or not relative_name or len(relative_name) > 255
            or '\0' in relative_name or '/' in relative_name or '\\' in relative_name
            or PureWindowsPath(relative_name).drive or relative_name in ('.', '..')):
        raise ValueError('Choose an image directly inside the selected folder.')
    if Path(relative_name).suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError('Unsupported image extension.')


def _name_key(name):
    return tuple((1, int(part)) if part.isdecimal() else (0, part.casefold())
                 for part in re.split(r'(\d+)', name)), name


def _page(items, offset, limit):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError('Use offset >= 0 and limit between 1 and 200.')
    return {'total': len(items), 'offset': offset, 'items': items[offset:offset + limit]}


def list_images(folder, offset=0, limit=100):
    base = resolve_folder(folder)
    names = []
    with os.scandir(base) as directory:
        for entry in directory:
            if Path(entry.name).suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            if entry.is_file(follow_symlinks=False):
                names.append(entry.name)
            elif entry.is_symlink():
                try:
                    _image_path(base, entry.name)
                    names.append(entry.name)
                except (OSError, ValueError):
                    pass
    names.sort(key=_name_key)
    page = _page(names, offset, limit)
    entries = []
    for name in page.pop('items'):
        try:
            path = _image_path(base, name)
            stat = path.stat()
        except (OSError, ValueError):
            continue
        entries.append({'file': name, 'name': name, 'size': stat.st_size, 'mtime_ns': str(stat.st_mtime_ns)})
    return {'folder': str(base), 'files': entries, **page}


def browse_folders(folder=None, offset=0, limit=100):
    roots = allowed_roots()
    base = resolve_folder(folder) if folder else None
    entries = roots if base is None else sorted(base.iterdir(), key=lambda p: _name_key(p.name))
    dirs = []
    for entry in entries:
        try:
            path = resolve_folder(str(entry))
        except (OSError, ValueError):
            continue
        dirs.append({'name': entry.name or str(entry), 'path': str(path)})
    parent = None
    if base is not None and base.parent != base:
        try:
            parent = str(resolve_folder(str(base.parent)))
        except (OSError, ValueError):
            pass
    page = _page(dirs, offset, limit)
    return {'path': str(base) if base else None, 'parent': parent, 'dirs': page.pop('items'), **page}


def make_thumbnail(folder, relative_name):
    path = resolve_image(folder, relative_name)
    with Image.open(path) as source:
        image = display_frame(source).convert('RGB')
        image.thumbnail((192, 192))
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=80)
    return buffer.getvalue()


def display_frame(source):
    frame = ImageOps.exif_transpose(source)
    if frame.mode.startswith('I;16') or frame.mode == 'I':
        frame = Image.fromarray(np.rint(np.clip(np.asarray(frame), 0, 65535) / 257).astype(np.uint8))
    return frame
