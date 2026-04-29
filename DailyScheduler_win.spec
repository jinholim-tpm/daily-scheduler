# -*- mode: python ; coding: utf-8 -*-
# Windows용 PyInstaller spec 파일
# 사용법: pyinstaller DailyScheduler_win.spec

import sys
import os

a = Analysis(
    ['daily_scheduler.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# .ico 파일이 있으면 사용, 없으면 아이콘 없이 빌드
icon_file = 'AppIcon.ico' if os.path.exists('AppIcon.ico') else None

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DailyScheduler',
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
    icon=icon_file,
)
