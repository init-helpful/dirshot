# Dirshot: A Flexible Project Snapshot and Search Tool

Dirshot is a Python utility that creates snapshots of a project's directory structure and file contents. It can operate in two modes: filtering files based on their type and path, or searching for files based on keywords in their name or content.

The script generates a single output file containing a directory tree and the concatenated text of the selected files. This is useful for quickly gathering project context for code analysis, sharing with collaborators, or providing to a Large Language Model (LLM).

## Key Features

*   **Two Operating Modes**:
    *   **Filter Mode**: Create a snapshot of your project by filtering files based on extensions, filenames, and directory paths.
    *   **Search Mode**: Search for files containing specific keywords in their name, path, or content.
*   **Customizable Filtering**:
    *   Use language presets for popular languages (Python, JavaScript, Java, etc.).
    *   Use ignore presets to exclude common files and directories (e.g., `.git`, `node_modules`, `__pycache__`).
    *   Define custom file types, and whitelist/blacklist substrings in filenames and paths.
*   **Flexible Tree Generation**:
    *   Display a directory tree in various styles (Unicode, ASCII, Compact).
    *   Show statistics for included/matched files and directories in the tree.
*   **Content Collation**:
    *   Concatenates the content of all selected files into a single output file.
    *   Optionally display an approximated token/character count.
*   **Snapshot Deconstruction**:
    *   A utility function to parse a generated snapshot file and extract the directory tree and file paths.

## Installation

You can install Dirshot from PyPI:

```bash
pip install dirshot
```



## Usage

Here are some examples of how to use Dirshot in your own Python scripts.

#### Example 1: Creating a Snapshot with Presets (Filter Mode)

This example creates a snapshot of a Python project, ignoring common virtual environment and build directories.

```python
from dirshot import filter_project, LanguagePreset, IgnorePreset

filter_project(
    root_dir_param=".",
    output_file_name="project_snapshot.txt",
    language_presets=[LanguagePreset.PYTHON],
    ignore_presets=[
        IgnorePreset.PYTHON_ENV,
        IgnorePreset.NODE_MODULES,
        IgnorePreset.BUILD_ARTIFACTS,
    ],
    show_token_count=True,
)
```

#### Example 2: Searching for Keywords in a Project (Search Mode)

This example searches for the keywords "API" or "Controller" within `.java` and `.js` files.

```python
from dirshot import find_in_project

find_in_project(
    root_dir_param="example_project",
    output_file_name="search_results.txt",
    search_keywords=["API", "Controller"],
    file_extensions_to_check=[".java", ".js"],
    ignore_dirs_in_path=["node_modules", "build"],
    search_file_contents=True,
    show_tree_stats=True,
)
```

### Deconstructing a Snapshot

You can also parse a previously generated snapshot file to extract the directory structure and the list of included files.

```python
from dirshot import deconstruct_snapshot

snapshot_data = deconstruct_snapshot("project_snapshot.txt")
print("Directory Tree:")
for line in snapshot_data["tree_lines"]:
    print(line)

print("\nIncluded Files:")
for file_path in snapshot_data["file_paths"]:
    print(file_path)
```

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue on the project's GitHub repository.