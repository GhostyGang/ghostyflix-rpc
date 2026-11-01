# PyInstaller recipe for the GhostyFlix RPC Windows desktop build.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

a = Analysis(
    ['run_app.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('assets/icon.png', 'assets'),
        ('assets/icon.ico', 'assets'),
        ('assets/ghostyflix-hero.png', 'assets'),
        ('assets/tmdb-approved-logo.png', 'assets'),
        ('LICENSE', '.'),
        *collect_data_files('customtkinter'),
        *collect_data_files('certifi'),
    ],
    hiddenimports=[
        *collect_submodules('pypresence'),
        *collect_submodules('pystray'),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GhostyFlix RPC',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico'],
)
