; =============================================================================
;  CHSuite_Installer.nsi
;  NSIS installer script for CHSuite by JURMR
;
;  Requirements:
;    - NSIS 3.x installed (https://nsis.sourceforge.io/Download)
;    - Run AFTER build.bat has produced dist\CHSuite\
;    - Place this .nsi file in the same folder as build.bat
;
;  To compile:
;    Right-click CHSuite_Installer.nsi -> "Compile NSIS Script"
;    OR from command line: makensis CHSuite_Installer.nsi
;
;  Output: CHSuite_Setup.exe  (in the same folder as this script)
; =============================================================================

!include "MUI2.nsh"
!include "LogicLib.nsh"

; ---------------------------------------------------------------------------
; Basic info
; ---------------------------------------------------------------------------
Name                "CHSuite"
OutFile             "CHSuite_Setup.exe"
InstallDir          "C:\CHSuite"
InstallDirRegKey    HKCU "Software\CHSuite" "InstallDir"
RequestExecutionLevel admin
SetCompressor       /SOLID lzma

; ---------------------------------------------------------------------------
; Version info
; ---------------------------------------------------------------------------
VIProductVersion    "1.0.0.0"
VIAddVersionKey     "ProductName"     "CHSuite"
VIAddVersionKey     "ProductVersion"  "1.0.0"
VIAddVersionKey     "CompanyName"     "JURMR"
VIAddVersionKey     "FileDescription" "CHSuite Installer"
VIAddVersionKey     "FileVersion"     "1.0.0"
VIAddVersionKey     "LegalCopyright"  "JURMR"

; ---------------------------------------------------------------------------
; Macro: set "Run as administrator" flag on a .lnk shortcut file.
; ---------------------------------------------------------------------------
!macro SetRunAsAdmin LNK_PATH
    FileOpen $9 "${LNK_PATH}" r
    FileSeek $9 21
    FileReadByte $9 $8
    FileClose $9
    IntOp $8 $8 | 0x20
    FileOpen $9 "${LNK_PATH}" a
    FileSeek $9 21
    FileWriteByte $9 $8
    FileClose $9
!macroend

; ---------------------------------------------------------------------------
; UI settings
; ---------------------------------------------------------------------------
!define MUI_ABORTWARNING
!define MUI_ICON                    "JURMRWEED.ico"
!define MUI_UNICON                  "JURMRWEED.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_RIGHT
!define MUI_WELCOMEFINISHPAGE_BITMAP_NOSTRETCH

; Finish page -- offer to launch the app immediately
!define MUI_FINISHPAGE_RUN          "$INSTDIR\CHSuite.exe"
!define MUI_FINISHPAGE_RUN_TEXT     "Launch CHSuite"
!define MUI_FINISHPAGE_RUN_NOTCHECKED

; ---------------------------------------------------------------------------
; Installer pages
; ---------------------------------------------------------------------------
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; ---------------------------------------------------------------------------
; Uninstaller pages
; ---------------------------------------------------------------------------
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; ---------------------------------------------------------------------------
; Language
; ---------------------------------------------------------------------------
!insertmacro MUI_LANGUAGE "English"

; ---------------------------------------------------------------------------
; Installer section
; ---------------------------------------------------------------------------
Section "CHSuite" SecMain

    SectionIn RO

    SetOutPath "$INSTDIR"

    ; Copy everything from the build output
    File /r "dist\CHSuite\*.*"

    ; Write install dir to registry
    WriteRegStr HKCU "Software\CHSuite" "InstallDir" "$INSTDIR"

    ; Write uninstall info to Add/Remove Programs
    WriteRegStr HKLM \
        "Software\Microsoft\Windows\CurrentVersion\Uninstall\CHSuite" \
        "DisplayName" "CHSuite"
    WriteRegStr HKLM \
        "Software\Microsoft\Windows\CurrentVersion\Uninstall\CHSuite" \
        "DisplayVersion" "1.0.0"
    WriteRegStr HKLM \
        "Software\Microsoft\Windows\CurrentVersion\Uninstall\CHSuite" \
        "Publisher" "JURMR"
    WriteRegStr HKLM \
        "Software\Microsoft\Windows\CurrentVersion\Uninstall\CHSuite" \
        "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr HKLM \
        "Software\Microsoft\Windows\CurrentVersion\Uninstall\CHSuite" \
        "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM \
        "Software\Microsoft\Windows\CurrentVersion\Uninstall\CHSuite" \
        "DisplayIcon" "$INSTDIR\CHSuite.exe"
    WriteRegDWORD HKLM \
        "Software\Microsoft\Windows\CurrentVersion\Uninstall\CHSuite" \
        "NoModify" 1
    WriteRegDWORD HKLM \
        "Software\Microsoft\Windows\CurrentVersion\Uninstall\CHSuite" \
        "NoRepair" 1

    ; Create Start Menu shortcut (with "Run as administrator" flag)
    CreateDirectory "$SMPROGRAMS\CHSuite"
    CreateShortcut \
        "$SMPROGRAMS\CHSuite\CHSuite.lnk" \
        "$INSTDIR\CHSuite.exe" \
        "" \
        "$INSTDIR\CHSuite.exe" \
        0 \
        SW_SHOWNORMAL \
        "" \
        "Clone Hero Utility Suite by JURMR"

    !insertmacro SetRunAsAdmin "$SMPROGRAMS\CHSuite\CHSuite.lnk"

    ; Desktop shortcut
    CreateShortcut \
        "$DESKTOP\CHSuite.lnk" \
        "$INSTDIR\CHSuite.exe" \
        "" \
        "$INSTDIR\CHSuite.exe" \
        0 \
        SW_SHOWNORMAL \
        "" \
        "Clone Hero Utility Suite by JURMR"

    !insertmacro SetRunAsAdmin "$DESKTOP\CHSuite.lnk"

    ; Write the uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"

SectionEnd

; ---------------------------------------------------------------------------
; Uninstaller section
; ---------------------------------------------------------------------------
Section "Uninstall"

    RMDir /r "$INSTDIR"
    RMDir /r "$SMPROGRAMS\CHSuite"
    Delete "$DESKTOP\CHSuite.lnk"

    DeleteRegKey HKCU "Software\CHSuite"
    DeleteRegKey HKLM \
        "Software\Microsoft\Windows\CurrentVersion\Uninstall\CHSuite"

SectionEnd
