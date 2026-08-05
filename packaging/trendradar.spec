# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['../trendradar/desktop/__main__.py'],
    pathex=['..'],
    binaries=[],
    datas=[
        ('../trendradar/desktop/webui', 'webui'),
        ('../config/frequency_words.txt', 'config'),
        ('../config/ai_interests.txt', 'config'),
        ('../config/timeline.yaml', 'config'),
    ] + collect_data_files('feedparser'),
    hiddenimports=[
        'feedparser', 'pystray', 'PIL', 'fastapi', 'uvicorn',
        'platformdirs', 'pydantic',
    ],
    hookspath=['hooks'],
    excludes=['tkinter', 'unittest', 'pytest', 'sphinx'],
    runtime_hooks=['runtime_hook_tray.py'],
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    name='TrendRadar',
    icon='icon.ico' if __import__('os').path.exists('icon.ico') else None,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    name='TrendRadar',
)
