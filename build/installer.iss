; Book-Keep Windows installer (Inno Setup)
; Build:
;   iscc build\installer.iss
;
; Prereq:
;   - Run PyInstaller first to produce dist\Book-Keep\...

#define AppName "Book-Keep"
#ifndef AppVersion
#define AppVersion "0.1.0"
#endif
#define AppExeName "Book-Keep.exe"

#ifndef SourceDir
#define SourceDir "..\dist\Book-Keep"
#endif

[Setup]
AppId={{C7B3563B-3B10-4CF3-8C3F-778FDCB2B865}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=dist-installer
OutputBaseFilename=Book-Keep-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
