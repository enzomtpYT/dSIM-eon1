# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=['C:/Users/enzomtp-Laptop/Documents/Code/dSIM-eon1'],
    binaries=[],
    datas=[
        ('./modules/Azure-ttk-theme-2.1.0', './modules/Azure-ttk-theme-2.1.0'),
        ('./images', './images')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DSIMpy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disable UPX compression
    upx_exclude=[],  # Ensure no files are excluded from UPX
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='images/Game_UI/icon.ico'  # Ensure this path is correct and the file exists
)
