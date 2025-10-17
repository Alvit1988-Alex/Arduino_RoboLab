; Inno Setup script for Arduino RoboLab (черновик)
[Setup]
AppName=Arduino RoboLab
AppVersion=0.1.0
DefaultDirName={pf64}\Arduino RoboLab
OutputBaseFilename=ArduinoRoboLab_Setup
ArchitecturesAllowed=x64
DisableProgramGroupPage=yes
UsePreviousAppDir=no
UninstallDisplayIcon={app}\ArduinoRoboLab.exe

[Files]
Source: "..\..\dist\portable\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{autodesktop}\Arduino RoboLab"; Filename: "{app}\ArduinoRoboLab.exe"
Name: "{group}\Arduino RoboLab"; Filename: "{app}\ArduinoRoboLab.exe"

[Run]
Filename: "{app}\ArduinoRoboLab.exe"; Flags: nowait postinstall skipifsilent
