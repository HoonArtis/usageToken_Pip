' Claude/Codex Session PIP - run run.bat hidden (no console window).
' Used by the Desktop/Startup shortcuts so login auto-start stays silent
' while still pulling the latest code (run.bat does git pull + restart).
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
Set sh = CreateObject("WScript.Shell")
sh.Run """" & root & "\run.bat""", 0, False
