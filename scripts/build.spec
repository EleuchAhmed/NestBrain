# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# We must collect dynamic submodules that might be missed
hidden_imports = []
hidden_imports += collect_submodules('nestbrain')
hidden_imports += collect_submodules('notebooklm')
hidden_imports += collect_submodules('playwright')
hidden_imports += [
    'pyqtgraph',
    'networkx',
    'OpenGL',
    'playwright',
    'requests',
    'yaml',
    'dotenv',
    'openai',
    'PIL',
]

a = Analysis(
    ['../nestbrain/main.py'],
    pathex=['../'],
    binaries=[],
    datas=[
        ('../nestbrain/assets/app.ico', 'nestbrain/assets'),
        ('../nestbrain/assets/logo.png', 'nestbrain/assets'),
        ('../launcher/windows/start-application.cmd', 'launcher/windows'),
        ('../launcher/windows/start-nestbrain-desktop.cmd', 'launcher/windows'),
        ('../launcher/windows/start-nestbrain-desktop.vbs', 'launcher/windows'),
        ('../launcher/windows/start-research-pipeline.vbs', 'launcher/windows'),
    ] + collect_data_files('playwright'),
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['src', 'automation', 'agents'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    [],
    name='Nestbrain',
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
    icon='../nestbrain/assets/app.ico',
    version='version_info.txt',
    exclude_binaries=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Nestbrain',
)
