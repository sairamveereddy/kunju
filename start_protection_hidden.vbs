Set shell = CreateObject("WScript.Shell")
root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
shell.Run """" & root & "\dist\PrivacyAlarm\PrivacyAlarm.exe"" --hidden", 0, False
