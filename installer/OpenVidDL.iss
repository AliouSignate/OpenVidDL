; Installateur Windows d'OpenVidDL (Inno Setup 6) — généré par build.py
; Compilation manuelle :  iscc /DAppVersion=1.0.0 installer\OpenVidDL.iss

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6F1C2D84-3B7E-4E52-9A0B-0E5D7A1C9F31}
AppName=OpenVidDL
AppVersion={#AppVersion}
AppVerName=OpenVidDL {#AppVersion}
AppPublisher=Les contributeurs d'OpenVidDL
AppPublisherURL=https://github.com/
DefaultDirName={autopf}\OpenVidDL
DefaultGroupName=OpenVidDL
DisableProgramGroupPage=yes
; Pas besoin des droits administrateur : installation pour l'utilisateur courant
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=OpenVidDL-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\OpenVidDL.exe
LicenseFile=..\LICENSE
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\OpenVidDL\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\OpenVidDL"; Filename: "{app}\OpenVidDL.exe"
Name: "{group}\Dossier des téléchargements"; Filename: "{%USERPROFILE}\Downloads\OpenVidDL"
Name: "{group}\{cm:UninstallProgram,OpenVidDL}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\OpenVidDL"; Filename: "{app}\OpenVidDL.exe"; Tasks: desktopicon

[Dirs]
Name: "{%USERPROFILE}\Downloads\OpenVidDL"; Flags: uninsneveruninstall

[Run]
Filename: "{app}\OpenVidDL.exe"; Description: "{cm:LaunchProgram,OpenVidDL}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM OpenVidDL.exe /F"; Flags: runhidden; RunOnceId: "KillApp"

[UninstallDelete]
Type: filesandordirs; Name: "{%USERPROFILE}\.openviddl"
