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
        # faster-whisper and its engine are IN the build: the app offers
        # Work offline and the README sells it, and for three versions
        # leaving them out meant turning it on broke every dictation.
        # They are what makes this a folder rather than one file - 150MB
        # unpacking itself on every launch is not a trade worth making.
        #
        # torch is not among them. faster-whisper runs on ctranslate2 and
        # never imports it, and it would add a gigabyte.
        'torch', 'sympy', 'mpmath',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# A folder, not a single file. One-file builds unpack their whole payload
# into a temporary directory on every launch; with the offline engine
# aboard that is ~180MB of unpacking before the window appears, every
# time, for everyone - including the people who never turn offline on.
# The installer hides the folder, and the portable download is a zip.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Voxel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='src/assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Voxel',
)
