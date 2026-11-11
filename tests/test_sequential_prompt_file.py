import asyncio
import importlib.util
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, os.environ["COMFYUI_PATH"])
from comfy.cli_args import args

args.cpu = True
from sequential_prompt_file import SequentialPromptFile, parse_prompts


class SequentialPromptFileTests(unittest.TestCase):
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
        extension = asyncio.run(module.comfy_entrypoint())
        classes = asyncio.run(extension.get_node_list())
        schema = classes[0].GET_SCHEMA()
        self.assertEqual(schema.node_id, "IridioSequentialPromptFile")
        self.assertEqual([o.io_type for o in schema.outputs], ["STRING", "INT", "INT"])
        self.assertEqual(schema.inputs[1].default, 1)
        self.assertTrue((root / module.WEB_DIRECTORY).is_dir())


if __name__ == "__main__":
    unittest.main()
