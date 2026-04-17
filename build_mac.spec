# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for macOS - builds a .app bundle

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
        'pynput.keyboard._darwin',
        'pynput.mouse._darwin',
        'PyQt6',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'customtkinter', 'tkinter',
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
    [],
    exclude_binaries=True,
    name='Voxel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Voxel',
)

app = BUNDLE(
    coll,
    name='Voxel.app',
    icon='src/assets/icon.icns',
    bundle_identifier='com.draxctrl.voxel',
    info_plist={
        'CFBundleShortVersionString': '2.0.1',
        'CFBundleVersion': '2.0.1',
        'LSUIElement': False,
        'NSMicrophoneUsageDescription': 'Voxel needs microphone access to record your voice for dictation.',
        'NSAppleEventsUsageDescription': 'Voxel needs accessibility access to paste dictated text into other apps.',
    },
)
