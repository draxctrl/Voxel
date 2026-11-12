; Voxel Installer Script
; NSIS Modern UI

!include "MUI2.nsh"

; General
Name "Voxel"
OutFile "dist\Voxel_Setup.exe"
InstallDir "$LOCALAPPDATA\Voxel"
RequestExecutionLevel user

; UI Settings
!define MUI_ICON "src\assets\icon.ico"
!define MUI_UNICON "src\assets\icon.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Welcome to Voxel Setup"
!define MUI_WELCOMEPAGE_TEXT "Voxel is a voice dictation tool for Windows.$\r$\n$\r$\nHold Ctrl+Shift+Space, speak naturally, and polished text is typed into any app.$\r$\n$\r$\nClick Next to continue."
!define MUI_FINISHPAGE_RUN "$INSTDIR\Voxel.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch Voxel"

; Pages
!insertmacro MUI_PAGE_WELCOME
; Voxel is free software under the GPL v3. The licence grants rights
; rather than taking them away, so it is shown, not click-wrapped.
!define MUI_LICENSEPAGE_TEXT_BOTTOM "Voxel is free software under the GNU General Public License v3. Click Next to continue."
!define MUI_LICENSEPAGE_BUTTON "Next"
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Language
!insertmacro MUI_LANGUAGE "English"

; Version info
VIProductVersion "3.1.1.0"
VIAddVersionKey "ProductName" "Voxel"
VIAddVersionKey "FileDescription" "Voxel Voice Dictation"
VIAddVersionKey "FileVersion" "3.1.1"
VIAddVersionKey "ProductVersion" "3.1.1"
VIAddVersionKey "LegalCopyright" "Copyright (C) 2026 draxctrl. Free software under the GNU GPL v3."

; Installer
Section "Install"
    SetOutPath "$INSTDIR"

    ; The whole program folder. Voxel ships as a folder rather than as one
    ; file because it carries the offline transcription engine, and a single
    ; file would unpack all of it on every launch.
    File /r "dist\Voxel\*.*"

    ; The GPL requires that everyone who receives the program also
    ; receives the licence, so it ships beside the executable.
    File "LICENSE"

    ; Create Start Menu shortcuts
    CreateDirectory "$SMPROGRAMS\Voxel"
    CreateShortcut "$SMPROGRAMS\Voxel\Voxel.lnk" "$INSTDIR\Voxel.exe" "" "$INSTDIR\Voxel.exe" 0
    CreateShortcut "$SMPROGRAMS\Voxel\Uninstall.lnk" "$INSTDIR\Uninstall.exe"

    ; Desktop shortcut
    CreateShortcut "$DESKTOP\Voxel.lnk" "$INSTDIR\Voxel.exe" "" "$INSTDIR\Voxel.exe" 0

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Add to Windows "Apps & Features"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Voxel" "DisplayName" "Voxel"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Voxel" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Voxel" "DisplayIcon" "$INSTDIR\Voxel.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Voxel" "Publisher" "Voxel"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Voxel" "DisplayVersion" "3.1.1"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Voxel" "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Voxel" "NoRepair" 1
SectionEnd

; Uninstaller
Section "Uninstall"
    ; Kill running instance first
    ExecWait 'taskkill /f /im Voxel.exe'

    ; Remove shortcuts first
    Delete "$SMPROGRAMS\Voxel\Voxel.lnk"
    Delete "$SMPROGRAMS\Voxel\Uninstall.lnk"
    RMDir "$SMPROGRAMS\Voxel"
    Delete "$DESKTOP\Voxel.lnk"

    ; Remove registry
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Voxel"

    ; Remove files — delete self last
    Delete "$INSTDIR\Voxel.exe"
    Delete "$INSTDIR\LICENSE"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir /r "$INSTDIR"
SectionEnd
