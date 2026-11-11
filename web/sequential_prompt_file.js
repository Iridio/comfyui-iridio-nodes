import { app } from "../../scripts/app.js";
import { setupPromptFile } from "./prompt_file.mjs";

app.registerExtension({
    name: "Iridio.SequentialPromptFile",
    nodeCreated(node) {
        if (node.comfyClass === "IridioSequentialPromptFile") setupPromptFile(node);
    },
});
