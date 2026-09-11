; SandiRaksa Windows installer (Inno Setup).
;
; The installer packages the ALREADY-SIGNED application from signed-app/.
; Build with:
;   ISCC.exe /DAppVersion=1.0.2 /DSignedAppDir=<abs path to signed-app> installer\SandiRaksa.iss
;
; Never point [Files] at dist/ (that is the unsigned build artifact).

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

#ifndef SignedAppDir
  #define SignedAppDir "..\signed-app"
#endif

[Setup]
AppName=SandiRaksa
AppVersion={#AppVersion}
AppVerName=SandiRaksa {#AppVersion}
AppPublisher=SandiRaksa
AppPublisherURL=https://sandiraksa.infosecguru.id

DefaultDirName={autopf}\SandiRaksa
DefaultGroupName=SandiRaksa

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
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "{#SignedAppDir}\SandiRaksa.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\SandiRaksa"; Filename: "{app}\SandiRaksa.exe"
Name: "{autodesktop}\SandiRaksa"; Filename: "{app}\SandiRaksa.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SandiRaksa.exe"; Description: "Launch SandiRaksa"; Flags: nowait postinstall skipifsilent
