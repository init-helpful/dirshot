import os
import sys
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple, Callable, NamedTuple, Dict, Any
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO

# --- TQDM Dependency Handler ---
try:
    from tqdm import tqdm
except ImportError:

    class tqdm:
        def __init__(self, iterable=None, **kwargs):
            self.iterable = iterable

        def __iter__(self):
            return iter(self.iterable)

        def update(self, n=1):
            pass

        def set_description(self, desc):
            pass

        def close(self):
            pass


# --- Configuration Constants ---
DEFAULT_SEPARATOR_CHAR = "-"
DEFAULT_SEPARATOR_LINE_LENGTH = 80
DEFAULT_ENCODING = "utf-8"
TREE_HEADER_TEXT = "Project File Structure"
FILE_HEADER_PREFIX = "FILE: "
TOKEN_APPROX_MODE = "CHAR_COUNT"

# --- Public Enums for Import and Usage ---


class ProjectMode(Enum):
    """The mode of operation for the script."""

    FILTER = "filter"
    SEARCH = "search"


class LanguagePreset(Enum):
    """Predefined sets of file extensions/names for common languages/frameworks."""

    PYTHON = [
        ".py",
        ".pyw",
        "setup.py",
        "requirements.txt",
        "Pipfile",
        "pyproject.toml",
    ]
    JAVASCRIPT = [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]
    WEB = [".html", ".css", ".scss", ".less"]
    JAVA = [".java", ".groovy", ".kt", ".gradle", ".properties"]


class IgnorePreset(Enum):
    """Predefined sets of path components and filename substrings to ignore."""

    VERSION_CONTROL = [".git", ".svn", ".hg", ".idea"]
    NODE_MODULES = ["node_modules", "package-lock.json", "yarn.lock"]
    PYTHON_ENV = ["__pycache__", "venv", ".venv", "env", "lib", "bin"]
    BUILD_ARTIFACTS = ["dist", "build", "target", "out", "temp", "tmp"]
    TEST_FILES = ["test", "spec", "fixture", "example", "mock"]


class TreeStylePreset(Enum):
    """Predefined character sets for directory tree rendering."""

    UNICODE = ("├── ", "└── ", "│   ", "    ")
    ASCII = ("|-- ", "+-- ", "|   ", "    ")
    COMPACT = ("|---", "`---", "|   ", "    ")

    def to_style(self) -> "TreeStyle":
        return TreeStyle(self.value[0], self.value[1], self.value[2], self.value[3])


class TreeStyle(NamedTuple):
    """Holds the characters used to render the directory tree."""

    t_connector: str
    l_connector: str
    v_connector: str
    h_spacer: str


# --- Helper Data Structures ---


@dataclass
class FilterCriteria:
    """Holds normalized filter criteria for files and directories."""

    file_extensions: Set[str] = field(default_factory=set)
    exact_filenames: Set[str] = field(default_factory=set)
    whitelist_fname_substrings: Set[str] = field(default_factory=set)
    ignore_fname_substrings: Set[str] = field(default_factory=set)
    ignore_path_components: Set[str] = field(default_factory=set)

    @classmethod
    def normalize_inputs(
        cls,
        file_types: Optional[List[str]],
        whitelist_substrings: Optional[List[str]],
        ignore_filename_substrings: Optional[List[str]],
        ignore_path_components_list: Optional[List[str]],
        language_presets: Optional[List[LanguagePreset]] = None,
        ignore_presets: Optional[List[IgnorePreset]] = None,
    ) -> "FilterCriteria":
        all_file_types, all_ignore_paths, all_ignore_fnames = (
            set(file_types or []),
            set(ignore_path_components_list or []),
            set(ignore_filename_substrings or []),
        )
        if language_presets:
            for preset in language_presets:
                all_file_types.update(preset.value)
        if ignore_presets:
            for preset in ignore_presets:
                all_ignore_paths.update(preset.value)
                all_ignore_fnames.update(preset.value)
        norm_exts, norm_exact_fnames = set(), set()
        for ft in all_file_types:
            ft_lower = ft.lower().strip()
            if ft_lower.startswith("."):
                norm_exts.add(ft_lower)
            elif ft_lower:
                norm_exact_fnames.add(ft_lower)
        return cls(
            file_extensions=norm_exts,
            exact_filenames=norm_exact_fnames,
            whitelist_fname_substrings=(
                set(s.lower() for s in whitelist_substrings if s.strip())
                if whitelist_substrings
                else set()
            ),
            ignore_fname_substrings=set(
                s.lower() for s in all_ignore_fnames if s.strip()
            ),
            ignore_path_components=set(
                d.lower() for d in all_ignore_paths if d.strip()
            ),
        )


class FileToProcess(NamedTuple):
    """Represents a file selected for content processing."""

    absolute_path: Path
    relative_path_posix: str


# --- Helper Functions ---


def validate_root_directory(root_dir_param: Optional[str]) -> Optional[Path]:
    original_param_for_messaging = (
        root_dir_param if root_dir_param else "current working directory"
    )
    try:
        resolved_path = Path(root_dir_param or Path.cwd()).resolve(strict=True)
    except Exception as e:
        print(
            f"Error: Could not resolve root directory '{original_param_for_messaging}': {e}"
        )
        return None
    if not resolved_path.is_dir():
        print(f"Error: Root path '{resolved_path}' is not a directory.")
        return None
    return resolved_path


def _should_include_entry(
    entry_path: Path,
    root_dir: Path,
    criteria: FilterCriteria,
    is_dir: bool,
    log_func: Optional[Callable[[str], None]] = None,
) -> bool:
    try:
        relative_path = entry_path.relative_to(root_dir)
    except ValueError:
        return False
    entry_name_lower = entry_path.name.lower()
    if criteria.ignore_path_components and any(
        part.lower() in criteria.ignore_path_components for part in relative_path.parts
    ):
        return False
    if is_dir:
        return True
    file_ext_lower = entry_path.suffix.lower()
    matched_type = (file_ext_lower in criteria.file_extensions) or (
        entry_name_lower in criteria.exact_filenames
    )
    if not criteria.file_extensions and not criteria.exact_filenames:
        matched_type = True
    if not matched_type:
        return False
    if criteria.whitelist_fname_substrings and not any(
        sub in entry_name_lower for sub in criteria.whitelist_fname_substrings
    ):
        return False
    if criteria.ignore_fname_substrings and any(
        sub in entry_name_lower for sub in criteria.ignore_fname_substrings
    ):
        return False
    return True


def process_file_for_search(
    file_path: Path,
    normalized_keywords: List[str],
    search_file_contents: bool,
    full_path_compare: bool,
) -> Optional[Path]:
    compare_target = str(file_path) if full_path_compare else file_path.name
    if any(key in compare_target.lower() for key in normalized_keywords):
        return file_path
    if search_file_contents:
        try:
            with open(str(file_path), "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if any(key in line.lower() for key in normalized_keywords):
                        return file_path
        except (IOError, OSError):
            pass
    return None


def _calculate_total_stats(
    root_dir: Path, criteria: FilterCriteria
) -> Dict[Path, Tuple[int, int]]:
    stats: Dict[Path, Tuple[int, int]] = {}
    for dirpath_str, dirnames, filenames in os.walk(str(root_dir), topdown=True):
        current_dir = Path(dirpath_str)
        all_children = [current_dir / d for d in dirnames] + [
            current_dir / f for f in filenames
        ]
        total_files, total_dirs = 0, 0
        for child_path in all_children:
            try:
                is_dir = child_path.is_dir()
            except OSError:
                continue
            if criteria.ignore_path_components:
                try:
                    relative_path = child_path.relative_to(root_dir)
                except ValueError:
                    continue
                if any(
                    part.lower() in criteria.ignore_path_components
                    for part in relative_path.parts
                ):
                    continue
            if is_dir:
                total_dirs += 1
            else:
                total_files += 1
        stats[current_dir] = (total_files, total_dirs)
        dirnames[:] = [
            d
            for d in dirnames
            if (current_dir / d).name.lower() not in criteria.ignore_path_components
        ]
    return stats


# --- Tree Generation Functions ---


def _generate_tree_lines(
    root_dir: Path, criteria: FilterCriteria, style: TreeStyle, show_stats: bool
) -> List[str]:
    """Generates a list of strings representing the directory tree based on criteria, style, and stats."""
    dir_stats: Optional[Dict[Path, Tuple[int, int]]] = (
        _calculate_total_stats(root_dir, criteria) if show_stats else None
    )
    tree_lines: List[str] = []

    def format_dir_name(
        path: Path, path_name: str, included_files: int, included_dirs: int
    ) -> str:
        if not show_stats or not dir_stats:
            return path_name
        total_files, total_dirs = dir_stats.get(path, (0, 0))

        stats_str = f" [I: {included_files}f, {included_dirs}d | T: {total_files}f, {total_dirs}d]"
        return path_name + stats_str

    def _recursive_build(current_path: Path, prefix_parts: List[str]):
        try:
            entries = sorted(current_path.iterdir(), key=lambda p: p.name.lower())
        except OSError as e:
            error_prefix = "".join(prefix_parts) + style.l_connector
            tree_lines.append(
                error_prefix + f"[Error accessing: {current_path.name} - {e.strerror}]"
            )
            return
        displayable_children: List[Tuple[Path, bool]] = []
        for e in entries:
            try:
                is_dir = e.is_dir()
            except OSError:
                continue
            if _should_include_entry(
                e, root_dir, criteria, is_dir=is_dir, log_func=None
            ):
                displayable_children.append((e, is_dir))
        num_children = len(displayable_children)
        included_files_in_level = sum(
            1 for _, is_dir in displayable_children if not is_dir
        )
        included_dirs_in_level = sum(1 for _, is_dir in displayable_children if is_dir)
        if not prefix_parts:
            tree_lines.append(
                format_dir_name(
                    current_path,
                    current_path.name,
                    included_files_in_level,
                    included_dirs_in_level,
                )
            )
        for i, (child_path, child_is_dir) in enumerate(displayable_children):
            is_last = i == num_children - 1
            connector = style.l_connector if is_last else style.t_connector
            entry_name = child_path.name
            if child_is_dir:
                try:
                    child_entries = sorted(
                        child_path.iterdir(), key=lambda p: p.name.lower()
                    )
                    child_displayable_children = [
                        (e, e.is_dir())
                        for e in child_entries
                        if _should_include_entry(
                            e, root_dir, criteria, is_dir=e.is_dir(), log_func=None
                        )
                    ]
                    child_included_files = sum(
                        1 for _, is_dir in child_displayable_children if not is_dir
                    )
                    child_included_dirs = sum(
                        1 for _, is_dir in child_displayable_children if is_dir
                    )
                    entry_name = format_dir_name(
                        child_path,
                        child_path.name,
                        child_included_files,
                        child_included_dirs,
                    )
                except OSError:
                    pass
            tree_lines.append("".join(prefix_parts) + connector + entry_name)
            if child_is_dir:
                new_prefix_parts = prefix_parts + [
                    style.h_spacer if is_last else style.v_connector
                ]
                _recursive_build(child_path, new_prefix_parts)

    _recursive_build(root_dir, [])
    return tree_lines


def _generate_tree_from_paths(
    root_dir: Path, file_paths: List[Path], style: TreeStyle, show_stats: bool
) -> List[str]:
    """Generates a directory tree structure from a list of *matched* file paths using the given style."""
    tree_dict: Dict[str, Any] = {}
    matched_paths = {p.relative_to(root_dir) for p in file_paths}
    for rel_path in matched_paths:
        parts = rel_path.parts
        current_level = tree_dict
        for part in parts:
            current_level = current_level.setdefault(part, {})
    tree_lines: List[str] = []

    def format_dir_name_search(name: str, matched_files: int, matched_dirs: int) -> str:
        if not show_stats:
            return name

        stats_str = f" [M: {matched_files}f, {matched_dirs}d]"
        return name + stats_str

    def build_lines(d: Dict[str, Any], prefix: str):
        items = sorted(d.keys(), key=lambda k: (len(d[k]) == 0, k.lower()))
        num_children = len(items)
        matched_files_in_level = sum(1 for k in items if not d[k])
        matched_dirs_in_level = sum(1 for k in items if d[k])
        if not prefix:
            tree_lines.append(
                format_dir_name_search(
                    root_dir.name, matched_files_in_level, matched_dirs_in_level
                )
            )
        for i, name in enumerate(items):
            is_last = i == num_children - 1
            connector = style.l_connector if is_last else style.t_connector
            entry_name = name
            if d[name]:
                child_matched_files = sum(1 for k in d[name] if not d[name][k])
                child_matched_dirs = sum(1 for k in d[name] if d[name][k])
                entry_name = format_dir_name_search(
                    name, child_matched_files, child_matched_dirs
                )
            tree_lines.append(prefix + connector + entry_name)
            if d[name]:
                extension = style.h_spacer if is_last else style.v_connector
                build_lines(d[name], prefix + extension)

    build_lines(tree_dict, "")
    return tree_lines


# --- Collation and Main Modes ---


def _collate_content_to_file(
    output_file_path_str: str,
    tree_content_lines: Optional[List[str]],
    files_to_process: List[FileToProcess],
    encoding: str,
    separator_char: str,
    separator_line_len: int,
    show_token_count: bool,
    show_tree_stats: bool,
    mode: ProjectMode,
) -> None:
    """
    Collates content to a string buffer, calculates token count,
    and then writes to the output file.
    """
    output_file_path = Path(output_file_path_str).resolve()
    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    separator_line = separator_char * separator_line_len

    # Use an in-memory buffer to build the output first
    buffer = StringIO()

    if tree_content_lines:
        buffer.write(f"{TREE_HEADER_TEXT}\n{separator_line}\n\n")
        stats_key = ""
        if show_tree_stats:
            if mode == ProjectMode.FILTER:
                stats_key = (
                    "Key: [I: Included f/d | T: Total f/d in original dir]\n"
                    "     (f=files, d=directories)\n\n"
                )
            else:  # ProjectMode.SEARCH
                stats_key = (
                    "Key: [M: Matched files/dirs]\n"
                    "     (f=files, d=directories)\n\n"
                )
            buffer.write(stats_key)
        tree_content = "\n".join(tree_content_lines)
        buffer.write(tree_content + "\n")
        buffer.write(f"\n{separator_line}\n\n")

    for file_info in files_to_process:
        header_content = f"{separator_line}\n{FILE_HEADER_PREFIX}{file_info.relative_path_posix}\n{separator_line}\n\n"
        buffer.write(header_content)
        try:
            with open(
                file_info.absolute_path, "r", encoding=encoding, errors="replace"
            ) as infile:
                file_content = infile.read()
                buffer.write(file_content)
            buffer.write("\n\n")
        except Exception:
            buffer.write(
                f"Error: Could not read file '{file_info.relative_path_posix}'.\n\n"
            )

    if not files_to_process and not tree_content_lines:
        buffer.write(
            "No files found matching the specified criteria for content aggregation.\n"
        )

    # Get the complete content from the buffer
    final_content = buffer.getvalue()
    total_token_count = 0
    mode_display = "Characters" if TOKEN_APPROX_MODE == "CHAR_COUNT" else "Words"

    if show_token_count:
        if TOKEN_APPROX_MODE == "CHAR_COUNT":
            total_token_count = len(final_content)
        elif TOKEN_APPROX_MODE == "WORD_COUNT":
            total_token_count = len(final_content.split())

    # Now, write everything to the actual file
    try:
        with open(output_file_path, "w", encoding=encoding) as outfile:
            if show_token_count:
                # Add the token count at the top of the file as requested
                outfile.write(f"Token Count ({mode_display}): {total_token_count}\n\n")

            # Write the main content
            outfile.write(final_content)
    except IOError as e:
        print(f"Error: Could not write to output file '{output_file_path}': {e}")
        return

    # Final console output remains for user feedback
    print(f"\nProcess complete. Output written to: {output_file_path}")
    if show_token_count:
        print(f"Total Approximated Tokens ({mode_display}): {total_token_count}")
    if len(files_to_process) > 0:
        print(
            f"Summary: {len(files_to_process)} files selected for content processing."
        )


def filter_and_append_content(
    root_dir: Path,
    output_file_path_str: str,
    tree_style: TreeStyle,
    generate_tree: bool,
    file_types: Optional[List[str]],
    whitelist_substrings_in_filename: Optional[List[str]],
    ignore_substrings_in_filename: Optional[List[str]],
    ignore_dirs_in_path: Optional[List[str]],
    language_presets: Optional[List[LanguagePreset]],
    ignore_presets: Optional[List[IgnorePreset]],
    encoding: str,
    separator_char: str,
    separator_line_len: int,
    show_token_count: bool,
    show_tree_stats: bool,
) -> None:
    """FILTER MODE: Selects files based on explicit criteria and prepares content/tree."""
    criteria = FilterCriteria.normalize_inputs(
        file_types,
        whitelist_substrings_in_filename,
        ignore_substrings_in_filename,
        ignore_dirs_in_path,
        language_presets,
        ignore_presets,
    )
    tree_content_lines: Optional[List[str]] = (
        _generate_tree_lines(root_dir, criteria, tree_style, show_tree_stats)
        if generate_tree
        else None
    )
    files_to_process: List[FileToProcess] = []
    for dirpath_str, dirnames, filenames in os.walk(str(root_dir), topdown=True):
        current_dir_path = Path(dirpath_str)
        orig_dirnames = list(dirnames)
        dirnames[:] = []
        for d_name in orig_dirnames:
            dir_abs_path = current_dir_path / d_name
            if _should_include_entry(dir_abs_path, root_dir, criteria, is_dir=True):
                dirnames.append(d_name)
        for filename in filenames:
            file_abs_path = current_dir_path / filename
            if _should_include_entry(file_abs_path, root_dir, criteria, is_dir=False):
                files_to_process.append(
                    FileToProcess(
                        file_abs_path, file_abs_path.relative_to(root_dir).as_posix()
                    )
                )
    files_to_process.sort(key=lambda f_info: f_info.relative_path_posix.lower())
    _collate_content_to_file(
        output_file_path_str,
        tree_content_lines,
        files_to_process,
        encoding,
        separator_char,
        separator_line_len,
        show_token_count,
        show_tree_stats,
        ProjectMode.FILTER,
    )


def search_and_collate_content(
    root_dir: Path,
    sub_string_match: List[str],
    output_file: str,
    tree_style: TreeStyle,
    file_extensions_to_check: Optional[List[str]],
    ignore_substrings_in_path: Optional[List[str]],
    language_presets: Optional[List[LanguagePreset]],
    ignore_presets: Optional[List[IgnorePreset]],
    search_file_contents: bool,
    max_workers: Optional[int],
    full_path_compare: bool,
    show_token_count: bool,
    show_tree_stats: bool,
) -> None:
    """SEARCH MODE: Scans for files that match a substring in their path/name or content."""
    criteria = FilterCriteria.normalize_inputs(
        file_extensions_to_check,
        None,
        None,
        ignore_substrings_in_path,
        language_presets,
        ignore_presets,
    )
    normalized_keywords = [
        sub.lower().strip() for sub in sub_string_match if sub.strip()
    ]
    if not normalized_keywords:
        print("Error: Search mode requires 'search_keywords' to be provided.")
        return
    candidate_files: List[Path] = []
    for dirpath_str, dirnames, filenames in os.walk(str(root_dir), topdown=True):
        current_dir_path = Path(dirpath_str)
        dirnames[:] = [
            d for d in dirnames if d.lower() not in criteria.ignore_path_components
        ]
        for filename in filenames:
            file_abs_path = current_dir_path / filename
            if (
                file_abs_path.suffix.lower() in criteria.file_extensions
                or not criteria.file_extensions
            ):
                candidate_files.append(file_abs_path)
    matched_files: Set[Path] = set()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(
                process_file_for_search,
                file,
                normalized_keywords,
                search_file_contents,
                full_path_compare,
            ): file
            for file in candidate_files
        }
        progress_bar = tqdm(
            as_completed(future_to_file),
            total=len(candidate_files),
            unit="file",
            desc="Scanning",
        )
        for future in progress_bar:
            result = future.result()
            if result:
                matched_files.add(result)
    if not matched_files:
        print("\nScan complete. No matching files were found.")
        _collate_content_to_file(
            output_file,
            None,
            [],
            DEFAULT_ENCODING,
            DEFAULT_SEPARATOR_CHAR,
            DEFAULT_SEPARATOR_LINE_LENGTH,
            show_token_count,
            show_tree_stats,
            ProjectMode.SEARCH,
        )
        return
    sorted_matched_files = sorted(
        list(matched_files), key=lambda p: p.relative_to(root_dir).as_posix().lower()
    )
    tree_content_lines = _generate_tree_from_paths(
        root_dir, sorted_matched_files, tree_style, show_tree_stats
    )
    files_to_process = [
        FileToProcess(f, f.relative_to(root_dir).as_posix())
        for f in sorted_matched_files
    ]
    _collate_content_to_file(
        output_file,
        tree_content_lines,
        files_to_process,
        DEFAULT_ENCODING,
        DEFAULT_SEPARATOR_CHAR,
        DEFAULT_SEPARATOR_LINE_LENGTH,
        show_token_count,
        show_tree_stats,
        ProjectMode.SEARCH,
    )


# --- DECONSTRUCTION FUNCTION ---


def deconstruct_snapshot(snapshot_file_path: str) -> Dict[str, Any]:
    """Scans a compiled snapshot file, extracts the directory tree lines and file paths."""
    snapshot_path = Path(snapshot_file_path)
    if not snapshot_path.is_file():
        raise FileNotFoundError(f"Snapshot file not found: {snapshot_file_path}")
    tree_lines: List[str] = []
    file_paths: List[str] = []
    separator_pattern = re.compile(
        r"^[{}]{{4,}}[{}|]*$".format(
            re.escape(DEFAULT_SEPARATOR_CHAR), re.escape(DEFAULT_SEPARATOR_CHAR)
        )
    )
    state = "LOOKING_FOR_TREE"
    with open(snapshot_path, "r", encoding=DEFAULT_ENCODING, errors="replace") as f:
        for line in f:
            line = line.strip()
            if state == "LOOKING_FOR_TREE":
                if line == TREE_HEADER_TEXT:
                    state = "READING_TREE"
            elif state == "READING_TREE":
                if not line or separator_pattern.match(line):
                    if tree_lines and separator_pattern.match(line):
                        state = "LOOKING_FOR_CONTENT"
                    continue
                if state == "READING_TREE" and not line.startswith("Key:"):
                    tree_lines.append(line)
            elif state == "LOOKING_FOR_CONTENT":
                if line.startswith(FILE_HEADER_PREFIX):
                    file_paths.append(line[len(FILE_HEADER_PREFIX) :].strip())
                    state = "READING_CONTENT"
            elif state == "READING_CONTENT":
                if line.startswith(FILE_HEADER_PREFIX):
                    file_paths.append(line[len(FILE_HEADER_PREFIX) :].strip())
    # Post-process to remove the key lines if they were accidentally captured
    tree_lines = [
        line
        for line in tree_lines
        if not line.strip().startswith("Key:")
        and not line.strip().startswith("(f=files")
    ]
    return {"tree_lines": tree_lines, "file_paths": file_paths}


# --- UNIFIED ENTRY POINT AND UTILITY WRAPPERS ---


def process_project(
    root_dir_param: Optional[str] = None,
    output_file_name: str = "project_output.txt",
    mode: ProjectMode = ProjectMode.FILTER,
    file_types: Optional[List[str]] = None,
    ignore_dirs_in_path: Optional[List[str]] = None,
    language_presets: Optional[List[LanguagePreset]] = None,
    ignore_presets: Optional[List[IgnorePreset]] = None,
    whitelist_filename_substrings: Optional[List[str]] = None,
    ignore_filename_substrings: Optional[List[str]] = None,
    generate_tree: bool = True,
    search_keywords: Optional[List[str]] = None,
    search_file_contents: bool = False,
    full_path_compare: bool = True,
    max_workers: Optional[int] = None,
    tree_style_preset: TreeStylePreset = TreeStylePreset.UNICODE,
    tree_style_t_connector: Optional[str] = None,
    tree_style_l_connector: Optional[str] = None,
    tree_style_v_connector: Optional[str] = None,
    tree_style_h_spacer: Optional[str] = None,
    show_token_count: bool = False,
    show_tree_stats: bool = False,
    encoding: str = DEFAULT_ENCODING,
    separator_char: str = DEFAULT_SEPARATOR_CHAR,
    separator_line_len: int = DEFAULT_SEPARATOR_LINE_LENGTH,
) -> None:
    """Main function to process a project directory in either FILTER or SEARCH mode."""
    actual_root_dir = validate_root_directory(root_dir_param)
    if actual_root_dir is None:
        sys.exit(1)
    style = tree_style_preset.to_style()
    final_style = TreeStyle(
        t_connector=tree_style_t_connector or style.t_connector,
        l_connector=tree_style_l_connector or style.l_connector,
        v_connector=tree_style_v_connector or style.v_connector,
        h_spacer=tree_style_h_spacer or style.h_spacer,
    )
    print(f"--- Starting Project Processing in {mode.name} Mode ---")
    if mode == ProjectMode.FILTER:
        filter_and_append_content(
            actual_root_dir,
            output_file_name,
            final_style,
            generate_tree,
            file_types,
            whitelist_filename_substrings,
            ignore_filename_substrings,
            ignore_dirs_in_path,
            language_presets,
            ignore_presets,
            encoding,
            separator_char,
            separator_line_len,
            show_token_count,
            show_tree_stats,
        )
    elif mode == ProjectMode.SEARCH:
        if not search_keywords:
            print("Error: Search mode requires 'search_keywords' to be provided.")
            return
        search_and_collate_content(
            actual_root_dir,
            search_keywords,
            output_file_name,
            final_style,
            file_types,
            ignore_dirs_in_path,
            language_presets,
            ignore_presets,
            search_file_contents,
            max_workers,
            full_path_compare,
            show_token_count,
            show_tree_stats,
        )
    print("--- Script Execution Finished ---")


def filter_project(
    root_dir_param: Optional[str] = None,
    output_file_name: str = "project_filter_output.txt",
    file_types: Optional[List[str]] = None,
    ignore_dirs_in_path: Optional[List[str]] = None,
    language_presets: Optional[List[LanguagePreset]] = None,
    ignore_presets: Optional[List[IgnorePreset]] = None,
    whitelist_filename_substrings: Optional[List[str]] = None,
    ignore_filename_substrings: Optional[List[str]] = None,
    generate_tree: bool = True,
    tree_style_preset: TreeStylePreset = TreeStylePreset.UNICODE,
    tree_style_t_connector: Optional[str] = None,
    tree_style_l_connector: Optional[str] = None,
    tree_style_v_connector: Optional[str] = None,
    tree_style_h_spacer: Optional[str] = None,
    show_token_count: bool = False,
    show_tree_stats: bool = False,
    encoding: str = DEFAULT_ENCODING,
    separator_char: str = DEFAULT_SEPARATOR_CHAR,
    separator_line_len: int = DEFAULT_SEPARATOR_LINE_LENGTH,
) -> None:
    """Utility wrapper for process_project in FILTER mode."""
    process_project(
        root_dir_param=root_dir_param,
        output_file_name=output_file_name,
        mode=ProjectMode.FILTER,
        file_types=file_types,
        ignore_dirs_in_path=ignore_dirs_in_path,
        language_presets=language_presets,
        ignore_presets=ignore_presets,
        whitelist_filename_substrings=whitelist_filename_substrings,
        ignore_filename_substrings=ignore_filename_substrings,
        generate_tree=generate_tree,
        tree_style_preset=tree_style_preset,
        tree_style_t_connector=tree_style_t_connector,
        tree_style_l_connector=tree_style_l_connector,
        tree_style_v_connector=tree_style_v_connector,
        tree_style_h_spacer=tree_style_h_spacer,
        show_token_count=show_token_count,
        show_tree_stats=show_tree_stats,
        encoding=encoding,
        separator_char=separator_char,
        separator_line_len=separator_line_len,
    )


def find_in_project(
    root_dir_param: Optional[str] = None,
    output_file_name: str = "project_search_output.txt",
    search_keywords: Optional[List[str]] = None,
    file_extensions_to_check: Optional[List[str]] = None,
    ignore_dirs_in_path: Optional[List[str]] = None,
    language_presets: Optional[List[LanguagePreset]] = None,
    ignore_presets: Optional[List[IgnorePreset]] = None,
    search_file_contents: bool = False,
    full_path_compare: bool = True,
    max_workers: Optional[int] = None,
    tree_style_preset: TreeStylePreset = TreeStylePreset.UNICODE,
    tree_style_t_connector: Optional[str] = None,
    tree_style_l_connector: Optional[str] = None,
    tree_style_v_connector: Optional[str] = None,
    tree_style_h_spacer: Optional[str] = None,
    show_token_count: bool = False,
    show_tree_stats: bool = False,
    encoding: str = DEFAULT_ENCODING,
    separator_char: str = DEFAULT_SEPARATOR_CHAR,
    separator_line_len: int = DEFAULT_SEPARATOR_LINE_LENGTH,
) -> None:
    """Utility wrapper for process_project in SEARCH mode."""
    if not search_keywords:
        print("Error: 'search_keywords' must be provided for find_in_project.")
        return
    process_project(
        root_dir_param=root_dir_param,
        output_file_name=output_file_name,
        mode=ProjectMode.SEARCH,
        file_types=file_extensions_to_check,
        ignore_dirs_in_path=ignore_dirs_in_path,
        language_presets=language_presets,
        ignore_presets=ignore_presets,
        search_keywords=search_keywords,
        search_file_contents=search_file_contents,
        full_path_compare=full_path_compare,
        max_workers=max_workers,
        tree_style_preset=tree_style_preset,
        tree_style_t_connector=tree_style_t_connector,
        tree_style_l_connector=tree_style_l_connector,
        tree_style_v_connector=tree_style_v_connector,
        tree_style_h_spacer=tree_style_h_spacer,
        show_token_count=show_token_count,
        show_tree_stats=show_tree_stats,
        encoding=encoding,
        separator_char=separator_char,
        separator_line_len=separator_line_len,
    )


__all__ = [
    "process_project",
    "filter_project",
    "find_in_project",
    "deconstruct_snapshot",
    "ProjectMode",
    "LanguagePreset",
    "IgnorePreset",
    "TreeStylePreset",
]

if __name__ == "__main__":
    # --- Example: Scan with Custom Filters and the New Readable Stats ---
    print("\n--- Running a custom filter scan with new stats format ---")
    filter_project(
        root_dir_param=".",
        output_file_name="custom_snapshot_readable.txt",
        file_types=[".py", "requirements.txt", ".sql", ".md"],
        ignore_dirs_in_path=["venv", "build", "node_modules", "static", "templates"],
        show_tree_stats=True,
        show_token_count=True,
    )