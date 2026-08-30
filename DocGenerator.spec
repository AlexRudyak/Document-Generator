# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for Document Generator.

    pip install -r requirements.txt -r requirements-dev.txt
    pyinstaller DocGenerator.spec

Produces ``dist/DocGenerator/DocGenerator(.exe)``. Run it and the app opens in
the default browser. User data (SQLite DB + uploads) is stored per-user under
``%LOCALAPPDATA%/DocGenerator`` (Windows) and NOT inside the bundle.
"""

from PyInstaller.utils.hooks import collect_all

datas = [
    ('app/templates', 'app/templates'),
    ('app/static/css', 'app/static/css'),
    ('app/static/js', 'app/static/js'),
    ('app/static/assets', 'app/static/assets'),   # logos + bundled Hebrew font
]
binaries = []
hiddenimports = ['waitress']

# Third-party packages that ship data files / native extensions.
for pkg in ('reportlab', 'bidi'):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=['matplotlib', 'numpy', 'pytest', 'tkinter'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='DocGenerator',
    console=True,          # keep a console window so the user can close it to quit
    icon=None,
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    name='DocGenerator',
)
