"""全テストを省略できる差分を保守的に判定する。"""

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

script = Path(__file__).resolve().parents[1] / "ci-change-scope.py"
spec = importlib.util.spec_from_file_location("ci_change_scope", script)
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)


class ChangeScopeTests(unittest.TestCase):
    def test_root_and_nested_documentation_only(self):
        self.assertTrue(scope.documentation_only(["STATUS.md", "docs/examples/導入例.md"]))

    def test_code_configuration_ci_and_data_require_runtime_checks(self):
        for name in (
            "specimens/forms.py",
            "compose.production.yaml",
            ".github/workflows/ci.yml",
            ".github/scripts/verify-static-assets.py",
            "specimens/data/classification.json",
            "templates/base.html",
            "docs/example.sh",
            "specimens/data/example.md",
        ):
            with self.subTest(name=name):
                self.assertFalse(scope.documentation_only(["STATUS.md", name]))

    def test_empty_unknown_and_unsafe_paths_require_runtime_checks(self):
        for paths in ([], [""], ["../docs/a.md"], ["/docs/a.md"], ["other.md"]):
            self.assertFalse(scope.documentation_only(paths))

    def test_missing_zero_or_invalid_base_requires_runtime_checks(self):
        for base in (None, "", "0" * 40, "--option", "a" * 39):
            self.assertTrue(scope.needs_runtime_checks(base, "b" * 40))

    @patch.object(scope.subprocess, "run")
    def test_comparison_failure_requires_runtime_checks(self, run):
        run.side_effect = subprocess.CalledProcessError(1, "git")
        self.assertTrue(scope.needs_runtime_checks("a" * 40, "b" * 40))

    @patch.object(scope.subprocess, "run")
    def test_documentation_diff_skips_runtime_and_does_not_hide_renamed_code(self, run):
        run.return_value.stdout = b"STATUS.md\0docs/example.md\0"
        self.assertFalse(scope.needs_runtime_checks("a" * 40, "b" * 40))
        self.assertIn("--no-renames", run.call_args.args[0])
        run.return_value.stdout = b"specimens/forms.py\0docs/forms.md\0"
        self.assertTrue(scope.needs_runtime_checks("a" * 40, "b" * 40))

    @patch.object(scope.subprocess, "run")
    def test_invalid_utf8_requires_runtime_checks(self, run):
        run.return_value.stdout = b"docs/\xff.md\0"
        self.assertTrue(scope.needs_runtime_checks("a" * 40, "b" * 40))

    @patch.object(scope.subprocess, "run")
    def test_removed_readme_requires_a_container_build(self, run):
        run.return_value.stdout = b"README.md\0"
        with patch.object(scope.Path, "is_file", return_value=False):
            self.assertTrue(scope.needs_runtime_checks("a" * 40, "b" * 40))

    @patch.object(scope.subprocess, "run")
    def test_symbolic_document_requires_runtime_checks(self, run):
        run.return_value.stdout = b"docs/example.md\0"
        with patch.object(scope.Path, "is_symlink", return_value=True):
            self.assertTrue(scope.needs_runtime_checks("a" * 40, "b" * 40))


if __name__ == "__main__":
    unittest.main()
