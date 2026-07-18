import tempfile
import unittest
from pathlib import Path

import yaml

from booru_download.core.fs_safety import (
    atomic_write_yaml,
    clamp_concurrency,
    normalize_file_ext,
    normalize_max_posts,
    normalize_timeout,
    safe_join,
    sanitize_subfolder,
    unique_tmp_path,
)


class NormalizeFileExtTests(unittest.TestCase):
    def test_plain_extensions_pass(self):
        self.assertEqual(normalize_file_ext("PNG"), "png")
        self.assertEqual(normalize_file_ext(".webp"), "webp")

    def test_path_separators_rejected(self):
        self.assertEqual(normalize_file_ext(r"x\..\..\escaped\payload.bin"), "jpg")
        self.assertEqual(normalize_file_ext("a/b"), "jpg")
        self.assertEqual(normalize_file_ext("../png"), "jpg")

    def test_empty_and_overlong_rejected(self):
        self.assertEqual(normalize_file_ext(""), "jpg")
        self.assertEqual(normalize_file_ext(None), "jpg")
        self.assertEqual(normalize_file_ext("a" * 11), "jpg")


class SanitizeSubfolderTests(unittest.TestCase):
    def test_normal_names_kept(self):
        self.assertEqual(sanitize_subfolder("my_folder"), "my_folder")
        self.assertEqual(sanitize_subfolder("a/b"), "a/b")

    def test_traversal_removed(self):
        self.assertEqual(sanitize_subfolder(r"..\..\escaped"), "escaped")
        self.assertEqual(sanitize_subfolder("../../x"), "x")

    def test_rooted_paths_neutralized(self):
        result = sanitize_subfolder(r"C:\Windows\System32")
        self.assertNotIn(":", result)
        self.assertNotIn("\\", result)

    def test_reserved_names_dropped(self):
        self.assertEqual(sanitize_subfolder("CON"), "")
        self.assertEqual(sanitize_subfolder("nul.txt"), "")

    def test_empty_input(self):
        self.assertEqual(sanitize_subfolder(""), "")
        self.assertEqual(sanitize_subfolder("   "), "")


class SafeJoinTests(unittest.TestCase):
    def test_inside_root_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = safe_join(root, "sub/file.jpg")
            self.assertTrue(str(result).startswith(str(root.resolve())))

    def test_escape_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "inner"
            root.mkdir()
            with self.assertRaises(ValueError):
                safe_join(root, r"..\escaped.jpg")
            with self.assertRaises(ValueError):
                safe_join(root, "99.x/../../../escaped/payload.bin")


class AtomicWriteTests(unittest.TestCase):
    def test_atomic_yaml_roundtrip_and_no_leftover_tmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.yaml"
            atomic_write_yaml(target, {"known_good": True})
            atomic_write_yaml(target, {"second": 2})
            data = yaml.safe_load(target.read_text(encoding="utf-8"))
            self.assertEqual(data, {"second": 2})
            leftovers = [p for p in Path(tmp).iterdir() if p.name != "config.yaml"]
            self.assertEqual(leftovers, [])

    def test_serialization_error_keeps_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.yaml"
            atomic_write_yaml(target, {"known_good": True})
            with self.assertRaises(yaml.YAMLError):
                atomic_write_yaml(target, {"bad": object()})
            data = yaml.safe_load(target.read_text(encoding="utf-8"))
            self.assertEqual(data, {"known_good": True})

    def test_unique_tmp_paths_differ(self):
        target = Path("some/dir/file.jpg")
        self.assertNotEqual(unique_tmp_path(target), unique_tmp_path(target))


class LimitClampTests(unittest.TestCase):
    def test_concurrency(self):
        self.assertEqual(clamp_concurrency(0), 1)
        self.assertEqual(clamp_concurrency(-5), 1)
        self.assertEqual(clamp_concurrency(8), 8)
        self.assertEqual(clamp_concurrency(9999), 64)
        self.assertEqual(clamp_concurrency("abc"), 8)

    def test_timeout(self):
        self.assertEqual(normalize_timeout(0), 30.0)
        self.assertEqual(normalize_timeout(-1), 30.0)
        self.assertEqual(normalize_timeout(float("nan")), 30.0)
        self.assertEqual(normalize_timeout(float("inf")), 30.0)
        self.assertEqual(normalize_timeout(45), 45.0)

    def test_max_posts(self):
        self.assertEqual(normalize_max_posts(0), 1)
        self.assertEqual(normalize_max_posts(-3), 1)
        self.assertEqual(normalize_max_posts(50), 50)
        self.assertEqual(normalize_max_posts("abc"), 100)


if __name__ == "__main__":
    unittest.main()
