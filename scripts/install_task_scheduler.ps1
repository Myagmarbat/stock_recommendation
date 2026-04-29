param(
    [string]$TaskName = "stock_option_agent",
    [string]$PythonBin = "",
    [string]$AgentConfigPath = "",
    [switch]$EnableAfterHours
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir
$runnerPath = Join-Path $scriptDir "run_agent.ps1"

if (-not $PythonBin) {
    $venvPython = Join-Path $rootDir ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $PythonBin = $venvPython
    } else {
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        if ($pythonCmd) {
            $PythonBin = $pythonCmd.Source
        } else {
            throw "Python executable not found. Set -PythonBin or create .venv."
        }
    }
}

if (-not $AgentConfigPath) {
    $AgentConfigPath = Join-Path $rootDir "config\agent_config.json"
}

$runnerArgs = @(
    "-NoProfile"
    "-ExecutionPolicy", "Bypass"
    "-File", ('"{0}"' -f $runnerPath)
)

if ($EnableAfterHours) {
    $runnerArgs += "-EnableAfterHours"
}

$taskCommand = 'powershell.exe {0}' -f ($runnerArgs -join " ")

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    schtasks.exe /Delete /TN $TaskName /F | Out-Null
}

$createArgs = @(
    "/Create"
    "/TN", $TaskName
    "/TR", $taskCommand
    "/SC", "WEEKLY"
    "/D", "MON,TUE,WED,THU,FRI"
    "/ST", "06:30"
    "/RI", "5"
    "/DU", "06:30"
    "/F"
)

$createOutput = & schtasks.exe @createArgs 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "schtasks.exe failed to create task. Output: $createOutput"
}

Write-Host "Installed scheduled task: $TaskName"
Write-Host "Runs every 5 minutes from 6:30 AM to 1:00 PM local time."
