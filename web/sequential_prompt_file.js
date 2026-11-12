import { app } from "../../scripts/app.js";
// ComfyUI sends Cache-Control: no-store for .js modules.
import { setupPromptFile } from "./prompt_file.js";

app.registerExtension({
    name: "Iridio.SequentialPromptFile",
    nodeCreated(node) {
        if (node.comfyClass === "IridioSequentialPromptFile") setupPromptFile(node);
    },
});
