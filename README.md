
# dirshot 📸

[![PyPI version](https://badge.fury.io/py/dirshot.svg)](https://badge.fury.io/py/dirshot)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Python Version](https://img.shields.io/pypi/pyversions/dirshot)

A flexible, high-performance utility for creating project snapshots and searching files, complete with rich visual feedback in your terminal.

`dirshot` scans your project directories to either create a single, comprehensive text file "snapshot" of your codebase or to search for specific keywords within your files. It's perfect for feeding project context to Large Language Models (LLMs), archiving codebases, conducting security audits, or simply navigating complex projects.

---

## ✨ Key Features

-   **Rich Terminal Visuals**: Powered by `rich`, `dirshot` provides a beautiful and informative live view of its progress, including spinners, progress bars, summary tables, and thread activity. It falls back to a simple text-based progress indicator if `rich` is not installed.
-   **Powerful Presets**: Comes with an extensive list of `LanguagePreset` and `IgnorePreset` enums to instantly configure scans for dozens of languages, frameworks, and tools (Python, JavaScript, Go, Rust, Terraform, Docker, etc.).
-   **Dual Modes**:
    -   **Snapshot Mode**: Collate all project files matching your criteria into a single, easy-to-share output file.
    -   **Search Mode**: Hunt for specific keywords in filenames or, optionally, within file contents.
-   **Highly Customizable**: Fine-tune scans by combining presets with manual lists of file extensions, ignore paths, and specific file names to include or exclude.
-   **Concurrent & Fast**: Uses a `ThreadPoolExecutor` for high-performance file discovery and processing, making scans quick and efficient.
-   **Detailed Output**: Generates an optional file tree, shows detailed scan summaries, and can even approximate token/character counts, which is useful for LLM context limits.

## 📦 Installation

You can install `dirshot` directly from PyPI.

**Basic Installation (no visual dependencies):**

```bash
pip install dirshot
```

**Installation with Enhanced Terminal Visuals:**

To get the full rich terminal experience, install the `rich` extra, which adds support for `rich`.

```bash
pip install dirshot[rich]
```

## 🚀 How to Use

`dirshot` is used by importing the `generate_snapshot` function into a Python script.

Here is a basic example of creating a snapshot of a Python project:

```python
# snapshot_script.py
from src.dirshot import generate_snapshot, LanguagePreset, IgnorePreset
# or 
# from src.dirshot import *

generate_snapshot(
    root_directory=".", # optional
    output_file_name="my_python_project.txt",
    language_presets=[LanguagePreset.PYTHON, LanguagePreset.MARKUP],
    ignore_presets=[
        IgnorePreset.VERSION_CONTROL, # Ignore .git
        IgnorePreset.PYTHON,          # Ignore __pycache__, venv, etc.
        IgnorePreset.IDE_METADATA     # Ignore .vscode, .idea
    ],
    generate_tree=True,
    show_token_count=True
)
```

To run this, save the code as a Python file (e.g., `snapshot_script.py`) and execute it from your terminal:

```bash
python snapshot_script.py
```

## 📋 Examples

The `examples.py` file in the repository contains many more use cases. Here are a few common ones:

#### 1. Full-Stack Web App (React + Node.js)

This example combines multiple presets to capture a full-stack JavaScript project while ignoring common clutter like `node_modules`.

```python
generate_snapshot(
    root_directory=".",
    output_file_name="fullstack_js_snapshot.txt",
    language_presets=[
        LanguagePreset.REACT,      # Handles all frontend JS/TS/JSX files
        LanguagePreset.WEB_FRONTEND  # Includes HTML and CSS files
    ],
    ignore_presets=[
        IgnorePreset.NODE_JS,      # Crucial for ignoring node_modules
        IgnorePreset.IDE_METADATA,
        IgnorePreset.BUILD_ARTIFACTS,
        IgnorePreset.VERSION_CONTROL
    ],
    generate_tree=True,
    show_tree_stats=True
)
```

#### 2. Data Science Project (Python, Notebooks & SQL)

Collate all relevant files from a data analysis or machine learning project.

```python
generate_snapshot(
    root_directory="./data_science_project",
    output_file_name="data_science_snapshot.txt",
    language_presets=[
        LanguagePreset.PYTHON,
        LanguagePreset.DATA_SCIENCE_NOTEBOOKS, # .ipynb
        LanguagePreset.SQL,
        LanguagePreset.MARKUP # Include READMEs
    ],
    ignore_presets=[
        IgnorePreset.PYTHON,             # Ignores venv, __pycache__, etc.
        IgnorePreset.JUPYTER_NOTEBOOKS,  # Ignores .ipynb_checkpoints
        IgnorePreset.IDE_METADATA,
        IgnorePreset.VERSION_CONTROL
    ]
)
```

#### 3. Search for Secrets or API Keys

Use "Search Mode" to perform a security audit. This example intentionally omits the `SECRET_FILES` ignore preset to ensure `.env` files are searched.

```python
generate_snapshot(
    root_directory=".",
    output_file_name="secrets_audit_results.txt",
    search_keywords=["password", "secret_key", "api_key", "token"],
    language_presets=[LanguagePreset.CONFIGURATION],
    search_file_contents=True,
    ignore_presets=[
        IgnorePreset.VERSION_CONTROL,
        IgnorePreset.NODE_JS,
        IgnorePreset.BUILD_ARTIFACTS
        # Deliberately not ignoring SECRET_FILES
    ]
)
```

## ⚙️ API Reference

The `generate_snapshot()` function accepts the following parameters:

| Parameter                             | Type                         | Default                      | Description                                                                                             |
| ------------------------------------- | ---------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------- |
| `root_directory`                      | `str`                        | `"."`                        | The starting directory for the scan.                                                                    |
| `output_file_name`                    | `str`                        | `"project_snapshot.txt"`     | The name of the file to save the results to.                                                            |
| `search_keywords`                     | `Optional[List[str]]`        | `None`                       | If provided, switches to **Search Mode**. Otherwise, runs in **Snapshot Mode**.                         |
| `language_presets`                    | `Optional[List[LanguagePreset]]` | `None`                       | A list of `LanguagePreset` enums for common file types (e.g., `LanguagePreset.PYTHON`).                 |
| `ignore_presets`                      | `Optional[List[IgnorePreset]]`   | `None`                       | A list of `IgnorePreset` enums for common ignore patterns (e.g., `IgnorePreset.NODE_JS`).             |
| `file_extensions`                     | `Optional[List[str]]`        | `None`                       | A manual list of file extensions to include (e.g., `[".py", ".md"]`).                                   |
| `ignore_if_in_path`                   | `Optional[List[str]]`        | `None`                       | A manual list of directory or file names to exclude.                                                    |
| `ignore_extensions`                   | `Optional[List[str]]`        | `None`                       | A manual list of file extensions to explicitly ignore (e.g., `[".log", ".tmp"]`).                       |
| `search_file_contents`                | `bool`                       | `True`                       | In Search Mode, search for keywords within file contents.                                               |
| `generate_tree`                       | `bool`                       | `True`                       | Include a file tree of the matched files at the top of the output.                                      |
| `show_tree_stats`                     | `bool`                       | `False`                      | Display file and directory counts in the generated tree.                                                |
| `show_token_count`                    | `bool`                       | `False`                      | Display an approximated token/character count in the summary and output file.                           |
| `exclude_whitespace_in_token_count`   | `bool`                       | `False`                      | If `True`, removes whitespace before counting tokens for a more compact count.                          |
| `max_workers`                         | `Optional[int]`              | `CPU count + 4`              | The maximum number of worker threads for concurrent processing.                                         |
| `read_binary_files`                   | `bool`                       | `False`                      | If `True`, the content search will attempt to read and search through binary files.                     |

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue.

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature-name`).
3.  Make your changes.
4.  Commit your changes (`git commit -m 'Add some feature'`).
5.  Push to the branch (`git push origin feature/your-feature-name`).
6.  Open a pull request.

