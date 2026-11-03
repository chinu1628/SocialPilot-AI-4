# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
pyside = collect_all('PySide6')
a = Analysis(['main.py'],
             pathex=[],
             binaries=pyside[0],
             datas=pyside[1],
             hiddenimports=pyside[2] + ['keyring.backends.Windows'],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas,
          [],
          name='SocialPilotAI',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False)
