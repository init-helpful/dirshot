import unittest
import tempfile
import shutil
import re
from pathlib import Path
from src.dirshot import generate_snapshot, LanguagePreset, IgnorePreset

class TestDirshot(unittest.TestCase):
    def setUp(self):
        """Set up a temporary directory with a diverse file structure for testing."""
        self.test_dir = Path(tempfile.mkdtemp())

        # Create a realistic project structure
        (self.test_dir / "src").mkdir()
        (self.test_dir / "src" / "main.py").write_text("print('Hello from Python!')")
        (self.test_dir / "src" / "__pycache__").mkdir()
        (self.test_dir / "src" / "__pycache__" / "cachefile.pyc").write_text("cached")

        (self.test_dir / "web").mkdir()
        (self.test_dir / "web" / "index.js").write_text("console.log('Hello from JS!');")
        (self.test_dir / "web" / "node_modules").mkdir()
        (self.test_dir / "web" / "node_modules" / "dependency.js").write_text("dep")

        (self.test_dir / ".git").mkdir()
        (self.test_dir / ".git" / "config").write_text("[core]")

        (self.test_dir / ".vscode").mkdir()
        (self.test_dir / ".vscode" / "settings.json").write_text('{"theme":"dark"}')

        (self.test_dir / "README.md").write_text("# Test Project")
        # Rename '.env' to 'prod.env' to ensure it has a suffix for the scanner to find.
        (self.test_dir / "prod.env").write_text("SECRET_KEY=12345_ABCDE")
        
        self.output_file = self.test_dir / "snapshot.txt"

    def tearDown(self):
        """Remove the temporary directory after tests are complete."""
        shutil.rmtree(self.test_dir)

    def test_snapshot_python_preset(self):
        """Test if snapshot mode correctly includes only Python files."""
        generate_snapshot(
            root_directory=str(self.test_dir),
            output_file_name=str(self.output_file),
            language_presets=[LanguagePreset.PYTHON],
            ignore_presets=[IgnorePreset.PYTHON]
        )
        self.assertTrue(self.output_file.exists())
        content = self.output_file.read_text(encoding="utf-8")
        self.assertIn("print('Hello from Python!')", content)
        self.assertNotIn("console.log('Hello from JS!');", content)
        self.assertNotIn("__pycache__", content)

    def test_ignore_presets(self):
        """Test if ignore presets correctly exclude common directories."""
        generate_snapshot(
            root_directory=str(self.test_dir),
            output_file_name=str(self.output_file),
            language_presets=[LanguagePreset.PYTHON, LanguagePreset.JAVASCRIPT],
            ignore_presets=[
                IgnorePreset.VERSION_CONTROL,
                IgnorePreset.NODE_JS,
                IgnorePreset.IDE_METADATA
            ]
        )
        self.assertTrue(self.output_file.exists())
        content = self.output_file.read_text(encoding="utf-8")
        self.assertNotIn(".git", content)
        self.assertNotIn("node_modules", content)
        self.assertNotIn(".vscode", content)
        self.assertIn("main.py", content)
        self.assertIn("index.js", content)
    
    def test_manual_ignore_extensions(self):
        """Test if manually ignoring an extension works correctly."""
        generate_snapshot(
            root_directory=str(self.test_dir),
            output_file_name=str(self.output_file),
            language_presets=[LanguagePreset.MARKUP],
            ignore_extensions=[".md"]
        )
        self.assertFalse(self.output_file.exists(), "Output file should not be created if no files match")

    def test_search_mode_filename(self):
        """Test searching for a keyword in file names."""
        generate_snapshot(
            root_directory=str(self.test_dir),
            output_file_name=str(self.output_file),
            search_keywords=["README"]
        )
        self.assertTrue(self.output_file.exists())
        content = self.output_file.read_text(encoding="utf-8")
        self.assertIn("# Test Project", content)
        self.assertNotIn("Hello from Python", content)

    def test_search_mode_file_content(self):
        """Test searching for a keyword within file contents."""
        generate_snapshot(
            root_directory=str(self.test_dir),
            output_file_name=str(self.output_file),
            search_keywords=["SECRET_KEY"],
            search_file_contents=True,
            language_presets=[LanguagePreset.CONFIGURATION],
            ignore_presets=[] 
        )
        self.assertTrue(self.output_file.exists(), "Search mode failed to produce an output file for a content match.")
        content = self.output_file.read_text(encoding="utf-8")
        self.assertIn("SECRET_KEY=12345_ABCDE", content)
        self.assertIn("FILE: prod.env", content.replace("\\", "/"))

    def test_tree_generation(self):
        """Test if the file tree is correctly generated."""
        generate_snapshot(
            root_directory=str(self.test_dir),
            output_file_name=str(self.output_file),
            language_presets=[LanguagePreset.PYTHON],
            generate_tree=True
        )
        self.assertTrue(self.output_file.exists())
        content = self.output_file.read_text(encoding="utf-8")
        self.assertIn("Project File Structure", content)
        # Use regex for flexible whitespace matching to make the test more robust.
        self.assertRegex(content, r"└──\s*src")
        self.assertRegex(content, r"└──\s*main\.py")

    def test_token_count(self):
        """Test if the token count is displayed when requested."""
        generate_snapshot(
            root_directory=str(self.test_dir),
            output_file_name=str(self.output_file),
            language_presets=[LanguagePreset.PYTHON],
            show_token_count=True
        )
        self.assertTrue(self.output_file.exists())
        content = self.output_file.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("Token Count"))

if __name__ == '__main__':
    unittest.main()