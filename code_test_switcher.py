"""Switch between Python source/tests and copy Testify commands in Sublime Text."""

import functools
import os
import re

import sublime
import sublime_plugin


class SwitchBetweenCodeAndTest(sublime_plugin.TextCommand):
    def run(self, edit):
        window = self.view.window()
        if window is None:
            return
        if not self.view.file_name():
            sublime.error_message("Save this file before switching between code and tests.")
            return
        if not window.folders():
            sublime.error_message("Open the project folder before switching between code and tests.")
            return

        alternates = self.project_files(self.opposite_file_names())
        if len(alternates) == 1:
            window.open_file(alternates[0])
        elif alternates:
            callback = functools.partial(self.on_selected, alternates)
            window.show_quick_panel(alternates, callback)
        else:
            sublime.error_message("No matching code or test file found in the open project folders.")

    def opposite_file_names(self):
        file_name = os.path.basename(self.view.file_name())
        if file_name.endswith("_test.py"):
            stem = file_name[:-len("_test.py")]
            return [stem + ".py", stem + ".tmpl"]
        stem, extension = os.path.splitext(file_name)
        if extension in (".py", ".tmpl"):
            return [stem + "_test.py"]
        return []

    def on_selected(self, alternates, index):
        if index != -1 and self.view.window() is not None:
            self.view.window().open_file(alternates[index])

    def walk(self, directory):
        for dirname, dirnames, files in os.walk(directory):
            # Prune before descending, including on Windows and in hidden project roots.
            dirnames[:] = [name for name in dirnames if not name.startswith(".")]
            yield dirname, dirnames, files

    def project_files(self, files_matcher):
        candidates = set()
        for directory in self.view.window().folders():
            for dirname, _, files in self.walk(directory):
                for file_name in files:
                    if file_name in files_matcher:
                        candidates.add(os.path.join(dirname, file_name))
        return sorted(candidates)


class TestCommander(sublime_plugin.TextCommand):
    def extract_class_and_name(self):
        region = self.view.sel()[0]
        line_region = self.view.line(region)
        text = self.view.substr(sublime.Region(max(0, region.begin() - 65536), line_region.end()))
        text = text.replace("\n", "\\N")[::-1]

        test_name, test_class = "", ""
        # Search backwards for 'def test_name(self, ...):' and 'class Name(Base):'.
        match = re.search(r':\)[,\sa-zA-Z_\d]*fles\(([a-zA-Z_\d]+_tset) fed', text)
        if match:
            test_name = match.group(1)[::-1]
        match = re.search(r':\)[a-zA-Z_.,\d\s]+\(([a-zA-Z_\d]+) ssalc', text)
        if match:
            test_class = match.group(1)[::-1]
        return [test_name, test_class]

    def extract_path(self):
        file_path = self.view.file_name()
        window = self.view.window()
        if not file_path or window is None or not file_path.endswith(".py"):
            return ""

        # Longest root first so nested project folders use their own module path.
        for directory in sorted(window.folders(), key=len, reverse=True):
            try:
                relative = os.path.relpath(file_path, directory)
            except ValueError:  # Different drives on Windows.
                continue
            if relative == os.pardir or relative.startswith(os.pardir + os.sep):
                continue
            return relative[:-len(".py")].replace(os.sep, ".")
        return ""

    def is_present(self, content, message):
        if not content:
            sublime.error_message(message)
            return False
        return True

    def copy_command(self, include_method):
        test_path = self.extract_path()
        if not self.is_present(test_path, "Save this Python file inside an open project folder first."):
            return
        test_name, test_class = self.extract_class_and_name()
        if include_method and not self.is_present(test_name, "No test function!"):
            return
        if not self.is_present(test_class, "No test class!"):
            return

        target = "%s.%s" % (test_class, test_name) if include_method else test_class
        command = "testify %s %s" % (test_path, target)
        sublime.set_clipboard(command)
        sublime.status_message(command)


class PrepareTestCommander(TestCommander):
    def run(self, edit):
        self.copy_command(include_method=True)


class PrepareTestClassCommander(TestCommander):
    def run(self, edit):
        self.copy_command(include_method=False)
