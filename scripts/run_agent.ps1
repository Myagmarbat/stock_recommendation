param(
    [string]$PythonBin = "",
    [string]$AgentConfigPath = "",
    [string]$DayKey = "",
    [string]$BaseDir = "",
    [switch]$EnableAfterHours
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir
Set-Location $rootDir

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

if (-not $DayKey) {
    $DayKey = Get-Date -Format "yyyyMMdd"
}

if (-not $BaseDir) {
    $BaseDir = Join-Path $rootDir "data\daily\$DayKey"
}

$logDir = Join-Path $BaseDir "logs"
$todayLink = Join-Path $rootDir "data\today"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $rootDir "data\daily") | Out-Null

if (Test-Path $todayLink) {
    Remove-Item -LiteralPath $todayLink -Force -Recurse
}
New-Item -ItemType Junction -Path $todayLink -Target $BaseDir | Out-Null

$ts = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
$logFile = Join-Path $logDir "run_$ts.log"

$arguments = @(
    (Join-Path $rootDir "stock_option_agent\agent.py")
    "--base-dir", $BaseDir
    "--universe-count", "50"
    "--config", $AgentConfigPath
)

if ($EnableAfterHours) {
    $arguments += "--enable-after-hours"
}

$stdoutFile = Join-Path $logDir "run_${ts}.stdout.log"
$stderrFile = Join-Path $logDir "run_${ts}.stderr.log"

$process = Start-Process `
    -FilePath $PythonBin `
    -ArgumentList $arguments `
    -WorkingDirectory $rootDir `
    -RedirectStandardOutput $stdoutFile `
    -RedirectStandardError $stderrFile `
    -NoNewWindow `
    -Wait `
    -PassThru

$stdout = if (Test-Path $stdoutFile) { Get-Content $stdoutFile -Raw } else { "" }
$stderr = if (Test-Path $stderrFile) { Get-Content $stderrFile -Raw } else { "" }

@(
    $stdout
    if ($stderr) { "`n[stderr]`n$stderr" }
) | Out-File -FilePath $logFile -Encoding utf8

if ($process.ExitCode -ne 0) {
    throw "Agent run failed with exit code $($process.ExitCode). See $logFile"
}
