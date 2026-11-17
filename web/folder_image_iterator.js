import { app } from '../../scripts/app.js';
import { api } from '../../scripts/api.js';
import { setupFolderImageIterator } from './folder_image_panel.js';

app.registerExtension({
    name: 'Iridio.FolderImageIterator',
    nodeCreated(node) {
        if (node.comfyClass === 'IridioFolderImageIterator') setupFolderImageIterator(node, api);
    },
    setup() {
        const graphToPrompt = app.graphToPrompt;
        app.graphToPrompt = async function () {
            const result = await graphToPrompt.apply(this, arguments);
            const contains = value => value && typeof value === 'object' &&
                (value.type === 'IridioFolderImageIterator' || Object.values(value).some(contains));
            if (contains(result.workflow?.definitions)) {
                throw new Error('Folder Image Iterator is not supported inside subgraphs. Move it to the main graph.');
            }
            return result;
        };
    },
});
