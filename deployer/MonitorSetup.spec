# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['c:\\Users\\dani0\\GitProjects\\monitor\\deployer\\deploy.py'],
    pathex=[],
    binaries=[],
    datas=[('c:\\Users\\dani0\\GitProjects\\monitor\\agent', 'agent'), ('c:\\Users\\dani0\\GitProjects\\monitor\\extensions\\chromium', 'extensions/chromium')],
    hiddenimports=['tkinter', 'tkinter.simpledialog'],
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
    name='MonitorSetup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    icon='NONE',
)
