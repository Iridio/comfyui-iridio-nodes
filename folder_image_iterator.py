import json
import asyncio
from pathlib import Path

import numpy as np
from PIL import Image
import torch
from comfy_api.latest import io

from .folder_image_files import resolve_image, validate_folder_path, validate_image_name, display_frame

NODE_ID = 'IridioFolderImageIterator'


def select_image(folder, selection_json, next_image):
    if not isinstance(selection_json, str) or len(selection_json) > 10_000_000:
        raise ValueError('Choose an image selection (maximum 10 MB).')
    selection = json.loads(selection_json)
    if isinstance(selection, dict) and isinstance(selection.get('error'), str):
        raise ValueError(selection['error'])
    if (not isinstance(selection, list) or not selection or len(selection) > 100000
            or any(not isinstance(name, str) for name in selection)
            or len(set(selection)) != len(selection)):
        raise ValueError('Choose a non-empty selection of unique image filenames.')
    if type(next_image) is not int or not 1 <= next_image <= 2147483647:
        raise ValueError('Next image must be a positive integer starting at 1.')
    base = validate_folder_path(folder)
    # Validate every submitted name without opening or decoding the other images.
    for name in selection:
        validate_image_name(name)
    index = (next_image - 1) % len(selection)
    path = base / selection[index]
    return {'folder': str(base), 'file': selection[index], 'path': str(path),
            'index': index + 1, 'total': len(selection)}


def _original_selection(candidate, used, next_image):
    return (isinstance(candidate, dict) and next_image == 1
            and all(candidate.get(key) == used[key] for key in ('folder', 'file'))
            and type(candidate.get('index')) is int and type(candidate.get('total')) is int
            and 1 <= candidate['index'] <= candidate['total'] <= 100000)


def _has_nested_iterator(workflow):
    definitions = workflow.get('definitions', {})
    def contains(value):
        if isinstance(value, dict):
            return value.get('type') == NODE_ID or any(contains(item) for item in value.values())
        return isinstance(value, list) and any(contains(item) for item in value)
    return contains(definitions)


def prepare_image_prompt(request):
    metadata = request.get('extra_data', {}).get('extra_pnginfo') or {}
    workflow = metadata.get('workflow') or {}
    if not (any(node.get('class_type') == NODE_ID for node in request.get('prompt', {}).values())
            or any(node.get('type') == NODE_ID for node in workflow.get('nodes', []))):
        return request
    request.setdefault('extra_data', {})['extra_pnginfo'] = metadata
    previous = metadata.get('iridioImageSelections') or {}
    if not isinstance(previous, dict):
        previous = {}
    selections = {}
    for node_id, node in request.get('prompt', {}).items():
        if node.get('class_type') != NODE_ID:
            continue
        inputs = node.setdefault('inputs', {})
        try:
            if _has_nested_iterator(workflow):
                raise ValueError('Folder Image Iterator is not supported inside subgraphs. Move it to the main graph.')
            values = {key: value.get('__value__', value) if isinstance(value, dict) else value
                      for key, value in inputs.items()}
            used = select_image(values.get('folder'), values.get('selection_json'), values.get('next_image'))
            candidate = previous.get(node_id)
            if _original_selection(candidate, used, values.get('next_image')):
                used = {**used, 'index': candidate['index'], 'total': candidate['total']}
            selections[node_id] = used
            inputs.update(folder=used['folder'], selection_json=json.dumps([used['file']], ensure_ascii=False), next_image=1)
        except (ValueError, TypeError, OSError) as error:
            # Prompt handlers swallow exceptions; an invalid input makes normal validation reject the job.
            inputs['selection_json'] = json.dumps({'error': str(error)})
    metadata['iridioImageSelections'] = selections
    for node in workflow.get('nodes', []):
        used = selections.get(str(node['id']))
        if used is None and node.get('type') != NODE_ID:
            continue
        folder = used['folder'] if used else ''
        selection = json.dumps([used['file']], ensure_ascii=False) if used else '[]'
        node.setdefault('widgets_values', [])[:3] = [folder, selection, 1]
        if 'widgets_values_named' in node:
            node['widgets_values_named'].update(folder=folder, selection_json=selection, next_image=1)
        node.setdefault('properties', {}).pop('iridioUsedImage', None)
    return request


class FolderImageIterator(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id=NODE_ID, display_name='Folder Image Iterator (Iridio)', category='Iridio Nodes',
            description='One server-folder image per run. Next image advances on successful queue submission and wraps to 1. Top-level graphs only.',
            inputs=[
                io.String.Input('folder', default='', socketless=True, dynamic_prompts=False,
                                tooltip='Absolute folder on the ComfyUI server. Browse opens the local OS picker; remote roots need iridio/allowed_folders.json.'),
                io.String.Input('selection_json', default='[]', socketless=True, dynamic_prompts=False,
                                tooltip='Ordered image selection. Use Select images to choose files.'),
                io.Int.Input('next_image', display_name='Next image', default=1, min=1, max=2147483647,
                             step=1, socketless=True, control_after_generate=False,
                             tooltip='One-based next queue position; wraps after the last image. Cancelled queued jobs consume their position.'),
            ],
            outputs=[io.Image.Output('image'), io.Mask.Output('mask'), io.Int.Output('width'),
                     io.Int.Output('height'), io.String.Output('filename'), io.Int.Output('index'),
                     io.Int.Output('total'), io.String.Output('path')],
            hidden=[io.Hidden.unique_id, io.Hidden.extra_pnginfo],
        )

    @classmethod
    async def validate_inputs(cls, folder, selection_json, next_image):
        try:
            used = select_image(folder, selection_json, next_image)
            await asyncio.to_thread(resolve_image, used['folder'], used['file'])
            return True
        except (ValueError, TypeError, OSError) as error:
            return str(error)

    @classmethod
    def fingerprint_inputs(cls, folder, selection_json, next_image):
        return float('nan')

    @classmethod
    def execute(cls, folder, selection_json, next_image):
        used = select_image(folder, selection_json, next_image)
        metadata = cls.hidden.extra_pnginfo if cls.hidden is not None else None
        node_id = cls.hidden.unique_id if cls.hidden is not None else None
        candidate = (metadata or {}).get('iridioImageSelections', {}).get(node_id)
        if _original_selection(candidate, used, next_image):
            used.update(index=candidate['index'], total=candidate['total'])
        source_path = resolve_image(used['folder'], used['file'])
        used['path'] = str(source_path)
        with Image.open(source_path) as source:
            frame = display_frame(source)
            rgba = frame.convert('RGBA')
            image = torch.from_numpy(np.array(rgba.convert('RGB'), dtype=np.float32) / 255)[None]
            mask = torch.from_numpy(1 - np.array(rgba.getchannel('A'), dtype=np.float32) / 255)[None]
            width, height = rgba.size
        used.update(width=width, height=height)
        if metadata is not None:
            for node in (metadata.get('workflow') or {}).get('nodes', []):
                if str(node['id']) == node_id:
                    node.setdefault('properties', {})['iridioUsedImage'] = used
                    break
        return io.NodeOutput(image, mask, width, height, Path(used['file']).stem,
                             used['index'], used['total'], used['path'], ui={'used_image': [used]})
