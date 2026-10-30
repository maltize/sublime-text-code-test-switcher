"""Regression tests with a minimal Sublime API double; no editor required."""

import importlib.util
import ntpath
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import warnings


SOURCE = Path(__file__).resolve().parents[1] / "code_test_switcher.py"


class Region:
    def __init__(self, start, end=None):
        self.start = start
        self.finish = start if end is None else end

    def begin(self):
        return min(self.start, self.finish)

    def end(self):
        return max(self.start, self.finish)


class TextCommand:
    def __init__(self, view):
        self.view = view


sublime = types.ModuleType("sublime")
sublime.Region = Region
sublime.error_message = Mock()
sublime.status_message = Mock()
sublime.set_clipboard = Mock()
sublime_plugin = types.ModuleType("sublime_plugin")
sublime_plugin.TextCommand = TextCommand
spec = importlib.util.spec_from_file_location("code_test_switcher", SOURCE)
plugin = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, sublime=sublime, sublime_plugin=sublime_plugin):
    spec.loader.exec_module(plugin)


class PluginTest(unittest.TestCase):
    def setUp(self):
        for callback in (sublime.error_message, sublime.status_message, sublime.set_clipboard):
            callback.reset_mock()
        self.window = Mock()
        self.window.folders.return_value = ["/project"]
        self.view = Mock()
        self.view.window.return_value = self.window
        self.view.file_name.return_value = "/project/tests/calculator_test.py"

    def buffer(self, text, cursor=None):
        if cursor is None:
            cursor = len(text)
        self.view.sel.return_value = [Region(cursor)]
        line_end = text.find("\n", cursor)
        if line_end == -1:
            line_end = len(text)
        self.view.line.return_value = Region(text.rfind("\n", 0, cursor) + 1, line_end)
        self.view.substr.side_effect = lambda region: text[region.begin():region.end()]


class LoadTests(unittest.TestCase):
    def test_source_compiles_with_all_warnings_as_errors(self):
        # Compile the source directly so a cached .pyc cannot hide invalid escapes.
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            compile(SOURCE.read_text(), str(SOURCE), "exec")


class SwitchingTests(PluginTest):
    def test_exact_python_and_template_suffixes(self):
        command = plugin.SwitchBetweenCodeAndTest(self.view)
        for name, expected in (
            ("calculator.py", ["calculator_test.py"]),
            ("calculator.tmpl", ["calculator_test.py"]),
            ("calculator_test.py", ["calculator.py", "calculator.tmpl"]),
            ("my_test_helper.py", ["my_test_helper_test.py"]),
            ("my_test_helper_test.py", ["my_test_helper.py", "my_test_helper.tmpl"]),
            ("happy.py", ["happy_test.py"]),
            ("calculator.py.backup", []),
        ):
            with self.subTest(name=name):
                self.view.file_name.return_value = "/project/" + name
                self.assertEqual(command.opposite_file_names(), expected)

    def test_walk_prunes_hidden_children_but_allows_a_hidden_project_root(self):
        with tempfile.TemporaryDirectory(prefix=".switcher-") as root:
            for relative in ("tests/calculator_test.py", ".git/nested/calculator_test.py"):
                path = Path(root, relative)
                path.parent.mkdir(parents=True)
                path.touch()
            self.window.folders.return_value = [root, root]
            command = plugin.SwitchBetweenCodeAndTest(self.view)
            self.assertEqual(command.project_files(["calculator_test.py"]),
                             [os.path.join(root, "tests", "calculator_test.py")])
            self.assertNotIn(os.path.join(root, ".git"),
                             [directory for directory, _, _ in command.walk(root)])

    def test_one_match_opens_directly(self):
        command = plugin.SwitchBetweenCodeAndTest(self.view)
        command.project_files = Mock(return_value=["/project/calculator.py"])
        command.run(None)
        self.window.open_file.assert_called_once_with("/project/calculator.py")
        self.window.show_quick_panel.assert_not_called()

    def test_multiple_matches_allow_selection_and_cancellation(self):
        command = plugin.SwitchBetweenCodeAndTest(self.view)
        alternates = ["/project/calculator.py", "/project/calculator.tmpl"]
        command.project_files = Mock(return_value=alternates)
        command.run(None)
        choices, callback = self.window.show_quick_panel.call_args.args
        self.assertEqual(choices, alternates)
        callback(-1)
        self.window.open_file.assert_not_called()
        callback(1)
        self.window.open_file.assert_called_once_with(alternates[1])

    def test_no_match_shows_error(self):
        command = plugin.SwitchBetweenCodeAndTest(self.view)
        command.project_files = Mock(return_value=[])
        command.run(None)
        sublime.error_message.assert_called_once()
        self.window.open_file.assert_not_called()

    def test_unsaved_file_shows_error(self):
        self.view.file_name.return_value = None
        plugin.SwitchBetweenCodeAndTest(self.view).run(None)
        sublime.error_message.assert_called_once()
        self.window.open_file.assert_not_called()

    def test_no_project_shows_error(self):
        self.window.folders.return_value = []
        plugin.SwitchBetweenCodeAndTest(self.view).run(None)
        sublime.error_message.assert_called_once()

    def test_closed_window_is_ignored(self):
        self.view.window.return_value = None
        plugin.SwitchBetweenCodeAndTest(self.view).run(None)
        sublime.error_message.assert_not_called()


class CommandTests(PluginTest):
    def setUp(self):
        super().setUp()
        self.buffer("class CalculatorTest(TestCase):\n"
                    "    def test_add(self):\n"
                    "        assert_equal(add(2, 3), 5)\n")

    def test_method_command_is_copied_without_running_it(self):
        plugin.PrepareTestCommander(self.view).run(None)
        sublime.set_clipboard.assert_called_once_with(
            "testify tests.calculator_test CalculatorTest.test_add")
        sublime.status_message.assert_called_once_with(sublime.set_clipboard.call_args.args[0])
        sublime.error_message.assert_not_called()

    def test_class_command(self):
        plugin.PrepareTestClassCommander(self.view).run(None)
        sublime.set_clipboard.assert_called_once_with("testify tests.calculator_test CalculatorTest")

    def test_cursor_on_method_line(self):
        text = "class CalculatorTest(TestCase):\n    def test_add(self):\n        pass\n"
        self.buffer(text, text.index("test_add"))
        self.assertEqual(plugin.TestCommander(self.view).extract_class_and_name(),
                         ["test_add", "CalculatorTest"])

    def test_class_command_on_class_line(self):
        self.buffer("class CalculatorTest(TestCase):")
        plugin.PrepareTestClassCommander(self.view).run(None)
        sublime.set_clipboard.assert_called_once_with("testify tests.calculator_test CalculatorTest")

    def test_missing_method_leaves_clipboard_unchanged(self):
        self.buffer("class CalculatorTest(TestCase):")
        plugin.PrepareTestCommander(self.view).run(None)
        sublime.error_message.assert_called_once_with("No test function!")
        sublime.set_clipboard.assert_not_called()

    def test_missing_class_leaves_clipboard_unchanged(self):
        self.buffer("def test_add(self):\n    pass\n")
        plugin.PrepareTestCommander(self.view).run(None)
        sublime.error_message.assert_called_once_with("No test class!")
        sublime.set_clipboard.assert_not_called()

    def test_paths_with_regex_characters_are_literal(self):
        self.window.folders.return_value = ["/project[demo]+"]
        self.view.file_name.return_value = "/project[demo]+/tests/happy_test.py"
        self.assertEqual(plugin.TestCommander(self.view).extract_path(), "tests.happy_test")

    def test_sibling_project_prefix_is_rejected(self):
        self.view.file_name.return_value = "/project-other/calculator_test.py"
        self.assertEqual(plugin.TestCommander(self.view).extract_path(), "")

    def test_nested_project_root_takes_precedence(self):
        self.window.folders.return_value = ["/project", "/project/service"]
        self.view.file_name.return_value = "/project/service/tests/calculator_test.py"
        self.assertEqual(plugin.TestCommander(self.view).extract_path(), "tests.calculator_test")

    def test_windows_separators_and_different_drives(self):
        self.window.folders.return_value = [r"D:\elsewhere", r"C:\project"]
        self.view.file_name.return_value = r"C:\project\tests\calculator_test.py"
        with patch.object(plugin.os, "path", ntpath), patch.object(plugin.os, "sep", "\\"):
            self.assertEqual(plugin.TestCommander(self.view).extract_path(), "tests.calculator_test")

    def test_invalid_paths_leave_clipboard_unchanged(self):
        for path in (None, "/elsewhere/calculator_test.py", "/project/calculator.tmpl"):
            with self.subTest(path=path):
                self.view.file_name.return_value = path
                plugin.PrepareTestCommander(self.view).run(None)
                sublime.set_clipboard.assert_not_called()
        self.assertEqual(sublime.error_message.call_count, 3)


if __name__ == "__main__":
    unittest.main()
