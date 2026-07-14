' Runs a command file with no visible console window.
' Task Scheduler invokes .cmd files in a visible console when the task runs
' interactively; a long posture run sitting in a black window invites an
' accidental close (which kills the job with 0xC000013A). This hides it.
' Usage: wscript.exe //B run_hidden.vbs "C:\path\to\job.cmd"
Set sh = CreateObject("WScript.Shell")
sh.Run """" & WScript.Arguments(0) & """", 0, False
