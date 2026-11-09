# Build on Windows with: pyinstaller --clean --noconfirm NocturneBattle.spec
import sys
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

a = Analysis(['scripts/desktop_entry.py'],
             datas=collect_data_files('nocturne') + copy_metadata('nocturne-chess') + copy_metadata('chess') + [('COPYING', '.'), ('THIRD_PARTY_NOTICES.md', '.')],
             hiddenimports=[], hookspath=[], excludes=['tkinter'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='NocturneBattle',
          console=False, debug=False, strip=False, upx=False,
          version='packaging/windows_version.txt' if sys.platform == 'win32' else None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='NocturneBattle')
