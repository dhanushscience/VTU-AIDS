[Setup]
AppName=VTU AIDS
AppVersion=2.0.0
AppPublisher=VTU AIDS Contributors
AppPublisherURL=https://github.com/dhanushscience/VTU-AIDS
AppSupportURL=https://github.com/dhanushscience/VTU-AIDS/issues
AppUpdatesURL=https://github.com/dhanushscience/VTU-AIDS/releases
DefaultDirName={autopf}\VTU AIDS
DefaultGroupName=VTU AIDS
OutputDir=Output
OutputBaseFilename=VTU_AIDS_Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
; Install per-machine by default so enterprise/AppControl path rules are more likely to allow launch.
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
SetupIconFile=..\static\app.ico
UninstallDisplayIcon={app}\VTU AIDS.ico
DisableProgramGroupPage=yes
DisableDirPage=no
UsePreviousAppDir=no

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The actual PyInstaller output folder (must run PyInstaller first)
Source: "..\dist\VTU AIDS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "SMART_APP_CONTROL.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\VTU AIDS"; Filename: "{app}\VTU AIDS.exe"; IconFilename: "{app}\VTU AIDS.ico"
Name: "{autodesktop}\VTU AIDS"; Filename: "{app}\VTU AIDS.exe"; IconFilename: "{app}\VTU AIDS.ico"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Get-ChildItem -LiteralPath '{app}' -Recurse -File | Unblock-File -ErrorAction SilentlyContinue"""; StatusMsg: "Preparing application files..."; Flags: runhidden waituntilterminated
; Do not auto-launch after install. On restricted PCs this can fail with
; "Application Control policy has blocked this file" and looks like setup failed.

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    if MsgBox('Do you also want to delete your generated diary entries and saved credentials?', mbConfirmation, MB_YESNO) = IDYES then
    begin
      DelTree(ExpandConstant('{localappdata}\VTU AIDS'), True, True, True);
    end;
  end;
end;
