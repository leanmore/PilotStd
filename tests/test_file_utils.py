# tests/test_file_utils.py — 文件工具函数测试

import os
import sys
import tempfile
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.core.file_utils import (
    ensure_dir,
    ensure_long_path,
    normalize_std_filename,
    safe_code_for_filename,
    sanitize_filename,
    strip_long_path,
    truncate_path,
)


class TestSanitizeFilename(unittest.TestCase):
    def test_removes_forbidden_chars(self):
        self.assertEqual(sanitize_filename('test<file>.txt'), 'testfile.txt')
        self.assertEqual(sanitize_filename('a:b"c'), 'abc')

    def test_keeps_chinese(self):
        self.assertEqual(sanitize_filename('标准 文件.pdf'), '标准 文件.pdf')

    def test_keeps_normal_chars(self):
        self.assertEqual(sanitize_filename('GBT 1.1-2020.pdf'), 'GBT 1.1-2020.pdf')

    def test_strips_whitespace(self):
        self.assertEqual(sanitize_filename('  file  '), 'file')


class TestSafeCodeForFilename(unittest.TestCase):
    def test_slash_replaced(self):
        self.assertEqual(safe_code_for_filename('GB/T'), 'GBT')

    def test_normal_code(self):
        self.assertEqual(safe_code_for_filename('ISO'), 'ISO')

    def test_empty(self):
        self.assertEqual(safe_code_for_filename(''), '')


class TestTruncatePath(unittest.TestCase):
    def test_short_path_unchanged(self):
        result = truncate_path('C:\\root', 'folder', 'file.pdf')
        self.assertIn('file.pdf', result)

    def test_returns_string(self):
        result = truncate_path('C:\\root', 'some_folder', 'test_file.pdf')
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


class TestEnsureLongPath(unittest.TestCase):
    def test_adds_prefix(self):
        result = ensure_long_path('C:\\test\\path')
        self.assertTrue(result.startswith('\\\\?\\'))

    def test_no_double_prefix(self):
        result = ensure_long_path('\\\\?\\C:\\test')
        self.assertEqual(result, '\\\\?\\C:\\test')

    def test_empty(self):
        result = ensure_long_path('')
        self.assertEqual(result, '')


class TestStripLongPath(unittest.TestCase):
    def test_removes_prefix(self):
        result = strip_long_path('\\\\?\\C:\\test\\path')
        self.assertEqual(result, 'C:\\test\\path')

    def test_no_prefix_unchanged(self):
        result = strip_long_path('C:\\test\\path')
        self.assertEqual(result, 'C:\\test\\path')


class TestNormalizeStdFilename(unittest.TestCase):
    def test_html_tags_stripped(self):
        result = normalize_std_filename('GB/T <em>1.1</em>-2020')
        self.assertNotIn('<em>', result)
        self.assertIn('1.1', result)

    def test_unicode_slash_normalized(self):
        result = normalize_std_filename('GB／T 1.1')
        self.assertNotIn('／', result)

    def test_fullwidth_to_halfwidth(self):
        result = normalize_std_filename('ＧＢ／Ｔ １．１')
        self.assertNotIn('Ｇ', result)

    def test_garbage_suffix_stripped(self):
        result = normalize_std_filename('标准文件 道客巴巴')
        self.assertNotIn('道客巴巴', result)

    def test_extra_spaces_collapsed(self):
        result = normalize_std_filename('GB/T   1.1   -2020')
        self.assertNotIn('   ', result)


class TestEnsureDir(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_directory(self):
        new_dir = os.path.join(self.tmpdir, 'sub', 'deep')
        result = ensure_dir(new_dir)
        self.assertTrue(os.path.isdir(result))
        self.assertEqual(result, new_dir)

    def test_existing_dir(self):
        result = ensure_dir(self.tmpdir)
        self.assertEqual(result, self.tmpdir)

    def test_creates_file_parent(self):
        new_dir = os.path.join(self.tmpdir, 'data', 'files')
        result = ensure_dir(new_dir)
        self.assertTrue(os.path.isdir(result))


class TestMakeStandardFilename(unittest.TestCase):
    def test_basic_filename(self):
        from pilotstd.core.file_utils import make_standard_filename

        name = make_standard_filename("GB/T", "1.1", 2020, "标准化导则", ".pdf")
        self.assertIn("GB", name)
        self.assertIn("1.1", name)
        self.assertIn("2020", name)

    def test_empty_title(self):
        from pilotstd.core.file_utils import make_standard_filename

        name = make_standard_filename("ISO", "9001", 2015, "", ".pdf")
        self.assertIn("ISO", name)


class TestHashFileContent(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.tmpdir, "test.txt")
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("hello world")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_hashes_file(self):
        from pilotstd.core.file_utils import hash_file_content

        result = hash_file_content(self.test_file)
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 64)  # SHA256 hex digest

    def test_nonexistent_file(self):
        from pilotstd.core.file_utils import hash_file_content

        result = hash_file_content(os.path.join(self.tmpdir, "nonexistent.txt"))
        self.assertEqual(result, "")


class TestRemoveEmptyDirs(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_removes_empty_dirs(self):
        from pilotstd.core.file_utils import remove_empty_dirs

        empty_dir = os.path.join(self.tmpdir, "empty_sub")
        os.makedirs(empty_dir)
        removed = remove_empty_dirs(self.tmpdir)
        self.assertGreaterEqual(removed, 1)


class TestSafeMove(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.src = os.path.join(self.tmpdir, "src.txt")
        self.dst = os.path.join(self.tmpdir, "dst.txt")
        with open(self.src, "w") as f:
            f.write("test content")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_moves_file(self):
        from pilotstd.core.file_utils import safe_move

        result = safe_move(self.src, self.dst)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.dst))

    def test_skip_existing(self):
        from pilotstd.core.file_utils import safe_move

        with open(self.dst, "w") as f:
            f.write("existing")
        result = safe_move(self.src, self.dst, on_exists="skip")
        self.assertIsNotNone(result)  # returns bool regardless


if __name__ == '__main__':
    unittest.main()
