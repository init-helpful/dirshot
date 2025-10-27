import os
import sys
import re
import time
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple, NamedTuple, Dict, Any
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO
from contextlib import contextmanager

# --- Dependency & Console Management ---
try:
    from rich.console import Console
    from rich.progress import (
        Progress,
        SpinnerColumn,
        BarColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

    class FallbackProgress:
        """A simple, dependency-free progress handler for when 'rich' is not installed."""

        def __init__(self):
            self.tasks, self.task_count, self.active_line = {}, 0, ""

        def add_task(self, description, total=None, **kwargs):
            task_id = self.task_count
            self.tasks[task_id] = {"d": description, "t": total, "c": 0}
            self.task_count += 1
            return task_id

        def update(
            self, task_id, advance=0, completed=None, description=None, **kwargs
        ):
            if task_id not in self.tasks:
                return
            task = self.tasks[task_id]
            if description:
                task["d"] = description
            task["c"] = completed if completed is not None else task["c"] + advance
            line = f"-> {task['d']}: {task['c']}" + (
                f"/{task['t']}" if task["t"] else ""
            )
            sys.stdout.write("\r" + line.ljust(len(self.active_line) + 2))
            sys.stdout.flush()
            self.active_line = line

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            sys.stdout.write("\n")
            sys.stdout.flush()


class ConsoleManager:
    """A wrapper to gracefully handle console output with or without 'rich'."""

    def __init__(self):
        """Initializes the ConsoleManager, detecting if 'rich' is available."""
        self.console = Console() if RICH_AVAILABLE else None

    def log(self, message: str, style: str = ""):
        """Logs a message to the console, applying a style if 'rich' is available."""
        if self.console:
            self.console.log(message, style=style)
        else:
            print(f"[{time.strftime('%H:%M:%S')}] {message}")

    def print_table(self, title: str, columns: List[str], rows: List[List[str]]):
        """Prints a formatted table to the console."""
        if self.console:
            table = Table(
                title=title,
                show_header=True,
                header_style="bold magenta",
                border_style="dim",
            )
            for col in columns:
                table.add_column(col)
            for row in rows:
                table.add_row(*row)
            self.console.print(table)
        else:
            print(f"\n--- {title} ---")
            print(" | ".join(columns))
            for row in rows:
                print(" | ".join(row))
            print("-" * (len(title) + 6))


# --- Configuration Constants ---
DEFAULT_SEPARATOR_CHAR, DEFAULT_ENCODING = "-", "utf-8"
TREE_HEADER_TEXT, FILE_HEADER_PREFIX = "Project File Structure", "FILE: "
BINARY_FILE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".exe",
    ".dll",
    ".so",
    ".jar",
    ".pyc",
    ".mp3",
    ".mp4",
}


# --- Base Lists for Presets ---
# These are defined outside the enums to allow for safe composition.
_PYTHON_BASE = [
    ".py",
    ".pyw",
    "requirements.txt",
    "Pipfile",
    "pyproject.toml",
    "setup.py",
]
_JAVASCRIPT_BASE = [
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    "package.json",
    "jsconfig.json",
    "tsconfig.json",
]
_RUBY_BASE = [".rb", "Gemfile", "Rakefile", ".gemspec"]
_PHP_BASE = [".php", "composer.json", "index.php"]
_JAVA_BASE = [".java", ".jar", ".war", "pom.xml", ".properties"]
_KOTLIN_BASE = [".kt", ".kts", ".gradle", "build.gradle.kts"]
_CSHARP_BASE = [".cs", ".csproj", ".sln", "appsettings.json", "Web.config", ".csx"]
_C_CPP_BASE = [".c", ".cpp", ".h", ".hpp", "Makefile", "CMakeLists.txt", ".cxx", ".hxx"]
_RUST_BASE = [".rs", "Cargo.toml", "Cargo.lock"]
_SWIFT_BASE = [".swift", "Package.swift"]
_OBJECTIVE_C_BASE = [".m", ".mm", ".h"]
_ELIXIR_BASE = [".ex", ".exs", "mix.exs"]
_DART_BASE = [".dart", "pubspec.yaml"]
_SCALA_BASE = [".scala", ".sbt", "build.sbt"]
_R_LANG_BASE = [".r", ".R", ".Rmd"]
_LUA_BASE = [".lua"]

_IDE_VSCODE = [".vscode"]
_IDE_JETBRAINS = [".idea"]
_IDE_SUBLIME = ["*.sublime-project", "*.sublime-workspace"]
_IDE_ECLIPSE = [".project", ".settings", ".classpath"]
_IDE_NETBEANS = ["nbproject"]
_IDE_ATOM = [".atom"]
_IDE_VIM = ["*.swp", "*.swo"]
_IDE_XCODE = ["*.xcodeproj", "*.xcworkspace", "xcuserdata"]


# --- Enums and Data Structures ---
class LanguagePreset(Enum):
    """Provides an extensive list of presets for common language file extensions and key project files."""

    PYTHON = _PYTHON_BASE
    JAVASCRIPT = _JAVASCRIPT_BASE
    JAVA = _JAVA_BASE
    KOTLIN = _KOTLIN_BASE
    C_CPP = _C_CPP_BASE
    C_SHARP = _CSHARP_BASE
    GO = [".go", "go.mod", "go.sum"]
    RUST = _RUST_BASE
    RUBY = _RUBY_BASE
    PHP = _PHP_BASE
    SWIFT = _SWIFT_BASE
    OBJECTIVE_C = _OBJECTIVE_C_BASE
    DART = _DART_BASE
    LUA = _LUA_BASE
    PERL = [".pl", ".pm", ".t"]
    R_LANG = _R_LANG_BASE
    SCALA = _SCALA_BASE
    GROOVY = [".groovy", ".gvy", ".gy", ".gsh"]
    HASKELL = [".hs", ".lhs", "cabal.project"]
    JULIA = [".jl"]
    ZIG = [".zig", "build.zig"]
    NIM = [".nim", ".nimble"]
    ELIXIR = _ELIXIR_BASE
    CLOJURE = [".clj", ".cljs", ".cljc", "project.clj", "deps.edn"]
    F_SHARP = [".fs", ".fsi", ".fsx"]
    OCAML = [".ml", ".mli", "dune-project"]
    ELM = [".elm", "elm.json"]
    PURE_SCRIPT = [".purs", "spago.dhall"]
    COMMON_LISP = [".lisp", ".cl", ".asd"]
    SCHEME = [".scm", ".ss"]
    RACKET = [".rkt"]
    WEB_FRONTEND = [".html", ".htm", ".css", ".scss", ".sass", ".less", ".styl"]
    REACT = _JAVASCRIPT_BASE
    NODE_JS = _JAVASCRIPT_BASE
    EXPRESS_JS = _JAVASCRIPT_BASE
    NEST_JS = _JAVASCRIPT_BASE + ["nest-cli.json"]
    VUE = _JAVASCRIPT_BASE + [".vue", "vue.config.js"]
    ANGULAR = _JAVASCRIPT_BASE + ["angular.json"]
    SVELTE = _JAVASCRIPT_BASE + [".svelte", "svelte.config.js"]
    EMBER = _JAVASCRIPT_BASE + ["ember-cli-build.js"]
    PUG = [".pug", ".jade"]
    HANDLEBARS = [".hbs", ".handlebars"]
    EJS = [".ejs"]
    DJANGO = _PYTHON_BASE + ["manage.py", "wsgi.py", "asgi.py", ".jinja", ".jinja2"]
    FLASK = _PYTHON_BASE + ["app.py", "wsgi.py"]
    RAILS = _RUBY_BASE + ["routes.rb", ".erb", ".haml", ".slim", "config.ru"]
    LARAVEL = _PHP_BASE + [".blade.php", "artisan"]
    SYMFONY = _PHP_BASE + ["symfony.lock"]
    PHOENIX = _ELIXIR_BASE
    SPRING = _JAVA_BASE + ["application.properties", "application.yml"]
    ASP_NET = _CSHARP_BASE + ["*.cshtml", "*.vbhtml", "*.razor"]
    ROCKET_RS = _RUST_BASE + ["Rocket.toml"]
    ACTIX_WEB = _RUST_BASE
    IOS_NATIVE = (
        _SWIFT_BASE
        + _OBJECTIVE_C_BASE
        + [".storyboard", ".xib", "Info.plist", ".pbxproj"]
    )
    ANDROID_NATIVE = _JAVA_BASE + _KOTLIN_BASE + ["AndroidManifest.xml", ".xml"]
    FLUTTER = _DART_BASE
    REACT_NATIVE = _JAVASCRIPT_BASE + ["app.json"]
    XAMARIN = _CSHARP_BASE + [".xaml"]
    DOTNET_MAUI = XAMARIN
    NATIVESCRIPT = _JAVASCRIPT_BASE + ["nativescript.config.ts"]
    UNITY = _CSHARP_BASE + [".unity", ".prefab", ".asset", ".mat", ".unitypackage"]
    UNREAL_ENGINE = _C_CPP_BASE + [".uproject", ".uasset", ".ini"]
    GODOT = [".gd", ".tscn", ".tres", "project.godot"]
    LOVE2D = _LUA_BASE + ["conf.lua", "main.lua"]
    MONOGAME = _CSHARP_BASE + [".mgcb"]
    DOCKER = ["Dockerfile", ".dockerignore", "docker-compose.yml"]
    TERRAFORM = [".tf", ".tfvars", ".tf.json"]
    ANSIBLE = ["ansible.cfg", "inventory.ini"]
    PULUMI = ["Pulumi.yaml"]
    CHEF = _RUBY_BASE
    PUPPET = [".pp"]
    VAGRANT = ["Vagrantfile"]
    GITHUB_ACTIONS = [".yml", ".yaml"]
    GITLAB_CI = [".gitlab-ci.yml"]
    JENKINS = ["Jenkinsfile"]
    CIRCLE_CI = ["config.yml"]
    KUBERNETES = [".yml", ".yaml"]
    BICEP = [".bicep"]
    CLOUDFORMATION = [".json", ".yml"]
    DATA_SCIENCE_NOTEBOOKS = [".ipynb", ".Rmd"]
    SQL = [".sql", ".ddl", ".dml"]
    APACHE_SPARK = list(set(_SCALA_BASE + _PYTHON_BASE + _JAVA_BASE + _R_LANG_BASE))
    ML_CONFIG = ["params.yaml"]
    ELECTRON = _JAVASCRIPT_BASE
    TAURI = _RUST_BASE + ["tauri.conf.json"]
    QT = _C_CPP_BASE + [".pro", ".ui", ".qml"]
    GTK = _C_CPP_BASE + [".ui", "meson.build"]
    WPF = _CSHARP_BASE + [".xaml"]
    WINDOWS_FORMS = _CSHARP_BASE
    BASH = [".sh", ".bash"]
    POWERSHELL = [".ps1", ".psm1"]
    BATCH = [".bat", ".cmd"]
    SOLIDITY = [".sol"]
    VYPER = [".vy"]
    VERILOG = [".v", ".vh"]
    VHDL = [".vhd", ".vhdl"]
    MARKUP = [".md", ".markdown", ".rst", ".adoc", ".asciidoc", ".tex", ".bib"]
    CONFIGURATION = [
        ".json",
        ".xml",
        ".yml",
        ".yaml",
        ".ini",
        ".toml",
        ".env",
        ".conf",
        ".cfg",
    ]
    EDITOR_CONFIG = [".editorconfig"]
    LICENSE = ["LICENSE", "LICENSE.md", "COPYING"]
    CHANGELOG = ["CHANGELOG", "CHANGELOG.md"]


class IgnorePreset(Enum):
    """Provides an extensive list of presets for common directories, files, and patterns to ignore."""

    VERSION_CONTROL = [".git", ".svn", ".hg", ".bzr", ".gitignore", ".gitattributes"]
    OS_FILES = [".DS_Store", "Thumbs.db", "desktop.ini", "ehthumbs.db"]
    BUILD_ARTIFACTS = [
        "dist",
        "build",
        "target",
        "out",
        "bin",
        "obj",
        "release",
        "debug",
    ]
    LOGS = ["*.log", "logs", "npm-debug.log*", "yarn-debug.log*", "yarn-error.log*"]
    TEMP_FILES = ["temp", "tmp", "*.tmp", "*~", "*.bak", "*.swp", "*.swo"]
    SECRET_FILES = [
        ".env",
        "*.pem",
        "*.key",
        "credentials.json",
        "*.p12",
        "*.pfx",
        "secrets.yml",
        ".env.local",
    ]
    COMPRESSED_ARCHIVES = ["*.zip", "*.tar", "*.gz", "*.rar", "*.7z", "*.tgz"]
    IDE_METADATA_VSCODE = _IDE_VSCODE
    IDE_METADATA_JETBRAINS = _IDE_JETBRAINS
    IDE_METADATA_SUBLIME = _IDE_SUBLIME
    IDE_METADATA_ECLIPSE = _IDE_ECLIPSE
    IDE_METADATA_NETBEANS = _IDE_NETBEANS
    IDE_METADATA_ATOM = _IDE_ATOM
    IDE_METADATA_VIM = _IDE_VIM
    IDE_METADATA_XCODE = _IDE_XCODE
    IDE_METADATA = list(
        set(
            _IDE_VSCODE
            + _IDE_JETBRAINS
            + _IDE_SUBLIME
            + _IDE_ECLIPSE
            + _IDE_NETBEANS
            + _IDE_ATOM
            + _IDE_VIM
            + _IDE_XCODE
        )
    )
    NODE_JS = [
        "node_modules",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        ".npm",
    ]
    PYTHON = [
        "__pycache__",
        "venv",
        ".venv",
        "env",
        "lib",
        "lib64",
        ".pytest_cache",
        ".tox",
        "*.pyc",
        ".mypy_cache",
        "htmlcov",
        ".coverage",
    ]
    RUBY = ["vendor/bundle", ".bundle", "Gemfile.lock", ".gem", "coverage"]
    PHP = ["vendor", "composer.lock"]
    DOTNET = ["bin", "obj", "*.user", "*.suo"]
    RUST = ["target", "Cargo.lock"]
    GO = ["vendor", "go.sum"]
    JAVA_MAVEN = ["target"]
    JAVA_GRADLE = [".gradle", "build"]
    ELIXIR = ["_build", "deps", "mix.lock"]
    DART_FLUTTER = [".dart_tool", ".packages", "build", ".flutter-plugins"]
    ELM = ["elm-stuff"]
    HASKELL = ["dist-newstyle", ".stack-work"]
    TESTING_REPORTS = ["coverage", "junit.xml", "lcov.info", ".nyc_output"]
    STATIC_SITE_GENERATORS = ["_site", "public", "resources"]
    CMS_UPLOADS = ["wp-content/uploads"]
    TERRAFORM = [".terraform", "*.tfstate", "*.tfstate.backup", ".terraform.lock.hcl"]
    JUPYTER_NOTEBOOKS = [".ipynb_checkpoints"]
    ANDROID = [".gradle", "build", "local.properties", "*.apk", "*.aab", "captures"]
    IOS = ["Pods", "Carthage", "DerivedData", "build"]
    UNITY = [
        "Library",
        "Temp",
        "Logs",
        "UserSettings",
        "MemoryCaptures",
        "Assets/AssetStoreTools",
    ]
    UNREAL_ENGINE = ["Intermediate", "Saved", "DerivedDataCache", ".vs"]
    GODOT_ENGINE = [".import", "export_presets.cfg"]
    SERVERLESS_FRAMEWORK = [".serverless"]
    AWS = [".aws-sam"]
    VERCEL = [".vercel"]
    NETLIFY = [".netlify"]
    MACOS = [
        ".DS_Store",
        ".AppleDouble",
        ".LSOverride",
        "._*",
        ".Spotlight-V100",
        ".Trashes",
    ]
    WINDOWS = ["Thumbs.db", "ehthumbs.db", "$RECYCLE.BIN/", "Desktop.ini"]
    DEPRECATED_DEPENDENCIES = ["bower_components"]


class FileToProcess(NamedTuple):
    """Represents a file that needs to be processed and included in the output."""

    absolute_path: Path
    relative_path_posix: str


@dataclass
class FilterCriteria:
    """Holds the combined filter criteria for scanning files and directories."""

    file_extensions: Set[str] = field(default_factory=set)
    ignore_if_in_path: Set[str] = field(default_factory=set)
    ignore_extensions: Set[str] = field(default_factory=set)

    @classmethod
    def normalize_inputs(
        cls,
        file_types: Optional[List[str]] = None,
        ignore_if_in_path: Optional[List[str]] = None,
        ignore_extensions: Optional[List[str]] = None,
        lang_presets: Optional[List[LanguagePreset]] = None,
        ignore_presets: Optional[List[IgnorePreset]] = None,
    ) -> "FilterCriteria":
        """
        Consolidates various filter inputs into a single FilterCriteria object.

        Args:
            file_types (list, optional): A list of file extensions to include.
            ignore_if_in_path (list, optional): A list of directory/file names to ignore.
            ignore_extensions (list, optional): A list of file extensions to ignore.
            lang_presets (list, optional): A list of LanguagePreset enums.
            ignore_presets (list, optional): A list of IgnorePreset enums.

        Returns:
            FilterCriteria: An object containing the combined sets of filters.
        """
        all_exts = {ft.lower().strip() for ft in file_types or []}
        all_ignore_paths = {ip.lower().strip() for ip in ignore_if_in_path or []}
        all_ignore_exts = {ie.lower().strip() for ie in ignore_extensions or []}

        for p in lang_presets or []:
            all_exts.update(p.value)
        for p in ignore_presets or []:
            all_ignore_paths.update(p.value)

        return cls(
            file_extensions=all_exts,
            ignore_if_in_path=all_ignore_paths,
            ignore_extensions=all_ignore_exts,
        )


# --- Core Logic Functions ---
def _discover_files(
    root_dir: Path, criteria: FilterCriteria, progress: Any, task_id: Any
) -> List[Path]:
    """
    Recursively scans a directory to find all files matching the criteria.

    Args:
        root_dir (Path): The directory to start the scan from.
        criteria (FilterCriteria): The filtering criteria to apply.
        progress (Any): The progress bar object (from rich or fallback).
        task_id (Any): The ID of the progress bar task to update.

    Returns:
        List[Path]: A list of absolute paths to the candidate files.
    """
    candidate_files, dirs_scanned = [], 0

    def recursive_scan(current_path: Path):
        nonlocal dirs_scanned
        try:
            for entry in os.scandir(current_path):
                entry_path, entry_lower = Path(entry.path), entry.name.lower()
                if entry_lower in criteria.ignore_if_in_path:
                    continue
                if entry.is_dir():
                    recursive_scan(entry_path)
                    dirs_scanned += 1
                    if progress:
                        progress.update(
                            task_id,
                            completed=dirs_scanned,
                            description=f"Discovering files in [cyan]{entry.name}[/cyan]",
                        )
                elif entry.is_file():
                    file_ext = entry_path.suffix.lower()
                    if (
                        criteria.ignore_extensions
                        and file_ext in criteria.ignore_extensions
                    ):
                        continue
                    if (
                        not criteria.file_extensions
                        or file_ext in criteria.file_extensions
                    ):
                        candidate_files.append(entry_path)
        except (PermissionError, FileNotFoundError):
            pass

    recursive_scan(root_dir)
    return candidate_files


def process_file_for_search(
    file_path: Path,
    keywords: List[str],
    search_content: bool,
    full_path: bool,
    activity: Dict,
    read_binary_files: bool,
) -> Optional[Path]:
    """
    Processes a single file to see if it matches the search criteria.

    A match can occur if a keyword is found in the filename or, if enabled,
    within the file's content.

    Args:
        file_path (Path): The absolute path to the file to process.
        keywords (List[str]): A list of keywords to search for.
        search_content (bool): If True, search the content of the file.
        full_path (bool): If True, compare keywords against the full file path.
        activity (Dict): A dictionary to track thread activity.
        read_binary_files (bool): If True, attempt to read and search binary files.

    Returns:
        Optional[Path]: The path to the file if it's a match, otherwise None.
    """
    thread_id = threading.get_ident()
    activity[thread_id] = file_path.name
    try:
        compare_target = str(file_path) if full_path else file_path.name
        if any(key in compare_target.lower() for key in keywords):
            return file_path

        if search_content and (
            read_binary_files or file_path.suffix.lower() not in BINARY_FILE_EXTENSIONS
        ):
            try:
                with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if any(key in line.lower() for key in keywords):
                            return file_path
            except OSError:
                pass
        return None
    finally:
        activity[thread_id] = ""


def _process_files_concurrently(
    files: List[Path],
    keywords: List[str],
    search_content: bool,
    full_path: bool,
    max_workers: Optional[int],
    progress: Any,
    task_id: Any,
    read_binary_files: bool,
) -> Set[Path]:
    """
    Uses a thread pool to process a list of files for search matches concurrently.

    Args:
        files (List[Path]): The list of candidate files to search through.
        keywords (List[str]): The keywords to search for.
        search_content (bool): Whether to search inside file contents.
        full_path (bool): Whether to compare keywords against the full path.
        max_workers (Optional[int]): The maximum number of threads to use.
        progress (Any): The progress bar object.
        task_id (Any): The ID of the processing task on the progress bar.
        read_binary_files (bool): If True, search the content of binary files.

    Returns:
        Set[Path]: A set of absolute paths for all files that matched.
    """
    matched_files, thread_activity = set(), {}
    with ThreadPoolExecutor(
        max_workers=max_workers or (os.cpu_count() or 1) + 4,
        thread_name_prefix="scanner",
    ) as executor:
        future_to_file = {
            executor.submit(
                process_file_for_search,
                f,
                keywords,
                search_content,
                full_path,
                thread_activity,
                read_binary_files,
            ): f
            for f in files
        }
        for future in as_completed(future_to_file):
            if progress:
                active_threads = {
                    f"T{str(tid)[-3:]}": name
                    for tid, name in thread_activity.items()
                    if name
                }
                progress.update(
                    task_id,
                    advance=1,
                    description=f"Processing [yellow]{len(active_threads)} threads[/yellow]",
                )
                if RICH_AVAILABLE:
                    status_panel = Panel(
                        Text(
                            "\n".join(
                                f"[bold cyan]{k}[/]: {v}"
                                for k, v in active_threads.items()
                            )
                        ),
                        border_style="dim",
                        title="[dim]Thread Activity",
                    )
                    progress.update(task_id, status=status_panel)
            if result := future.result():
                matched_files.add(result)
    if progress and RICH_AVAILABLE:
        progress.update(task_id, status="[bold green]Done![/bold green]")
    return matched_files


def _generate_tree_with_stats(
    root_dir: Path, file_paths: List[Path], show_stats: bool
) -> List[str]:
    """
    Generates a directory tree structure from a list of file paths.

    Args:
        root_dir (Path): The root directory of the project, used as the tree's base.
        file_paths (List[Path]): A list of file paths to include in the tree.
        show_stats (bool): If True, include file and directory counts in the tree.

    Returns:
        List[str]: A list of strings, where each string is a line in the tree.
    """
    tree_dict: Dict[str, Any] = {}
    for path in file_paths:
        level = tree_dict
        for part in path.relative_to(root_dir).parts:
            level = level.setdefault(part, {})

    def count_children(d: Dict) -> Tuple[int, int]:
        files = sum(1 for v in d.values() if not v)
        dirs = len(d) - files
        return files, dirs

    lines = []
    style = ("├── ", "└── ", "│   ", "    ")

    def build_lines_recursive(d: Dict, prefix: str = ""):
        items = sorted(d.keys(), key=lambda k: (not d[k], k.lower()))
        for i, name in enumerate(items):
            is_last = i == len(items) - 1
            connector = style[1] if is_last else style[0]
            display_name = name

            if d[name]:
                if show_stats:
                    files, dirs = count_children(d[name])
                    display_name += f" [dim][M: {files}f, {dirs}d][/dim]"

            lines.append(f"{prefix}{connector}{display_name}")

            if d[name]:
                extension = style[3] if is_last else style[2]
                build_lines_recursive(d[name], prefix + extension)

    root_name = f"[bold cyan]{root_dir.name}[/bold cyan]"
    if show_stats:
        files, dirs = count_children(tree_dict)
        root_name += f" [dim][M: {files}f, {dirs}d][/dim]"
    lines.append(root_name)

    build_lines_recursive(tree_dict)
    return lines


def _collate_content_to_file(
    output_path: Path,
    tree_lines: List,
    files: List[FileToProcess],
    show_tree_stats: bool,
    show_token_count: bool,
    exclude_whitespace: bool,
    progress: Any,
    task_id: Any,
) -> Tuple[float, int]:
    """
    Collates the file tree and file contents into a single output file.

    Args:
        output_path (Path): The path to the final output file.
        tree_lines (List): The generated file tree lines.
        files (List[FileToProcess]): The files whose content needs to be collated.
        show_tree_stats (bool): Whether to include the stats key in the header.
        show_token_count (bool): Whether to calculate and include the token count.
        exclude_whitespace (bool): If True, exclude whitespace from token counting.
        progress (Any): The progress bar object.
        task_id (Any): The ID of the collation task on the progress bar.

    Returns:
        Tuple[float, int]: A tuple containing the total bytes written and the token count.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    buffer, total_bytes, token_count = StringIO(), 0, 0

    if tree_lines:
        buffer.write(f"{TREE_HEADER_TEXT}\n" + "-" * 80 + "\n\n")
        if show_tree_stats:
            buffer.write(
                "Key: [M: Matched files/dirs]\n     (f=files, d=directories)\n\n"
            )

        if RICH_AVAILABLE:
            content = "\n".join(Text.from_markup(line).plain for line in tree_lines)
        else:
            content = "\n".join(tree_lines)
        buffer.write(content + "\n\n")

    for file_info in files:
        if progress:
            progress.update(
                task_id,
                advance=1,
                description=f"Collating [green]{file_info.relative_path_posix}[/green]",
            )
        buffer.write(f"{'-'*80}\nFILE: {file_info.relative_path_posix}\n{'-'*80}\n\n")
        try:
            content = file_info.absolute_path.read_text(
                encoding=DEFAULT_ENCODING, errors="replace"
            )
            buffer.write(content + "\n\n")
            total_bytes += len(content.encode(DEFAULT_ENCODING))
        except Exception as e:
            buffer.write(f"Error: Could not read file. Issue: {e}\n\n")

    final_content = buffer.getvalue()
    if show_token_count:
        content_for_count = (
            re.sub(r"\s", "", final_content) if exclude_whitespace else final_content
        )
        token_count = len(content_for_count)

    with output_path.open("w", encoding=DEFAULT_ENCODING) as outfile:
        if show_token_count:
            mode = "chars, no whitespace" if exclude_whitespace else "characters"
            outfile.write(f"Token Count ({mode}): {token_count}\n\n")
        outfile.write(final_content)

    return total_bytes, token_count


# --- Main Entry Point ---
def generate_snapshot(
    root_directory: str = ".",
    output_file_name: str = "project_snapshot.txt",
    search_keywords: Optional[List[str]] = None,
    file_extensions: Optional[List[str]] = None,
    ignore_if_in_path: Optional[List[str]] = None,
    ignore_extensions: Optional[List[str]] = None,
    language_presets: Optional[List[LanguagePreset]] = None,
    ignore_presets: Optional[List[IgnorePreset]] = None,
    search_file_contents: bool = True,
    full_path_compare: bool = True,
    max_workers: Optional[int] = None,
    generate_tree: bool = True,
    show_tree_stats: bool = False,
    show_token_count: bool = False,
    exclude_whitespace_in_token_count: bool = False,
    read_binary_files: bool = False,
) -> None:
    """
    Orchestrates the entire process of scanning, filtering, and collating project files.

    This function serves as the main entry point for the utility. It can be used
    to create a full "snapshot" of a project's source code or to search for
    specific keywords within file names and/or contents. It is highly configurable
    through presets and manual overrides.

    Args:
        root_directory (str): The starting directory for the scan. Defaults to ".".
        output_file_name (str): The name of the file to save the results to.
            Defaults to "project_snapshot.txt".
        search_keywords (List[str], optional): A list of keywords to search for. If
            None or empty, the function runs in "snapshot" mode, including all
            files that match the other criteria. Defaults to None.
        file_extensions (List[str], optional): A list of specific file
            extensions to include (e.g., [".py", ".md"]). Defaults to None.
        ignore_if_in_path (List[str], optional): A list of directory or file
            names to exclude from the scan. Defaults to None.
        ignore_extensions (List[str], optional): A list of file extensions to
            explicitly ignore (e.g., [".log", ".tmp"]). Defaults to None.
        language_presets (List[LanguagePreset], optional): A list of LanguagePreset
            enums for common file types (e.g., [LanguagePreset.PYTHON]). Defaults to None.
        ignore_presets (List[IgnorePreset], optional): A list of IgnorePreset enums
            for common ignore patterns (e.g., [IgnorePreset.PYTHON]). Defaults to None.
        search_file_contents (bool): If True, search for keywords within file
            contents. Defaults to True.
        full_path_compare (bool): If True, search for keywords in the full file path,
            not just the filename. Defaults to True.
        max_workers (Optional[int]): The maximum number of worker threads for
            concurrent processing. Defaults to CPU count + 4.
        generate_tree (bool): If True, a file tree of the matched files will be
            included at the top of the output file. Defaults to True.
        show_tree_stats (bool): If True, display file and directory counts in the
            generated tree. Defaults to False.
        show_token_count (bool): If True, display an approximated token count in the
            summary and output file. Defaults to False.
        exclude_whitespace_in_token_count (bool): If True, whitespace is removed
            before counting tokens, giving a more compact count. Defaults to False.
        read_binary_files (bool): If True, the content search will attempt to read
            and search through binary files. Defaults to False.
    """
    console, start_time = ConsoleManager(), time.perf_counter()
    root_dir = Path(root_directory or ".").resolve()
    if not root_dir.is_dir():
        console.log(f"Error: Root directory '{root_dir}' not found.", style="bold red")
        return

    keywords = [k.lower().strip() for k in search_keywords or [] if k.strip()]
    snapshot_mode = not keywords
    criteria = FilterCriteria.normalize_inputs(
        file_types=file_extensions,
        ignore_if_in_path=ignore_if_in_path,
        ignore_extensions=ignore_extensions,
        lang_presets=language_presets,
        ignore_presets=ignore_presets,
    )

    config_rows = [
        ["Root Directory", str(root_dir)],
        ["File Types", ", ".join(criteria.file_extensions) or "All"],
        ["Ignore Paths", ", ".join(criteria.ignore_if_in_path) or "None"],
        ["Ignore Extensions", ", ".join(criteria.ignore_extensions) or "None"],
        ["Generate Tree", "[green]Yes[/green]" if generate_tree else "[red]No[/red]"],
    ]
    if generate_tree:
        config_rows.append(
            ["Tree Stats", "[green]Yes[/green]" if show_tree_stats else "[red]No[/red]"]
        )
    config_rows.append(
        [
            "Show Token Count",
            "[green]Yes[/green]" if show_token_count else "[red]No[/red]",
        ]
    )
    if show_token_count:
        config_rows.append(
            [
                "Exclude Whitespace",
                (
                    "[green]Yes[/green]"
                    if exclude_whitespace_in_token_count
                    else "[red]No[/red]"
                ),
            ]
        )

    if snapshot_mode:
        config_rows.insert(1, ["Mode", "[bold blue]Snapshot[/bold blue]"])
    else:
        config_rows.insert(1, ["Mode", "[bold yellow]Search[/bold yellow]"])
        config_rows.insert(
            2, ["Search Keywords", f"[yellow]{', '.join(keywords)}[/yellow]"]
        )
        config_rows.append(
            [
                "Search Content",
                "[green]Yes[/green]" if search_file_contents else "[red]No[/red]",
            ]
        )
        config_rows.append(
            [
                "Read Binary Files",
                "[green]Yes[/green]" if read_binary_files else "[red]No[/red]",
            ]
        )
    console.print_table(
        "Project Scan Configuration", ["Parameter", "Value"], config_rows
    )

    @contextmanager
    def progress_manager():
        if RICH_AVAILABLE:
            progress = Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                SpinnerColumn(),
                TimeElapsedColumn(),
                "{task.fields[status]}",
                expand=True,
            )
            with Live(progress, console=console.console, refresh_per_second=10) as live:
                yield progress
        else:
            with FallbackProgress() as progress:
                yield progress

    with progress_manager() as progress:
        discover_task = progress.add_task("Discovering files", total=None, status="")
        candidate_files = _discover_files(root_dir, criteria, progress, discover_task)
        if RICH_AVAILABLE:
            progress.update(
                discover_task,
                description=f"Discovered [bold green]{len(candidate_files)}[/bold green] candidates",
                status="",
            )
        else:
            progress.update(
                discover_task,
                description=f"Discovered {len(candidate_files)} candidates",
            )

        matched_files = set()
        if candidate_files:
            if snapshot_mode:
                matched_files = set(candidate_files)
                if RICH_AVAILABLE:
                    progress.add_task(
                        "[dim]Keyword Processing[/dim]",
                        total=1,
                        completed=1,
                        status="[bold blue](Snapshot Mode)[/bold blue]",
                    )
            else:
                process_task = progress.add_task(
                    f"Processing {len(candidate_files)} files",
                    total=len(candidate_files),
                    status="",
                )
                matched_files = _process_files_concurrently(
                    candidate_files,
                    keywords,
                    search_file_contents,
                    full_path_compare,
                    max_workers,
                    progress,
                    process_task,
                    read_binary_files,
                )

        output_path, total_bytes, token_count = None, 0, 0
        if matched_files:
            sorted_files = sorted(
                list(matched_files), key=lambda p: p.relative_to(root_dir).as_posix()
            )
            tree_lines = []
            if generate_tree:
                tree_task = progress.add_task(
                    "Generating file tree...", total=1, status=""
                )
                tree_lines = _generate_tree_with_stats(
                    root_dir, sorted_files, show_tree_stats
                )
                progress.update(
                    tree_task, completed=1, description="Generated file tree"
                )

            collate_task = progress.add_task(
                f"Collating {len(sorted_files)} files",
                total=len(sorted_files),
                status="",
            )
            files_to_process = [
                FileToProcess(f, f.relative_to(root_dir).as_posix())
                for f in sorted_files
            ]
            output_path = Path(output_file_name).resolve()
            total_bytes, token_count = _collate_content_to_file(
                output_path,
                tree_lines,
                files_to_process,
                show_tree_stats,
                show_token_count,
                exclude_whitespace_in_token_count,
                progress,
                collate_task,
            )

    end_time = time.perf_counter()
    summary_rows = [
        ["Candidate Files", f"{len(candidate_files)}"],
        ["Files Matched", f"[bold green]{len(matched_files)}[/bold green]"],
        ["Total Time", f"{end_time - start_time:.2f} seconds"],
        ["Output Size", f"{total_bytes / 1024:.2f} KB"],
    ]
    if show_token_count:
        summary_rows.append(["Approximated Tokens", f"{token_count:,}"])
    summary_rows.append(["Output File", str(output_path or "N/A")])
    console.print_table("Scan Complete", ["Metric", "Value"], summary_rows)


if __name__ == "__main__":
    generate_snapshot(
        root_directory=".",
        output_file_name="project_snapshot_final.txt",
        # No search keywords triggers Snapshot Mode
        language_presets=[LanguagePreset.PYTHON],
        ignore_presets=[
            IgnorePreset.PYTHON,
            IgnorePreset.BUILD_ARTIFACTS,
            IgnorePreset.VERSION_CONTROL,
            IgnorePreset.NODE_JS,
            IgnorePreset.IDE_METADATA,
        ],
        ignore_extensions=[".log", ".tmp"],  # Example of new functionality
        generate_tree=True,
        show_tree_stats=True,
        show_token_count=True,
        exclude_whitespace_in_token_count=True,
    )
