Set ws = CreateObject("Wscript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
ws.CurrentDirectory = scriptDir

ws.Run "cmd /c python -m streamlit run """ & scriptDir & "\app.py""", 0, False
WScript.Sleep 5000
ws.Run "http://localhost:8501", 1, False
