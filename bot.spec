# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — портативная onefile-сборка TelethonBot.
# Запуск: pyinstaller bot.spec

import os

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'telethon',
        'telethon.network.connection.tcpmtproxy',
        'python_socks',
        'python_socks.async_.asyncio',
        'python_socks._protocols.errors',
        'cryptg',
    ],
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

exe_name = os.environ.get('PYI_EXE_NAME', 'TelethonBot')

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
