#!/usr/bin/env python3
"""Build a small GitHub Pages artifact using only public storefront files."""

from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[1]
BASE_FILES = {
    'index.html', 'shafiee-advanced.html', 'logo-motion.html', 'shafiee-logo2.png',
    'assets/css/store.css', 'assets/js/app.js', 'assets/js/catalog.js',
    'assets/fonts/OFL.txt',
}
MARKER = '.shafiee-pages-build'


def public_files(root=ROOT):
    root = Path(root).resolve()
    paths = set(BASE_FILES)
    for name in ('index.html', 'assets/js/catalog.js'):
        paths.update(re.findall(r'assets/images/[^\s"\'<>]+', (root / name).read_text()))
    stylesheet = root / 'assets/css/store.css'
    for ref in re.findall(r'url\(["\']?([^\)"\']+)["\']?\)', stylesheet.read_text()):
        resolved = (stylesheet.parent / ref).resolve()
        paths.add(resolved.relative_to(root).as_posix())
    for name in paths:
        resolved = (root / name).resolve(strict=True)
        resolved.relative_to(root)
        if not resolved.is_file():
            raise ValueError(f'Public asset is not a regular file: {name}')
    return sorted(paths)


def build_site(root=ROOT):
    root = Path(root).resolve()
    paths = public_files(root)
    output = root / '_site'
    if output.is_symlink():
        raise ValueError('Refusing to replace a symlink at _site')
    if output.exists():
        if not output.is_dir() or not (output / MARKER).is_file():
            raise ValueError('_site already exists and is not a generated storefront build')
        shutil.rmtree(output)
    output.mkdir()
    (output / MARKER).write_text('shafiee-pages-v1\n')
    for name in paths:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
    (output / '.nojekyll').touch()
    print(f'Built {len(paths)} public files in {output}')
    return output


if __name__ == '__main__':
    build_site()
