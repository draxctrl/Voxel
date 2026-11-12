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
        ('src/assets/icon.png', 'src/assets'),
        ('src/assets/icon.icns', 'src/assets'),
        ('src/assets/fonts', 'src/assets/fonts'),
        ('src/assets/flags', 'src/assets/flags'),
        ('src/assets/icons/phosphor', 'src/assets/icons/phosphor'),
    ],
    hiddenimports=[
        'pynput.keyboard._darwin',
        'pynput.mouse._darwin',
        'PyQt6',
        # The settings panes are looked up by name through importlib, so
        # nothing imports them in a way PyInstaller can see. Left out, the
        # built app dies on launch with "No module named ...", which is
        # what the Windows build did before this list existed.
        # tests/test_build_spec.py checks both specs against the registry.
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
        # Offline transcription is left out of the macOS build for now.
        # The Windows one carries it; doing the same here needs a DMG
        # several times this size and a mac to test it on, and shipping
        # it untested is how the last broken build happened. The app
        # says plainly that offline is not included rather than failing
        # silently, so this is honest rather than hidden.
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
