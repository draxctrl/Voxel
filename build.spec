# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('src/assets/icon_idle.png', 'src/assets'),
        ('src/assets/icon_recording.png', 'src/assets'),
        ('src/assets/icon_processing.png', 'src/assets'),
        ('src/assets/chime.wav', 'src/assets'),
        ('src/assets/chime_pop.wav', 'src/assets'),
        ('src/assets/chime_doubletap.wav', 'src/assets'),
        ('src/assets/chime_rising.wav', 'src/assets'),
        ('src/assets/icon.ico', 'src/assets'),
    ],
    hiddenimports=[
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'PyQt6',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'customtkinter', 'tkinter',
        # Offline mode deps - excluded to keep launch fast
        # Users can pip install faster-whisper separately to enable offline mode
        'faster_whisper', 'ctranslate2', 'onnxruntime', 'tokenizers',
        'huggingface_hub', 'av', 'numpy', 'torch', 'sympy', 'mpmath',
        'protobuf', 'flatbuffers',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Voxel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='src/assets/icon.ico',
)
