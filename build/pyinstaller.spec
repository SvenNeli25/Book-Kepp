# Build with:
#   pyinstaller --noconfirm build/pyinstaller.spec
#
# Output ends up under `dist/Book-Keep/Book-Keep.exe` (onedir build).

from pathlib import Path

block_cipher = None

# PyInstaller provides SPECPATH (directory containing this spec file).
BASE = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(BASE / "desktop.py")],
    pathex=[str(BASE)],
    binaries=[],
    datas=[
        (str(BASE / "templates"), "templates"),
        (str(BASE / "static"), "static"),
        (str(BASE / "data.json"), "."),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Book-Keep",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Book-Keep",
)
