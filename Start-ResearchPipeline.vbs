Option Explicit

Dim fso, shell, repoPath, vcxsrvPath, dockerPath, cmd

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

' Get the repository root directory
repoPath = fso.GetParentFolderName(WScript.ScriptFullName)

' Paths
vcxsrvPath = "C:\Program Files\VcXsrv\vcxsrv.exe"
dockerPath = "docker"

' Check if VcXsrv is installed
If Not fso.FileExists(vcxsrvPath) Then
    MsgBox "VcXsrv not found at: " & vcxsrvPath & vbCrLf & vbCrLf & _
           "Please install it from: https://sourceforge.net/projects/vcxsrv/", vbExclamation, "Research Pipeline Launcher"
    WScript.Quit 1
End If

' Start VcXsrv (multiwindow mode, no taskbar icon)
On Error Resume Next
shell.Run """" & vcxsrvPath & """ -multiwindow -clipboard -wgl -notrayicon", 0, False
If Err.Number <> 0 Then
    MsgBox "Failed to start VcXsrv: " & Err.Description, vbExclamation, "Research Pipeline Launcher"
    WScript.Quit 1
End If
On Error GoTo 0

' Wait for VcXsrv to initialize
WScript.Sleep 2000

' Start Docker Compose stack with desktop profile
shell.CurrentDirectory = repoPath
cmd = "cmd /c docker compose --profile desktop up -d"
shell.Run cmd, 0, False

' Show completion message
MsgBox "Research Pipeline started!" & vbCrLf & vbCrLf & _
       "• VcXsrv X server: Running" & vbCrLf & _
       "• Docker services: Starting (pipeline, watcher, ollama, nestbrain)" & vbCrLf & vbCrLf & _
       "Check taskbar for Nestbrain GUI window.", vbInformation, "Research Pipeline Launcher"
