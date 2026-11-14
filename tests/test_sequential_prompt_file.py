import asyncio
import copy
import importlib.util
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, os.environ["COMFYUI_PATH"])
from comfy.cli_args import args
from comfy_api.latest import io

args.cpu = True
from sequential_prompt_file import SequentialPromptFile, parse_prompts
import sequential_prompt_file


class SequentialPromptFileTests(unittest.TestCase):
    def test_queued_request_contains_only_selected_prompt_in_both_graphs(self):
        request = {"prompt": {
            "7": {"class_type": "IridioSequentialPromptFile",
                  "inputs": {"prompt_text": "private first\nselected café\nprivate third", "next_prompt": 5}},
            "8": {"class_type": "OtherNode", "inputs": {"text": "untouched"}},
        }, "extra_data": {"extra_pnginfo": {"workflow": {"nodes": [
            {"id": 7, "widgets_values": ["private first\nselected café\nprivate third", 5, ""],
             "widgets_values_named": {"prompt_text": "private first\nselected café\nprivate third",
                                      "next_prompt": 5, "other": "keep"},
             "properties": {"label": "keep"}},
            {"id": 8, "widgets_values": ["untouched"]},
        ]}, "other_metadata": "keep"}}}
        working = copy.deepcopy(request)
        prepared = sequential_prompt_file.prepare_prompt(request)
        inputs = prepared["prompt"]["7"]["inputs"]
        self.assertEqual(inputs, {"prompt_text": "selected café", "next_prompt": 1})
        metadata = prepared["extra_data"]["extra_pnginfo"]
        source = metadata["workflow"]["nodes"][0]
        self.assertEqual(source["widgets_values"], ["selected café", 1, ""])
        self.assertEqual(source["widgets_values_named"],
                         {"prompt_text": "selected café", "next_prompt": 1, "other": "keep"})
        used = {"text": "selected café", "index": 2, "total": 3}
        self.assertEqual(source["properties"], {"label": "keep", "iridioUsedPrompt": used})
        self.assertEqual(metadata["other_metadata"], "keep")
        self.assertEqual(prepared["prompt"]["8"], working["prompt"]["8"])
        self.assertEqual(metadata["workflow"]["nodes"][1],
                         working["extra_data"]["extra_pnginfo"]["workflow"]["nodes"][1])
        self.assertNotIn("private first", str(prepared))
        self.assertNotIn("private third", str(prepared))
        node = SequentialPromptFile.PREPARE_CLASS_CLONE({"hidden_inputs": {
            io.Hidden.unique_id: "7", io.Hidden.extra_pnginfo: metadata,
        }})
        result = node.execute(**inputs)
        self.assertEqual(result.result, ("selected café", 2, 3))
        self.assertEqual(result.ui, {"used_prompt": [used]})

    def test_headless_queue_preserves_original_index_and_total_without_workflow(self):
        request = {"prompt": {"7": {"class_type": "IridioSequentialPromptFile",
                    "inputs": {"prompt_text": "first\nsecond", "next_prompt": 2}}}}
        prepared = sequential_prompt_file.prepare_prompt(request)
        node = SequentialPromptFile.PREPARE_CLASS_CLONE({"hidden_inputs": {
            io.Hidden.unique_id: "7", io.Hidden.extra_pnginfo: prepared["extra_data"]["extra_pnginfo"],
        }})
        self.assertEqual(node.execute(**prepared["prompt"]["7"]["inputs"]).result,
                         ("second", 2, 2))
        self.assertNotIn("first", str(prepared))

    def test_selected_later_line_bom_is_not_reparsed_as_a_file_bom(self):
        request = {"prompt": {"7": {"class_type": "IridioSequentialPromptFile",
                    "inputs": {"prompt_text": "first\n\ufeffsecond", "next_prompt": 2}}}}
        prepared = sequential_prompt_file.prepare_prompt(request)
        node = SequentialPromptFile.PREPARE_CLASS_CLONE({"hidden_inputs": {
            io.Hidden.unique_id: "7", io.Hidden.extra_pnginfo: prepared["extra_data"]["extra_pnginfo"],
        }})
        self.assertEqual(node.execute(**prepared["prompt"]["7"]["inputs"]).result,
                         ("\ufeffsecond", 2, 2))
        self.assertEqual(SequentialPromptFile.execute(**prepared["prompt"]["7"]["inputs"]).result,
                         ("\ufeffsecond", 1, 1))

    def test_stale_selection_metadata_cannot_replace_the_actual_output_text(self):
        metadata = {"iridioPromptSelections": {"7": {"text": "stale text", "index": 9, "total": 10}}}
        node = SequentialPromptFile.PREPARE_CLASS_CLONE({"hidden_inputs": {
            io.Hidden.unique_id: "7", io.Hidden.extra_pnginfo: metadata,
        }})
        self.assertEqual(node.execute("actual text", 1).result, ("actual text", 1, 1))

    def test_queue_drops_client_selection_metadata_for_linked_inputs(self):
        request = {"prompt": {"7": {"class_type": "IridioSequentialPromptFile",
                    "inputs": {"prompt_text": ["upstream", 0], "next_prompt": 1}}},
                   "extra_data": {"extra_pnginfo": {"iridioPromptSelections": {
                       "7": {"text": "stale text", "index": 9, "total": 10}}}}}
        prepared = sequential_prompt_file.prepare_prompt(request)
        self.assertNotIn("iridioPromptSelections", prepared["extra_data"]["extra_pnginfo"])

    def test_invalid_inputs_remain_on_the_existing_execution_error_path(self):
        for text, position in [("", 1), ("first\x00second", 1), ("first", 0),
                               ("first", "invalid"), (["upstream", 0], 1)]:
            with self.subTest(text=text, position=position):
                request = {"prompt": {"7": {"class_type": "IridioSequentialPromptFile",
                            "inputs": {"prompt_text": text, "next_prompt": position}}}}
                before = copy.deepcopy(request)
                self.assertEqual(sequential_prompt_file.prepare_prompt(request), before)

    def test_queue_normalizes_literals_accepted_by_comfyui_before_selecting(self):
        for position, index, expected in [("2", 2, "second"), (2.8, 2, "second"),
                                          ({"__value__": 2}, 2, "second"), (True, 1, "first")]:
            with self.subTest(position=position):
                request = {"prompt": {"7": {"class_type": "IridioSequentialPromptFile",
                    "inputs": {"prompt_text": {"__value__": "first\nsecond"}, "next_prompt": position}}}}
                prepared = sequential_prompt_file.prepare_prompt(request)
                self.assertEqual(prepared["prompt"]["7"]["inputs"],
                                 {"prompt_text": expected, "next_prompt": 1})
                selection = prepared["extra_data"]["extra_pnginfo"]["iridioPromptSelections"]["7"]
                self.assertEqual(selection, {"text": expected, "index": index, "total": 2})

    def test_null_optional_metadata_still_sanitizes_headless_request(self):
        request = {"prompt": {"7": {"class_type": "IridioSequentialPromptFile",
            "inputs": {"prompt_text": "private first\nselected second", "next_prompt": 2}}},
            "extra_data": {"extra_pnginfo": None}}
        prepared = sequential_prompt_file.prepare_prompt(request)
        self.assertNotIn("private first", str(prepared))
        self.assertEqual(prepared["prompt"]["7"]["inputs"],
                         {"prompt_text": "selected second", "next_prompt": 1})

    def test_muted_source_omitted_from_api_does_not_leak_its_txt(self):
        request = {"prompt": {"7": {"class_type": "IridioSequentialPromptFile",
            "inputs": {"prompt_text": "selected", "next_prompt": 1}}},
            "extra_data": {"extra_pnginfo": {"workflow": {"nodes": [
                {"id": 7, "type": "IridioSequentialPromptFile", "widgets_values": ["selected", 1]},
                {"id": 8, "type": "IridioSequentialPromptFile", "mode": 2,
                 "widgets_values": ["private muted first\nprivate muted second", 2],
                 "widgets_values_named": {"prompt_text": "private muted first\nprivate muted second", "next_prompt": 2},
                 "properties": {"iridioUsedPrompt": {"text": "private previous"}}},
            ]}}}}
        prepared = sequential_prompt_file.prepare_prompt(request)
        self.assertNotIn("private", str(prepared))
        muted = prepared["extra_data"]["extra_pnginfo"]["workflow"]["nodes"][1]
        self.assertEqual(muted["widgets_values"], ["", 1])
        self.assertEqual(muted["widgets_values_named"], {"prompt_text": "", "next_prompt": 1})

    def test_execution_reports_used_prompt_and_updates_only_its_workflow_node(self):
        metadata = {"workflow": {"nodes": [
            {"id": 7, "properties": {"label": "keep", "iridioUsedPrompt": "stale"}},
            {"id": 8, "properties": {"iridioUsedPrompt": "other"}},
        ]}, "other_metadata": "keep"}
        node = SequentialPromptFile.PREPARE_CLASS_CLONE({"hidden_inputs": {
            io.Hidden.unique_id: "7", io.Hidden.extra_pnginfo: metadata,
        }})
        result = node.execute(" first \nsecond café", 4)
        used = {"text": "second café", "index": 2, "total": 2}
        self.assertEqual(result.result, ("second café", 2, 2))
        self.assertEqual(result.ui, {"used_prompt": [used]})
        self.assertEqual(metadata["workflow"]["nodes"][0]["properties"],
                         {"label": "keep", "iridioUsedPrompt": used})
        self.assertEqual(metadata["workflow"]["nodes"][1]["properties"],
                         {"iridioUsedPrompt": "other"})
        self.assertEqual(metadata["other_metadata"], "keep")

    def test_metadata_is_optional_and_missing_workflow_node_is_ignored(self):
        for metadata in [None, {}, {"workflow": {"nodes": []}}]:
            with self.subTest(metadata=metadata):
                node = SequentialPromptFile.PREPARE_CLASS_CLONE({"hidden_inputs": {
                    io.Hidden.unique_id: "7", io.Hidden.extra_pnginfo: metadata,
                }})
                self.assertEqual(node.execute("first", 1).ui,
                                 {"used_prompt": [{"text": "first", "index": 1, "total": 1}]})

    def test_separate_jobs_retain_their_own_used_prompt(self):
        snapshots = []
        for position in [1, 2, 3]:
            metadata = {"workflow": {"nodes": [{"id": 7}]}}
            node = SequentialPromptFile.PREPARE_CLASS_CLONE({"hidden_inputs": {
                io.Hidden.unique_id: "7", io.Hidden.extra_pnginfo: metadata,
            }})
            node.execute("first\nsecond", position)
            snapshots.append(metadata)
        self.assertEqual([m["workflow"]["nodes"][0]["properties"]["iridioUsedPrompt"]["text"]
                          for m in snapshots], ["first", "second", "first"])

    def test_txt_lines_bom_blank_lines_and_unicode(self):
        self.assertEqual(
            parse_prompts("\ufeff first \r\n\t\r\nsecond café\rthird\n  \n"),
            ["first", "second café", "third"],
        )

    def test_circular_selection_and_outputs(self):
        for index, expected in [(1, ("first", 1, 2)), (2, ("second", 2, 2)),
                                (3, ("first", 1, 2)), (100, ("second", 2, 2))]:
            with self.subTest(index=index):
                self.assertEqual(
                    SequentialPromptFile.execute("first\n\nsecond", index).result,
                    expected,
                )

    def test_unicode_whitespace_and_later_line_bom_match_browser(self):
        self.assertEqual(parse_prompts("first\n\u0085\n\u001c\nsecond\n\ufeffthird"),
                         ["first", "second", "\ufeffthird"])

    def test_single_prompt(self):
        self.assertEqual(SequentialPromptFile.execute("only", 99).result, ("only", 1, 1))

    def test_empty_file_fails_clearly(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            SequentialPromptFile.execute("\ufeff\n \r\n", 1)

    def test_invalid_api_input_is_rejected(self):
        for value in [0, -1, 1.5, True, "1", None]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "positive integer"):
                SequentialPromptFile.execute("first", value)
        for value in [None, ["first"], 123, "first\x00second"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                SequentialPromptFile.execute(value, 1)

    def test_extension_is_discoverable(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("iridio_test", root / "__init__.py",
                                                   submodule_search_locations=[str(root)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.assertTrue(callable(module.comfy_entrypoint))
        extension = module.IridioNodes()
        classes = asyncio.run(extension.get_node_list())
        schema = classes[0].GET_SCHEMA()
        self.assertEqual(schema.node_id, "IridioSequentialPromptFile")
        self.assertEqual([o.io_type for o in schema.outputs], ["STRING", "INT", "INT"])
        self.assertEqual(schema.inputs[1].default, 1)
        self.assertTrue((root / module.WEB_DIRECTORY).is_dir())


if __name__ == "__main__":
    unittest.main()
