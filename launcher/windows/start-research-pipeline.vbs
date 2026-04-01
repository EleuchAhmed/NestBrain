Option Explicit

Dim fso, shell, launcherDir, repoPath, vcxsrvPath, cmd

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

' This script lives in launcher/windows, so go two levels up to repo root.
launcherDir = fso.GetParentFolderName(WScript.ScriptFullName)
repoPath = fso.GetParentFolderName(launcherDir)

vcxsrvPath = "C:\Program Files\VcXsrv\vcxsrv.exe"

If Not fso.FileExists(vcxsrvPath) Then
    MsgBox "VcXsrv not found at: " & vcxsrvPath & vbCrLf & vbCrLf & _
           "Please install it from: https://sourceforge.net/projects/vcxsrv/", vbExclamation, "Research Pipeline Launcher"
    WScript.Quit 1
End If

On Error Resume Next
shell.Run """" & vcxsrvPath & """ -multiwindow -clipboard -wgl -notrayicon", 0, False
If Err.Number <> 0 Then
    MsgBox "Failed to start VcXsrv: " & Err.Description, vbExclamation, "Research Pipeline Launcher"
    WScript.Quit 1
End If
On Error GoTo 0

WScript.Sleep 2000

shell.CurrentDirectory = repoPath
cmd = "cmd /c docker compose --profile desktop up -d"
shell.Run cmd, 0, False

MsgBox "Research Pipeline started!" & vbCrLf & vbCrLf & _
       "- VcXsrv X server: Running" & vbCrLf & _
       "- Docker services: Starting (pipeline, watcher, ollama, nestbrain)", vbInformation, "Research Pipeline Launcher"
