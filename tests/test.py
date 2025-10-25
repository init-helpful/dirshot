import unittest
import sys
import os
import shutil
from pathlib import Path
from io import StringIO
from contextlib import redirect_stdout


from src.dirshot.dirshot import (
    filter_project,
    find_in_project,
    deconstruct_snapshot,
    LanguagePreset,
    IgnorePreset,
)


class TestCodeMapper(unittest.TestCase):
    """Test suite for the CodeMapper script."""

    def setUp(self):
        """Set up a temporary directory structure for testing."""
        self.test_dir = Path("temp_test_project")
        self.output_file = self.test_dir / "output.txt"

        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

        self.test_dir.mkdir()

        (self.test_dir / "src").mkdir()
        (self.test_dir / "src" / "api").mkdir()
        (self.test_dir / "docs").mkdir()
        (self.test_dir / "node_modules").mkdir()
        (self.test_dir / ".venv").mkdir()

        (self.test_dir / "main.py").write_text("import api\n# Main entry point")
        (self.test_dir / "src" / "utils.py").write_text("def helper_function(): pass")
        (self.test_dir / "src" / "api" / "routes.js").write_text("const value = 'api';")
        (self.test_dir / "README.md").write_text("Project documentation.")
        (self.test_dir / "requirements.txt").write_text("tqdm==4.62.3")
        (self.test_dir / ".gitignore").write_text("node_modules/\n.venv/")
        (self.test_dir / "src" / "config.json").write_text('{"key": "secret-key"}')
        (self.test_dir / "docs" / "guide.md").write_text("A user guide.")
        (self.test_dir / "node_modules" / "dependency.js").write_text("// some lib")
        (self.test_dir / ".venv" / "activate").write_text("# shell script")
        (self.test_dir / "legacy_code.py").write_text("# Old code to be ignored")

    def tearDown(self):
        """Remove the temporary directory after tests."""
        shutil.rmtree(self.test_dir)

    def _read_output(self) -> str:
        """Helper to read the content of the generated output file."""
        if self.output_file.exists():
            return self.output_file.read_text(encoding="utf-8")
        return ""

    def test_filter_project_with_python_preset(self):
        """Test filtering for Python files using presets."""
        filter_project(
            root_dir_param=str(self.test_dir),
            output_file_name=str(self.output_file),
            language_presets=[LanguagePreset.PYTHON],
            ignore_presets=[IgnorePreset.PYTHON_ENV],
        )
        content = self._read_output()
        self.assertIn("FILE: main.py", content)
        self.assertIn("FILE: src/utils.py", content)
        self.assertIn("FILE: requirements.txt", content)
        self.assertNotIn("FILE: src/api/routes.js", content)
        self.assertNotIn(".venv", content)

    def test_filter_project_with_ignore_substring(self):
        """Test ignoring files based on a filename substring."""
        filter_project(
            root_dir_param=str(self.test_dir),
            output_file_name=str(self.output_file),
            language_presets=[LanguagePreset.PYTHON],
            ignore_filename_substrings=["legacy"],
        )
        content = self._read_output()
        self.assertIn("FILE: main.py", content)
        self.assertNotIn("legacy_code.py", content)

    def test_find_in_project_by_filename(self):
        """Test searching for files by a keyword in the filename."""
        find_in_project(
            root_dir_param=str(self.test_dir),
            output_file_name=str(self.output_file),
            search_keywords=["main", "utils"],
        )
        content = self._read_output()
        self.assertIn("FILE: main.py", content)
        self.assertIn("FILE: src/utils.py", content)
        self.assertNotIn("routes.js", content)

    def test_find_in_project_with_content_search(self):
        """Test searching for a keyword within file contents."""
        find_in_project(
            root_dir_param=str(self.test_dir),
            output_file_name=str(self.output_file),
            search_keywords=["secret-key"],
            search_file_contents=True,
        )
        content = self._read_output()
        self.assertIn("FILE: src/config.json", content)
        self.assertNotIn("main.py", content)

    def test_find_in_project_no_results(self):
        """Test search that yields no results."""
        find_in_project(
            root_dir_param=str(self.test_dir),
            output_file_name=str(self.output_file),
            search_keywords=["non_existent_keyword"],
            search_file_contents=True,
        )
        content = self._read_output()

        self.assertIn("No files found matching the specified criteria", content)

        self.assertNotIn("FILE:", content)

    def test_show_token_count_option(self):
        """Verify that the token count summary is printed to stdout."""
        string_io = StringIO()
        with redirect_stdout(string_io):
            filter_project(
                root_dir_param=str(self.test_dir),
                output_file_name=str(self.output_file),
                language_presets=[LanguagePreset.PYTHON],
                show_token_count=True,
            )
        console_output = string_io.getvalue()
        self.assertIn("Total Approximated Tokens", console_output)

    def test_filter_with_tree_stats(self):
        """Verify tree stats are correctly added in filter mode."""
        filter_project(
            root_dir_param=str(self.test_dir),
            output_file_name=str(self.output_file),
            language_presets=[LanguagePreset.PYTHON],
            ignore_presets=[IgnorePreset.PYTHON_ENV, IgnorePreset.NODE_MODULES],
            show_tree_stats=True,
        )
        content = self._read_output()
        stats_pattern = r"\[I:\d+/\d+\|T:\d+/\d+\]"
        self.assertRegex(content, stats_pattern)
        self.assertIn("Project File Structure", content)
        self.assertRegex(content, r"└── src \[I:1/1\|T:2/1\]")

    def test_search_with_tree_stats(self):
        """Verify tree stats are correctly added in search mode."""
        find_in_project(
            root_dir_param=str(self.test_dir),
            output_file_name=str(self.output_file),
            search_keywords=["main", "utils"],
            show_tree_stats=True,
        )
        content = self._read_output()
        stats_pattern = r"\[I:F/D - M:\d+/\d+\]"
        self.assertRegex(content, stats_pattern)
        self.assertIn("Project File Structure", content)
        self.assertRegex(content, r"temp_test_project \[I:F/D - M:1/1\]")

    def test_deconstruct_snapshot(self):
        """Test the deconstruction of a generated output file."""
        filter_project(
            root_dir_param=str(self.test_dir),
            output_file_name=str(self.output_file),
            language_presets=[LanguagePreset.PYTHON],
            ignore_presets=[IgnorePreset.PYTHON_ENV],
        )

        data = deconstruct_snapshot(str(self.output_file))

        self.assertIsInstance(data, dict)
        self.assertIn("tree_lines", data)
        self.assertIn("file_paths", data)

        self.assertIn("main.py", "".join(data["tree_lines"]))
        self.assertIn("utils.py", "".join(data["tree_lines"]))

        expected_paths = sorted(
            ["main.py", "requirements.txt", "src/utils.py", "legacy_code.py"]
        )
        actual_paths = sorted(data["file_paths"])

        self.assertEqual(len(actual_paths), 4)
        self.assertListEqual(expected_paths, actual_paths)

    def test_deconstruct_non_existent_file(self):
        """Ensure deconstruction raises an error for a missing file."""
        with self.assertRaises(FileNotFoundError):
            deconstruct_snapshot("non_existent_file.txt")


if __name__ == "__main__":
    unittest.main(verbosity=2)
