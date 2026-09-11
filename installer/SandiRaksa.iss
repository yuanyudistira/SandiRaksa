; SandiRaksa Windows installer (Inno Setup).
;
; Public/unsigned build: packages the application from the PyInstaller output.
; Build with:
;   ISCC.exe /DAppVersion=1.0.4 /DSignedAppDir=<abs path to dist> installer\SandiRaksa.iss
;
; SignedAppDir defaults to ..\dist so the installer works without a signing
; step. When a signing pipeline is added, pass /DSignedAppDir=<signed dir>.

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

#ifndef SignedAppDir
  #define SignedAppDir "..\dist"
#endif

[Setup]
; Stable AppId so upgrades replace the same install and uninstall is detected.
AppId={{7C1B3E42-9A6D-4C5E-B0F2-5A1D2E3F4B60}
AppName=SandiRaksa
AppVersion={#AppVersion}
AppVerName=SandiRaksa {#AppVersion}
AppPublisher=SandiRaksa
AppPublisherURL=https://sandiraksa.infosecguru.id

DefaultDirName={autopf}\SandiRaksa
DefaultGroupName=SandiRaksa
; Always create the Start Menu group (do not let the user opt out / skip page).
DisableProgramGroupPage=yes
AllowNoIcons=no

OutputDir=..\installer-output
OutputBaseFilename=SandiRaksa-Setup-{#AppVersion}

SetupIconFile=..\assets\windows\sandiraksa.ico
UninstallDisplayIcon={app}\SandiRaksa.exe

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

PrivilegesRequired=admin
CloseApplications=yes
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
; Checked by default so silent installs still create a desktop shortcut.
; Users running the wizard can uncheck it.
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "Create a Quick Launch shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Files]
Source: "{#SignedAppDir}\SandiRaksa.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu (always created).
Name: "{autoprograms}\SandiRaksa"; Filename: "{app}\SandiRaksa.exe"; WorkingDir: "{app}"; IconFilename: "{app}\SandiRaksa.exe"
Name: "{autoprograms}\Uninstall SandiRaksa"; Filename: "{uninstallexe}"
; Desktop + Quick Launch (task-controlled, checked by default).
Name: "{autodesktop}\SandiRaksa"; Filename: "{app}\SandiRaksa.exe"; WorkingDir: "{app}"; IconFilename: "{app}\SandiRaksa.exe"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\SandiRaksa"; Filename: "{app}\SandiRaksa.exe"; WorkingDir: "{app}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\SandiRaksa.exe"; Description: "Launch SandiRaksa"; Flags: nowait postinstall skipifsilent
