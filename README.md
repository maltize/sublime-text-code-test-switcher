Sublime Text Code Test Switcher
===============================

Overview
--------

* Plugin allows you to easily switch between code and test (or vice versa).
* Base on the current position of your cursor in test file it can generate test command for you, in a form:

``` shell
  testify [test_path] [test_class].[test_name]
```

Current version support only Python language.

Maintainers:
------------
* Maciej Gajek (https://github.com/maltize)
* Grzegorz Smajdor (https://github.com/gs)

Installation
------------

Go to your Sublime Text `Packages` directory

 - OS X: `~/Library/Application\ Support/Sublime\ Text/Packages`
 - Windows: `%APPDATA%/Sublime Text/Packages/`
 - Linux: `~/.config/sublime-text/Packages/`

and clone the repository using the command below:

``` shell
git clone https://github.com/maltize/sublime-text-code-test-switcher.git CodeTestSwitcher
```

Usage
-----

 - Switching between code <=> test: `Command-.`
 - Generate test command and copy it to clipboard: `Command-,`
 - Generate test class command and copy it to clipboard: `Command-Shift-,`

  Keys: 'Command' (OSX), 'Ctrl' (Linux / Windows)

Note
----
Please open an issue at https://github.com/maltize/sublime-text-code-test-switcher if you discover a problem or would like to see a feature/change implemented.
