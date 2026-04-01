Option Explicit

Dim fso, shell, launcherDir, repoPath, pythonwPath, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

' This script lives in launcher/windows, so go two levels up to repo root.
launcherDir = fso.GetParentFolderName(WScript.ScriptFullName)
repoPath = fso.GetParentFolderName(launcherDir)
pythonwPath = repoPath & "\.venv\Scripts\pythonw.exe"

If Not fso.FileExists(pythonwPath) Then
    MsgBox "Nestbrain virtual environment not found at:" & vbCrLf & pythonwPath & vbCrLf & vbCrLf & _
           "Run setup once in terminal to create .venv and install dependencies.", vbExclamation, "Nestbrain Launcher"
    WScript.Quit 1
End If

cmd = """" & pythonwPath & """ -m nestbrain.main"
shell.CurrentDirectory = repoPath
shell.Run cmd, 0, False
