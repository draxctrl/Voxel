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
        ('src/assets/icon.png', 'src/assets'),
        ('src/assets/fonts', 'src/assets/fonts'),
        ('src/assets/flags', 'src/assets/flags'),
        ('src/assets/icons/phosphor', 'src/assets/icons/phosphor'),
    ],
    hiddenimports=[
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'PyQt6',
        # The settings panes are looked up by name through importlib, so
        # nothing imports them in a way PyInstaller can see. Left out,
        # the built app dies on startup with "No module named ...".
        # tests/test_build_spec.py keeps this list in step with the registry.
        'src.ui_pyqt6.panes.writing_style',
        'src.ui_pyqt6.panes.voice_commands',
        'src.ui_pyqt6.panes.language',
        'src.ui_pyqt6.panes.microphone',
        'src.ui_pyqt6.panes.shortcuts',
        'src.ui_pyqt6.panes.appearance',
        'src.ui_pyqt6.panes.history',
        'src.ui_pyqt6.panes.stats',
        'src.ui_pyqt6.panes.general',
        'src.ui_pyqt6.panes.about',
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
