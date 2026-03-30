Option Explicit

Dim fso, shell, repoPath, pythonwPath, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

repoPath = fso.GetParentFolderName(WScript.ScriptFullName)
pythonwPath = repoPath & "\.venv\Scripts\pythonw.exe"

If Not fso.FileExists(pythonwPath) Then
    MsgBox "Nestbrain virtual environment not found at:" & vbCrLf & pythonwPath & vbCrLf & vbCrLf & _
           "Run setup once in terminal to create .venv and install dependencies.", vbExclamation, "Nestbrain Launcher"
    WScript.Quit 1
End If

cmd = """" & pythonwPath & """ -m nestbrain.main"
shell.CurrentDirectory = repoPath
shell.Run cmd, 0, False
