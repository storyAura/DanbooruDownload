# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


block_cipher = None

customtkinter_datas = collect_data_files("customtkinter")
customtkinter_hiddenimports = collect_submodules("customtkinter")
app_datas = [
    ("booru_download/assets", "booru_download/assets"),
]

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=[],
    datas=customtkinter_datas + app_datas,
    hiddenimports=customtkinter_hiddenimports,
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
    name="BooruDownload",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="booru_download/assets/app_icon.ico",
    contents_directory="win-x64",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="BooruDownload",
)
