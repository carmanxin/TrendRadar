# packaging/hooks/hook-feedparser.py
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("feedparser")
hiddenimports = collect_submodules("feedparser")
