# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['Monitor\\main.py'],
    pathex=['C:/Users/Sam/Documents/GitHub/BetMonitor/Monitor'],
    binaries=[],
    datas=[
        ('C:/Users/Sam/Documents/GitHub/BetMonitor/Monitor/Forest-ttk-theme-master', 'Forest-ttk-theme-master'),
        ('C:/Users/Sam/Documents/GitHub/BetMonitor/Monitor/splash.ico', 'splash.ico')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main',
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)