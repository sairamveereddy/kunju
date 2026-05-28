Set shell = CreateObject("WScript.Shell")
root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
shell.Run """" & root & "\dist\PrivacyAlarm\PrivacyAlarm.exe""", 1, False
