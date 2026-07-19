# Registers the daily eRank keyword-collection script as a Windows scheduled
# task, running at 7:00 AM every day using the project's own virtual env.
#
# Run once, manually, from an elevated or normal PowerShell prompt:
#   powershell -ExecutionPolicy Bypass -File scripts\register_erank_task.ps1
#
# To remove it later:
#   Unregister-ScheduledTask -TaskName "EverframeDigital-eRank-Daily" -Confirm:$false

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ScriptPath = Join-Path $ProjectRoot "scripts\erank_daily_collect.py"
$TaskName = "EverframeDigital-eRank-Daily"

if (-not (Test-Path $PythonExe)) {
    throw "Could not find project venv python at $PythonExe -- check the path."
}

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ScriptPath`"" -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At 7:00AM
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Daily eRank keyword collection for EverframeDigital (Phase 1: collection only)." -Force

Write-Host "Registered scheduled task '$TaskName' to run daily at 7:00 AM."
Write-Host "Note: eRank searches happen in a visible (non-headless) Chrome window since the task runs launch_persistent_context(headless=False) -- this requires the machine to be logged in (not locked/sleeping) at 7am for the browser windows to actually render and complete."
