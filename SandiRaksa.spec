# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('src/sandiraksa/resources', 'sandiraksa/resources'),
    ('assets/windows', 'assets/windows'),
    ('assets/branding', 'assets/branding'),
]
binaries = []
hiddenimports = ['PySide6.QtSvg', 'PySide6.QtXml', 'PySide6.QtNetwork', 'presidio_analyzer', 'presidio_anonymizer', 'spacy', 'openpyxl', 'docx', 'pptx', 'cryptography', 'keyring', 'charset_normalizer', 'sandiraksa.clipboard', 'sandiraksa.clipboard.worker_process', 'sandiraksa.clipboard.controller', 'sandiraksa.clipboard.supervisor']
tmp_ret = collect_all('presidio_analyzer')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('spacy')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
# Bundle the English spaCy model package. Without this the frozen app has no
# NLP model, so spacy.load('en_core_web_sm') fails at runtime. Since the app
# now preloads the analyzer at startup, a missing model crashed the .exe on
# launch (worked from source only because the model was in site-packages).
tmp_ret = collect_all('en_core_web_sm')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['src/sandiraksa/__main__.py'],
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
    name='SandiRaksa',
    icon='assets/windows/sandiraksa.ico',
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
)
