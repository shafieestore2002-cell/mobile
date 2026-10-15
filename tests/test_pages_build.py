"""Verify the public deployment artifact, including accidental-file exclusion."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('build_site', ROOT / 'scripts/build_site.py')
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class PagesBuildTests(unittest.TestCase):
    def test_only_public_referenced_files_are_selected(self):
        paths = builder.public_files()
        self.assertIn('index.html', paths)
        self.assertIn('assets/js/catalog.js', paths)
        self.assertIn('assets/fonts/OFL.txt', paths)
        self.assertTrue(any(name.endswith('.woff2') for name in paths))
        self.assertTrue(any(name.endswith('.webp') for name in paths))
        for name in paths:
            self.assertFalse(name.startswith(('Apple Store/', 'tests/', '.git/', '.github/', '.test-results/')))
            self.assertNotIn('/reference/', name)
            self.assertNotIn('/utility/', name)
            self.assertNotIn('image-manifest', name)
            self.assertNotIn('ROADMAP', name)

    def test_rebuilds_owned_output_without_shipping_new_unreferenced_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in builder.public_files():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / name).read_bytes())
            excluded = root / 'assets/images/reference/private-example.txt'
            excluded.parent.mkdir(parents=True, exist_ok=True)
            excluded.write_text('not part of the website')
            output = builder.build_site(root)
            expected = set(builder.public_files(root)) | {builder.MARKER, '.nojekyll'}
            actual = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
            self.assertEqual(actual, expected)
            (output / 'stale-file.txt').write_text('old generated file')
            builder.build_site(root)
            self.assertFalse((output / 'stale-file.txt').exists())
            self.assertEqual((output / 'index.html').read_bytes(), (root / 'index.html').read_bytes())

    def test_preserves_an_unowned_existing_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in builder.public_files():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / name).read_bytes())
            (root / '_site').mkdir()
            original = root / '_site/user-file.txt'
            original.write_text('preserve me')
            with self.assertRaisesRegex(ValueError, 'not a generated'):
                builder.build_site(root)
            self.assertEqual(original.read_text(), 'preserve me')


if __name__ == '__main__':
    unittest.main()
