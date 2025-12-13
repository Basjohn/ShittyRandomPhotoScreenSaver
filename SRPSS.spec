# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import sys
import os

# Add project root to path so we can import versioning
sys.path.insert(0, 'F:\\Programming\\Apps\\ShittyRandomPhotoScreenSaver')
from versioning import APP_VERSION, APP_NAME, APP_DESCRIPTION, APP_COMPANY, APP_EXE_NAME, parse_version

# Generate version info for Windows exe metadata
v = parse_version(APP_VERSION)
version_info_content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({v.major}, {v.minor}, {v.patch}, 0),
    prodvers=({v.major}, {v.minor}, {v.patch}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'{APP_COMPANY}'),
        StringStruct(u'FileDescription', u'{APP_DESCRIPTION}'),
        StringStruct(u'FileVersion', u'{APP_VERSION}'),
        StringStruct(u'InternalName', u'{APP_EXE_NAME}'),
        StringStruct(u'LegalCopyright', u'Copyright (c) {APP_COMPANY}'),
        StringStruct(u'OriginalFilename', u'{APP_EXE_NAME}.exe'),
        StringStruct(u'ProductName', u'{APP_NAME}'),
        StringStruct(u'ProductVersion', u'{APP_VERSION}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
version_file = os.path.join(os.path.dirname(os.path.abspath(SPECPATH)), 'file_version_info.txt')
with open(version_file, 'w', encoding='utf-8') as f:
    f.write(version_info_content)

datas = [('themes', 'themes'), ('images', 'images')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('PySide6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('PIL')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('certifi')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['F:\\Programming\\Apps\\ShittyRandomPhotoScreenSaver\\main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='SRPSS',
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
    icon=['F:\\Programming\\Apps\\ShittyRandomPhotoScreenSaver\\SRPSS.ico'],
    version='F:\\Programming\\Apps\\ShittyRandomPhotoScreenSaver\\file_version_info.txt',
)
