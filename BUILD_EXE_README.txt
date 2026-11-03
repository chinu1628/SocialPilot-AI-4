SOCIALPILOT AI — WINDOWS EXE BUILD

Why you couldn't open the BAT:
- A BAT file is a build/launch script, not the installed app.
- If it exits instantly, this version keeps the console open and displays errors.
- Windows may block files downloaded from the internet: right-click ZIP > Properties > Unblock (if shown), then extract.

REQUIREMENTS
- Windows 10/11 64-bit
- Python 3.11 or newer (python.org; check "Add Python to PATH")
- Internet for initial package install/build
- For installer wizard: Inno Setup 6 (https://jrsoftware.org/isinfo.php)

BUILD THE APP EXE
1. Extract this package into a normal folder, e.g. Documents\SocialPilotAI.
2. Install Python 3.11+ from python.org and tick Add Python to PATH.
3. Double-click build_windows.bat. Wait until it says BUILD SUCCESS.
4. EXE is created at dist\SocialPilotAI\SocialPilotAI.exe.
5. To create a setup wizard: install Inno Setup 6, right-click SocialPilotAI-Setup.iss > Compile.
6. Installer appears in installer\SocialPilotAI-Setup-4.0.0.exe.

NOTE
The app's SQLite database remains in %USERPROFILE%\SocialPilotAI\socialpilot.db so upgrades won't erase local data.
This package is source + build scripts. It does not contain a prebuilt EXE because Windows/PyInstaller packaging must run on Windows. Meta API sending requires internet and Meta credentials.
